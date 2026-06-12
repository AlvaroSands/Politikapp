"""
Vitalidad de crisis y relaciones: severidad viva con decay temporal,
estados (activa / latente / archivada) y fusión de relaciones bilaterales.

Principio: la severidad que se muestra es la EVIDENCIA RECIENTE, no una
etiqueta editorial congelada. Cada crisis conserva su `severity_base`
(el techo editorial o el asignado al crearse) y la severidad efectiva se
recalcula en cada ciclo a partir de la actividad del timeline.
"""
from datetime import date, datetime, timedelta
from math import exp

# ── Parámetros (días) ────────────────────────────────────────────────────────

TAU_ACTIVIDAD = 4.0      # decay e^(-edad/τ) del peso de cada noticia
VENTANA_FUENTES = 7      # ventana para contar fuentes independientes
DIAS_POR_ESCALON = 7     # sin noticias, la severidad baja 1 nivel por tramo
DIAS_LATENTE = 14        # sin noticias ≥ → latente
DIAS_ARCHIVO = 30        # sin noticias ≥ → archivada
UMBRAL_SOSTENIDA = 2.0   # actividad que mantiene la severidad base
UMBRAL_ESCALADA = 8.0    # actividad que permite subir base+1
FUENTES_ESCALADA = 3     # ... si además hay ≥3 fuentes independientes
TTL_RELACIONES = 14      # días de vida de una relación sin eventos nuevos
MAX_EVENTOS_RELACION = 10

PESO_NIVEL = {"rojo": 3.0, "naranja": 2.0, "amarillo": 1.0}
ORDEN_NIVEL = {"rojo": 3, "naranja": 2, "amarillo": 1}


def _parse_fecha(s: str) -> date | None:
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def actividad_reciente(timeline: list[dict], hoy: date,
                       inferir_nivel=None) -> dict:
    """
    Mide la actividad de un timeline: score con decay, fuentes únicas en
    la ventana, días desde la última noticia y nº de noticias en 24/48 h.
    `inferir_nivel(texto) -> 'rojo'|'naranja'|'amarillo'` pondera cada item.
    """
    score = 0.0
    fuentes: set[str] = set()
    mas_reciente: date | None = None
    noticias_24h = 0
    noticias_48h = 0

    for item in timeline or []:
        f = _parse_fecha(item.get("when", ""))
        if f is None or f > hoy:
            continue
        edad = (hoy - f).days
        if mas_reciente is None or f > mas_reciente:
            mas_reciente = f
        nivel = inferir_nivel(item.get("what", "")) if inferir_nivel else "amarillo"
        score += PESO_NIVEL.get(nivel, 1.0) * exp(-edad / TAU_ACTIVIDAD)
        if edad <= VENTANA_FUENTES:
            fuentes.add(item.get("source", "?"))
        if edad <= 1:
            noticias_24h += 1
        if edad <= 2:
            noticias_48h += 1

    dias_sin = (hoy - mas_reciente).days if mas_reciente else 9999
    return {
        "score": round(score, 2),
        "fuentes_recientes": len(fuentes),
        "dias_sin_noticias": dias_sin,
        "noticias_24h": noticias_24h,
        "noticias_48h": noticias_48h,
    }


def severidad_efectiva(base: int, act: dict) -> int:
    """
    Severidad mostrada = base modulada por evidencia:
    - actividad fuerte y multi-fuente → puede subir a base+1 (escalada)
    - actividad sostenida → se mantiene en base
    - silencio → baja 1 nivel por cada DIAS_POR_ESCALON sin noticias
    """
    base = max(1, min(5, int(base or 1)))
    score = act["score"]
    if score >= UMBRAL_ESCALADA and act["fuentes_recientes"] >= FUENTES_ESCALADA:
        return min(5, base + 1)
    if score >= UMBRAL_SOSTENIDA:
        return base
    escalones = act["dias_sin_noticias"] // DIAS_POR_ESCALON
    return max(1, base - escalones)


def estado_crisis(act: dict) -> str:
    dias = act["dias_sin_noticias"]
    if dias >= DIAS_ARCHIVO:
        return "archivada"
    if dias >= DIAS_LATENTE:
        return "latente"
    return "activa"


