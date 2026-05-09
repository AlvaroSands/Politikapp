"""
Actualizador geopolítico sin dependencias de IA externa.
Clasificación por palabras clave + coordenadas de países conocidos.
Ejecutar manualmente o programar con cron.
"""
import feedparser
import json
import os
import re
import time
from datetime import date

ARCHIVO_DATOS = "datos.json"

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
    # Anglófonas — especializadas geopolítica/defensa
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
    # Alemanas / Europeas
    "https://www.dw.com/en/rss/rss.xml",
    "https://www.dw.com/de/rss/rss.xml",
    "https://www.politico.eu/feed/",
    "https://euobserver.com/rss.xml",
    "https://www.euractiv.com/sections/global-europe/feed/",
    # Radio pública / think tanks extra
    "https://feeds.npr.org/1004/rss.xml",
    "https://www.wilsoncenter.org/rss.xml",
    "https://carnegieendowment.org/rss/solr/articles",
    # Ucrania / Rusia / Europa del Este
    "https://www.kyivpost.com/rss",
    "https://www.ukrinform.net/rss/block-ato",
    "https://meduza.io/rss/all",
    # Seguridad / Ciberdefensa
    "https://www.securityweek.com/feed",
    "https://krebsonsecurity.com/feed/",
    "https://feeds.feedburner.com/TheHackersNews",
]

