from contextlib import asynccontextmanager
from datetime import datetime, date, timezone
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from actualizador import ejecutar_actualizacion
from notificaciones import briefing_diario, agregar_suscriptor, eliminar_suscriptor, enviar_a
import uvicorn
import json
import os
import logging
import requests
from html import escape as _e

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="UTC")

BRIEFING_HORA_UTC = 6
BRIEFING_MARCA = "briefing_ultima_fecha.txt"


def _briefing_ya_enviado_hoy() -> bool:
    hoy = date.today().isoformat()
    try:
        with open(BRIEFING_MARCA, "r") as f:
            return f.read().strip() == hoy
    except Exception:
        return False


def _marcar_briefing_enviado():
    try:
        with open(BRIEFING_MARCA, "w") as f:
            f.write(date.today().isoformat())
    except Exception:
        pass


def _briefing_con_marca():
    briefing_diario()
    _marcar_briefing_enviado()


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
        _briefing_con_marca,
        CronTrigger(hour=BRIEFING_HORA_UTC, minute=0, timezone="UTC"),
        id="briefing",
    )
    scheduler.start()
    logger.info("Scheduler iniciado — actualizador RSS ahora y cada 3h · briefing diario 6:00 UTC")

    # Recovery: si el servidor arranca después de las 6:00 UTC y el briefing no se envió hoy, enviarlo
    ahora_utc = datetime.now(timezone.utc)
    if ahora_utc.hour >= BRIEFING_HORA_UTC and not _briefing_ya_enviado_hoy():
        logger.info("Briefing pendiente detectado al arrancar — enviando ahora")
        import threading
        threading.Thread(target=_briefing_con_marca, daemon=True).start()
    # Registrar webhook de Telegram
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if token:
        try:
            webhook_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
            payload = {"url": "https://geopolitikapp.com/webhook/telegram"}
            if webhook_secret:
                payload["secret_token"] = webhook_secret
            else:
                logger.warning("TELEGRAM_WEBHOOK_SECRET no configurado — el webhook no verificará el origen")
            r = requests.post(
                f"https://api.telegram.org/bot{token}/setWebhook",
                json=payload,
                timeout=10,
            )
            logger.info(f"Telegram webhook: {r.json()}")
        except Exception as e:
            logger.warning(f"No se pudo registrar webhook Telegram: {e}")
    yield
    scheduler.shutdown()


app = FastAPI(title="Intel-Geo Command Center", lifespan=lifespan)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response


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
        f"<li><strong>{_e(c.get('title',''))}</strong> — {_e(c.get('location',''))} "
        f"({_e(TYPE_ES.get(c.get('type',''), ''))}, severidad {c.get('severity',1)}/5)</li>"
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