def aplicar_vitalidad(db: dict, hoy: date, inferir_nivel=None) -> list[dict]:
    """
    Recalcula severidad y estado de todas las crisis IN PLACE y mueve las
    archivadas a db['crisis_archivadas']. Devuelve la lista de cambios:
    [{'crisis', 'antes', 'despues'}] para alertas de escalada/desescalada.
    """
    cambios = []
    vivas = []
    archivadas = db.setdefault("crisis_archivadas", [])

    for c in db.get("crisis", []):
        # Migración: congelar la severidad editorial como base la 1.ª vez.
        if "severity_base" not in c:
            c["severity_base"] = c.get("severity", 1)

        act = actividad_reciente(c.get("timeline", []), hoy, inferir_nivel)
        antes = c.get("severity", c["severity_base"])
        despues = severidad_efectiva(c["severity_base"], act)
        estado = estado_crisis(act)

        c["severity"] = despues
        c["estado"] = estado
        c["actividad"] = {
            "score": act["score"],
            "fuentes_7d": act["fuentes_recientes"],
            "dias_sin_noticias": act["dias_sin_noticias"]
            if act["dias_sin_noticias"] < 9999 else None,
            "noticias_24h": act["noticias_24h"],
        }

        if despues != antes:
            cambios.append({"crisis": c, "antes": antes, "despues": despues})

        if estado == "archivada":
            c["archivada_en"] = hoy.isoformat()
            archivadas.append(c)
        else:
            vivas.append(c)

    db["crisis"] = vivas
    return cambios


# ── Relaciones bilaterales ──────────────────────────────────────────────────

def clave_par(origen: str, destino: str) -> str:
    return "|".join(sorted([origen or "?", destino or "?"]))


def _nombre(extremo) -> str:
    if isinstance(extremo, dict):
        return extremo.get("nombre", "?")
    return str(extremo or "?")


def fusionar_relaciones(relaciones: list[dict], hoy: date,
                        ttl: int = TTL_RELACIONES) -> list[dict]:
    """
    Una sola relación por par de países: nivel = el peor de los eventos
    vigentes, titular = el del evento más reciente de mayor nivel, y el
    histórico reciente queda en 'eventos'. Caducan sin eventos en `ttl` días.
    """
    limite = hoy - timedelta(days=ttl)
    grupos: dict[str, list[dict]] = {}

    for r in relaciones:
        # Aplanar: tanto relaciones ya fusionadas (con 'eventos') como sueltas.
        eventos = r.get("eventos") or [{
            "fecha": r.get("fecha", ""),
            "nivel": r.get("nivel", "amarillo"),
            "titular": r.get("titular", ""),
            "fuente": r.get("fuente", ""),
            "url": r.get("url", ""),
            "tipo": r.get("tipo", "diplomática"),
        }]
        par = clave_par(_nombre(r.get("origen")), _nombre(r.get("destino")))
        base = grupos.setdefault(par, [])
        for e in eventos:
            f = _parse_fecha(e.get("fecha", ""))
            if f is None or f < limite:
                continue
            if any(x.get("url") == e.get("url") and x.get("titular") == e.get("titular")
                   for x in base):
                continue
            # conservar referencia a los extremos para reconstruir la relación
            e["_origen"], e["_destino"] = r.get("origen"), r.get("destino")
            base.append(e)

    fusionadas = []
    for par, eventos in grupos.items():
        if not eventos:
            continue
        eventos.sort(key=lambda e: (e.get("fecha", ""), ORDEN_NIVEL.get(e.get("nivel"), 0)),
                     reverse=True)
        nivel = max((e.get("nivel", "amarillo") for e in eventos),
                    key=lambda n: ORDEN_NIVEL.get(n, 0))
        # el evento más reciente DEL nivel dominante define el titular
        cabeza = next(e for e in eventos if e.get("nivel") == nivel)
        primero = eventos[0]
        fusionadas.append({
            "id_relacion": "rel-" + par.lower().replace("|", "-").replace(" ", "-").replace(".", ""),
            "origen": primero.get("_origen"),
            "destino": primero.get("_destino"),
            "tipo": cabeza.get("tipo", "diplomática"),
            "nivel": nivel,
            "fecha": primero.get("fecha", ""),
            "titular": cabeza.get("titular", ""),
            "fuente": cabeza.get("fuente", ""),
            "url": cabeza.get("url", ""),
            "eventos": [
                {k: v for k, v in e.items() if not k.startswith("_")}
                for e in eventos[:MAX_EVENTOS_RELACION]
            ],
        })

    fusionadas.sort(key=lambda r: (ORDEN_NIVEL.get(r["nivel"], 0), r["fecha"]), reverse=True)
    return fusionadas
