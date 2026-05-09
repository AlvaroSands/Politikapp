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
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.france24.com/es/rss",
    "https://elpais.com/rss/internacional/el-pais.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://feeds.reuters.com/reuters/worldNews",
    "https://foreignpolicy.com/feed/",
    "https://theeconomist.com/sections/world-politics/rss.xml",
    "https://www.elmundo.es/rss/internacional.xml",
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
    "conflicto-mar-rojo-huties":["houthi", "huti", "hutí", "red sea", "mar rojo", "yemen"],
    "crisis-energetica-europa": ["energy", "energía", "gas", "oil", "petróleo", "europa", "europe"],
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

        for entrada in feed.entries[:5]:
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
                id_crisis = clasificar_crisis(titulo)
                nueva_act = {"fecha": hoy, "titular": titulo, "fuente": nombre_fuente, "url": enlace}

                if id_crisis:
                    nueva_tl = {"when": hoy, "what": titulo, "source": nombre_fuente, "url": enlace}
                    for c in db["crisis"]:
                        if id_crisis(c) == id_crisis:
                            timeline = c.setdefault("timeline", c.pop("actualizaciones", []))
                            timeline.insert(0, nueva_tl)
                            c["timeline"] = timeline[:20]
                            print(f"     📎 Actualiza crisis: {id_crisis}")
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
