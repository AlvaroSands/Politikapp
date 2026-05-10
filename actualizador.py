"""
Actualizador geopolítico — RSS + scraping HTML + auto-creación de crisis.
Clasificación por keywords, scraping de fuentes sin RSS, y detección de
nuevos eventos a partir de menciones repetidas en fuentes independientes.
"""
import feedparser
import json
import os
import re
import time
import unicodedata
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher

import requests
from notificaciones import alerta_nueva_crisis, alerta_escalada, alerta_relacion_bilateral
from twitter import tweet_nueva_crisis, tweet_escalada, tweet_tension_bilateral
from bs4 import BeautifulSoup

ARCHIVO_DATOS     = "datos.json"
ARCHIVO_PENDIENTES   = "pendientes.json"
ARCHIVO_HISTORIAL    = "historial_severidad.json"

HEADERS_HTTP = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; GeopolitikApp/1.0; +https://geopolitikapp.com)"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── FUENTES RSS ─────────────────────────────────────────────────────────────

FUENTES_RSS = [
    # Anglófonas — generalistas
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.bbci.co.uk/news/world/europe/rss.xml",
    "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml",
    "https://feeds.bbci.co.uk/news/world/asia/rss.xml",
    "https://feeds.bbci.co.uk/news/world/africa/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/MiddleEast.xml",
    "https://feeds.reuters.com/reuters/worldNews",
    "https://feeds.reuters.com/reuters/topNews",
    "https://www.theguardian.com/world/rss",
    "https://www.theguardian.com/world/europe-news/rss",
    "https://www.theguardian.com/world/middleeast/rss",
    "https://apnews.com/rss",
    "https://www.independent.co.uk/news/world/rss",
    "https://www.ft.com/world?format=rss",
    "https://www.wsj.com/xml/rss/3_7085.xml",
    # Geopolítica / defensa / estrategia
    "https://foreignpolicy.com/feed/",
    "https://theeconomist.com/sections/world-politics/rss.xml",
    "https://warontherocks.com/feed/",
    "https://www.chathamhouse.org/rss.xml",
    "https://www.brookings.edu/feed/",
    "https://www.cfr.org/rss.xml",
    "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml",
    "https://www.janes.com/feeds/news",
    "https://thediplomat.com/feed/",
    "https://eastasiaforum.org/feed/",
    "https://www.lowyinstitute.org/the-interpreter/rss.xml",
    "https://www.iiss.org/rss",
    "https://www.atlanticcouncil.org/feed/",
    "https://www.crisisgroup.org/rss-feed",
    "https://www.rand.org/blog.xml",
    "https://www.justsecurity.org/feed/",
    "https://www.stimson.org/feed/",
    "https://carnegieendowment.org/rss/solr/articles",
    "https://www.wilsoncenter.org/rss.xml",
    # OSINT / inteligencia verificada
    "https://www.bellingcat.com/feed/",
    "https://www.understandingwar.org/rss.xml",
    "https://occrp.org/en/rss/",
    # Oriente Medio / África / Asia
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.middleeasteye.net/rss",
    "https://english.alarabiya.net/rss.xml",
    "https://www.africaintelligence.com/rss",
    "https://www.africanews.com/rss",
    "https://www.scmp.com/rss/91/feed",
    "https://www.scmp.com/rss/2/feed",
    "https://asia.nikkei.com/rss/feed/nar",
    "https://www.rfa.org/english/rss2.xml",
    "https://www.voanews.com/api/zy$tqepmve",
    # Derechos humanos
    "https://www.hrw.org/rss.xml",
    "https://www.amnesty.org/en/latest/feed/",
    "https://news.un.org/feed/subscribe/en/news/all/rss.xml",
    # Francófonas
    "https://www.france24.com/es/rss",
    "https://www.france24.com/fr/monde/rss",
    "https://www.lemonde.fr/international/rss_full.xml",
    "https://www.liberation.fr/arc/outboundfeeds/rss/?outputType=xml",
    # Hispanófonas
    "https://elpais.com/rss/internacional/el-pais.xml",
    "https://www.elmundo.es/rss/internacional.xml",
    "https://www.lavanguardia.com/mvc/feed/rss/internacional",
    "https://www.elconfidencial.com/rss/mundo/",
    "https://www.infobae.com/feeds/rss/america/",
    "https://www.bbc.com/mundo/rss.xml",
    "https://www.dw.com/es/rss/rss.xml",
    # Europeas / alemanas
    "https://www.dw.com/en/rss/rss.xml",
    "https://www.dw.com/de/rss/rss.xml",
    "https://www.politico.eu/feed/",
    "https://euobserver.com/rss.xml",
    "https://www.euractiv.com/sections/global-europe/feed/",
    # Europa del Este / Rusia
    "https://www.kyivpost.com/rss",
    "https://www.ukrinform.net/rss/block-ato",
    "https://meduza.io/rss/all",
    # Ciberseguridad — feeds RSS
    "https://www.securityweek.com/feed",
    "https://krebsonsecurity.com/feed/",
    "https://feeds.feedburner.com/TheHackersNews",
    "https://www.bleepingcomputer.com/feed/",
    "https://isc.sans.edu/rssfeed.xml",
    "https://www.darkreading.com/rss.xml",
    "https://feeds.feedburner.com/Threatpost",
    "https://blog.malwarebytes.com/feed/",
    # Radio pública / NPR
    "https://feeds.npr.org/1004/rss.xml",
]