# Coordenadas de países frecuentes
PAISES = {
    "ukraine": {"nombre": "Ucrania",  "lat": 48.38, "lng": 31.17},
    "russia":  {"nombre": "Rusia",    "lat": 55.76, "lng": 37.62},
    "rusia":   {"nombre": "Rusia",    "lat": 55.76, "lng": 37.62},
    "ucrania": {"nombre": "Ucrania",  "lat": 48.38, "lng": 31.17},
    "iran":    {"nombre": "Irán",     "lat": 35.69, "lng": 51.39},
    "irán":    {"nombre": "Irán",     "lat": 35.69, "lng": 51.39},
    "israel":  {"nombre": "Israel",   "lat": 31.77, "lng": 35.21},
    "gaza":    {"nombre": "Gaza",     "lat": 31.50, "lng": 34.47},
    "china":   {"nombre": "China",    "lat": 39.90, "lng": 116.41},
    "taiwan":  {"nombre": "Taiwán",   "lat": 23.70, "lng": 120.96},
    "taiwán":  {"nombre": "Taiwán",   "lat": 23.70, "lng": 120.96},
    "usa":     {"nombre": "EE.UU.",   "lat": 38.90, "lng": -77.04},
    "us ":     {"nombre": "EE.UU.",   "lat": 38.90, "lng": -77.04},
    "trump":   {"nombre": "EE.UU.",   "lat": 38.90, "lng": -77.04},
    "america": {"nombre": "EE.UU.",   "lat": 38.90, "lng": -77.04},
    "eeuu":    {"nombre": "EE.UU.",   "lat": 38.90, "lng": -77.04},
    "north korea": {"nombre": "Corea del Norte", "lat": 39.04, "lng": 125.76},
    "corea":   {"nombre": "Corea del Norte", "lat": 39.04, "lng": 125.76},
    "sudan":   {"nombre": "Sudán",    "lat": 15.55, "lng": 32.53},
    "sudán":   {"nombre": "Sudán",    "lat": 15.55, "lng": 32.53},
    "mali":    {"nombre": "Mali",     "lat": 17.57,  "lng": -3.99},
    "mali":    {"nombre": "Mali",     "lat": 17.57,  "lng": -3.99},
    "niger":   {"nombre": "Níger",    "lat": 17.61,  "lng": 8.08},
    "india":   {"nombre": "India",    "lat": 20.59,  "lng": 78.96},
    "pakistan":{"nombre": "Pakistán", "lat": 30.38,  "lng": 69.35},
    "venezuela":{"nombre":"Venezuela","lat": 10.48,  "lng": -66.90},
    "haiti":   {"nombre": "Haití",    "lat": 18.54,  "lng": -72.34},
    "ecuador": {"nombre": "Ecuador",  "lat": -2.20,  "lng": -79.89},
    "hungary": {"nombre": "Hungría",  "lat": 47.50,  "lng": 19.04},
    "hungría": {"nombre": "Hungría",  "lat": 47.50,  "lng": 19.04},
    "ethiopia": {"nombre": "Etiopía",  "lat": 9.02,   "lng": 38.75},
    "etiopía":  {"nombre": "Etiopía",  "lat": 9.02,   "lng": 38.75},
    "somalia":  {"nombre": "Somalia",  "lat": 2.05,   "lng": 45.34},
    "myanmar":  {"nombre": "Myanmar",  "lat": 19.74,  "lng": 96.08},
    "birmania": {"nombre": "Myanmar",  "lat": 19.74,  "lng": 96.08},
    "afghanistan":{"nombre":"Afganistán","lat":33.93, "lng": 67.71},
    "afganistán":{"nombre":"Afganistán","lat":33.93,  "lng": 67.71},
    "syria":    {"nombre": "Siria",    "lat": 34.80,  "lng": 38.99},
    "siria":    {"nombre": "Siria",    "lat": 34.80,  "lng": 38.99},
    "lebanon":  {"nombre": "Líbano",   "lat": 33.85,  "lng": 35.86},
    "líbano":   {"nombre": "Líbano",   "lat": 33.85,  "lng": 35.86},
    "houthi":   {"nombre": "Yemen",    "lat": 15.55,  "lng": 48.52},
    "yemen":    {"nombre": "Yemen",    "lat": 15.55,  "lng": 48.52},
    "saudi":    {"nombre": "Arabia Saudí","lat":23.89,"lng": 45.08},
    "arabia":   {"nombre": "Arabia Saudí","lat":23.89,"lng": 45.08},
    "turkey":   {"nombre": "Turquía",  "lat": 38.96,  "lng": 35.24},
    "turquía":  {"nombre": "Turquía",  "lat": 38.96,  "lng": 35.24},
    "erdogan":  {"nombre": "Turquía",  "lat": 38.96,  "lng": 35.24},
    "poland":   {"nombre": "Polonia",  "lat": 51.92,  "lng": 19.15},
    "polonia":  {"nombre": "Polonia",  "lat": 51.92,  "lng": 19.15},
    "finland":  {"nombre": "Finlandia","lat": 64.96,  "lng": 25.75},
    "sweden":   {"nombre": "Suecia",   "lat": 60.13,  "lng": 18.64},
    "baltic":   {"nombre": "Bálticos", "lat": 56.88,  "lng": 24.60},
    "congo":    {"nombre": "Congo",    "lat": -4.03,  "lng": 21.76},
    "drc":      {"nombre": "Congo",    "lat": -4.03,  "lng": 21.76},
    "colombia": {"nombre": "Colombia", "lat": 4.57,   "lng": -74.30},
    "mexico":   {"nombre": "México",   "lat": 23.63,  "lng": -102.55},
    "méxico":   {"nombre": "México",   "lat": 23.63,  "lng": -102.55},
    "brazil":   {"nombre": "Brasil",   "lat": -14.24, "lng": -51.93},
    "brasil":   {"nombre": "Brasil",   "lat": -14.24, "lng": -51.93},
    "argentina":{"nombre":"Argentina", "lat": -38.42, "lng": -63.62},
    "japan":    {"nombre": "Japón",    "lat": 36.20,  "lng": 138.25},
    "japón":    {"nombre": "Japón",    "lat": 36.20,  "lng": 138.25},
    "south korea":{"nombre":"Corea del Sur","lat":35.91,"lng":127.77},
    "philippines":{"nombre":"Filipinas","lat":12.88,  "lng":121.77},
    "filipinas":{"nombre": "Filipinas","lat": 12.88,  "lng":121.77},
    "indonesia":{"nombre":"Indonesia", "lat": -0.79,  "lng":113.92},
    "vietnam":  {"nombre": "Vietnam",  "lat": 14.06,  "lng":108.28},
    "nigeria":  {"nombre": "Nigeria",  "lat": 9.08,   "lng": 8.68},
    "egypt":    {"nombre": "Egipto",   "lat": 26.82,  "lng": 30.80},
    "egipto":   {"nombre": "Egipto",   "lat": 26.82,  "lng": 30.80},
    "libya":    {"nombre": "Libia",    "lat": 26.34,  "lng": 17.23},
    "libia":    {"nombre": "Libia",    "lat": 26.34,  "lng": 17.23},
    "morocco":  {"nombre": "Marruecos","lat": 31.79,  "lng": -7.09},
    "marruecos":{"nombre":"Marruecos", "lat": 31.79,  "lng": -7.09},
    "serbia":   {"nombre": "Serbia",   "lat": 44.02,  "lng": 21.01},
    "kosovo":   {"nombre": "Kosovo",   "lat": 42.60,  "lng": 20.90},
    "georgia":  {"nombre": "Georgia",  "lat": 42.31,  "lng": 43.36},
    "armenia":  {"nombre": "Armenia",  "lat": 40.07,  "lng": 45.04},
    "azerbaijan":{"nombre":"Azerbaiyán","lat":40.14,  "lng": 47.58},
}

