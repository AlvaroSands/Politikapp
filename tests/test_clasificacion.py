"""Tests del matching de países y clasificación de titulares."""
from clasificacion import (
    clasificar_crisis, detectar_paises_en_texto, es_bilateral, es_ruido,
    inferir_nivel,
)


def test_es_ruido_deporte_y_cultura():
    # caso real: pieza del Mundial cuyo summary menciona Haití
    assert es_ruido("She waited decades for Scotland to make the World Cup")
    assert es_ruido("Eurovision winner announces concert tour of Israel")
    # pero una señal roja explícita no se descarta nunca
    assert not es_ruido("Bombing at World Cup stadium kills three")
    assert not es_ruido("Russia launches offensive in Donbas")


def nombres(texto):
    return [p["nombre"] for p in detectar_paises_en_texto(texto)]


def test_limites_de_palabra():
    # "status" no contiene el país "us"; "Jordan Peterson" sí matchearía
    # "jordan", pero "ambassador" no debe matchear nada
    assert "EE.UU." not in nombres("The status quo remains")
    assert "Jordania" not in nombres("ambassadors meet in Vienna")


def test_us_solo_en_mayusculas():
    assert "EE.UU." in nombres("US deploys carriers to the Gulf")
    assert "EE.UU." in nombres("U.S. sanctions on Iran")
    assert "EE.UU." not in nombres("give us more time, says envoy")


def test_orden_de_aparicion():
    n = nombres("China warns Japan over disputed islands")
    assert n[:2] == ["China", "Japón"]
    n2 = nombres("Japan protests after China incursion")
    assert n2[:2] == ["Japón", "China"]


def test_corea_del_sur_no_es_corea_del_norte():
    n = nombres("South Korea holds drills with US forces")
    assert "Corea del Sur" in n
    assert "Corea del Norte" not in n


def test_acentos_normalizados():
    assert "Irán" in nombres("Irán amenaza con cerrar Ormuz")
    assert "Irán" in nombres("Iran threatens to close Hormuz")


def test_bilateral_orden_origen_destino():
    bilateral, paises = es_bilateral("India summons Pakistan ambassador over clash")
    assert bilateral
    assert paises[0]["nombre"] == "India"
    assert paises[1]["nombre"] == "Pakistán"


def test_no_bilateral_sin_keyword():
    bilateral, _ = es_bilateral("India and Pakistan share monsoon rains")
    assert not bilateral


def test_clasificar_crisis_conocida():
    assert clasificar_crisis("Russian drones strike Kharkiv overnight") == "ucrania-este-2026"
    assert clasificar_crisis("Houthis attack tanker in the Red Sea") == "conflicto-mar-rojo-huties"


def test_energetica_ya_no_es_cajon_desastre():
    # antes: "energy"+"europe" se tragaba cualquier noticia económica europea
    assert clasificar_crisis("European stocks rise on tech earnings") is None
    assert clasificar_crisis("Nord Stream repairs spark European gas dispute") == "crisis-energetica-europa"


def test_inferir_nivel():
    assert inferir_nivel("Air strike kills dozens") == "rojo"
    assert inferir_nivel("Military deployment raises tension") == "naranja"
    assert inferir_nivel("Leaders meet for trade summit") == "amarillo"


def test_keywords_de_crisis_con_limites_de_palabra():
    # bugs reales del primer ciclo: 'mali' en 'malicious', 'indus' en 'industry'
    assert clasificar_crisis("Attack tricks AI agents into running malicious code") is None
    assert clasificar_crisis("Industry reactions to the new AI model") is None
    assert clasificar_crisis("JNIM militants strike near Bamako, Mali") == "sahel-mali-yihadistas-2026"
    assert clasificar_crisis("Indus water treaty tensions rise") == "india-pakistan-sindoor-2026"