# ── FUENTES CON SCRAPING HTML ───────────────────────────────────────────────

FUENTES_SCRAPING = {
    "CISA Advisories": {
        "url": "https://www.cisa.gov/news-events/cybersecurity-advisories",
        "tipo_hint": "cyber",
        "selectores_item": ["article.c-news-article", "div.views-row", "li.c-view__row"],
        "selectores_titulo": ["h3 a", "h2 a", ".c-news-article__title a"],
        "base_url": "https://www.cisa.gov",
    },
    "NCSC UK": {
        "url": "https://www.ncsc.gov.uk/news/all-news",
        "tipo_hint": "cyber",
        "selectores_item": ["article.article-preview", "li.search-result", "div.search-result"],
        "selectores_titulo": ["h3 a", "h2 a", ".article-preview__title a"],
        "base_url": "https://www.ncsc.gov.uk",
    },
    "ISW Ukraine": {
        "url": "https://www.understandingwar.org/ukraine-conflict-updates",
        "tipo_hint": "armed",
        "selectores_item": ["div.views-row", "article", "div.field-content"],
        "selectores_titulo": ["h3 a", "h2 a", "span.field-content a"],
        "base_url": "https://www.understandingwar.org",
    },
}

# ── PAÍSES Y COORDENADAS ────────────────────────────────────────────────────

