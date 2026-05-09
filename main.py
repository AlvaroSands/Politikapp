from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from apscheduler.schedulers.background import BackgroundScheduler
from actualizador import ejecutar_actualizacion
import uvicorn
import json
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        ejecutar_actualizacion, "interval", hours=3, id="actualizador",
        next_run_time=datetime.now()
    )
    scheduler.start()
    logger.info("Scheduler iniciado — actualizador RSS ahora y cada 3 horas")
    yield
    scheduler.shutdown()


app = FastAPI(title="Intel-Geo Command Center", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/datos.json")
async def api_datos():
    try:
        with open("datos.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error leyendo datos.json: {e}")
        return JSONResponse(status_code=500, content={"error": "No se pudo leer la base de datos"})


@app.get("/historial.json")
async def api_historial():
    try:
        with open("historial_severidad.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


@app.get("/", response_class=HTMLResponse)
async def pagina_principal():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/analisis", response_class=HTMLResponse)
async def pagina_analisis():
    with open("analisis.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/sitemap.xml")
async def sitemap():
    from datetime import date
    hoy = date.today().isoformat()
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://geopolitikapp.com/</loc>
    <lastmod>{hoy}</lastmod>
    <changefreq>hourly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://geopolitikapp.com/analisis</loc>
    <lastmod>{hoy}</lastmod>
    <changefreq>hourly</changefreq>
    <priority>0.8</priority>
  </url>
</urlset>"""
    return Response(content=xml, media_type="application/xml")


@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots():
    return """User-agent: *
Allow: /
Allow: /analisis

Sitemap: https://geopolitikapp.com/sitemap.xml
"""


if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=puerto)
