"""
Actualizador geopolítico — RSS + scraping HTML + auto-creación de crisis.

Pipeline por ciclo (cada 3 h desde main.py, o manual):
  1. Lee los feeds RSS y las fuentes con scraping, registrando la SALUD de
     cada fuente (salud_fuentes.json) para detectar feeds muertos.
  2. Clasifica cada titular (clasificacion.py): relación bilateral, noticia
     de una crisis conocida, o candidato a crisis nueva (umbral multi-fuente).
  3. VITALIDAD (vitalidad.py): recalcula la severidad de cada crisis según
     su actividad reciente (decay), marca latentes, archiva muertas y
     fusiona las relaciones bilaterales por par de países con caducidad.
  4. Persiste de forma atómica y notifica (Telegram) solo cambios reales.
"""
import json
import os
import socket
import time
from datetime import date, datetime, timedelta

import feedparser
import requests
from bs4 import BeautifulSoup

from clasificacion import (
    clasificar_crisis, clasificar_crisis_dinamica, detectar_paises_en_texto,
    es_bilateral, es_ruido, inferir_nivel, inferir_severidad, inferir_tipo,
    normalizar, slugify,
)
from vitalidad import aplicar_vitalidad, fusionar_relaciones
from notificaciones import alerta_nueva_crisis, alerta_escalada, alerta_relacion_bilateral
from twitter import tweet_nueva_crisis, tweet_escalada, tweet_tension_bilateral
import rutas

socket.setdefaulttimeout(15)  # feedparser hereda este timeout

HEADERS_HTTP = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; GeopolitikApp/1.0; +https://geopolitikapp.com)"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── FUENTES RSS ─────────────────────────────────────────────────────────────
# Lista depurada el 2026-06-12 contra la realidad (34 de 81 feeds estaban
# muertos). salud_fuentes.json registra cada ciclo quién responde; antes de
# añadir o quitar fuentes, mirar ahí.

FUENTES_RSS = [
    # Anglófonas — generalistas
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.bbci.co.uk/news/world/europe/rss.xml",
    "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml",
    "https://feeds.bbci.co.uk/news/world/asia/rss.xml",
    "https://feeds.bbci.co.uk/news/world/africa/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/MiddleEast.xml",
    "https://www.theguardian.com/world/rss",
    "https://www.theguardian.com/world/europe-news/rss",
    "https://www.theguardian.com/world/middleeast/rss",
    "https://www.independent.co.uk/news/world/rss",
    "https://www.ft.com/world?format=rss",
    "https://feeds.a.dj.com/rss/RSSWorldNews.xml",          # WSJ (corregido)
    "https://www.economist.com/international/rss.xml",      # corregido (typo)
    # Geopolítica / defensa / estrategia
    "https://foreignpolicy.com/feed/",
    "https://warontherocks.com/feed/",
    "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml",
    "https://thediplomat.com/feed/",
    "https://www.lowyinstitute.org/the-interpreter/rss.xml",
    "https://www.atlanticcouncil.org/feed/",
    "https://www.rand.org/blog.xml",
    "https://www.justsecurity.org/feed/",
    "https://geopoliticalfutures.com/feed/",
    "https://timothyash.substack.com/feed",
    # OSINT / inteligencia verificada
    "https://www.bellingcat.com/feed/",
    # Oriente Medio / África / Asia
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.middleeasteye.net/rss",
    "https://www.scmp.com/rss/91/feed",
    "https://www.scmp.com/rss/2/feed",
    "https://asia.nikkei.com/rss/feed/nar",
    "https://www.rfa.org/english/rss2.xml",
    # Derechos humanos / multilaterales
    "https://www.hrw.org/rss.xml",
    "https://www.amnesty.org/en/latest/feed/",
    "https://news.un.org/feed/subscribe/en/news/all/rss.xml",
    # Francófonas
    "https://www.france24.com/es/rss",
    "https://www.france24.com/fr/monde/rss",
    "https://www.lemonde.fr/international/rss_full.xml",
    "https://www.liberation.fr/arc/outboundfeeds/rss/?outputType=xml",
    # Hispanófonas (corregidas 2026-06-12: las anteriores estaban todas caídas)
    "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada",
    "https://www.elmundo.es/rss/internacional.xml",
    "https://e00-elmundo.uecdn.es/elmundo/rss/internacional.xml",
    "https://rss.elconfidencial.com/mundo/",
    "https://www.lavanguardia.com/rss/internacional.xml",
    "https://feeds.bbci.co.uk/mundo/rss.xml",
    "https://rss.dw.com/rdf/rss-es-all",
    # Europeas / alemanas
    "https://rss.dw.com/rdf/rss-en-all",
    "https://rss.dw.com/rdf/rss-de-all",
    "https://www.politico.eu/feed/",
    "https://www.euractiv.com/feed/",
    # Europa del Este / Rusia
    "https://www.kyivpost.com/feed",
    "https://www.ukrinform.net/rss",
    "https://meduza.io/rss/all",
    # Ciberseguridad
    "https://www.cisa.gov/cybersecurity-advisories/all.xml",        # oficial (antes scraping)
    "https://www.ncsc.gov.uk/api/1/services/v1/all-rss-feed.xml",   # oficial (antes scraping)
    "https://www.securityweek.com/feed",
    "https://krebsonsecurity.com/feed/",
    "https://feeds.feedburner.com/TheHackersNews",
    "https://www.bleepingcomputer.com/feed/",
    "https://isc.sans.edu/rssfeed.xml",
    "https://www.darkreading.com/rss.xml",
    "https://blog.malwarebytes.com/feed/",
    # Radio pública / NPR
    "https://feeds.npr.org/1004/rss.xml",
]