PAISES = {
    "ukraine":      {"nombre": "Ucrania",        "lat": 48.38, "lng": 31.17},
    "ucrania":      {"nombre": "Ucrania",        "lat": 48.38, "lng": 31.17},
    "russia":       {"nombre": "Rusia",          "lat": 55.76, "lng": 37.62},
    "rusia":        {"nombre": "Rusia",          "lat": 55.76, "lng": 37.62},
    "iran":         {"nombre": "Irán",           "lat": 35.69, "lng": 51.39},
    "irán":         {"nombre": "Irán",           "lat": 35.69, "lng": 51.39},
    "israel":       {"nombre": "Israel",         "lat": 31.77, "lng": 35.21},
    "gaza":         {"nombre": "Gaza",           "lat": 31.50, "lng": 34.47},
    "china":        {"nombre": "China",          "lat": 39.90, "lng": 116.41},
    "taiwan":       {"nombre": "Taiwán",         "lat": 23.70, "lng": 120.96},
    "taiwán":       {"nombre": "Taiwán",         "lat": 23.70, "lng": 120.96},
    "usa":          {"nombre": "EE.UU.",         "lat": 38.90, "lng": -77.04},
    "us ":          {"nombre": "EE.UU.",         "lat": 38.90, "lng": -77.04},
    "trump":        {"nombre": "EE.UU.",         "lat": 38.90, "lng": -77.04},
    "america":      {"nombre": "EE.UU.",         "lat": 38.90, "lng": -77.04},
    "eeuu":         {"nombre": "EE.UU.",         "lat": 38.90, "lng": -77.04},
    "north korea":  {"nombre": "Corea del Norte","lat": 39.04, "lng": 125.76},
    "corea":        {"nombre": "Corea del Norte","lat": 39.04, "lng": 125.76},
    "sudan":        {"nombre": "Sudán",          "lat": 15.55, "lng": 32.53},
    "sudán":        {"nombre": "Sudán",          "lat": 15.55, "lng": 32.53},
    "mali":         {"nombre": "Mali",           "lat": 17.57, "lng": -3.99},
    "niger":        {"nombre": "Níger",          "lat": 17.61, "lng": 8.08},
    "india":        {"nombre": "India",          "lat": 20.59, "lng": 78.96},
    "pakistan":     {"nombre": "Pakistán",       "lat": 30.38, "lng": 69.35},
    "venezuela":    {"nombre": "Venezuela",      "lat": 10.48, "lng": -66.90},
    "haiti":        {"nombre": "Haití",          "lat": 18.54, "lng": -72.34},
    "ecuador":      {"nombre": "Ecuador",        "lat": -2.20, "lng": -79.89},
    "hungary":      {"nombre": "Hungría",        "lat": 47.50, "lng": 19.04},
    "hungría":      {"nombre": "Hungría",        "lat": 47.50, "lng": 19.04},
    "ethiopia":     {"nombre": "Etiopía",        "lat": 9.02,  "lng": 38.75},
    "etiopía":      {"nombre": "Etiopía",        "lat": 9.02,  "lng": 38.75},
    "somalia":      {"nombre": "Somalia",        "lat": 2.05,  "lng": 45.34},
    "myanmar":      {"nombre": "Myanmar",        "lat": 19.74, "lng": 96.08},
    "birmania":     {"nombre": "Myanmar",        "lat": 19.74, "lng": 96.08},
    "afghanistan":  {"nombre": "Afganistán",     "lat": 33.93, "lng": 67.71},
    "afganistán":   {"nombre": "Afganistán",     "lat": 33.93, "lng": 67.71},
    "syria":        {"nombre": "Siria",          "lat": 34.80, "lng": 38.99},
    "siria":        {"nombre": "Siria",          "lat": 34.80, "lng": 38.99},
    "lebanon":      {"nombre": "Líbano",         "lat": 33.85, "lng": 35.86},
    "líbano":       {"nombre": "Líbano",         "lat": 33.85, "lng": 35.86},
    "houthi":       {"nombre": "Yemen",          "lat": 15.55, "lng": 48.52},
    "yemen":        {"nombre": "Yemen",          "lat": 15.55, "lng": 48.52},
    "saudi":        {"nombre": "Arabia Saudí",   "lat": 23.89, "lng": 45.08},
    "arabia":       {"nombre": "Arabia Saudí",   "lat": 23.89, "lng": 45.08},
    "turkey":       {"nombre": "Turquía",        "lat": 38.96, "lng": 35.24},
    "turquía":      {"nombre": "Turquía",        "lat": 38.96, "lng": 35.24},
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
    "méxico":       {"nombre": "México",         "lat": 23.63, "lng": -102.55},
    "brazil":       {"nombre": "Brasil",         "lat": -14.24,"lng": -51.93},
    "brasil":       {"nombre": "Brasil",         "lat": -14.24,"lng": -51.93},
    "argentina":    {"nombre": "Argentina",      "lat": -38.42,"lng": -63.62},
    "japan":        {"nombre": "Japón",          "lat": 36.20, "lng": 138.25},
    "japón":        {"nombre": "Japón",          "lat": 36.20, "lng": 138.25},
    "south korea":  {"nombre": "Corea del Sur",  "lat": 35.91, "lng": 127.77},
    "philippines":  {"nombre": "Filipinas",      "lat": 12.88, "lng": 121.77},
    "filipinas":    {"nombre": "Filipinas",      "lat": 12.88, "lng": 121.77},
    "indonesia":    {"nombre": "Indonesia",      "lat": -0.79, "lng": 113.92},
    "vietnam":      {"nombre": "Vietnam",        "lat": 14.06, "lng": 108.28},
    "nigeria":      {"nombre": "Nigeria",        "lat": 9.08,  "lng": 8.68},
    "egypt":        {"nombre": "Egipto",         "lat": 26.82, "lng": 30.80},
    "egipto":       {"nombre": "Egipto",         "lat": 26.82, "lng": 30.80},
    "libya":        {"nombre": "Libia",          "lat": 26.34, "lng": 17.23},
    "libia":        {"nombre": "Libia",          "lat": 26.34, "lng": 17.23},
    "morocco":      {"nombre": "Marruecos",      "lat": 31.79, "lng": -7.09},
    "marruecos":    {"nombre": "Marruecos",      "lat": 31.79, "lng": -7.09},
    "serbia":       {"nombre": "Serbia",         "lat": 44.02, "lng": 21.01},
    "kosovo":       {"nombre": "Kosovo",         "lat": 42.60, "lng": 20.90},
    "georgia":      {"nombre": "Georgia",        "lat": 42.31, "lng": 43.36},
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
    "jordan":       {"nombre": "Jordania",       "lat": 30.59, "lng": 36.24},
    "jordania":     {"nombre": "Jordania",       "lat": 30.59, "lng": 36.24},
    "qatar":        {"nombre": "Catar",          "lat": 25.35, "lng": 51.18},
    "kuwait":       {"nombre": "Kuwait",         "lat": 29.31, "lng": 47.49},
    "oman":         {"nombre": "Omán",           "lat": 21.51, "lng": 55.92},
    "uae":          {"nombre": "Emiratos Árabes","lat": 23.42, "lng": 53.85},
    "emirates":     {"nombre": "Emiratos Árabes","lat": 23.42, "lng": 53.85},
    "spain":        {"nombre": "España",         "lat": 40.46, "lng": -3.75},
    "españa":       {"nombre": "España",         "lat": 40.46, "lng": -3.75},
    "france":       {"nombre": "Francia",        "lat": 46.23, "lng": 2.21},
    "francia":      {"nombre": "Francia",        "lat": 46.23, "lng": 2.21},
    "germany":      {"nombre": "Alemania",       "lat": 51.17, "lng": 10.45},
    "alemania":     {"nombre": "Alemania",       "lat": 51.17, "lng": 10.45},
    "uk":           {"nombre": "Reino Unido",    "lat": 55.38, "lng": -3.44},
    "britain":      {"nombre": "Reino Unido",    "lat": 55.38, "lng": -3.44},
    "nato":         {"nombre": "OTAN",           "lat": 50.88, "lng": 4.49},
}

