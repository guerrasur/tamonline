"""PedidosYa. Claves a verificar si la plataforma cambia su página: ver logs/pedidosya.log."""
from .base import Adaptador


class PedidosYa(Adaptador):
    clave = "pedidosya"
    nombre = "PedidosYa"
    # Claves que PedidosYa suele usar en su JSON embebido (a confirmar con la página real)
    claves_abierto = ("isopen", "is_open", "isopened", "opened", "isrestaurantopen",
                      "availability", "openstatus", "open")
    claves_cerrado = ("isclosed", "closed")


ADAPTADOR = PedidosYa()
