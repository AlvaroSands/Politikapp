from contextlib import asynccontextmanager
from datetime import datetime, date
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from apscheduler.schedulers.background import BackgroundScheduler
from actualizador import ejecutar_actualizacion
from notificaciones import briefing_diario, agregar_suscriptor, eliminar_suscriptor, enviar_a
import uvicorn
import json
import os
import logging
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

TYPE_ES = {
    "armed": "Conflicto armado",
    "diplo": "Crisis diplomática",
    "econ":  "Tensión económica",
    "cyber": "Ciberataque",
    "intel": "Operación de inteligencia",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        ejecutar_actualizacion, "interval", hours=3, id="actualizador",
        next_run_time=datetime.now()
    )
    scheduler.add_job(
        briefing_diario, "cron", hour=6, minute=0, id="briefing",
    )
    scheduler.start()
    logger.info("Scheduler iniciado — actualizador RSS ahora y cada 3 horas · briefing diario 6:00 UTC")
    # Registrar webhook de Telegram
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if token:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/setWebhook",
                json={"url": "https://geopolitikapp.com/webhook/telegram"},
                timeout=10,
            )
            logger.info(f"Telegram webhook: {r.json()}")
        except Exception as e:
            logger.warning(f"No se pudo registrar webhook Telegram: {e}")
    yield
    scheduler.shutdown()


app = FastAPI(title="Intel-Geo Command Center", lifespan=lifespan)


def _leer_datos():
    try:
        with open("datos.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"crisis": [], "relaciones": []}


def _inyectar_seo(html: str) -> str:
    """Inyecta JSON-LD dinámico con los datos actuales antes de </head>."""
    datos = _leer_datos()
    crisis = datos.get("crisis", [])

    # ItemList de crisis activas para Google
    item_list = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "Crisis geopolíticas activas",
        "description": "Listado de conflictos y crisis geopolíticas activas en el mundo, actualizadas en tiempo real.",
        "numberOfItems": len(crisis),
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": c.get("title", ""),
                "description": (
                    f"{TYPE_ES.get(c.get('type',''), c.get('type',''))} en {c.get('location', '')}. "
                    f"Severidad {c.get('severity', 1)}/5. "
                    f"{c.get('summary', '')[:150]}"
                ),
                "url": f"https://geopolitikapp.com/#crisis-{c.get('id', '')}",
                "areaServed": c.get("location", ""),
            }
            for i, c in enumerate(
                sorted(crisis, key=lambda x: -x.get("severity", 0))[:20]
            )
        ],
    }

    ld_tag = f'\n<script type="application/ld+json">\n{json.dumps(item_list, ensure_ascii=False, indent=2)}\n</script>\n'

    # noscript con resumen legible para crawlers sin JS
    noscript_items = "".join(
        f"<li><strong>{c.get('title','')}</strong> — {c.get('location','')} "
        f"({TYPE_ES.get(c.get('type',''), '')}, severidad {c.get('severity',1)}/5)</li>"
        for c in sorted(crisis, key=lambda x: -x.get("severity", 0))[:10]
    )
    noscript = (
        f'<noscript><div style="position:absolute;left:-9999px" aria-hidden="true">'
        f'<h1>Monitor Geopolítico Mundial — Crisis Activas</h1><ul>{noscript_items}</ul>'
        f'</div></noscript>\n'
    )

    return html.replace("</head>", ld_tag + "</head>", 1).replace(
        "<body>", "<body>\n" + noscript, 1
    )


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
        html = f.read()
    return _inyectar_seo(html)


@app.get("/analisis", response_class=HTMLResponse)
async def pagina_analisis():
    with open("analisis.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/sitemap.xml")
async def sitemap():
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


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
    except Exception:
        return {"ok": True}
    message = data.get("message", {})
    text = (message.get("text") or "").strip()
    chat_id = message.get("chat", {}).get("id")
    if not chat_id:
        return {"ok": True}
    if text.startswith("/start"):
        es_nuevo = agregar_suscriptor(chat_id)
        if es_nuevo:
            enviar_a(
                "👋 <b>Bienvenido a Geopolitikapp</b>\n\n"
                "A partir de ahora recibirás alertas en tiempo real:\n\n"
                "🔴 Nuevas crisis detectadas\n"
                "⬆️ Escaladas de conflictos\n"
                "🔴 Tensiones bilaterales críticas\n"
                "🌍 Briefing diario a las 8:00h\n\n"
                "Para darte de baja: /stop\n"
                "🌐 geopolitikapp.com",
                chat_id,
            )
        else:
            enviar_a("✅ Ya estás suscrito a las alertas de Geopolitikapp.\n🌐 geopolitikapp.com", chat_id)
    elif text.startswith("/stop"):
        eliminar_suscriptor(chat_id)
        enviar_a(
            "👋 Te has dado de baja de las alertas de Geopolitikapp.\n"
            "Para volver a suscribirte: /start",
            chat_id,
        )
    return {"ok": True}


if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=puerto)