# ── KEYWORDS DE CRISIS EXISTENTES ──────────────────────────────────────────

CRISIS_KEYWORDS = {
    "ucrania-este-2026":          ["ukraine", "ucrania", "russia", "rusia", "zelenski", "zelenskyy", "kiev", "kyiv", "kharkiv", "bakhmut", "donbas", "zaporizhzhia", "kursk"],
    "iran-ormuz-2026":            ["iran", "irán", "ormuz", "hormuz", "strait", "persian gulf", "golfo pérsico"],
    "oriente-medio-gaza":         ["gaza", "hamas", "west bank", "rafah", "cisjordania", "netanyahu", "idf", "jenin", "hezbollah"],
    "sudan-guerra-civil-2026":    ["sudan", "sudán", "rsf", "jartum", "khartoum", "darfur", "port sudan"],
    "sahel-mali-yihadistas-2026": ["mali", "sahel", "jnim", "burkina", "niger", "niamey", "bamako", "aes", "gsim"],
    "india-pakistan-sindoor-2026":["india", "pakistan", "sindoor", "kashmir", "cachemira", "indus", "loc"],
    "corea-norte-misiles-2026":   ["north korea", "corea del norte", "pyongyang", "kim jong", "missile", "misil", "icbm", "dprk"],
    "tension-estrecho-taiwan":    ["taiwan", "taiwán", "strait", "estrecho", "pla", "tsmc", "taipei"],
    "violencia-haiti":            ["haiti", "haití", "gang", "banda", "port-au-prince"],
    "conflicto-ecuador":          ["ecuador", "noboa", "crimen organizado", "eln", "narcotráfico"],
    "conflicto-mar-rojo-huties":  ["houthi", "huti", "hutí", "red sea", "mar rojo", "yemen", "bab el-mandeb", "bab-el-mandeb"],
    "crisis-energetica-europa":   ["energy", "energía", "gas", "oil", "petróleo", "europa", "europe", "lng", "pipeline", "gasoducto"],
    "china-estrategia-energetica":["china", "xi jinping", "bri", "belt and road", "nueva ruta", "south china sea"],
    # Entradas de cyber/intel
    "ciber-ataques-estado":       ["cyberattack", "ciberataque", "ransomware", "hack", "espionage", "espionaje", "apt", "malware", "exploit", "phishing", "ddos", "critical infrastructure"],
    "operaciones-inteligencia":   ["intelligence", "inteligencia", "spy", "espía", "leak", "filtración", "covert", "clandestine", "surveillance", "cia", "mi6", "fsb", "svr", "mossad"],
}