# Patrones de relaciones bilaterales (pares de países en un titular)
PATRON_BILATERAL = re.compile(
    r'\b(ukraine|russia|iran|israel|china|taiwan|usa|north korea|india|pakistan|sudan|venezuela|eeuu|ucrania|rusia|irán|taiwán|sudán)\b',
    re.IGNORECASE
)

# Mapa de crisis a keywords para detectar a qué crisis existente pertenece una noticia
CRISIS_KEYWORDS = {
    "ucrania-este-2026":       ["ukraine", "ucrania", "russia", "rusia", "zelenski", "zelenskyy", "kiev", "kyiv", "kharkiv", "bakhmut", "donbas"],
    "iran-ormuz-2026":         ["iran", "irán", "ormuz", "hormuz", "hormuz", "strait", "persian gulf"],
    "oriente-medio-gaza":      ["gaza", "hamas", "west bank", "rafah", "cisjordania", "netanyahu", "idf"],
    "sudan-guerra-civil-2026": ["sudan", "sudán", "rsf", "jartum", "khartoum", "darfur"],
    "sahel-mali-yihadistas-2026": ["mali", "sahel", "jnim", "burkina", "niger", "niamey", "bamako", "aes"],
    "india-pakistan-sindoor-2026": ["india", "pakistan", "sindoor", "kashmir", "cachemira", "indus"],
    "corea-norte-misiles-2026": ["north korea", "corea", "pyongyang", "kim jong", "missile", "misil"],
    "tension-estrecho-taiwan":  ["taiwan", "taiwán", "strait", "estrecho", "pla"],
    "violencia-haiti":          ["haiti", "haití", "gang", "banda"],
    "conflicto-ecuador":        ["ecuador", "noboa", "crimen organizado"],
    "conflicto-mar-rojo-huties":["houthi", "huti", "hutí", "red sea", "mar rojo", "yemen", "bab el-mandeb"],
    "crisis-energetica-europa": ["energy", "energía", "gas", "oil", "petróleo", "europa", "europe", "lng", "pipeline"],
    "myanmar-golpe-guerra-civil":["myanmar", "birmania", "junta", "tatmadaw", "sac", "coup"],
    "sahel-burkina-niger":      ["burkina", "niamey", "bamako", "aes", "sahel", "jihadist", "yihadista", "wagner"],
    "armenia-azerbaiyan":       ["armenia", "azerbaiján", "azerbaiyán", "nagorno", "karabaj", "karabakh"],
    "taiwan-china-estrecho":    ["taiwan", "taiwán", "strait", "estrecho", "pla", "tsmc"],
    "africa-golfo-guinea":      ["nigeria", "bight of benin", "cameroon", "piracy", "gulf of guinea"],
    "crisis-diplomatica-unsc":  ["united nations", "naciones unidas", "security council", "consejo de seguridad", "veto", "unsc"],
    "ciber-ataques-estado":     ["cyberattack", "ciberataque", "ransomware", "hack", "espionage", "espionaje", "apt", "malware", "exploit"],
    "suramerica-crisis":        ["venezuela", "maduro", "colombia", "farc", "cartels", "cartel", "narco", "ecuador"],
}

# Palabras que indican tensión entre dos actores (para detectar relación bilateral)
KEYWORDS_BILATERAL = [
    "sanctions", "sanciones", "tariffs", "aranceles", "expel", "expulsa",
    "ambassador", "embajador", "threatens", "amenaza", "deploys", "despliega",
    "ceasefire", "alto el fuego", "agreement", "acuerdo", "tensions", "tensiones",
    "clash", "choque", "confrontation", "confrontación", "negotiations", "negociaciones"
]