def _crisis_page(crisis: dict) -> str:
    cid      = crisis.get("id", "")
    title    = crisis.get("title", "")
    location = crisis.get("location", "")
    tipo     = crisis.get("type", "diplo")
    tipo_es  = TYPE_ES.get(tipo, "Crisis")
    severity = int(crisis.get("severity", 1))
    summary  = crisis.get("summary", "")
    actors   = crisis.get("actors", [])
    timeline = crisis.get("timeline", [])[:12]
    hoy      = date.today().isoformat()

    colors = {
        "armed": "#e05050", "diplo": "#4aa3d9", "econ": "#d9a441",
        "cyber": "#b860d4", "intel": "#4ad48f",
    }
    color    = colors.get(tipo, "#8195a0")
    sev_str  = "■" * severity + "□" * (5 - severity)
    meta_desc = f"{tipo_es} en {location}. Severidad {severity}/5. {(summary or '')[:155]}"
    pub_date  = timeline[-1].get("when", hoy) if timeline else hoy
    mod_date  = timeline[0].get("when", hoy)  if timeline else hoy

    # JSON-LD usa json.dumps — no necesita escape HTML
    ld_article = {
        "@context": "https://schema.org", "@type": "NewsArticle",
        "headline": title,
        "description": meta_desc,
        "url": f"https://geopolitikapp.com/crisis/{cid}",
        "datePublished": pub_date, "dateModified": mod_date,
        "publisher": {"@type": "Organization", "name": "Geopolitikapp",
                      "url": "https://geopolitikapp.com"},
        "about": {"@type": "Event", "name": title,
                  "location": {"@type": "Place", "name": location}},
    }
    ld_breadcrumb = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Inicio",
             "item": "https://geopolitikapp.com/"},
            {"@type": "ListItem", "position": 2, "name": "Análisis Regional",
             "item": "https://geopolitikapp.com/analisis"},
            {"@type": "ListItem", "position": 3, "name": title,
             "item": f"https://geopolitikapp.com/crisis/{cid}"},
        ],
    }

    # Versiones escapadas para inserción directa en HTML
    e_title    = _e(title)
    e_location = _e(location)
    e_tipo_es  = _e(tipo_es)
    e_meta     = _e(meta_desc)
    e_cid      = _e(cid)
    e_summary  = _e(summary)

    actors_html = "".join(
        f'<span style="display:inline-block;padding:3px 8px;border:1px solid #233339;'
        f'font-size:10px;letter-spacing:.1em;margin:2px 3px 2px 0;color:#8195a0">{_e(a)}</span>'
        for a in actors
    )

    tl_items = ""
    for t in timeline:
        raw_url = t.get("url") or ""
        safe_url = raw_url if raw_url.startswith(("https://", "http://")) else "#"
        what = _e(t.get("what", ""))
        link = (
            f'<a href="{_e(safe_url)}" target="_blank" rel="noopener noreferrer" style="color:#c1d1d8">{what}</a>'
            if safe_url != "#" else what
        )
        tl_items += (
            f'<div style="padding:8px 0;border-bottom:1px solid #182225">'
            f'<div style="font-size:9px;color:#4f6168;margin-bottom:3px">'
            f'{_e(t.get("when", "—"))} · {_e(t.get("source", "—"))}</div>'
            f'<div style="font-size:11px;color:#c1d1d8;line-height:1.5">{link}</div>'
            f'</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{e_title} — {e_tipo_es} en {e_location} | Geopolitikapp</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{e_meta}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://geopolitikapp.com/crisis/{e_cid}">
<meta property="og:type" content="article">
<meta property="og:title" content="{e_title} | Geopolitikapp">
<meta property="og:description" content="{e_meta}">
<meta property="og:url" content="https://geopolitikapp.com/crisis/{e_cid}">
<meta property="og:site_name" content="Geopolitikapp">
<script type="application/ld+json">{json.dumps(ld_article, ensure_ascii=False)}</script>
<script type="application/ld+json">{json.dumps(ld_breadcrumb, ensure_ascii=False)}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500&family=Space+Grotesk:wght@600;700&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#07090a;color:#c1d1d8;font-family:'IBM Plex Mono',monospace;font-size:13px;line-height:1.6;-webkit-font-smoothing:antialiased}}
a{{color:inherit;text-decoration:none}}
.topbar{{display:flex;align-items:center;gap:0;height:52px;background:#0c1214;border-bottom:1px solid #182428;position:sticky;top:0;z-index:10;padding:0 24px}}
.brand{{font-family:'Space Grotesk',sans-serif;font-size:11px;font-weight:700;letter-spacing:.18em;color:#e8f1f4;margin-right:auto}}
.nav-link{{padding:0 16px;height:100%;display:flex;align-items:center;font-size:10px;letter-spacing:.14em;color:#8195a0;border-left:1px solid #182428;transition:color .15s}}
.nav-link:hover{{color:#e8f1f4}}
.page{{max-width:780px;margin:0 auto;padding:40px 24px 80px}}
.breadcrumb{{font-size:9px;letter-spacing:.12em;color:#4f6168;margin-bottom:28px}}
.breadcrumb a{{color:#4f6168}}
.breadcrumb a:hover{{color:#8195a0}}
.ribbon{{display:inline-block;padding:3px 10px;font-size:9px;letter-spacing:.18em;margin-bottom:14px;border:1px solid {color};color:{color}}}
h1{{font-family:'Space Grotesk',sans-serif;font-size:24px;font-weight:700;color:#e8f1f4;line-height:1.3;margin-bottom:8px;letter-spacing:.03em}}
.meta-loc{{font-size:11px;color:#4f6168;letter-spacing:.1em;margin-bottom:24px}}
.severity{{display:flex;align-items:center;gap:12px;padding:14px 0;border-top:1px solid #182428;border-bottom:1px solid #182428;margin-bottom:24px}}
.sev-label{{font-size:9px;letter-spacing:.14em;color:#4f6168}}
.sev-val{{font-size:13px;letter-spacing:.06em;color:{color}}}
.section-title{{font-size:9px;letter-spacing:.18em;color:#4f6168;text-transform:uppercase;margin-bottom:10px;padding-bottom:6px;border-bottom:1px dashed #233339}}
.summary{{font-size:12px;color:#8195a0;line-height:1.7;margin-bottom:28px}}
.actors{{margin-bottom:28px}}
.timeline{{margin-bottom:40px}}
.back-map{{display:inline-flex;align-items:center;gap:8px;padding:10px 20px;border:1px solid #233339;font-size:10px;letter-spacing:.14em;color:#8195a0;transition:color .15s,border-color .15s;margin-top:12px}}
.back-map:hover{{color:#e8f1f4;border-color:#4f6168}}
</style>
</head>
<body>
<header class="topbar">
  <div class="brand">MONITOR GEOPOLÍTICO</div>
  <a href="/" class="nav-link">← Mapa</a>
  <a href="/analisis" class="nav-link">Análisis Regional</a>
</header>
<main class="page">
  <nav class="breadcrumb" aria-label="Ruta">
    <a href="/">Inicio</a> &rsaquo; <a href="/analisis">Análisis Regional</a> &rsaquo; {e_title}
  </nav>
  <div class="ribbon">{e_tipo_es.upper()}</div>
  <h1>{e_title}</h1>
  <p class="meta-loc">{e_location}</p>
  <div class="severity">
    <span class="sev-label">SEVERIDAD</span>
    <span class="sev-val">{sev_str}</span>
    <span class="sev-label">{severity}/5</span>
  </div>
  {f'<div class="summary"><h2 class="section-title">Resumen</h2>{e_summary}</div>' if summary else ''}
  {f'<div class="actors"><div class="section-title">Actores</div>{actors_html}</div>' if actors else ''}
  {f'<div class="timeline"><h2 class="section-title">Cronología</h2>{tl_items}</div>' if tl_items else ''}
  <a href="/" class="back-map">← Ver en el mapa en tiempo real</a>
</main>
</body>
</html>"""


@app.get("/crisis/{crisis_id}", response_class=HTMLResponse)
async def pagina_crisis(crisis_id: str):
    datos = _leer_datos()
    crisis = next((c for c in datos.get("crisis", []) if c.get("id") == crisis_id), None)
    if not crisis:
        return HTMLResponse(status_code=404, content="<h1>Crisis no encontrada</h1>")
    return _crisis_page(crisis)


@app.get("/sitemap.xml")
async def sitemap():
    hoy   = date.today().isoformat()
    datos = _leer_datos()
    crisis_urls = "".join(
        f"""  <url>
    <loc>https://geopolitikapp.com/crisis/{c.get('id','')}</loc>
    <lastmod>{c.get('timeline', [{}])[0].get('when', hoy) if c.get('timeline') else hoy}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.7</priority>
  </url>\n"""
        for c in datos.get("crisis", []) if c.get("id")
    )
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
{crisis_urls}</urlset>"""
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
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    if secret and request.headers.get("X-Telegram-Bot-Api-Secret-Token", "") != secret:
        return JSONResponse(status_code=403, content={"ok": False})
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