# ── KEYWORDS BILATERALES ────────────────────────────────────────────────────

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

# Keywords para inferir el tipo de nueva crisis
KEYWORDS_TIPO = {
    "cyber": ["cyberattack", "ciberataque", "ransomware", "malware", "hack", "apt", "exploit",
               "vulnerability", "cve", "breach", "phishing", "ddos", "critical infrastructure",
               "zero-day", "zero day", "spyware", "botnet", "data breach"],
    "intel": ["spy", "espionage", "intelligence", "espionaje", "inteligencia", "leak", "infiltrat",
               "covert", "clandestine", "surveillance", "intercept", "defect", "mole", "cia",
               "mi6", "fsb", "svr", "mossad", "bnd", "disinformation", "desinformación", "psyop"],
    "armed": ["war", "guerra", "attack", "ataque", "bombing", "bombardeo", "troops", "troops",
               "offensive", "invasion", "airstrike", "artillery", "missile", "conflict", "batalla",
               "soldiers", "killed", "muertos", "ceasefire", "frontline"],
    "econ":  ["sanctions", "sanciones", "tariff", "arancel", "trade", "comercio", "export",
               "import", "embargo", "gdp", "recession", "currency", "debt", "deuda", "imf",
               "world bank", "economic crisis", "crisis económica"],
}

# ── FUNCIONES AUXILIARES ────────────────────────────────────────────────────

def cargar_db():
    if os.path.exists(ARCHIVO_DATOS):
        with open(ARCHIVO_DATOS, "r", encoding="utf-8") as f:
            try:
                datos = json.load(f)
                if isinstance(datos, list):
                    return {"crisis": datos, "relaciones": []}
                return datos
            except json.JSONDecodeError:
                pass
    return {"crisis": [], "relaciones": []}


def guardar_db(datos):
    with open(ARCHIVO_DATOS, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def id_crisis(c):
    return c.get("id") or c.get("id_crisis", "")


def cargar_pendientes():
    if os.path.exists(ARCHIVO_PENDIENTES):
        with open(ARCHIVO_PENDIENTES, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except (json.JSONDecodeError, ValueError):
                pass
    return []


def guardar_pendientes(pendientes):
    with open(ARCHIVO_PENDIENTES, "w", encoding="utf-8") as f:
        json.dump(pendientes, f, ensure_ascii=False, indent=2)


def cargar_historial():
    if os.path.exists(ARCHIVO_HISTORIAL):
        with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except (json.JSONDecodeError, ValueError):
                pass
    return {}


def guardar_historial(historial):
    with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=2)


def registrar_severidad(historial, crisis_id, severity):
    """Añade un punto al historial solo si han pasado ≥24h desde el último."""
    hoy = date.today().isoformat()
    entradas = historial.setdefault(crisis_id, [])
    if entradas and entradas[-1]["fecha"] == hoy:
        entradas[-1]["severity"] = severity
    else:
        entradas.append({"fecha": hoy, "severity": severity})
    # Mantener últimos 90 días
    historial[crisis_id] = entradas[-90:]


def normalizar(texto):
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def similitud(a, b):
    return SequenceMatcher(None, normalizar(a), normalizar(b)).ratio()


def slugify(texto):
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^\w\s-]", "", t)
    t = re.sub(r"\s+", "-", t.strip())
    return t[:48] + f"-{date.today().year}"


def inferir_nivel(texto):
    t = texto.lower()
    if any(k in t for k in KEYWORDS_ROJO):
        return "rojo"
    if any(k in t for k in KEYWORDS_NARANJA):
        return "naranja"
    return "amarillo"


def inferir_tipo(texto):
    t = texto.lower()
    for tipo, kws in KEYWORDS_TIPO.items():
        if any(k in t for k in kws):
            return tipo
    return "diplo"


def inferir_severidad(texto, menciones):
    t = texto.lower()
    if any(k in t for k in KEYWORDS_ROJO):
        base = 4
    elif any(k in t for k in KEYWORDS_NARANJA):
        base = 3
    else:
        base = 2
    return min(5, base + (1 if menciones >= 6 else 0))


def detectar_paises_en_texto(texto):
    t = texto.lower()
    encontrados, vistos = [], set()
    for clave, datos in PAISES.items():
        if clave in t and datos["nombre"] not in vistos:
            encontrados.append(datos)
            vistos.add(datos["nombre"])
    return encontrados


