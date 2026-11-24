"""Ciclo de verificación: consulta cada plataforma de cada local cada N segundos."""
import asyncio
import logging
import random

from . import adapters, config
from . import schedule_utils as su
from .adapters.base import Resultado
from .notifier_state import Detector

log = logging.getLogger("tamo.scheduler")


class Programador:
    def __init__(self, almacen, detector: Detector):
        self.almacen = almacen
        self.detector = detector
        self.adaptadores = adapters.cargar()
        self._lock = asyncio.Lock()
        self._despertar = asyncio.Event()
        self._tarea = None

    def iniciar(self):
        self._tarea = asyncio.create_task(self._bucle())

    async def detener(self):
        if self._tarea:
            self._tarea.cancel()

    async def _bucle(self):
        while True:
            try:
                await self.verificar_todo()
            except asyncio.CancelledError:
                raise
            except Exception:  # el ciclo nunca debe morir
                log.exception("Fallo inesperado en el ciclo")
            cfg = self.almacen.obtener()
            espera = cfg["intervalo_segundos"] * random.uniform(0.85, 1.15)
            try:
                await asyncio.wait_for(self._despertar.wait(), espera)
            except asyncio.TimeoutError:
                pass
            self._despertar.clear()

    async def refrescar(self):
        """Verifica ya mismo. Si hay un ciclo en curso, espera a que termine."""
        if self._lock.locked():
            async with self._lock:
                return
        await self.verificar_todo()
        self._despertar.set()

    def horarios_efectivos(self, local, clave):
        """Manual si está cargado; si no, el leído de la página."""
        manual = local.get("horarios", {}).get(clave)
        if su.normalizar(manual):
            return manual, "manual"
        auto = self.detector.entrada(local["id"], clave).get("horarios_auto")
        if su.normalizar(auto):
            return auto, "página"
        return None, ""

    async def verificar_todo(self):
        async with self._lock:
            cfg = self.almacen.obtener()
            for local in cfg["locales"]:
                for clave, ad in self.adaptadores.items():
                    url = local["links"].get(clave, "")
                    if not url:
                        continue
                    try:
                        res = await asyncio.wait_for(ad.consultar(url, local["id"]), 120)
                    except Exception as e:
                        res = Resultado("error", "Fallo inesperado: %s" % type(e).__name__)
                    try:
                        ahora = config.ahora()
                        previo = self.detector.entrada(local["id"], clave)
                        auto = res.horarios or previo.get("horarios_auto")
                        manual = local.get("horarios", {}).get(clave)
                        h = manual if su.normalizar(manual) else auto
                        self.detector.registrar(local, ad, url, res, su.esta_en_horario(h, ahora),
                                                res.horarios, cfg["errores_para_notificar"], ahora)
                    except Exception:
                        log.exception("No se pudo registrar el estado de %s/%s", local["nombre"], clave)
                    await asyncio.sleep(random.uniform(0.5, 2.0))

    def instantanea(self):
        """Estructura que devuelve /api/status."""
        cfg = self.almacen.obtener()
        ahora = config.ahora()
        locales = []
        for local in cfg["locales"]:
            plats = []
            for clave, ad in self.adaptadores.items():
                url = local["links"].get(clave, "")
                e = self.detector.entrada(local["id"], clave) if url else {}
                if url and e.get("url") != url:
                    e = {}
                h, fuente = self.horarios_efectivos(local, clave)
                plats.append({
                    "clave": clave, "nombre": ad.nombre, "url": url,
                    "clase": e.get("clase") or ("sin_link" if not url else "pendiente"),
                    "motivo": e.get("motivo", ""),
                    "ultima_verificacion": e.get("ultima_verificacion"),
                    "desde": e.get("desde"),
                    "sin_horario": h is None,
                    "horario_hoy": su.texto_hoy(h, ahora),
                    "fuente_horario": fuente,
                })
            locales.append({"id": local["id"], "nombre": local["nombre"], "plataformas": plats})
        return {"version": config.leer_version(), "ahora": ahora.isoformat(),
                "configurado": cfg["configurado"], "intervalo": cfg["intervalo_segundos"],
                "sonido": cfg["sonido"], "locales": locales,
                "eventos": self.detector.lista_eventos()}
