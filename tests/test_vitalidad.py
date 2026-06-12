"""Tests de la severidad viva, estados y fusión de relaciones."""
from datetime import date, timedelta

from clasificacion import inferir_nivel
from vitalidad import (
    actividad_reciente, aplicar_vitalidad, estado_crisis,
    fusionar_relaciones, severidad_efectiva,
)

HOY = date(2026, 6, 12)


def tl(*items):
    """timeline de (hace_días, titular, fuente)."""
    return [
        {"when": (HOY - timedelta(days=d)).isoformat(), "what": w, "source": s, "url": f"u{i}"}
        for i, (d, w, s) in enumerate(items)
    ]


def test_actividad_decae_con_la_edad():
    fresca = actividad_reciente(tl((0, "war attack", "A")), HOY, inferir_nivel)
    vieja = actividad_reciente(tl((10, "war attack", "A")), HOY, inferir_nivel)
    assert fresca["score"] > vieja["score"] > 0


def test_severidad_se_mantiene_con_actividad_sostenida():
    act = actividad_reciente(
        tl((0, "talks resume", "A"), (1, "summit planned", "B")), HOY, inferir_nivel,
    )
    assert severidad_efectiva(4, act) == 4


def test_severidad_decae_en_silencio():
    act = actividad_reciente(tl((16, "war", "A")), HOY, inferir_nivel)
    # 16 días sin noticias → 2 escalones de 7 días → 4 - 2 = 2
    assert severidad_efectiva(4, act) == 2


def test_sin_noticias_nunca_baja_de_1():
    act = actividad_reciente([], HOY, inferir_nivel)
    assert severidad_efectiva(5, act) == 1


def test_escalada_requiere_actividad_fuerte_multifuente():
    intensa = actividad_reciente(
        tl(*[(0, "major attack killed many", f"F{i}") for i in range(4)]),
        HOY, inferir_nivel,
    )
    assert severidad_efectiva(3, intensa) == 4
    una_fuente = actividad_reciente(
        tl(*[(0, "major attack killed many", "F0") for _ in range(4)]),
        HOY, inferir_nivel,
    )
    assert severidad_efectiva(3, una_fuente) == 3


def test_estados_por_dias_sin_noticias():
    assert estado_crisis({"dias_sin_noticias": 3}) == "activa"
    assert estado_crisis({"dias_sin_noticias": 20}) == "latente"
    assert estado_crisis({"dias_sin_noticias": 31}) == "archivada"


def test_aplicar_vitalidad_archiva_y_migra_base():
    db = {
        "crisis": [
            {"id": "viva", "severity": 4, "timeline": tl((0, "attack", "A"), (1, "war", "B"))},
            {"id": "muerta", "severity": 5, "timeline": tl((45, "old war", "A"))},
        ],
    }
    cambios = aplicar_vitalidad(db, HOY, inferir_nivel)
    ids_vivas = [c["id"] for c in db["crisis"]]
    assert ids_vivas == ["viva"]
    assert db["crisis_archivadas"][0]["id"] == "muerta"
    assert db["crisis"][0]["severity_base"] == 4
    # la muerta decayó (5 → 1), debe constar como cambio
    assert any(c["crisis"]["id"] == "muerta" and c["despues"] == 1 for c in cambios)


def rel(origen, destino, hace_dias, nivel, titular):
    return {
        "id_relacion": "x",
        "origen": {"nombre": origen, "lat": 0, "lng": 0},
        "destino": {"nombre": destino, "lat": 1, "lng": 1},
        "tipo": "diplomática",
        "nivel": nivel,
        "fecha": (HOY - timedelta(days=hace_dias)).isoformat(),
        "titular": titular,
        "fuente": "F",
        "url": f"http://x/{titular[:8]}",
    }


def test_fusion_un_par_una_relacion():
    rels = [
        rel("EE.UU.", "China", 0, "amarillo", "talks"),
        rel("China", "EE.UU.", 2, "rojo", "attack warning"),  # par invertido
        rel("EE.UU.", "Rusia", 1, "naranja", "sanctions"),
    ]
    out = fusionar_relaciones(rels, HOY)
    assert len(out) == 2
    usa_chn = next(r for r in out if "China" in (r["origen"]["nombre"], r["destino"]["nombre"]))
    assert usa_chn["nivel"] == "rojo"          # el peor nivel vigente manda
    assert usa_chn["titular"] == "attack warning"
    assert len(usa_chn["eventos"]) == 2


def test_fusion_caduca_por_ttl():
    rels = [rel("EE.UU.", "China", 20, "rojo", "old attack")]
    assert fusionar_relaciones(rels, HOY) == []


def test_fusion_id_estable():
    a = fusionar_relaciones([rel("EE.UU.", "China", 0, "rojo", "x")], HOY)
    b = fusionar_relaciones([rel("China", "EE.UU.", 1, "amarillo", "y")], HOY)
    assert a[0]["id_relacion"] == b[0]["id_relacion"]
