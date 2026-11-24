"""Configuración local (config.json) y rutas de la app."""
import json
import os
import threading
import uuid
from datetime import timedelta, timezone, datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA_CONFIG = os.path.join(RAIZ, "config.json")
RUTA_ESTADO = os.path.join(RAIZ, "estado.json")
RUTA_LOGS = os.path.join(RAIZ, "logs")
RUTA_DOCS = os.path.join(RAIZ, "docs")
RUTA_VERSION = os.path.join(RAIZ, "VERSION")

PUERTO = 8765
HOST = "127.0.0.1"
URL_PAGES = "https://guerrasur.github.io/tamonline/"


def plataformas():
    """Claves de plataformas disponibles (una por archivo en adapters/)."""
    try:
        from . import adapters
        return tuple(adapters.cargar().keys())
    except Exception:
        return ("pedidosya", "rappi", "rappi_turbo")


os.makedirs(RUTA_LOGS, exist_ok=True)

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("America/Argentina/Buenos_Aires")
except Exception:  # sin base tzdata (Windows sin el paquete): Argentina es UTC-3 fijo
    TZ = timezone(timedelta(hours=-3))


def ahora():
    return datetime.now(TZ)


def leer_version():
    try:
        with open(RUTA_VERSION, encoding="utf-8") as f:
            return f.read().strip() or "0.0.0"
    except OSError:
        return "0.0.0"


def config_por_defecto():
    return {
        "configurado": False,
        "locales": [],
        "intervalo_segundos": 120,
        "errores_para_notificar": 3,
        "sonido": False,
        "abrir_en": "local",  # "local" o "pages"
    }


def _hm_valido(s):
    try:
        h, m = str(s).split(":")[:2]
        return 0 <= int(h) <= 24 and 0 <= int(m) <= 59
    except Exception:
        return False


def _limpiar_horarios(h):
    """Devuelve {plataforma: {"0": [["11:00","23:00"], ...]}} solo con datos válidos."""
    salida = {}
    if not isinstance(h, dict):
        return salida
    for plat, dias in h.items():
        if plat not in plataformas() or not isinstance(dias, dict):
            continue
        d_ok = {}
        for dia, tramos in dias.items():
            if str(dia) not in {str(i) for i in range(7)} or not isinstance(tramos, list):
                continue
            t_ok = [[str(t[0]), str(t[1])] for t in tramos
                    if isinstance(t, (list, tuple)) and len(t) == 2
                    and _hm_valido(t[0]) and _hm_valido(t[1])]
            if t_ok:
                d_ok[str(dia)] = t_ok
        if d_ok:
            salida[plat] = d_ok
    return salida


def sanear(cfg):
    """Valida y completa la configuración recibida; nunca lanza excepción."""
    base = config_por_defecto()
    if not isinstance(cfg, dict):
        return base
    locales = []
    for l in cfg.get("locales", []) if isinstance(cfg.get("locales"), list) else []:
        if not isinstance(l, dict):
            continue
        links_in = l.get("links") if isinstance(l.get("links"), dict) else {}
        locales.append({
            "id": str(l.get("id") or uuid.uuid4().hex[:8]),
            "nombre": str(l.get("nombre") or "Mi local").strip()[:80] or "Mi local",
            "links": {p: str(links_in.get(p) or "").strip() for p in plataformas()},
            "horarios": _limpiar_horarios(l.get("horarios")),
        })
    base["locales"] = locales
    base["configurado"] = bool(locales)
    try:
        base["intervalo_segundos"] = max(30, min(3600, int(cfg.get("intervalo_segundos", 120))))
    except (TypeError, ValueError):
        pass
    try:
        base["errores_para_notificar"] = max(1, min(50, int(cfg.get("errores_para_notificar", 3))))
    except (TypeError, ValueError):
        pass
    base["sonido"] = bool(cfg.get("sonido", False))
    base["abrir_en"] = "pages" if cfg.get("abrir_en") == "pages" else "local"
    return base


class Almacen:
    """Lee y guarda config.json de forma segura entre hilos."""

    def __init__(self, ruta=RUTA_CONFIG):
        self.ruta = ruta
        self._lock = threading.Lock()
        self._cfg = self._cargar()

    def _cargar(self):
        try:
            with open(self.ruta, encoding="utf-8") as f:
                return sanear(json.load(f))
        except (OSError, ValueError):
            return config_por_defecto()

    def obtener(self):
        with self._lock:
            return json.loads(json.dumps(self._cfg))

    def guardar(self, nueva):
        cfg = sanear(nueva)
        with self._lock:
            tmp = self.ruta + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.ruta)
            self._cfg = cfg
        return json.loads(json.dumps(cfg))
