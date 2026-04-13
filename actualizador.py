import feedparser
import google.generativeai as genai
import json
import os
import time
from dotenv import load_dotenv  # <-- LIBRERÍA DE SEGURIDAD AÑADIDA

# --- CONFIGURACIÓN DE SEGURIDAD ---
load_dotenv()  # Esto busca y lee el archivo oculto .env
CLAVE_API = os.getenv("GEMINI_API_KEY")

# Pequeña comprobación para evitar sustos
if not CLAVE_API:
    print("🚨 ERROR CRÍTICO: No se encontró la GEMINI_API_KEY en el archivo .env")
    print("Por favor, asegúrate de haber creado el archivo .env correctamente.")
    exit(1)

genai.configure(api_key=CLAVE_API)
modelo_ia = genai.GenerativeModel('gemini-1.5-flash')
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
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def guardar_base_datos(datos):
    with open(ARCHIVO_DATOS, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Base de datos guardada exitosamente.")

def analizar_crisis_con_ia(titulo_noticia, lista_crisis_actuales):
    contexto_crisis = ", ".join([f"ID: '{c['id_crisis']}' ({c['titulo_principal']})" for c in lista_crisis_actuales])
    
    prompt = f"""
    Eres un analista geopolítico. Tienes una base de datos con estas crisis activas: [{contexto_crisis}]
    
    Analiza esta nueva noticia: "{titulo_noticia}"
    
    ¿Pertenece esta noticia a alguna de las crisis activas? 
    - Si SÍ pertenece, usa el 'id_crisis' correspondiente.
    - Si NO pertenece (es un nuevo conflicto/tensión), inventa un nuevo 'id_crisis' (ej. 'crisis-diplomatica-peru') y un 'titulo_principal'.
    
    Responde ÚNICAMENTE en JSON puro con esta estructura:
    {{
        "es_nueva_crisis": true/false,
        "id_crisis": "slug-de-la-crisis",
        "titulo_principal": "Título General del Conflicto (Solo si es_nueva_crisis es true)",
        "titular_traducido": "Traducción al español de la noticia específica",
        "nivel_actual": "rojo/naranja/amarillo",
        "lat": latitud_decimal (Solo si es_nueva_crisis es true),
        "lng": longitud_decimal (Solo si es_nueva_crisis es true)
    }}
    """
    try:
        respuesta = modelo_ia.generate_content(prompt)
        texto_limpio = respuesta.text.replace("```json", "").replace("```", "").strip()
        return json.loads(texto_limpio)
    except Exception as e:
        print(f"  ❌ Error IA: {e}")
        return None

def ejecutar_actualizacion():
    print("🚀 Iniciando el Actualizador Geopolítico Avanzado...")
    crisis_db = cargar_base_datos()
    
    urls_guardadas = []
    for c in crisis_db:
        for act in c.get("actualizaciones", []):
            urls_guardadas.append(act.get("url"))
            
    nuevas_añadidas = 0

    for url in Fuentes_RSS:
        print(f"\n📡 Escaneando: {url}")
        feed = feedparser.parse(url)
        
        for entrada in feed.entries[:3]:
            enlace = entrada.link
            if enlace in urls_guardadas:
                continue
                
            print(f"  🧠 Analizando: {entrada.title[:40]}...")
            analisis = analizar_crisis_con_ia(entrada.title, crisis_db)
            
            if analisis:
                nueva_actualizacion = {
                    "fecha": time.strftime('%Y-%m-%d'),
                    "titular": analisis["titular_traducido"],
                    "fuente": feed.feed.title if hasattr(feed.feed, 'title') else "Internacional",
                    "url": enlace
                }

                if analisis["es_nueva_crisis"]:
                    print(f"     🔥 ¡NUEVA CRISIS DETECTADA!: {analisis['titulo_principal']}")
                    nueva_crisis = {
                        "id_crisis": analisis["id_crisis"],
                        "titulo_principal": analisis["titulo_principal"],
                        "lat": analisis["lat"],
                        "lng": analisis["lng"],
                        "nivel_actual": analisis["nivel_actual"],
                        "actualizaciones": [nueva_actualizacion]
                    }
                    crisis_db.append(nueva_crisis)
                else:
                    print(f"     📎 Añadiendo a hilo existente: {analisis['id_crisis']}")
                    for c in crisis_db:
                        if c["id_crisis"] == analisis["id_crisis"]:
                            c["actualizaciones"].insert(0, nueva_actualizacion)
                            c["nivel_actual"] = analisis["nivel_actual"]
                            break
                            
                urls_guardadas.append(enlace)
                nuevas_añadidas += 1
                time.sleep(2)

    if nuevas_añadidas > 0:
        guardar_base_datos(crisis_db)
        print(f"🎉 Éxito: {nuevas_añadidas} nuevos eventos añadidos.")
    else:
        print("🤷‍♂️ Sin novedades internacionales.")

if __name__ == "__main__":
    ejecutar_actualizacion()