"""
Clasificación de titulares: países (con límites de palabra y orden de
aparición), nivel, tipo, severidad inicial y asignación a crisis conocidas.

Extraído de actualizador.py; arregla las trampas del matching por substring:
- "georgia" ya no matchea dentro de otras palabras (límites de palabra)
- el par origen→destino respeta el orden de aparición en el titular
- fuera claves ambiguas ("america", "corea" a secas)
- "US" se detecta en mayúsculas (o "U.S.") para no confundir con "us" inglés
"""
import re
import unicodedata
from datetime import date
from difflib import SequenceMatcher

# ── PAÍSES Y COORDENADAS ────────────────────────────────────────────────────
# clave (se normaliza) → nombre canónico y coordenadas

PAISES = {
    "ukraine":      {"nombre": "Ucrania",        "lat": 48.38, "lng": 31.17},
    "ucrania":      {"nombre": "Ucrania",        "lat": 48.38, "lng": 31.17},
    "zelensky":     {"nombre": "Ucrania",        "lat": 48.38, "lng": 31.17},
    "russia":       {"nombre": "Rusia",          "lat": 55.76, "lng": 37.62},
    "rusia":        {"nombre": "Rusia",          "lat": 55.76, "lng": 37.62},
    "putin":        {"nombre": "Rusia",          "lat": 55.76, "lng": 37.62},
    "kremlin":      {"nombre": "Rusia",          "lat": 55.76, "lng": 37.62},
    "iran":         {"nombre": "Irán",           "lat": 35.69, "lng": 51.39},
    "tehran":       {"nombre": "Irán",           "lat": 35.69, "lng": 51.39},
    "israel":       {"nombre": "Israel",         "lat": 31.77, "lng": 35.21},
    "israeli":      {"nombre": "Israel",         "lat": 31.77, "lng": 35.21},
    "gaza":         {"nombre": "Gaza",           "lat": 31.50, "lng": 34.47},
    "china":        {"nombre": "China",          "lat": 39.90, "lng": 116.41},
    "beijing":      {"nombre": "China",          "lat": 39.90, "lng": 116.41},
    "pekin":        {"nombre": "China",          "lat": 39.90, "lng": 116.41},
    "taiwan":       {"nombre": "Taiwán",         "lat": 23.70, "lng": 120.96},
    "taipei":       {"nombre": "Taiwán",         "lat": 23.70, "lng": 120.96},
    "usa":          {"nombre": "EE.UU.",         "lat": 38.90, "lng": -77.04},
    "washington":   {"nombre": "EE.UU.",         "lat": 38.90, "lng": -77.04},
    "trump":        {"nombre": "EE.UU.",         "lat": 38.90, "lng": -77.04},
    "eeuu":         {"nombre": "EE.UU.",         "lat": 38.90, "lng": -77.04},
    "estados unidos": {"nombre": "EE.UU.",       "lat": 38.90, "lng": -77.04},
    "north korea":  {"nombre": "Corea del Norte","lat": 39.04, "lng": 125.76},
    "corea del norte": {"nombre": "Corea del Norte","lat": 39.04, "lng": 125.76},
    "pyongyang":    {"nombre": "Corea del Norte","lat": 39.04, "lng": 125.76},
    "south korea":  {"nombre": "Corea del Sur",  "lat": 35.91, "lng": 127.77},
    "corea del sur":{"nombre": "Corea del Sur",  "lat": 35.91, "lng": 127.77},
    "seoul":        {"nombre": "Corea del Sur",  "lat": 35.91, "lng": 127.77},
    "sudan":        {"nombre": "Sudán",          "lat": 15.55, "lng": 32.53},
    "khartoum":     {"nombre": "Sudán",          "lat": 15.55, "lng": 32.53},
    "mali":         {"nombre": "Mali",           "lat": 17.57, "lng": -3.99},
    "niger":        {"nombre": "Níger",          "lat": 17.61, "lng": 8.08},
    "india":        {"nombre": "India",          "lat": 20.59, "lng": 78.96},
    "pakistan":     {"nombre": "Pakistán",       "lat": 30.38, "lng": 69.35},
    "venezuela":    {"nombre": "Venezuela",      "lat": 10.48, "lng": -66.90},
    "haiti":        {"nombre": "Haití",          "lat": 18.54, "lng": -72.34},
    "ecuador":      {"nombre": "Ecuador",        "lat": -2.20, "lng": -79.89},
    "hungary":      {"nombre": "Hungría",        "lat": 47.50, "lng": 19.04},
    "hungria":      {"nombre": "Hungría",        "lat": 47.50, "lng": 19.04},
    "ethiopia":     {"nombre": "Etiopía",        "lat": 9.02,  "lng": 38.75},
    "etiopia":      {"nombre": "Etiopía",        "lat": 9.02,  "lng": 38.75},
    "somalia":      {"nombre": "Somalia",        "lat": 2.05,  "lng": 45.34},
    "myanmar":      {"nombre": "Myanmar",        "lat": 19.74, "lng": 96.08},
    "birmania":     {"nombre": "Myanmar",        "lat": 19.74, "lng": 96.08},
    "afghanistan":  {"nombre": "Afganistán",     "lat": 33.93, "lng": 67.71},
    "afganistan":   {"nombre": "Afganistán",     "lat": 33.93, "lng": 67.71},
    "kabul":        {"nombre": "Afganistán",     "lat": 33.93, "lng": 67.71},
    "syria":        {"nombre": "Siria",          "lat": 34.80, "lng": 38.99},
    "siria":        {"nombre": "Siria",          "lat": 34.80, "lng": 38.99},
    "damascus":     {"nombre": "Siria",          "lat": 34.80, "lng": 38.99},
    "lebanon":      {"nombre": "Líbano",         "lat": 33.85, "lng": 35.86},
    "libano":       {"nombre": "Líbano",         "lat": 33.85, "lng": 35.86},
    "beirut":       {"nombre": "Líbano",         "lat": 33.85, "lng": 35.86},
    "houthi":       {"nombre": "Yemen",          "lat": 15.55, "lng": 48.52},
    "yemen":        {"nombre": "Yemen",          "lat": 15.55, "lng": 48.52},
    "saudi":        {"nombre": "Arabia Saudí",   "lat": 23.89, "lng": 45.08},
    "riyadh":       {"nombre": "Arabia Saudí",   "lat": 23.89, "lng": 45.08},
    "turkey":       {"nombre": "Turquía",        "lat": 38.96, "lng": 35.24},
    "turquia":      {"nombre": "Turquía",        "lat": 38.96, "lng": 35.24},
    "erdogan":      {"nombre": "Turquía",        "lat": 38.96, "lng": 35.24},
    "poland":       {"nombre": "Polonia",        "lat": 51.92, "lng": 19.15},
    "polonia":      {"nombre": "Polonia",        "lat": 51.92, "lng": 19.15},
    "finland":      {"nombre": "Finlandia",      "lat": 64.96, "lng": 25.75},
    "sweden":       {"nombre": "Suecia",         "lat": 60.13, "lng": 18.64},
    "baltic":       {"nombre": "Bálticos",       "lat": 56.88, "lng": 24.60},
    "congo":        {"nombre": "Congo",          "lat": -4.03, "lng": 21.76},
    "drc":          {"nombre": "Congo",          "lat": -4.03, "lng": 21.76},
    "colombia":     {"nombre": "Colombia",       "lat": 4.57,  "lng": -74.30},
    "mexico":       {"nombre": "México",         "lat": 23.63, "lng": -102.55},
    "brazil":       {"nombre": "Brasil",         "lat": -14.24,"lng": -51.93},
    "brasil":       {"nombre": "Brasil",         "lat": -14.24,"lng": -51.93},
    "argentina":    {"nombre": "Argentina",      "lat": -38.42,"lng": -63.62},
    "japan":        {"nombre": "Japón",          "lat": 36.20, "lng": 138.25},
    "japon":        {"nombre": "Japón",          "lat": 36.20, "lng": 138.25},
    "tokyo":        {"nombre": "Japón",          "lat": 36.20, "lng": 138.25},
    "philippines":  {"nombre": "Filipinas",      "lat": 12.88, "lng": 121.77},
    "filipinas":    {"nombre": "Filipinas",      "lat": 12.88, "lng": 121.77},
    "manila":       {"nombre": "Filipinas",      "lat": 12.88, "lng": 121.77},
    "indonesia":    {"nombre": "Indonesia",      "lat": -0.79, "lng": 113.92},
    "vietnam":      {"nombre": "Vietnam",        "lat": 14.06, "lng": 108.28},
    "nigeria":      {"nombre": "Nigeria",        "lat": 9.08,  "lng": 8.68},
    "egypt":        {"nombre": "Egipto",         "lat": 26.82, "lng": 30.80},
    "egipto":       {"nombre": "Egipto",         "lat": 26.82, "lng": 30.80},
    "cairo":        {"nombre": "Egipto",         "lat": 26.82, "lng": 30.80},
    "libya":        {"nombre": "Libia",          "lat": 26.34, "lng": 17.23},
    "libia":        {"nombre": "Libia",          "lat": 26.34, "lng": 17.23},
    "morocco":      {"nombre": "Marruecos",      "lat": 31.79, "lng": -7.09},
    "marruecos":    {"nombre": "Marruecos",      "lat": 31.79, "lng": -7.09},
    "serbia":       {"nombre": "Serbia",         "lat": 44.02, "lng": 21.01},
    "kosovo":       {"nombre": "Kosovo",         "lat": 42.60, "lng": 20.90},
    "georgia":      {"nombre": "Georgia",        "lat": 42.31, "lng": 43.36},
    "tbilisi":      {"nombre": "Georgia",        "lat": 42.31, "lng": 43.36},
    "armenia":      {"nombre": "Armenia",        "lat": 40.07, "lng": 45.04},
    "azerbaijan":   {"nombre": "Azerbaiyán",     "lat": 40.14, "lng": 47.58},
    "tunisia":      {"nombre": "Túnez",          "lat": 33.89, "lng": 9.54},
    "algeria":      {"nombre": "Argelia",        "lat": 28.03, "lng": 1.66},
    "argelia":      {"nombre": "Argelia",        "lat": 28.03, "lng": 1.66},
    "chad":         {"nombre": "Chad",           "lat": 15.45, "lng": 18.73},
    "mozambique":   {"nombre": "Mozambique",     "lat": -18.67,"lng": 35.53},
    "burkina":      {"nombre": "Burkina Faso",   "lat": 12.36, "lng": -1.53},
    "senegal":      {"nombre": "Senegal",        "lat": 14.50, "lng": -14.43},
    "cameroon":     {"nombre": "Camerún",        "lat": 7.37,  "lng": 12.35},
    "kenya":        {"nombre": "Kenia",          "lat": -0.02, "lng": 37.91},
    "tanzania":     {"nombre": "Tanzania",       "lat": -6.37, "lng": 34.89},
    "thailand":     {"nombre": "Tailandia",      "lat": 15.87, "lng": 100.99},
    "bangladesh":   {"nombre": "Bangladés",      "lat": 23.68, "lng": 90.35},
    "nepal":        {"nombre": "Nepal",          "lat": 28.39, "lng": 84.12},
    "iraq":         {"nombre": "Iraq",           "lat": 33.22, "lng": 43.68},
    "irak":         {"nombre": "Iraq",           "lat": 33.22, "lng": 43.68},
    "baghdad":      {"nombre": "Iraq",           "lat": 33.22, "lng": 43.68},
    "jordan":       {"nombre": "Jordania",       "lat": 30.59, "lng": 36.24},
    "jordania":     {"nombre": "Jordania",       "lat": 30.59, "lng": 36.24},
    "qatar":        {"nombre": "Catar",          "lat": 25.35, "lng": 51.18},
    "kuwait":       {"nombre": "Kuwait",         "lat": 29.31, "lng": 47.49},
    "oman":         {"nombre": "Omán",           "lat": 21.51, "lng": 55.92},
    "uae":          {"nombre": "Emiratos Árabes","lat": 23.42, "lng": 53.85},
    "emirates":     {"nombre": "Emiratos Árabes","lat": 23.42, "lng": 53.85},
    "spain":        {"nombre": "España",         "lat": 40.46, "lng": -3.75},
    "espana":       {"nombre": "España",         "lat": 40.46, "lng": -3.75},
    "france":       {"nombre": "Francia",        "lat": 46.23, "lng": 2.21},
    "francia":      {"nombre": "Francia",        "lat": 46.23, "lng": 2.21},
    "germany":      {"nombre": "Alemania",       "lat": 51.17, "lng": 10.45},
    "alemania":     {"nombre": "Alemania",       "lat": 51.17, "lng": 10.45},
    "berlin":       {"nombre": "Alemania",       "lat": 51.17, "lng": 10.45},
    "uk":           {"nombre": "Reino Unido",    "lat": 55.38, "lng": -3.44},
    "britain":      {"nombre": "Reino Unido",    "lat": 55.38, "lng": -3.44},
    "british":      {"nombre": "Reino Unido",    "lat": 55.38, "lng": -3.44},
    "nato":         {"nombre": "OTAN",           "lat": 50.88, "lng": 4.49},
    "otan":         {"nombre": "OTAN",           "lat": 50.88, "lng": 4.49},
    "greenland":    {"nombre": "Groenlandia",    "lat": 71.71, "lng": -42.60},
    "groenlandia":  {"nombre": "Groenlandia",    "lat": 71.71, "lng": -42.60},
}