# ── FUENTES CON SCRAPING HTML ───────────────────────────────────────────────
# Vacío desde 2026-06-12: CISA y NCSC publican RSS oficial (arriba) y la web
# de ISW devuelve 403 a cualquier bot. El mecanismo queda por si alguna
# fuente futura no ofrece RSS.

FUENTES_SCRAPING: dict[str, dict] = {}

# ── PERSISTENCIA ────────────────────────────────────────────────────────────

def _cargar_json(path, por_defecto):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except (json.JSONDecodeError, ValueError):
                pass
    return por_defecto


def _guardar_json_atomico(path, datos):
    """Escribe a tmp + rename: nadie lee nunca un JSON a medio escribir."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def cargar_db():
    datos = _cargar_json(rutas.ARCHIVO_DATOS, {"crisis": [], "relaciones": []})
    if isinstance(datos, list):  # formato antiguo
        return {"crisis": datos, "relaciones": []}
    return datos


def guardar_db(datos):
    _guardar_json_atomico(rutas.ARCHIVO_DATOS, datos)


def id_crisis(c):
    return c.get("id") or c.get("id_crisis", "")


def cargar_pendientes():
    return _cargar_json(rutas.ARCHIVO_PENDIENTES, [])


def guardar_pendientes(p):
    _guardar_json_atomico(rutas.ARCHIVO_PENDIENTES, p)


def cargar_historial():
    return _cargar_json(rutas.ARCHIVO_HISTORIAL, {})


def guardar_historial(h):
    _guardar_json_atomico(rutas.ARCHIVO_HISTORIAL, h)


def registrar_severidad(historial, crisis_id, severity):
    """Un punto por día y crisis (actualiza el del día si ya existe)."""
    hoy = date.today().isoformat()
    entradas = historial.setdefault(crisis_id, [])
    if entradas and entradas[-1]["fecha"] == hoy:
        entradas[-1]["severity"] = severity
    else:
        entradas.append({"fecha": hoy, "severity": severity})
    historial[crisis_id] = entradas[-90:]


# ── SALUD DE FUENTES ────────────────────────────────────────────────────────

def _registrar_salud(salud, fuente_id, nombre, ok, items, error=""):
    s = salud.setdefault(fuente_id, {
        "nombre": nombre, "fallos_consecutivos": 0,
        "last_ok": None, "last_error": None, "items_ultimo": 0,
    })
    s["nombre"] = nombre or s["nombre"]
    ahora = datetime.now().isoformat(timespec="seconds")
    if ok:
        s["last_ok"] = ahora
        s["items_ultimo"] = items
        s["fallos_consecutivos"] = 0
        s.pop("error", None)
    else:
        s["last_error"] = ahora
        s["items_ultimo"] = 0
        s["fallos_consecutivos"] = s.get("fallos_consecutivos", 0) + 1
        s["error"] = error[:120]


# ── AUTO-CREACIÓN DE CRISIS ─────────────────────────────────────────────────
# v2 (2026-06-12): los candidatos se agrupan por (países, tipo) en vez de
# por similitud de titulares (>0.60 entre medios distintos no disparaba
# nunca: cada medio titula a su manera). Madura un candidato con ≥5
# menciones de ≥3 fuentes en una ventana de 72 h.

UMBRAL_MENCIONES     = 5
UMBRAL_FUENTES       = 3
VENTANA_MADUREZ_DIAS = 3
MENCION_CADUCIDAD    = 7   # las menciones más viejas se purgan
MAX_CRISIS_POR_CICLO = 3


def clave_candidato(paises, tipo):
    nucleo = "|".join(sorted(normalizar(p["nombre"]) for p in paises[:2]))
    return f"{nucleo}|{tipo}"


def limpiar_pendientes_caducados(pendientes, hoy=None):
    """Purga menciones viejas y descarta candidatos vacíos o de formato v1."""
    hoy = hoy or date.today()
    limite = (hoy - timedelta(days=MENCION_CADUCIDAD)).isoformat()
    vivos = []
    for p in pendientes:
        if "clave" not in p:  # formato v1 (similitud de titulares): descartar
            continue
        p["menciones"] = [m for m in p["menciones"] if m.get("fecha", "") >= limite]
        if p["menciones"]:
            vivos.append(p)
    return vivos


def registrar_candidato(titulo, texto_clasif, fuente, url, fecha, pendientes,
                        ids_existentes, hoy=None):
    """
    Acumula la mención en el candidato (países del TITULAR + tipo del texto
    completo) y lo devuelve si alcanza la madurez. La geografía se decide
    solo por el titular para no arrastrar países tangenciales del summary.
    """
    hoy = hoy or date.today()
    paises = detectar_paises_en_texto(titulo)
    if not paises:
        return None
    tipo = inferir_tipo(texto_clasif)
    if tipo is None:
        return None

    clave = clave_candidato(paises, tipo)
    cand = next((p for p in pendientes if p.get("clave") == clave), None)
    if cand is None:
        cand = {
            "clave": clave,
            "tipo": tipo,
            "paises": [
                {"nombre": p["nombre"], "lat": p["lat"], "lng": p["lng"]}
                for p in paises[:2]
            ],
            "menciones": [],
        }
        pendientes.append(cand)
    if any(m["url"] == url for m in cand["menciones"]):
        return None
    cand["menciones"].append(
        {"fecha": fecha, "titulo": titulo, "fuente": fuente, "url": url},
    )

    limite = (hoy - timedelta(days=VENTANA_MADUREZ_DIAS)).isoformat()
    recientes = [m for m in cand["menciones"] if m["fecha"] >= limite]
    fuentes = {m["fuente"] for m in recientes}
    if len(recientes) >= UMBRAL_MENCIONES and len(fuentes) >= UMBRAL_FUENTES:
        reciente = max(recientes, key=lambda m: m["fecha"])
        if slugify(reciente["titulo"]) in ids_existentes:
            return None
        return cand
    return None


def promover_candidato(cand, db):
    menciones = sorted(cand["menciones"], key=lambda m: m["fecha"], reverse=True)
    titulo = menciones[0]["titulo"]
    paises = cand["paises"]
    fuentes = sorted({m["fuente"] for m in menciones})
    severidad = inferir_severidad(titulo, len(menciones))
    hoy = date.today().isoformat()

    nueva_crisis = {
        "id":       slugify(titulo),
        "type":     cand["tipo"],
        "severity": severidad,
        "severity_base": severidad,
        "creada":   hoy,
        "title":    titulo,
        "location": paises[0]["nombre"],
        "lat":      paises[0]["lat"],
        "lng":      paises[0]["lng"],
        "actors":   [p["nombre"] for p in paises],
        "paises_clave": [p["nombre"] for p in paises],
        "summary":  (
            f"Crisis detectada automáticamente: {len(menciones)} menciones "
            f"en {len(fuentes)} fuentes independientes "
            f"({', '.join(fuentes[:4])}{'…' if len(fuentes) > 4 else ''})."
        ),
        "timeline": [
            {"when": m["fecha"], "what": m["titulo"],
             "source": m["fuente"], "url": m["url"]}
            for m in menciones[:12]
        ],
    }

    db["crisis"].append(nueva_crisis)
    print(f"  🆕 NUEVA CRISIS [{cand['tipo'].upper()} SEV{severidad}]: {titulo[:70]}…")
    alerta_nueva_crisis(nueva_crisis)
    tweet_nueva_crisis(nueva_crisis)
    return nueva_crisis


# ── SCRAPING HTML ───────────────────────────────────────────────────────────

def scraping_fuente(nombre, cfg):
    resultados = []
    try:
        resp = requests.get(cfg["url"], headers=HEADERS_HTTP, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"  ⚠️  Scraping {nombre} falló: {e}")
        return None  # None = fuente caída (para salud); [] = sin items

    items = []
    for sel in cfg["selectores_item"]:
        items = soup.select(sel)
        if items:
            break
    if not items:
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
        href = enlace_tag.get("href", "")
        if not titulo or not href or titulo in vistos:
            continue
        vistos.add(titulo)
        if href.startswith("/"):
            href = base + href
        elif not href.startswith("http"):
            continue
        resultados.append({"titulo": titulo, "url": href})

    print(f"  🌐 Scraping {nombre}: {len(resultados)} titulares")
    return resultados


# ── PROCESADO DE UN TITULAR ─────────────────────────────────────────────────

def _procesar_titular(titulo, texto_clasif, enlace, nombre_fuente,
                      fecha_noticia, ctx, relaciones_nuevas):
    """Clasifica un titular y lo enruta. Devuelve nº de eventos añadidos.
    `texto_clasif` = titular + summary del RSS: se usa para asignar crisis y
    tipo (más contexto); la geografía de relaciones/candidatos sale solo del
    titular para no arrastrar países tangenciales."""
    db, pendientes, ids_existentes, ids_promovidos, ctx_news = ctx
    if es_ruido(texto_clasif):
        return 0
    tl_item = {"when": fecha_noticia, "what": titulo,
               "source": nombre_fuente, "url": enlace}

    nuevos = 0
    bilateral, paises = es_bilateral(titulo)
    if bilateral:
        origen, destino = paises[0], paises[1]
        relaciones_nuevas.append({
            "id_relacion": f"rel-nueva-{len(relaciones_nuevas)}",
            "origen":  {"nombre": origen["nombre"],  "lat": origen["lat"],  "lng": origen["lng"]},
            "destino": {"nombre": destino["nombre"], "lat": destino["lat"], "lng": destino["lng"]},
            "tipo":    "militar" if inferir_tipo(titulo) == "armed" else "diplomática",
            "nivel":   inferir_nivel(titulo),
            "fecha":   fecha_noticia,
            "titular": titulo,
            "fuente":  nombre_fuente,
            "url":     enlace,
        })
        print(f"     ⚡ Relación: {origen['nombre']} ↔ {destino['nombre']}")
        nuevos += 1
    else:
        crisis_id = (clasificar_crisis(texto_clasif)
                     or clasificar_crisis_dinamica(texto_clasif, db["crisis"]))
        if crisis_id:
            destino_crisis = None
            for c in db["crisis"]:
                if id_crisis(c) == crisis_id:
                    destino_crisis = c
                    break
            if destino_crisis is None:
                # Reactivación: una crisis archivada que vuelve a sonar revive.
                for c in db.get("crisis_archivadas", []):
                    if id_crisis(c) == crisis_id:
                        db["crisis_archivadas"].remove(c)
                        c.pop("archivada_en", None)
                        db["crisis"].append(c)
                        destino_crisis = c
                        print(f"     ♻️  Crisis reactivada: {crisis_id}")
                        break
            if destino_crisis is not None:
                tl = destino_crisis.setdefault(
                    "timeline", destino_crisis.pop("actualizaciones", []),
                )
                tl.insert(0, tl_item)
                destino_crisis["timeline"] = tl[:30]
                nuevos += 1
        else:
            promovido = registrar_candidato(
                titulo, texto_clasif, nombre_fuente, enlace, fecha_noticia,
                pendientes, ids_existentes | ids_promovidos,
            )
            if (promovido
                    and promovido["clave"] not in ids_promovidos
                    and len(ids_promovidos) < MAX_CRISIS_POR_CICLO):
                promover_candidato(promovido, db)
                ids_promovidos.add(promovido["clave"])
                pendientes.remove(promovido)
                nuevos += 1

    # Context nodes (fichas de actor) — independiente de la clasificación.
    t_low = titulo.lower()
    for node in db.get("context_nodes", []):
        if any(k.lower() in t_low for k in node.get("keywords", [])):
            ctx_news[node["id"]].append(tl_item)
    return nuevos


# ── MAIN ────────────────────────────────────────────────────────────────────

def ejecutar_actualizacion():
    print("🚀 Actualizador geopolítico (RSS + scraping + vitalidad)…")
    rutas.asegurar_semillas()
    db          = cargar_db()
    pendientes  = limpiar_pendientes_caducados(cargar_pendientes())
    historial   = cargar_historial()
    salud       = _cargar_json(rutas.ARCHIVO_SALUD, {})

    ctx_news = {n["id"]: [] for n in db.get("context_nodes", [])}
    urls_vistas = set()
    for c in db["crisis"] + db.get("crisis_archivadas", []):
        for act in c.get("timeline", c.get("actualizaciones", [])):
            urls_vistas.add(act.get("url", ""))
    for r in db["relaciones"]:
        urls_vistas.add(r.get("url", ""))
        for e in r.get("eventos", []):
            urls_vistas.add(e.get("url", ""))

    ids_existentes = {id_crisis(c) for c in db["crisis"]}
    ids_promovidos: set[str] = set()
    relaciones_nuevas: list[dict] = []
    ctx = (db, pendientes, ids_existentes, ids_promovidos, ctx_news)

    nuevos = 0
    hoy = date.today()

    # 1. RSS
    for rss_url in FUENTES_RSS:
        print(f"📡 {rss_url}")
        try:
            feed = feedparser.parse(rss_url)
        except Exception as e:
            _registrar_salud(salud, rss_url, rss_url, False, 0, str(e))
            continue
        nombre_fuente = getattr(feed.feed, "title", "") or "Internacional"
        entradas = feed.entries[:8]
        _registrar_salud(salud, rss_url, nombre_fuente, len(feed.entries) > 0,
                         len(feed.entries),
                         "" if feed.entries else f"bozo={getattr(feed, 'bozo', '?')}")

        for entrada in entradas:
            enlace = getattr(entrada, "link", "")
            titulo = getattr(entrada, "title", "")
            if not titulo or not enlace or enlace in urls_vistas:
                continue
            pub = (getattr(entrada, "published_parsed", None)
                   or getattr(entrada, "updated_parsed", None))
            try:
                fecha_noticia = date(*pub[:3]).isoformat() if pub else hoy.isoformat()
            except Exception:
                fecha_noticia = hoy.isoformat()
            resumen = getattr(entrada, "summary", "") or ""
            if "<" in resumen:
                resumen = BeautifulSoup(resumen, "html.parser").get_text(" ", strip=True)
            texto_clasif = f"{titulo}. {resumen[:300]}"
            nuevos += _procesar_titular(
                titulo, texto_clasif, enlace, nombre_fuente, fecha_noticia,
                ctx, relaciones_nuevas,
            )
            urls_vistas.add(enlace)
        time.sleep(0.2)  # cortesía entre FUENTES (no entre titulares)

    # 2. Scraping (vacío desde que CISA/NCSC tienen RSS; mecanismo en reserva)
    for nombre_src, cfg in FUENTES_SCRAPING.items():
        items = scraping_fuente(nombre_src, cfg)
        _registrar_salud(salud, cfg["url"], nombre_src, bool(items),
                         len(items or []), "" if items else "sin items")
        for item in items or []:
            if item["url"] in urls_vistas:
                continue
            nuevos += _procesar_titular(
                item["titulo"], item["titulo"], item["url"], nombre_src,
                hoy.isoformat(), ctx, relaciones_nuevas,
            )
            urls_vistas.add(item["url"])
        time.sleep(0.2)

    # 3. Vitalidad: severidad viva, estados, archivo y fusión de relaciones.
    cambios = aplicar_vitalidad(db, hoy, inferir_nivel)
    for cb in cambios:
        registrar_severidad(historial, id_crisis(cb["crisis"]), cb["despues"])
        flecha = "⬆️" if cb["despues"] > cb["antes"] else "⬇️"
        print(f"  {flecha} {id_crisis(cb['crisis'])}: {cb['antes']} → {cb['despues']}")
        if cb["despues"] > cb["antes"]:
            alerta_escalada(cb["crisis"], cb["antes"], cb["despues"])
            tweet_escalada(cb["crisis"], cb["antes"], cb["despues"])
    for c in db["crisis"]:
        registrar_severidad(historial, id_crisis(c), c.get("severity", 1))

    db["relaciones"] = fusionar_relaciones(db["relaciones"] + relaciones_nuevas, hoy)

    # Alertas de relaciones rojas estrenadas en este ciclo
    urls_nuevas = {r["url"] for r in relaciones_nuevas}
    for r in db["relaciones"]:
        if r.get("nivel") == "rojo" and r.get("url") in urls_nuevas:
            alerta_relacion_bilateral(
                r["origen"].get("nombre", "?"), r["destino"].get("nombre", "?"),
                "rojo", r.get("titular", ""),
            )
            tweet_tension_bilateral(
                r["origen"].get("nombre", "?"), r["destino"].get("nombre", "?"),
                r.get("titular", ""),
            )

    # 3b. Context nodes
    for node in db.get("context_nodes", []):
        collected = ctx_news.get(node["id"], [])
        if not collected:
            continue
        seen = {x["url"] for x in collected}
        node["news"] = (collected + [n for n in node.get("news", [])
                                     if n.get("url") not in seen])[:5]

    # 4. Persistencia atómica
    db["actualizado"] = datetime.now().isoformat(timespec="seconds")
    guardar_historial(historial)
    guardar_pendientes(pendientes)
    _guardar_json_atomico(rutas.ARCHIVO_SALUD, salud)
    guardar_db(db)

    activas = sum(1 for c in db["crisis"] if c.get("estado") == "activa")
    latentes = sum(1 for c in db["crisis"] if c.get("estado") == "latente")
    fuentes_ok = sum(1 for s in salud.values() if s.get("fallos_consecutivos", 0) == 0)
    print(f"\n🎉 {nuevos} eventos · crisis {activas} activas / {latentes} latentes / "
          f"{len(db.get('crisis_archivadas', []))} archivadas · "
          f"{len(db['relaciones'])} relaciones vigentes · "
          f"fuentes OK {fuentes_ok}/{len(salud)}")
    if cambios:
        print(f"   ↕ {len(cambios)} cambios de severidad")


if __name__ == "__main__":
    ejecutar_actualizacion()