def es_bilateral(titulo):
    paises = detectar_paises_en_texto(titulo)
    tiene_kw = any(k in titulo.lower() for k in KEYWORDS_BILATERAL)
    return len(paises) >= 2 and tiene_kw, paises


def clasificar_crisis(titulo):
    t = titulo.lower()
    for cid, kws in CRISIS_KEYWORDS.items():
        if any(k in t for k in kws):
            return cid
    return None


# ── LÓGICA DE AUTO-CREACIÓN ─────────────────────────────────────────────────

UMBRAL_MENCIONES = 3   # cuántas veces debe aparecer el evento
UMBRAL_FUENTES   = 2   # en cuántas fuentes distintas (mínimo)
CADUCIDAD_DIAS   = 14  # descartar candidatos más viejos


def limpiar_pendientes_caducados(pendientes):
    limite = (datetime.now() - timedelta(days=CADUCIDAD_DIAS)).isoformat()
    return [p for p in pendientes if p.get("fecha", "9999") >= limite[:10]]


def registrar_candidato(titulo, fuente, url, pendientes, ids_existentes):
    """
    Registra o incrementa un candidato de nueva crisis.
    Retorna el candidato si alcanza el umbral, o None.
    """
    for p in pendientes:
        if similitud(titulo, p["titulo_base"]) > 0.42:
            if fuente not in p["fuentes"]:
                p["fuentes"].append(fuente)
            p["menciones"] += 1
            if url not in p["urls"]:
                p["urls"].append(url)
                p["titulos"].append(titulo)
            if p["menciones"] >= UMBRAL_MENCIONES and len(p["fuentes"]) >= UMBRAL_FUENTES:
                return p
            return None

    paises = detectar_paises_en_texto(titulo)
    if not paises:
        return None  # sin país reconocido no puede ser crisis geopolítica

    id_tent = slugify(titulo)

    # Evitar duplicados con crisis ya existentes
    if id_tent in ids_existentes:
        return None

    pendientes.append({
        "id_tentativo": id_tent,
        "titulo_base":  titulo,
        "tipo":         inferir_tipo(titulo),
        "titulos":      [titulo],
        "fuentes":      [fuente],
        "urls":         [url],
        "paises":       [{"nombre": p["nombre"], "lat": p["lat"], "lng": p["lng"]} for p in paises],
        "fecha":        date.today().isoformat(),
        "menciones":    1,
    })
    return None


def promover_candidato(cand, db):
    """Convierte un candidato en una nueva crisis y la añade a datos.json."""
    titulo  = max(cand["titulos"], key=len)
    tipo    = cand["tipo"]
    paises  = cand["paises"]

    if not paises:
        print(f"  ⏭️  Candidato sin país reconocido, omitido: {titulo[:60]}")
        return None

    lat      = paises[0]["lat"]
    lng      = paises[0]["lng"]
    location = paises[0]["nombre"]
    actors   = list({p["nombre"] for p in paises[:3]})

    severidad = inferir_severidad(titulo, cand["menciones"])
    n_fuentes = len(cand["fuentes"])

    nueva_crisis = {
        "id":       cand["id_tentativo"],
        "type":     tipo,
        "severity": severidad,
        "title":    titulo,
        "location": location,
        "lat":      lat,
        "lng":      lng,
        "actors":   actors,
        "summary":  (
            f"Crisis detectada automáticamente: {cand['menciones']} menciones "
            f"en {n_fuentes} fuentes independientes. "
            f"Primera detección: {cand['fecha']}."
        ),
        "timeline": [
            {
                "when":   cand["fecha"],
                "what":   t,
                "source": cand["fuentes"][min(i, n_fuentes - 1)],
                "url":    cand["urls"][min(i, len(cand["urls"]) - 1)],
            }
            for i, t in enumerate(cand["titulos"][:12])
        ],
    }

    db["crisis"].append(nueva_crisis)
    print(f"  🆕 NUEVA CRISIS CREADA [{tipo.upper()} SEV{severidad}]: {titulo[:70]}...")
    alerta_nueva_crisis(nueva_crisis)
    tweet_nueva_crisis(nueva_crisis)
    return nueva_crisis


# ── SCRAPING HTML ────────────────────────────────────────────────────────────