# ── KEYWORDS (idénticas al sistema original, ver actualizador histórico) ───

CRISIS_KEYWORDS = {
    "ucrania-este-2026":          ["ukraine", "ucrania", "russia", "rusia", "zelenski", "zelenskyy", "kiev", "kyiv", "kharkiv", "bakhmut", "donbas", "zaporizhzhia", "kursk"],
    "iran-ormuz-2026":            ["iran", "irán", "ormuz", "hormuz", "persian gulf", "golfo pérsico"],
    "oriente-medio-gaza":         ["gaza", "hamas", "west bank", "rafah", "cisjordania", "netanyahu", "idf", "jenin"],
    "sudan-guerra-civil-2026":    ["sudan", "sudán", "rsf", "jartum", "khartoum", "darfur", "port sudan"],
    "sahel-mali-yihadistas-2026": ["mali", "sahel", "jnim", "burkina", "niger", "niamey", "bamako", "gsim"],
    "india-pakistan-sindoor-2026":["india", "pakistan", "sindoor", "kashmir", "cachemira", "indus"],
    "corea-norte-misiles-2026":   ["north korea", "corea del norte", "pyongyang", "kim jong", "icbm", "dprk"],
    "tension-estrecho-taiwan":    ["taiwan", "taiwán", "taipei", "pla navy", "tsmc"],
    "violencia-haiti":            ["haiti", "haití", "port-au-prince"],
    "conflicto-ecuador":          ["ecuador", "noboa", "los choneros"],
    "conflicto-mar-rojo-huties":  ["houthi", "huti", "hutí", "red sea", "mar rojo", "bab el-mandeb", "bab-el-mandeb"],
    "crisis-energetica-europa":   ["european gas", "europe energy", "gas europeo", "energía europea", "nord stream", "gasoducto europa"],
    "china-estrategia-energetica":["belt and road", "nueva ruta de la seda", "south china sea", "mar de china meridional"],
    "conflicto-israel-libano-2026":   ["lebanon", "líbano", "libano", "hezbollah", "hizbulá", "south lebanon", "beirut", "dahiyeh"],
    "pakistan-afghanistan-ataques-2026": ["afghanistan", "afganistán", "taliban", "talibán", "khyber", "nangarhar", "kabul"],
    "eeuu-groenlandia-bases-2026":    ["greenland", "groenlandia", "nuuk", "arctic base", "base ártica"],
    "crisis-politica-filipinas-2026": ["philippines", "filipinas", "duterte", "marcos", "manila"],
    "bosnia-crisis-dayton-2026":      ["bosnia", "sarajevo", "dayton", "republika srpska", "dodik"],
    "lago-chad-boko-haram-2026":      ["boko haram", "lake chad", "lago chad", "mnjtf", "borno", "diffa"],
}

