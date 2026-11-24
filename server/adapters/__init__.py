"""Descubre automáticamente los adaptadores: todo módulo con ADAPTADOR se registra.
Para sumar una plataforma nueva alcanza con agregar un archivo acá."""
import importlib
import pkgutil

ORDEN = ["pedidosya", "rappi", "rappi_turbo"]


def cargar():
    encontrados = {}
    for m in pkgutil.iter_modules(__path__):
        if m.name == "base":
            continue
        try:
            mod = importlib.import_module("%s.%s" % (__name__, m.name))
            ad = getattr(mod, "ADAPTADOR", None)
            if ad is not None:
                encontrados[ad.clave] = ad
        except Exception:  # un adaptador roto no debe tumbar a los demás
            continue
    claves = [c for c in ORDEN if c in encontrados] + sorted(c for c in encontrados if c not in ORDEN)
    return {c: encontrados[c] for c in claves}
