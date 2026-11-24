"""Servidor local de "Tamo online?" (FastAPI) en 127.0.0.1:8765."""
import asyncio
import logging
import os
import socket
import sys
import threading
import webbrowser
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

# Permite ejecutarlo con "python -m server.main" o "python server/main.py"
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "server"

from fastapi import Body, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .notifier_state import Detector
from .scheduler import Programador

_h = RotatingFileHandler(os.path.join(config.RUTA_LOGS, "servidor.log"),
                         maxBytes=500_000, backupCount=2, encoding="utf-8")
_h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
logging.getLogger().addHandler(_h)
logging.getLogger().setLevel(logging.INFO)

almacen = config.Almacen()
detector = Detector()
programador = Programador(almacen, detector)


@asynccontextmanager
async def ciclo_de_vida(app):
    programador.iniciar()
    yield
    await programador.detener()


app = FastAPI(title="Tamo online?", lifespan=ciclo_de_vida)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://guerrasur.github.io", "http://localhost:8765", "http://127.0.0.1:8765"],
    allow_methods=["*"], allow_headers=["*"],
)


@app.middleware("http")
async def red_privada(request: Request, call_next):
    """Chrome exige este encabezado al llamar a la red local desde una web https."""
    resp = await call_next(request)
    if request.headers.get("access-control-request-private-network"):
        resp.headers["Access-Control-Allow-Private-Network"] = "true"
    return resp


@app.get("/api/version")
async def api_version():
    return {"version": config.leer_version()}


@app.get("/api/status")
async def api_status():
    return programador.instantanea()


@app.get("/api/config")
async def api_config_get():
    cfg = almacen.obtener()
    cfg["plataformas"] = [{"clave": c, "nombre": a.nombre} for c, a in programador.adaptadores.items()]
    return cfg


@app.post("/api/config")
async def api_config_post(cuerpo: dict = Body(...)):
    cfg = almacen.guardar(cuerpo)
    asyncio.create_task(programador.refrescar())  # aplica los links nuevos enseguida
    return cfg


@app.post("/api/refresh")
async def api_refresh():
    try:
        await asyncio.wait_for(programador.refrescar(), 240)
    except asyncio.TimeoutError:
        return JSONResponse({"ok": False, "error": "La verificación tardó demasiado"}, status_code=504)
    return {"ok": True}


# La misma web como respaldo en http://localhost:8765 (va al final para no tapar /api)
if os.path.isdir(config.RUTA_DOCS):
    app.mount("/", StaticFiles(directory=config.RUTA_DOCS, html=True), name="web")


def puerto_en_uso():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((config.HOST, config.PUERTO)) == 0


def abrir_navegador():
    cfg = almacen.obtener()
    url = config.URL_PAGES if cfg.get("abrir_en") == "pages" else "http://localhost:%d/" % config.PUERTO
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main():
    if puerto_en_uso():  # ya hay una instancia: solo abrir el navegador
        abrir_navegador()
        return
    import uvicorn
    threading.Timer(1.5, abrir_navegador).start()
    uvicorn.run(app, host=config.HOST, port=config.PUERTO, log_level="warning")


if __name__ == "__main__":
    main()