KEYWORDS_BILATERAL = [
    "sanctions", "sanciones", "tariffs", "aranceles", "expel", "expulsa",
    "ambassador", "embajador", "threatens", "amenaza", "deploys", "despliega",
    "ceasefire", "alto el fuego", "agreement", "acuerdo", "tensions", "tensiones",
    "clash", "choque", "confrontation", "confrontación", "negotiations", "negociaciones",
    "summit", "cumbre", "ally", "aliado", "bloc", "bloqueo",
]

KEYWORDS_ROJO    = ["war", "guerra", "attack", "ataque", "killed", "muertos", "strike", "ceasefire violation", "bombing", "bombardeo", "offensive", "invasion"]
KEYWORDS_NARANJA = ["tension", "tensión", "deploy", "threat", "amenaza", "sanctions", "sanciones", "military", "naval", "troops", "alert"]
KEYWORDS_AMARILLO= ["talks", "negotiations", "agreement", "diplomat", "summit", "cumbre", "trade", "comercio", "envoy"]

KEYWORDS_TIPO = {
    "cyber": [
        "cyberattack", "ciberataque", "ransomware", "malware", "hack", "apt", "exploit",
        "vulnerability", "cve", "data breach", "phishing", "ddos", "critical infrastructure",
        "zero-day", "zero day", "spyware", "botnet", "cyber attack", "cyber incident",
        "critical system", "power grid", "infrastructure attack",
    ],
    "intel": [
        "spy ring", "red de espías", "espionage network", "red de espionaje",
        "spy arrested", "spy caught", "spy charged", "espía detenido", "espía arrestado",
        "charged with espionage", "acusado de espionaje",
        "classified documents", "documentos clasificados",
        "intelligence leak", "leaked intelligence", "leaked classified",
        "state secrets", "secretos de estado", "classified information disclosed",
        "defector", "double agent", "agente doble", "mole inside", "informant exposed",
        "covert operation revealed", "intelligence operation exposed",
        "secret program exposed", "cia operation", "programa secreto revelado",
        "surveillance program", "mass surveillance", "wiretapping scandal",
        "disinformation campaign", "campaña de desinformación",
        "influence operation", "operación de influencia", "psyop",
        "cyber espionage", "ciberespionaje", "state-sponsored hacking", "nation-state hackers",
    ],
    "armed": [
        "war", "guerra", "attack", "ataque", "bombing", "bombardeo", "offensive",
        "invasion", "airstrike", "artillery", "missile", "conflict", "batalla",
        "soldiers", "killed", "muertos", "ceasefire", "frontline", "troops deployed",
        "military strike", "air strike", "ground offensive", "naval blockade",
        "ataque militar", "ofensiva",
    ],
    "econ": [
        "sanctions", "sanciones", "tariff", "arancel", "trade war", "guerra comercial",
        "export ban", "import ban", "embargo", "recession", "currency crisis",
        "debt default", "imf bailout", "economic crisis",
        "crisis económica", "financial crisis", "crisis financiera", "oil price",
        "energy crisis", "crisis energética",
    ],
    "diplo": [
        "expels diplomat", "expels ambassador", "expulsa diplomático", "expulsa embajador",
        "persona non grata",
        "recalls ambassador", "ambassador recalled", "retira embajador",
        "withdraws ambassador", "llamado a consultas",
        "summons ambassador", "summon ambassador", "convoca embajador", "summons envoy",
        "diplomatic protest", "protesta diplomática", "nota de protesta",
        "formal complaint", "queja formal", "diplomatic note", "lodges protest",
        "breaks diplomatic", "severs diplomatic", "suspend diplomatic relations",
        "ruptura diplomática", "rompe relaciones", "suspende relaciones",
        "corta relaciones", "freeze diplomatic",
        "closes embassy", "shuts embassy", "cierra embajada",
        "embassy closed", "embajada cerrada", "consulate closed",
        "diplomatic incident", "incidente diplomático", "diplomatic crisis",
        "crisis diplomática",
    ],
}

