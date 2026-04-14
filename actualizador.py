import feedparser
import google.generativeai as genai
import json
import os
import time
from dotenv import load_dotenv

# --- CONFIGURACIÓN ---
load_dotenv()
CLAVE_API = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=CLAVE_API)
modelo_ia = genai.GenerativeModel('gemini-2.5-flash')
ARCHIVO_DATOS = "datos.json"

Fuentes_RSS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",                  
    "https://www.aljazeera.com/xml/rss/all.xml",                    
    "https://www.france24.com/es/rss",                              
    "https://elpais.com/rss/internacional/el-pais.xml"            
]

def cargar_base_datos():
    if os.path.exists(ARCHIVO_DATOS):
        with open(ARCHIVO_DATOS, "r", encoding="utf-8") as f:
            try:
                datos = json.load(f)
                # Asegurar la nueva estructura si el archivo es antiguo
                if isinstance(datos, list): 
                    return {"crisis": datos, "relaciones": []}
                return datos
            except json.JSONDecodeError:
                pass
    return {"crisis": [], "relaciones": []}

def guardar_base_datos(datos):
    with open(ARCHIVO_DATOS, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)

def analizar_con_ia_avanzada(titulo_noticia, db_actual):
    contexto = ", ".join([f"ID: '{c['id_crisis']}'" for c in db_actual["crisis"]])
    
    prompt = f"""
    Analiza esta noticia geopolítica: "{titulo_noticia}"
    
    Determina si describe una "Tensión Bilateral" directa entre dos países específicos (ej. sanciones mutuas, retirada de embajadores, amenazas directas de un país a otro).
    
    Responde ÚNICAMENTE en JSON puro con esta estructura:
    {{
        "es_relacion_bilateral": true/false,
        
        "datos_relacion": {{
            "origen": {{"nombre": "País A", "lat": 0.0, "lng": 0.0}},
            "destino": {{"nombre": "País B", "lat": 0.0, "lng": 0.0}},
            "tipo": "diplomatica/comercial/militar",
            "nivel": "rojo/naranja/amarillo",
            "titular_traducido": "Traducción de la noticia"
        }},
        
        "datos_crisis": {{
            "es_nueva_crisis": true/false,
            "id_crisis": "id-existente-o-nuevo",
            "titulo_principal": "Título si es nueva",
            "nivel_actual": "rojo/naranja/amarillo",
            "lat": 0.0, "lng": 0.0,
            "titular_traducido": "Traducción de la noticia"
        }}
    }}
    Nota: Si es_relacion_bilateral es true, ignora datos_crisis. Si es false, ignora datos_relacion y revisa si pertenece a alguna de estas crisis actuales: [{contexto}].
    """
    try:
        respuesta = modelo_ia.generate_content(prompt)
        texto = respuesta.text.replace("```json", "").replace("```", "").strip()
        return json.loads(texto)
    except Exception as e:
        print(f"  ❌ Error IA: {e}")
        return None

def ejecutar_actualizacion():
    print("🚀 Iniciando Motor Analítico V2 (Puntos y Relaciones)...")
    db = cargar_base_datos()
    
    # Extraer URLs guardadas para no repetir
    urls_guardadas = [act.get("url") for c in db["crisis"] for act in c.get("actualizaciones", [])]
    urls_guardadas += [r.get("url") for r in db["relaciones"]]
            
    nuevas = 0

    for url in Fuentes_RSS:
        print(f"\n📡 Escaneando: {url}")
        feed = feedparser.parse(url)
        
        for entrada in feed.entries[:3]:
            enlace = entrada.link
            if enlace in urls_guardadas: continue
                
            print(f"  🧠 Analizando: {entrada.title[:40]}...")
            analisis = analizar_con_ia_avanzada(entrada.title, db)
            
            if not analisis: continue

            fuente = feed.feed.title if hasattr(feed.feed, 'title') else "Internacional"
            fecha_hoy = time.strftime('%Y-%m-%d')

            if analisis.get("es_relacion_bilateral"):
                print("     ⚡ ¡NUEVA LÍNEA DE TENSIÓN DETECTADA!")
                rel = analisis["datos_relacion"]
                db["relaciones"].append({
                    "id_relacion": f"rel-{int(time.time())}",
                    "origen": rel["origen"],
                    "destino": rel["destino"],
                    "tipo": rel["tipo"],
                    "nivel": rel["nivel"],
                    "fecha": fecha_hoy,
                    "titular": rel["titular_traducido"],
                    "fuente": fuente,
                    "url": enlace
                })
                nuevas += 1
            else:
                cri = analisis["datos_crisis"]
                nueva_act = {"fecha": fecha_hoy, "titular": cri["titular_traducido"], "fuente": fuente, "url": enlace}
                
                if cri["es_nueva_crisis"]:
                    print(f"     🔥 Nueva crisis puntual: {cri['titulo_principal']}")
                    db["crisis"].append({
                        "id_crisis": cri["id_crisis"], "titulo_principal": cri["titulo_principal"],
                        "lat": cri["lat"], "lng": cri["lng"], "nivel_actual": cri["nivel_actual"],
                        "actualizaciones": [nueva_act]
                    })
                else:
                    print(f"     📎 Actualizando crisis: {cri['id_crisis']}")
                    for c in db["crisis"]:
                        if c["id_crisis"] == cri["id_crisis"]:
                            c["actualizaciones"].insert(0, nueva_act)
                            break
                nuevas += 1
                
            urls_guardadas.append(enlace)
            time.sleep(2)

    if nuevas > 0:
        guardar_base_datos(db)
        print(f"🎉 Éxito: {nuevas} nuevos eventos/relaciones añadidos.")
    else:
        print("🤷‍♂️ Sin novedades.")

if __name__ == "__main__":
    ejecutar_actualizacion()