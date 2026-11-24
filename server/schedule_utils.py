"""Utilidades de horarios: normalización, "¿está en horario?" y lectura de días."""
import re

DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_NOMBRES = {
    "mon": 0, "monday": 0, "lunes": 0, "lun": 0, "mo": 0,
    "tue": 1, "tuesday": 1, "martes": 1, "mar": 1, "tu": 1,
    "wed": 2, "wednesday": 2, "miercoles": 2, "miércoles": 2, "mie": 2, "mié": 2, "we": 2,
    "thu": 3, "thursday": 3, "jueves": 3, "jue": 3, "th": 3,
    "fri": 4, "friday": 4, "viernes": 4, "vie": 4, "fr": 4,
    "sat": 5, "saturday": 5, "sabado": 5, "sábado": 5, "sab": 5, "sáb": 5, "sa": 5,
    "sun": 6, "sunday": 6, "domingo": 6, "dom": 6, "su": 6,
}


def parse_hm(s):
    """'11:30' o '11:30:00' -> minutos desde medianoche (o None)."""
    m = re.match(r"^\s*(\d{1,2}):(\d{2})", str(s))
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 24 or mi > 59:
        return None
    return h * 60 + mi


def nombre_a_indice(valor):
    """Nombre de día (es/en, URL schema.org incluida) -> 0=lunes..6=domingo."""
    s = str(valor).strip().lower().rsplit("/", 1)[-1]
    return _NOMBRES.get(s)


def entero_a_indice(n):
    """Número de día -> 0=lunes..6=domingo. Sirve tanto para ISO (1=lunes..7=domingo)
    como para JavaScript (0=domingo..6=sábado): ambos dan (n-1) % 7."""
    return (int(n) - 1) % 7


def normalizar(h):
    """{'0': [['11:00','23:00']]} -> {0: [(660, 1380)]}; None si no hay datos."""
    if not isinstance(h, dict):
        return None
    out = {}
    for dia, tramos in h.items():
        try:
            d = int(dia)
        except (TypeError, ValueError):
            continue
        if not 0 <= d <= 6 or not isinstance(tramos, (list, tuple)):
            continue
        for t in tramos:
            if not isinstance(t, (list, tuple)) or len(t) != 2:
                continue
            a, c = parse_hm(t[0]), parse_hm(t[1])
            if a is None or c is None:
                continue
            out.setdefault(d, []).append((a, c))
    return out or None


def esta_en_horario(h, ahora):
    """True/False según el horario; None si no hay horario cargado.
    Soporta tramos que pasan la medianoche (cierre <= apertura)."""
    n = normalizar(h)
    if n is None:
        return None
    minuto = ahora.hour * 60 + ahora.minute
    hoy = ahora.weekday()
    ayer = (hoy - 1) % 7
    for a, c in n.get(hoy, []):
        if a == c:  # mismo valor: 24 horas
            return True
        if a < c and a <= minuto < c:
            return True
        if c < a and minuto >= a:  # abre hoy y cierra pasada la medianoche
            return True
    for a, c in n.get(ayer, []):
        if c < a and minuto < c:  # tramo de ayer que termina hoy
            return True
    return False


def texto_hoy(h, ahora):
    """Texto corto con el horario de hoy, p. ej. '11:00–23:00'."""
    n = normalizar(h)
    if n is None:
        return ""
    tramos = n.get(ahora.weekday(), [])
    if not tramos:
        return "Hoy: cerrado"
    f = lambda m: "%02d:%02d" % (m // 60 % 24, m % 60)
    return "Hoy: " + " / ".join("%s–%s" % (f(a), f(c)) for a, c in sorted(tramos))