# ── NORMALIZACIÓN Y MATCHING ────────────────────────────────────────────────

def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def similitud(a: str, b: str) -> float:
    return SequenceMatcher(None, normalizar(a), normalizar(b)).ratio()


def slugify(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^\w\s-]", "", t)
    t = re.sub(r"\s+", "-", t.strip())
    return t[:48] + f"-{date.today().year}"


def _patron(kw: str) -> re.Pattern:
    """Patrón con límites de palabra sobre texto normalizado: 'mali' deja de
    matchear 'malicious' e 'indus' deja de matchear 'industry'."""
    return re.compile(r"\b" + re.escape(normalizar(kw)) + r"\b")


def _alguno(patrones: list[re.Pattern], t: str) -> bool:
    return any(p.search(t) for p in patrones)


# Patrones compilados una vez (países, crisis, niveles, tipos, bilateral).
_PATRONES_PAIS: list[tuple[re.Pattern, dict]] = [
    (_patron(clave), datos) for clave, datos in PAISES.items()
]
_PATRONES_CRISIS = {cid: [_patron(k) for k in kws] for cid, kws in CRISIS_KEYWORDS.items()}
_PAT_ROJO = [_patron(k) for k in KEYWORDS_ROJO]
_PAT_NARANJA = [_patron(k) for k in KEYWORDS_NARANJA]
_PAT_BILATERAL = [_patron(k) for k in KEYWORDS_BILATERAL]
_PATRONES_TIPO = {tipo: [_patron(k) for k in kws] for tipo, kws in KEYWORDS_TIPO.items()}
# "US"/"U.S." se busca en el texto ORIGINAL (case-sensitive): en minúscula
# "us" es el pronombre inglés.
_PATRON_US = re.compile(r"\bU\.?S\.?A?\b")
_DATOS_US = {"nombre": "EE.UU.", "lat": 38.90, "lng": -77.04}


