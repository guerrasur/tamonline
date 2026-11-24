"""Actualizador automático: compara VERSION local con la de la rama main de GitHub.
Usa solo la biblioteca estándar. Códigos de salida: 0 = sin cambios o sin conexión,
10 = actualizado (el .bat reinstala dependencias). Nunca rompe el arranque."""
import io
import os
import shutil
import sys
import urllib.request
import zipfile

REPO = "guerrasur/tamonline"
RAIZ = os.path.dirname(os.path.abspath(__file__))
URL_VERSION = "https://raw.githubusercontent.com/%s/main/VERSION" % REPO
URL_ZIP = "https://github.com/%s/archive/refs/heads/main.zip" % REPO
# Lo que nunca se pisa: datos del usuario y entorno local
CONSERVAR = {"config.json", "estado.json", "logs", "venv", ".git", "__pycache__"}


def a_tupla(v):
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except ValueError:
        return (0,)


def descargar(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "tamonline-updater"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def version_local():
    try:
        with open(os.path.join(RAIZ, "VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "0.0.0"


def copiar_arbol(origen, destino):
    for nombre in os.listdir(origen):
        if nombre in CONSERVAR:
            continue
        src = os.path.join(origen, nombre)
        dst = os.path.join(destino, nombre)
        if nombre == "iniciar_app.bat":
            # Un .bat en ejecución no se puede pisar sin riesgo: se deja como .new
            # y el propio .bat lo aplica en el próximo arranque.
            shutil.copy2(src, dst + ".new")
        elif os.path.isdir(src):
            os.makedirs(dst, exist_ok=True)
            copiar_arbol(src, dst)
        else:
            shutil.copy2(src, dst)


def main():
    try:
        remota = descargar(URL_VERSION).decode("utf-8").strip()
    except Exception as e:
        print("[actualizador] Sin conexión o repositorio no disponible (%s). Se usa la versión instalada." % e)
        return 0
    local = version_local()
    if a_tupla(remota) <= a_tupla(local):
        print("[actualizador] Versión al día (v%s)." % local)
        return 0
    print("[actualizador] Nueva versión v%s (instalada: v%s). Descargando…" % (remota, local))
    try:
        datos = descargar(URL_ZIP, timeout=90)
        with zipfile.ZipFile(io.BytesIO(datos)) as z:
            tmp = os.path.join(RAIZ, ".update_tmp")
            shutil.rmtree(tmp, ignore_errors=True)
            z.extractall(tmp)
        carpetas = [d for d in os.listdir(tmp) if os.path.isdir(os.path.join(tmp, d))]
        if not carpetas:
            raise RuntimeError("El ZIP descargado está vacío")
        copiar_arbol(os.path.join(tmp, carpetas[0]), RAIZ)
        shutil.rmtree(tmp, ignore_errors=True)
        print("[actualizador] Actualizado a v%s." % remota)
        return 10
    except Exception as e:
        shutil.rmtree(os.path.join(RAIZ, ".update_tmp"), ignore_errors=True)
        print("[actualizador] La actualización falló (%s). Se sigue con la versión instalada." % e)
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # último resguardo
        print("[actualizador] Error inesperado: %s" % e)
        sys.exit(0)