def scraping_fuente(nombre, cfg):
    """
    Descarga una página HTML y extrae titulares + enlaces.
    Retorna lista de {'titulo': str, 'url': str}.
    """
    resultados = []
    try:
        resp = requests.get(cfg["url"], headers=HEADERS_HTTP, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"  ⚠️  Scraping {nombre} falló: {e}")
        return resultados

    items = []
    for sel in cfg["selectores_item"]:
        items = soup.select(sel)
        if items:
            break

    if not items:
        # Fallback: intentar extraer todos los <h3> y <h2> con enlaces
        items = soup.select("h3, h2")

    base = cfg.get("base_url", "")
    vistos = set()

    for item in items[:15]:
        enlace_tag = None
        for sel in cfg["selectores_titulo"]:
            enlace_tag = item.select_one(sel)
            if enlace_tag:
                break
        if not enlace_tag:
            enlace_tag = item.find("a")
        if not enlace_tag:
            continue

        titulo = enlace_tag.get_text(strip=True)
        href   = enlace_tag.get("href", "")
        if not titulo or not href or titulo in vistos:
            continue
        vistos.add(titulo)

        if href.startswith("/"):
            href = base + href
        elif not href.startswith("http"):
            continue

        resultados.append({"titulo": titulo, "url": href})

    print(f"  🌐 Scraping {nombre}: {len(resultados)} titulares extraídos")
    return resultados


# ── MAIN ─────────────────────────────────────────────────────────────────────

