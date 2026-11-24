"""Detector de cambios de estado. Guarda entradas y últimos 50 eventos en estado.json."""
import json
import os
import threading

from . import config

MAX_EVENTOS = 50
CLASES_ALERTA = ("offline_horario", "online_fuera")


def calcular_clase(estado, en_horario):
    """Combina estado real + horario esperado en una de las 5 clases visibles."""
    if estado == "error":
        return "error"
    if estado == "online":
        return "online" if en_horario is not False else "online_fuera"
    return "offline_horario" if en_horario is True else "offline_fuera"


class Detector:
    def __init__(self, ruta=config.RUTA_ESTADO):
        self.ruta = ruta
        self.lock = threading.Lock()
        self.entradas = {}
        self.eventos = []  # más nuevo al final
        self.sig_id = 1
        self._cargar()

    # ---- persistencia
    def _cargar(self):
        try:
            with open(self.ruta, encoding="utf-8") as f:
                d = json.load(f)
            self.entradas = d.get("entradas", {}) if isinstance(d.get("entradas"), dict) else {}
            self.eventos = d.get("eventos", [])[-MAX_EVENTOS:] if isinstance(d.get("eventos"), list) else []
            self.sig_id = int(d.get("sig_id", 1))
        except (OSError, ValueError, TypeError):
            pass

    def _guardar(self):
        try:
            tmp = self.ruta + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"entradas": self.entradas, "eventos": self.eventos,
                           "sig_id": self.sig_id}, f, ensure_ascii=False)
            os.replace(tmp, self.ruta)
        except OSError:
            pass

    # ---- eventos
    def _evento(self, ahora, local, plat, tipo, texto, notificar):
        hm = ahora.strftime("%H:%M")
        ev = {"id": self.sig_id, "hora": ahora.isoformat(), "local_id": local["id"],
              "local": local["nombre"], "clave": plat.clave, "plataforma": plat.nombre,
              "tipo": tipo, "notificar": notificar,
              "mensaje": "%s · %s: %s (%s)" % (local["nombre"], plat.nombre, texto, hm)}
        self.sig_id += 1
        self.eventos.append(ev)
        self.eventos = self.eventos[-MAX_EVENTOS:]
        return ev

    _TEXTOS = {
        "online": "la tienda está online",
        "offline_fuera": "la tienda cerró",
        "offline_horario": "la tienda se apagó fuera de lo esperado",
        "online_fuera": "la tienda está online fuera de horario",
    }

    def registrar(self, local, plat, url, res, en_horario, horarios_auto, umbral, ahora):
        """Procesa una lectura y devuelve la lista de eventos nuevos."""
        clave = "%s|%s" % (local["id"], plat.clave)
        iso = ahora.isoformat()
        nuevos = []
        with self.lock:
            e = self.entradas.get(clave)
            if not e or e.get("url") != url:  # primera vez o cambió el link
                e = {"url": url, "clase_estable": None, "desde_estable": iso,
                     "errores": 0, "error_notificado": False}
            clase = calcular_clase(res.estado, en_horario)
            e.update(url=url, estado=res.estado, clase=clase, motivo=res.motivo if clase == "error" else "",
                     ultima_verificacion=iso, en_horario=en_horario, metodo=res.metodo)
            if horarios_auto:
                e["horarios_auto"] = horarios_auto

            if clase == "error":
                e["errores"] = e.get("errores", 0) + 1
                if e["errores"] == 1:
                    e["desde_error"] = iso
                e["desde"] = e.get("desde_error", iso)
                if e["errores"] >= umbral and not e.get("error_notificado"):
                    e["error_notificado"] = True
                    nuevos.append(self._evento(
                        ahora, local, plat, "error",
                        "sin datos hace %d verificaciones (%s)" % (e["errores"], res.motivo or "error"), True))
            else:
                e["errores"] = 0
                previa = e.get("clase_estable")
                if previa != clase:
                    e["clase_estable"] = clase
                    e["desde_estable"] = iso
                    nuevos.append(self._evento(ahora, local, plat, clase, self._TEXTOS[clase],
                                               clase in CLASES_ALERTA))
                elif e.get("error_notificado"):
                    nuevos.append(self._evento(ahora, local, plat, "recuperado",
                                               "volvió a obtenerse el estado", False))
                e["error_notificado"] = False
                e["desde"] = e["desde_estable"]
            self.entradas[clave] = e
            self._guardar()
        return nuevos

    def entrada(self, local_id, clave):
        with self.lock:
            return dict(self.entradas.get("%s|%s" % (local_id, clave), {}))

    def lista_eventos(self):
        with self.lock:
            return list(reversed(self.eventos))
