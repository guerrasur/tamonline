"""Rappi. Claves a verificar si la plataforma cambia su página: ver logs/rappi.log."""
from .base import Adaptador


class Rappi(Adaptador):
    clave = "rappi"
    nombre = "Rappi"
    claves_abierto = ("is_available", "isavailable", "is_open", "isopen", "storeopen",
                      "store_status", "storestatus", "open")
    claves_cerrado = ("isclosed", "is_closed", "closed")


ADAPTADOR = Rappi()