def ejecutar_actualizacion():
    print("🚀 Iniciando Actualizador Geopolítico (RSS + scraping + auto-crisis)...")
    db          = cargar_db()
    pendientes  = cargar_pendientes()
    pendientes  = limpiar_pendientes_caducados(pendientes)
    historial   = cargar_historial()

    # Snapshot de severidades antes de procesar (para detectar escaladas)
    sev_antes = {id_crisis(c): c.get("severity", 1) for c in db["crisis"]}

    # URLs ya vistas (para no duplicar)
    urls_vistas = set()
    for c in db["crisis"]:
        for act in c.get("timeline", c.get("actualizaciones", [])):
            urls_vistas.add(act.get("url", ""))
    urls_vistas.update(r.get("url", "") for r in db["relaciones"])

    ids_existentes = {id_crisis(c) for c in db["crisis"]}
    ids_promovidos = set()

    nuevas = 0
    hoy    = date.today().isoformat()

    # ── 1. RSS ───────────────────────────────────────────────────────────────
    for rss_url in FUENTES_RSS:
        print(f"\n📡 Escaneando: {rss_url}")
        try:
            feed = feedparser.parse(rss_url)
        except Exception as e:
            print(f"  ⚠️  Error RSS: {e}")
            continue

        nombre_fuente = getattr(feed.feed, "title", "Internacional")

        for entrada in feed.entries[:8]:
            enlace = getattr(entrada, "link", "")
            titulo = getattr(entrada, "title", "")
            if not titulo or enlace in urls_vistas:
                continue

            print(f"  ✎ {titulo[:58]}...")
            nivel   = inferir_nivel(titulo)
            tl_item = {"when": hoy, "what": titulo, "source": nombre_fuente, "url": enlace}

            bilateral, paises = es_bilateral(titulo)
            if bilateral and len(paises) >= 2:
                origen, destino = paises[0], paises[1]
                db["relaciones"].append({
                    "id_relacion": f"rel-auto-{int(time.time())}",
                    "origen":  {"nombre": origen["nombre"],  "lat": origen["lat"],  "lng": origen["lng"]},
                    "destino": {"nombre": destino["nombre"], "lat": destino["lat"], "lng": destino["lng"]},
                    "tipo":    "diplomática",
                    "nivel":   nivel,
                    "fecha":   hoy,
                    "titular": titulo,
                    "fuente":  nombre_fuente,
                    "url":     enlace,
                })
                print(f"     ⚡ Relación: {origen['nombre']} ↔ {destino['nombre']} [{nivel}]")
                nuevas += 1
            else:
                crisis_id = clasificar_crisis(titulo)
                if crisis_id:
                    for c in db["crisis"]:
                        if id_crisis(c) == crisis_id:
                            tl = c.setdefault("timeline", c.pop("actualizaciones", []))
                            tl.insert(0, tl_item)
                            c["timeline"] = tl[:20]
                            print(f"     📎 → crisis existente: {crisis_id}")
                            nuevas += 1
                            break
                else:
                    # Candidato a nueva crisis
                    promovido = registrar_candidato(
                        titulo, nombre_fuente, enlace, pendientes, ids_existentes | ids_promovidos
                    )
                    if promovido and promovido["id_tentativo"] not in ids_promovidos:
                        promover_candidato(promovido, db)
                        ids_promovidos.add(promovido["id_tentativo"])
                        pendientes.remove(promovido)
                        nuevas += 1

            urls_vistas.add(enlace)
            time.sleep(0.3)

    # ── 2. SCRAPING HTML ─────────────────────────────────────────────────────
    print("\n\n🔍 Iniciando scraping HTML de fuentes especializadas...")
    for nombre_src, cfg in FUENTES_SCRAPING.items():
        items_scraping = scraping_fuente(nombre_src, cfg)
        tipo_hint = cfg.get("tipo_hint", "diplo")

        for item in items_scraping:
            titulo = item["titulo"]
            enlace = item["url"]
            if not titulo or enlace in urls_vistas:
                continue

            print(f"  ✎ [{nombre_src}] {titulo[:58]}...")
            tl_item = {"when": hoy, "what": titulo, "source": nombre_src, "url": enlace}

            crisis_id = clasificar_crisis(titulo)
            if crisis_id:
                for c in db["crisis"]:
                    if id_crisis(c) == crisis_id:
                        tl = c.setdefault("timeline", c.pop("actualizaciones", []))
                        tl.insert(0, tl_item)
                        c["timeline"] = tl[:20]
                        print(f"     📎 → crisis existente: {crisis_id}")
                        nuevas += 1
                        break
            else:
                promovido = registrar_candidato(
                    titulo, nombre_src, enlace, pendientes, ids_existentes | ids_promovidos
                )
                if promovido and promovido["id_tentativo"] not in ids_promovidos:
                    # Respetar tipo_hint del scraper si no hay señal clara
                    if promovido["tipo"] == "diplo":
                        promovido["tipo"] = tipo_hint
                    promover_candidato(promovido, db)
                    ids_promovidos.add(promovido["id_tentativo"])
                    pendientes.remove(promovido)
                    nuevas += 1

            urls_vistas.add(enlace)
            time.sleep(0.4)

    # ── 3. HISTORIAL DE SEVERIDAD + ALERTAS DE ESCALADA ─────────────────────
    for c in db["crisis"]:
        cid     = id_crisis(c)
        sev_act = c.get("severity", 1)
        sev_ant = sev_antes.get(cid, sev_act)
        registrar_severidad(historial, cid, sev_act)
        if sev_act > sev_ant:
            print(f"  ⬆️  Escalada [{cid}]: {sev_ant} → {sev_act}")
            alerta_escalada(c, sev_ant, sev_act)
            tweet_escalada(c, sev_ant, sev_act)

    # Alerta para relaciones bilaterales rojas nuevas
    for r in db["relaciones"]:
        if r.get("nivel") == "rojo" and r.get("url", "") not in urls_vistas:
            alerta_relacion_bilateral(
                r.get("origen", {}).get("nombre", "?"),
                r.get("destino", {}).get("nombre", "?"),
                "rojo",
                r.get("titular", ""),
            )
            tweet_tension_bilateral(
                r.get("origen", {}).get("nombre", "?"),
                r.get("destino", {}).get("nombre", "?"),
                r.get("titular", ""),
            )

    guardar_historial(historial)

    # ── 4. PERSISTIR ─────────────────────────────────────────────────────────
    guardar_pendientes(pendientes)

    if nuevas > 0:
        guardar_db(db)
        print(f"\n🎉 {nuevas} eventos añadidos/actualizados en datos.json")
        if ids_promovidos:
            print(f"   🆕 Nuevas crisis auto-creadas: {len(ids_promovidos)}")
            for cid in ids_promovidos:
                print(f"      · {cid}")
    else:
        print("\n🤷  Sin novedades.")

    pendientes_count = len(pendientes)
    if pendientes_count:
        print(f"\n📋 {pendientes_count} candidatos en seguimiento (pendientes.json):")
        for p in sorted(pendientes, key=lambda x: -x["menciones"])[:5]:
            print(f"   [{p['menciones']}× / {len(p['fuentes'])} fuentes] {p['titulo_base'][:60]}")


if __name__ == "__main__":
    ejecutar_actualizacion()
