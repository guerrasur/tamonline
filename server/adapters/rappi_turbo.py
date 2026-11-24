"""Rappi Turbo (tiendas express de Rappi). Logs en logs/rappi_turbo.log."""
from .base import Adaptador


class RappiTurbo(Adaptador):
    clave = "rappi_turbo"
    nombre = "Rappi Turbo"
    claves_abierto = ("is_available", "isavailable", "is_open", "isopen", "storeopen",
                      "store_status", "storestatus", "open")
    claves_cerrado = ("isclosed", "is_closed", "closed")


ADAPTADOR = RappiTurbo()