# Niveles de alerta por keywords
KEYWORDS_ROJO    = ["war", "guerra", "attack", "ataque", "killed", "muertos", "strike", "ceasefire violation", "bombing", "bombardeo"]
KEYWORDS_NARANJA = ["tension", "tensión", "deploy", "threat", "amenaza", "sanctions", "sanciones", "military", "naval"]
KEYWORDS_AMARILLO= ["talks", "negotiations", "agreement", "diplomat", "summit", "cumbre", "trade", "comercio"]


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


def id_crisis(c):
    return c.get("id") or c.get("id_crisis", "")


def guardar_db(datos):
    with open(ARCHIVO_DATOS, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def inferir_nivel(texto):
    t = texto.lower()
    if any(k in t for k in KEYWORDS_ROJO):
        return "rojo"
    if any(k in t for k in KEYWORDS_NARANJA):
        return "naranja"
    return "amarillo"


def detectar_paises_en_texto(texto):
    t = texto.lower()
    encontrados = []
    for clave, datos in PAISES.items():
        if clave in t and datos not in encontrados:
            encontrados.append(datos)
    return encontrados


def es_bilateral(titulo):
    paises_encontrados = detectar_paises_en_texto(titulo)
    tiene_keyword = any(k in titulo.lower() for k in KEYWORDS_BILATERAL)
    return len(paises_encontrados) >= 2 and tiene_keyword, paises_encontrados


def clasificar_crisis(titulo):
    t = titulo.lower()
    for id_crisis, keywords in CRISIS_KEYWORDS.items():
        if any(k in t for k in keywords):
            return id_crisis
    return None


def ejecutar_actualizacion():
    print("🚀 Iniciando Actualizador Geopolítico (sin IA externa)...")
    db = cargar_db()

    urls_vistas = set()
    for c in db["crisis"]:
        for act in c.get("timeline", c.get("actualizaciones", [])):
            urls_vistas.add(act.get("url", ""))
    urls_vistas.update(r.get("url", "") for r in db["relaciones"])

    nuevas = 0
    hoy = date.today().isoformat()

    for rss_url in FUENTES_RSS:
        print(f"\n📡 Escaneando: {rss_url}")
        try:
            feed = feedparser.parse(rss_url)
        except Exception as e:
            print(f"  ⚠️  Error al leer feed: {e}")
            continue

        nombre_fuente = getattr(feed.feed, "title", "Internacional")

        for entrada in feed.entries[:8]:
            enlace = getattr(entrada, "link", "")
            titulo = getattr(entrada, "title", "")

            if not titulo or enlace in urls_vistas:
                continue

            print(f"  ✎ Analizando: {titulo[:55]}...")
            nivel = inferir_nivel(titulo)

            # ¿Es una relación bilateral?
            bilateral, paises = es_bilateral(titulo)
            if bilateral and len(paises) >= 2:
                origen, destino = paises[0], paises[1]
                db["relaciones"].append({
                    "id_relacion": f"rel-auto-{int(time.time())}",
                    "origen":  {"nombre": origen["nombre"], "lat": origen["lat"], "lng": origen["lng"]},
                    "destino": {"nombre": destino["nombre"], "lat": destino["lat"], "lng": destino["lng"]},
                    "tipo": "diplomática",
                    "nivel": nivel,
                    "fecha": hoy,
                    "titular": titulo,
                    "fuente": nombre_fuente,
                    "url": enlace
                })
                print(f"     ⚡ Relación: {origen['nombre']} ↔ {destino['nombre']} [{nivel}]")
                nuevas += 1
            else:
                # Intentar asignar a crisis existente
                crisis_id = clasificar_crisis(titulo)

                if crisis_id:
                    nueva_tl = {"when": hoy, "what": titulo, "source": nombre_fuente, "url": enlace}
                    for c in db["crisis"]:
                        if id_crisis(c) == crisis_id:
                            timeline = c.setdefault("timeline", c.pop("actualizaciones", []))
                            timeline.insert(0, nueva_tl)
                            c["timeline"] = timeline[:20]
                            print(f"     📎 Actualiza crisis: {crisis_id}")
                            nuevas += 1
                            break
                # Si no encaja en ninguna crisis conocida, ignorar (evita ruido)

            urls_vistas.add(enlace)
            time.sleep(0.5)

    if nuevas > 0:
        guardar_db(db)
        print(f"\n🎉 {nuevas} nuevos eventos añadidos a datos.json")
    else:
        print("\n🤷  Sin novedades en los feeds.")


if __name__ == "__main__":
    ejecutar_actualizacion()