def detectar_paises_en_texto(texto: str) -> list[dict]:
    """Países mencionados, ordenados por posición de aparición en el texto."""
    t = normalizar(texto)
    encontrados: dict[str, tuple[int, dict]] = {}
    for patron, datos in _PATRONES_PAIS:
        m = patron.search(t)
        if m:
            nombre = datos["nombre"]
            if nombre not in encontrados or m.start() < encontrados[nombre][0]:
                encontrados[nombre] = (m.start(), datos)
    m = _PATRON_US.search(texto)
    if m and _DATOS_US["nombre"] not in encontrados:
        # posición aproximada en el normalizado: usa la del original
        encontrados[_DATOS_US["nombre"]] = (m.start(), _DATOS_US)
    return [d for _, d in sorted(encontrados.values(), key=lambda x: x[0])]


def inferir_nivel(texto: str) -> str:
    t = normalizar(texto)
    if _alguno(_PAT_ROJO, t):
        return "rojo"
    if _alguno(_PAT_NARANJA, t):
        return "naranja"
    return "amarillo"


def inferir_tipo(texto: str) -> str | None:
    t = normalizar(texto)
    for tipo, patrones in _PATRONES_TIPO.items():
        if _alguno(patrones, t):
            return tipo
    return None


def inferir_severidad(texto: str, menciones: int) -> int:
    t = normalizar(texto)
    if _alguno(_PAT_ROJO, t):
        base = 4
    elif _alguno(_PAT_NARANJA, t):
        base = 3
    else:
        base = 2
    return min(5, base + (1 if menciones >= 6 else 0))


def es_bilateral(titulo: str) -> tuple[bool, list[dict]]:
    paises = detectar_paises_en_texto(titulo)
    tiene_kw = _alguno(_PAT_BILATERAL, normalizar(titulo))
    return len(paises) >= 2 and tiene_kw, paises


def clasificar_crisis(titulo: str) -> str | None:
    t = normalizar(titulo)
    for cid, patrones in _PATRONES_CRISIS.items():
        if _alguno(patrones, t):
            return cid
    return None
