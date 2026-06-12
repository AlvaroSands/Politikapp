"""Tests de la auto-creación de crisis v2 (agrupación por países+tipo)."""
from datetime import date, timedelta

import actualizador
from actualizador import (
    clave_candidato, limpiar_pendientes_caducados, registrar_candidato,
)
from clasificacion import clasificar_crisis_dinamica

HOY = date(2026, 6, 12)


def mencion(i, titulo, fuente, hace_dias=0):
    return {
        "titulo": titulo, "fuente": fuente, "url": f"http://x/{i}",
        "fecha": (HOY - timedelta(days=hace_dias)).isoformat(),
    }


def registrar(pendientes, i, titulo, fuente, hace_dias=0):
    return registrar_candidato(
        titulo, titulo, fuente, f"http://x/{i}",
        (HOY - timedelta(days=hace_dias)).isoformat(),
        pendientes, set(), hoy=HOY,
    )


def test_clave_ignora_orden_de_paises():
    a = [{"nombre": "Venezuela", "lat": 0, "lng": 0}, {"nombre": "EE.UU.", "lat": 1, "lng": 1}]
    b = list(reversed(a))
    assert clave_candidato(a, "armed") == clave_candidato(b, "armed")


def test_acumula_titulares_distintos_del_mismo_evento():
    # v1 exigía similitud >0.6 entre titulares: esto NUNCA maduraba.
    pendientes = []
    titulares = [
        ("US warships approach Venezuela amid invasion fears", "BBC"),
        ("Venezuela mobilises army as US warships near coast", "Reuters"),
        ("Maduro denuncia ataque inminente de EE.UU. a Venezuela", "El País"),
        ("Pentagon confirms strike group off Venezuela war footing", "Guardian"),
    ]
    for i, (t, f) in enumerate(titulares):
        assert registrar(pendientes, i, t, f) is None
    assert len(pendientes) == 1
    assert len(pendientes[0]["menciones"]) == 4
    # la 5.ª mención (3 fuentes ya superadas) madura el candidato
    maduro = registrar(pendientes, 9, "Venezuela war: US attack imminent", "DW")
    assert maduro is not None
    assert maduro["tipo"] == "armed"


def test_no_madura_con_una_sola_fuente():
    pendientes = []
    for i in range(6):
        r = registrar(pendientes, i, f"US strike on Venezuela day {i} war", "BBC")
    assert r is None


def test_menciones_viejas_no_cuentan_para_madurez():
    pendientes = []
    for i in range(4):
        registrar(pendientes, i, f"US Venezuela war buildup {i}", f"F{i}", hace_dias=5)
    r = registrar(pendientes, 9, "US Venezuela war attack", "F9")
    assert r is None  # solo 1 mención dentro de la ventana de 72 h


def test_limpiar_purga_viejas_y_formato_v1():
    pendientes = [
        {"clave": "x|armed", "tipo": "armed", "paises": [],
         "menciones": [mencion(1, "t", "F", hace_dias=10)]},
        {"titulo_base": "formato viejo", "menciones": 3},
        {"clave": "y|econ", "tipo": "econ", "paises": [],
         "menciones": [mencion(2, "t2", "F", hace_dias=1)]},
    ]
    vivos = limpiar_pendientes_caducados(pendientes, hoy=HOY)
    assert [p["clave"] for p in vivos] == ["y|econ"]


def test_dedupe_por_url():
    pendientes = []
    registrar(pendientes, 1, "US Venezuela war", "BBC")
    registrar(pendientes, 1, "US Venezuela war", "BBC")  # misma url
    assert len(pendientes[0]["menciones"]) == 1


def test_clasificacion_dinamica_dos_paises():
    crisis = [{
        "id": "us-venezuela-2026", "type": "armed",
        "paises_clave": ["EE.UU.", "Venezuela"],
    }]
    assert clasificar_crisis_dinamica(
        "US carrier moves closer to Venezuela coast", crisis,
    ) == "us-venezuela-2026"
    assert clasificar_crisis_dinamica("Venezuela inflation hits record", crisis) is None


def test_clasificacion_dinamica_un_pais_exige_tipo():
    crisis = [{"id": "haiti-gangs", "type": "armed", "paises_clave": ["Haití"]}]
    assert clasificar_crisis_dinamica(
        "Gang attack kills dozens in Haiti", crisis,
    ) == "haiti-gangs"
    # noticia económica de Haití: mismo país, tipo distinto → no se asigna
    assert clasificar_crisis_dinamica("Haiti receives IMF bailout package", crisis) is None
