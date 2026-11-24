"""Base común de los adaptadores de plataforma.

Cada plataforma vive en su propio archivo y solo define qué claves buscar.
Flujo: 1) HTTP simple (httpx) leyendo JSON embebido -> 2) Playwright (Chromium)
si lo anterior no alcanza. Todo falla de forma controlada con estado "error".
"""
import asyncio
import html as htmllib
import json
import logging
import os
import random
import re
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from typing import Any, Optional

import httpx

from .. import config
from .. import schedule_utils as su

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
]
_pw_lock = asyncio.Lock()  # un solo Chromium a la vez


@dataclass
class Resultado:
    estado: str  # "online" | "offline" | "error"
    motivo: str = ""
    horarios: Optional[dict] = None  # {"0": [["11:00","23:00"]], ...} leído de la página
    metodo: str = ""


def logger_de(clave):
    lg = logging.getLogger("tamo." + clave)
    if not lg.handlers:
        lg.setLevel(logging.INFO)
        h = RotatingFileHandler(os.path.join(config.RUTA_LOGS, clave + ".log"),
                                maxBytes=500_000, backupCount=2, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        lg.addHandler(h)
    return lg


# ---------------------------------------------------------------- extracción
_RE_SCRIPT_JSON = re.compile(
    r'<script[^>]*type=["\']application/(?:ld\+)?json["\'][^>]*>(.*?)</script>', re.S | re.I)
_RE_NEXT = re.compile(r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', re.S | re.I)
_RE_ESTADO = re.compile(
    r'window\.(?:__[A-Z_]+__|__[A-Za-z_]+__)\s*=\s*({.*?})\s*;?\s*</script>', re.S)


def extraer_bloques(html):
    """Devuelve todos los JSON embebidos que se puedan parsear."""
    bloques = []
    for rx in (_RE_NEXT, _RE_SCRIPT_JSON, _RE_ESTADO):
        for m in rx.finditer(html):
            try:
                bloques.append(json.loads(htmllib.unescape(m.group(1)) if rx is _RE_ESTADO else m.group(1)))
            except ValueError:
                continue
    return bloques


def texto_visible(html):
    t = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", htmllib.unescape(t)).strip()


def recorrer(obj, ruta=""):
    """Itera (ruta, clave, valor) de forma recursiva, en orden de aparición."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            r = ruta + "." + str(k)
            yield r, str(k), v
            yield from recorrer(v, r)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:500]):
            yield from recorrer(v, "%s[%d]" % (ruta, i))


_ABIERTO = {"open", "opened", "online", "available", "abierto", "opening", "active"}
_CERRADO = {"closed", "close", "offline", "unavailable", "cerrado", "temporarily_closed",
            "temporarily_unavailable", "scheduled_closed", "busy", "inactive", "paused"}


def interpretar(valor, invertido=False):
    """bool/0-1/texto -> True (abierto) / False (cerrado) / None (no sirve)."""
    r = None
    if isinstance(valor, bool):
        r = valor
    elif isinstance(valor, int) and valor in (0, 1):
        r = bool(valor)
    elif isinstance(valor, str):
        v = valor.strip().lower().replace(" ", "_")
        if v in _ABIERTO:
            r = True
        elif v in _CERRADO:
            r = False
    elif isinstance(valor, dict):  # p. ej. {"state": "OPEN"}
        for k in ("state", "status", "value"):
            if k in valor:
                return interpretar(valor[k], invertido)
    if r is None:
        return None
    return (not r) if invertido else r


def buscar_estado(bloques, claves_abierto, claves_cerrado=()):
    """Busca la primera clave conocida con un valor interpretable.
    Devuelve (abierto: bool, ruta) o (None, None)."""
    ab = {c.lower() for c in claves_abierto}
    ce = {c.lower() for c in claves_cerrado}
    for b in bloques:
        for ruta, k, v in recorrer(b):
            kl = k.lower()
            if kl in ab:
                r = interpretar(v)
                if r is not None:
                    return r, ruta
            elif kl in ce:
                r = interpretar(v, invertido=True)
                if r is not None:
                    return r, ruta
    return None, None


def estado_por_texto(texto):
    """Heurística de último recurso sobre el texto visible. Devuelve True/False/None."""
    t = texto.lower()
    cerrado = ["tienda cerrada", "local cerrado", "restaurante cerrado", "cerrado por ahora",
               "temporalmente cerrad", "cerrado temporalmente", "no está disponible por ahora",
               "abre a las", "abre mañana", "abre el ", "volvé a las", "closed"]
    abierto = ["cierra a las", "abierto ahora", "hacer pedido", "pedí ahora", "open now"]
    if any(x in t for x in cerrado):
        return False
    if any(x in t for x in abierto):
        return True
    return None


# ------------------------------------------------------------------ horarios
_K_DIA = ("dayofweek", "day_of_week", "day", "weekday", "dia", "week_day")
_K_ABRE = ("opens", "open", "opening", "opening_time", "openingtime", "start", "starttime",
           "start_time", "from", "desde", "opentime", "open_time")
_K_CIERRA = ("closes", "close", "closing", "closing_time", "closingtime", "end", "endtime",
             "end_time", "to", "until", "hasta", "closetime", "close_time")


def _dias_de(valor):
    out = []
    vals = valor if isinstance(valor, list) else [valor]
    for v in vals:
        if isinstance(v, int) and not isinstance(v, bool):
            out.append(su.entero_a_indice(v))
        elif isinstance(v, str) and v.strip().isdigit():
            out.append(su.entero_a_indice(int(v)))
        else:
            i = su.nombre_a_indice(v)
            if i is not None:
                out.append(i)
    return out


def _tramo_de(d):
    low = {str(k).lower(): v for k, v in d.items()}
    a = next((low[k] for k in _K_ABRE if k in low and su.parse_hm(low[k]) is not None), None)
    c = next((low[k] for k in _K_CIERRA if k in low and su.parse_hm(low[k]) is not None), None)
    dia = next((low[k] for k in _K_DIA if k in low), None)
    if a is None or c is None or dia is None:
        return None
    dias = _dias_de(dia)
    return (dias, str(a)[:5], str(c)[:5]) if dias else None


def horarios_de_bloques(bloques):
    """Busca estructuras de horarios (JSON-LD, listas día/apertura/cierre) en los bloques."""
    res = {}
    for b in bloques:
        for _, k, v in recorrer(b):
            if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
                for x in v:
                    t = _tramo_de(x)
                    if t:
                        for d in t[0]:
                            tr = res.setdefault(str(d), [])
                            if [t[1], t[2]] not in tr:
                                tr.append([t[1], t[2]])
            elif k.lower() == "openinghours" and isinstance(v, (str, list)):
                # JSON-LD tipo "Mo-Fr 09:00-18:00"
                for linea in (v if isinstance(v, list) else [v]):
                    m = re.match(r"^\s*([A-Za-z]{2})(?:-([A-Za-z]{2}))?\s+(\d{1,2}:\d{2})-(\d{1,2}:\d{2})", str(linea))
                    if m:
                        i = su.nombre_a_indice(m.group(1))
                        j = su.nombre_a_indice(m.group(2)) if m.group(2) else i
                        if i is not None and j is not None:
                            d = i
                            for _ in range(7):
                                res.setdefault(str(d), []).append([m.group(3), m.group(4)])
                                if d == j:
                                    break
                                d = (d + 1) % 7
    return res or None


# ------------------------------------------------------------------ adaptador
class Adaptador:
    clave = "base"
    nombre = "Base"
    claves_abierto = ("isopen", "is_open", "isopened", "opened", "open")
    claves_cerrado = ("isclosed", "is_closed", "closed")

    def analizar(self, bloques, texto):
        """Decide el estado a partir de JSON embebido y texto. Se puede sobrescribir."""
        abierto, ruta = buscar_estado(bloques, self.claves_abierto, self.claves_cerrado)
        horarios = horarios_de_bloques(bloques)
        if abierto is not None:
            return Resultado("online" if abierto else "offline", "clave " + ruta, horarios)
        t = estado_por_texto(texto)
        if t is not None:
            return Resultado("online" if t else "offline", "texto de la página", horarios)
        return Resultado("error", "No se encontró el estado de la tienda en la página", horarios)

    async def _http(self, url, log):
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-AR,es;q=0.9,en;q=0.6",
        }
        async with httpx.AsyncClient(follow_redirects=True, timeout=25, headers=headers) as c:
            r = await c.get(url)
        log.info("HTTP %s %s bytes=%d", r.status_code, url, len(r.text))
        if r.status_code in (401, 403, 429) or "captcha" in r.text[:5000].lower():
            return None, "Bloqueado por la plataforma (HTTP %s)" % r.status_code
        if r.status_code >= 400:
            return None, "La página respondió HTTP %s" % r.status_code
        return r.text, ""

    async def _playwright(self, url, log):
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return None, [], "Playwright no instalado"
        extra = []
        async with _pw_lock:
            async with async_playwright() as p:
                nav = await p.chromium.launch(headless=True)
                try:
                    ctx = await nav.new_context(user_agent=USER_AGENTS[0], locale="es-AR",
                                                timezone_id="America/Argentina/Buenos_Aires")
                    page = await ctx.new_page()

                    async def al_responder(resp):
                        try:
                            if "json" in (resp.headers.get("content-type") or "") and len(extra) < 60:
                                extra.append(json.loads(await resp.text()))
                        except Exception:
                            pass

                    page.on("response", lambda r: asyncio.ensure_future(al_responder(r)))
                    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    try:
                        await page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    await asyncio.sleep(2)
                    contenido = await page.content()
                finally:
                    await nav.close()
        log.info("Playwright ok url=%s json_capturados=%d", url, len(extra))
        return contenido, extra, ""

    def _guardar_diagnostico(self, local_id, html):
        try:
            ruta = os.path.join(config.RUTA_LOGS, "%s_%s_ultima.html" % (self.clave, local_id))
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(html[:400_000])
        except OSError:
            pass

    async def consultar(self, url, local_id):
        """Nunca lanza excepción: cualquier fallo vuelve como Resultado('error')."""
        log = logger_de(self.clave)
        motivo = ""
        try:
            html, motivo = await self._http(url, log)
            if html:
                res = self.analizar(extraer_bloques(html), texto_visible(html))
                if res.estado != "error":
                    res.metodo = "http"
                    log.info("%s -> %s (%s)", url, res.estado, res.motivo)
                    return res
                motivo = res.motivo
                self._guardar_diagnostico(local_id, html)
        except Exception as e:  # red caída, DNS, timeout...
            motivo = "Error de conexión: %s" % type(e).__name__
            log.warning("HTTP falló: %r", e)
        try:
            html, extra, err = await self._playwright(url, log)
            if html:
                res = self.analizar(extraer_bloques(html) + extra, texto_visible(html))
                res.metodo = "playwright"
                if res.estado == "error":
                    self._guardar_diagnostico(local_id, html)
                log.info("%s -> %s (%s)", url, res.estado, res.motivo)
                if res.estado != "error" or not motivo:
                    return res
                res.motivo = motivo + " · " + res.motivo
                return res
            if err and "no instalado" not in err:
                motivo = (motivo + " · " if motivo else "") + err
        except Exception as e:
            log.warning("Playwright falló: %r", e)
            motivo = (motivo + " · " if motivo else "") + "Navegador: %s" % type(e).__name__
        log.error("%s -> error: %s", url, motivo)
        return Resultado("error", motivo or "No se pudo leer la página", None, "")
