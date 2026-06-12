"""
Rutas de los datos de runtime. En local todo vive junto al código (DATA_DIR
no definido → "."). En Railway hay que montar un volumen y definir
DATA_DIR=/data para que crisis, historial y suscriptores sobrevivan a los
deploys; sin esto, cada deploy resetea datos.json al estado del repo.
"""
import os
import shutil

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_DIR", REPO_DIR)


def ruta(nombre: str) -> str:
    return os.path.join(DATA_DIR, nombre)


ARCHIVO_DATOS        = ruta("datos.json")
ARCHIVO_PENDIENTES   = ruta("pendientes.json")
ARCHIVO_HISTORIAL    = ruta("historial_severidad.json")
ARCHIVO_SUSCRIPTORES = ruta("suscriptores.json")
ARCHIVO_BRIEFING     = ruta("briefing_ultima_fecha.txt")
ARCHIVO_SALUD        = ruta("salud_fuentes.json")

# Ficheros que se siembran desde el repo la primera vez que se usa un
# DATA_DIR vacío (primer arranque con volumen).
_SEMILLAS = ["datos.json", "historial_severidad.json"]


def asegurar_semillas() -> None:
    if DATA_DIR == REPO_DIR:
        return
    os.makedirs(DATA_DIR, exist_ok=True)
    for nombre in _SEMILLAS:
        destino = ruta(nombre)
        origen = os.path.join(REPO_DIR, nombre)
        if not os.path.exists(destino) and os.path.exists(origen):
            shutil.copy2(origen, destino)
            print(f"[rutas] semilla copiada al volumen: {nombre}")
