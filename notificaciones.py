"""
Módulo de alertas Telegram para geopolitikapp.com.

SETUP (una sola vez):
  1. Abre Telegram y busca @BotFather
  2. Envía /newbot y sigue los pasos → te dará un TOKEN
  3. Abre https://t.me/tu_bot y escríbele cualquier mensaje
  4. Abre en el navegador:
       https://api.telegram.org/bot<TOKEN>/getUpdates
     Busca "chat":{"id": XXXXXXX} — ese número es tu CHAT_ID
  5. Añade al .env (local) y a Railway (producción):
       TELEGRAM_BOT_TOKEN=xxxxxxxxxx:xxxxxxxxxxxxxxxxxxxxxxx
       TELEGRAM_CHAT_ID=xxxxxxxxx

El briefing diario es un DIFF de las últimas 24 h (qué cambió), no un
listado de las crisis de siempre. Si no hubo cambios, lo dice en dos líneas.
"""
import json
import os
import requests
from datetime import date, datetime, timedelta
from dotenv import load_dotenv

import rutas

load_dotenv()

_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

TYPE_EMOJI = {
    "armed": "🔴",
    "diplo": "🔵",
    "econ":  "🟡",
    "cyber": "🟣",
    "intel": "🟢",
}

SEV_BAR = {1: "▪︎░░░░", 2: "▪︎▪︎░░░", 3: "▪︎▪︎▪︎░░", 4: "▪︎▪︎▪︎▪︎░", 5: "▪︎▪︎▪︎▪︎▪︎"}

MESES_ES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _configurado():
    return bool(_TOKEN)


def _cargar_suscriptores() -> list:
    ids = []
    try:
        with open(rutas.ARCHIVO_SUSCRIPTORES, "r", encoding="utf-8") as f:
            ids = json.load(f)
    except Exception:
        pass
    if _CHAT_ID:
        try:
            owner = int(_CHAT_ID)
            if owner not in ids:
                ids.insert(0, owner)
        except ValueError:
            pass
    return ids


def _guardar_suscriptores(ids: list):
    try:
        with open(rutas.ARCHIVO_SUSCRIPTORES, "w", encoding="utf-8") as f:
            json.dump(ids, f)
    except Exception:
        pass


def agregar_suscriptor(chat_id: int) -> bool:
    ids = _cargar_suscriptores()
    if chat_id not in ids:
        ids.append(chat_id)
        _guardar_suscriptores(ids)
        return True
    return False


def eliminar_suscriptor(chat_id: int) -> bool:
    ids = _cargar_suscriptores()
    if chat_id in ids:
        ids.remove(chat_id)
        _guardar_suscriptores(ids)
        return True
    return False


def enviar_a(mensaje: str, chat_id: int) -> bool:
    if not _configurado():
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": mensaje, "parse_mode": "HTML"},
            timeout=10,
        )
        return resp.ok
    except Exception:
        return False


def enviar_a_todos(mensaje: str) -> bool:
    if not _configurado():
        return False
    exito = False
    for chat_id in _cargar_suscriptores():
        if enviar_a(mensaje, chat_id):
            exito = True
    return exito


def enviar_telegram(mensaje: str) -> bool:
    """Compatibilidad — envía solo al propietario."""
    if not _CHAT_ID:
        return False
    try:
        return enviar_a(mensaje, int(_CHAT_ID))
    except ValueError:
        return False


# ── ALERTAS PUNTUALES ───────────────────────────────────────────────────────

def alerta_nueva_crisis(crisis: dict) -> bool:
    tipo   = crisis.get("type", "diplo")
    emoji  = TYPE_EMOJI.get(tipo, "⚪")
    sev    = crisis.get("severity", 1)
    msg = (
        f"{emoji} <b>NUEVA CRISIS DETECTADA</b>\n\n"
        f"<b>{crisis.get('title', '—')}</b>\n"
        f"📍 {crisis.get('location', '—')}\n"
        f"⚠️ Severidad: {SEV_BAR.get(sev, '?')} ({sev}/5)\n"
        f"🏷 Tipo: {tipo.upper()}\n\n"
        f"{crisis.get('summary', '')[:200]}\n\n"
        f"🌐 geopolitikapp.com"
    )
    return enviar_a_todos(msg)


def alerta_escalada(crisis: dict, sev_anterior: int, sev_nueva: int) -> bool:
    emoji = TYPE_EMOJI.get(crisis.get("type", "diplo"), "⚪")
    msg = (
        f"⬆️ <b>ESCALADA DE CRISIS</b>\n\n"
        f"{emoji} <b>{crisis.get('title', '—')}</b>\n"
        f"📍 {crisis.get('location', '—')}\n\n"
        f"Severidad: {SEV_BAR.get(sev_anterior, '?')} ({sev_anterior}) → "
        f"{SEV_BAR.get(sev_nueva, '?')} ({sev_nueva})\n\n"
        f"🌐 geopolitikapp.com"
    )
    return enviar_a_todos(msg)


def alerta_relacion_bilateral(origen: str, destino: str, nivel: str, titular: str) -> bool:
    if nivel != "rojo":
        return False
    msg = (
        f"🔴 <b>TENSIÓN BILATERAL CRÍTICA</b>\n\n"
        f"<b>{origen} ↔ {destino}</b>\n\n"
        f"<i>{titular[:200]}</i>\n\n"
        f"🌐 geopolitikapp.com"
    )
    return enviar_a_todos(msg)


# ── BRIEFING DIARIO (diff de 24 h) ──────────────────────────────────────────

def _fecha_es(d: datetime) -> str:
    return f"{d.day} de {MESES_ES[d.month]} de {d.year}"


def briefing_texto(ahora: datetime | None = None) -> str:
    """Compone el briefing como diff de las últimas 24 h. Puro: no envía."""
    ahora = ahora or datetime.now()
    hoy = ahora.date()
    ayer = hoy - timedelta(days=1)
    corte = {hoy.isoformat(), ayer.isoformat()}

    try:
        with open(rutas.ARCHIVO_DATOS, "r", encoding="utf-8") as f:
            db = json.load(f)
    except Exception:
        db = {}
    crisis = db.get("crisis", [])
    relaciones = db.get("relaciones", [])

    try:
        with open(rutas.ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
            historial = json.load(f)
    except Exception:
        historial = {}

    lineas = [f"🌍 <b>BRIEFING GEOPOLÍTICO — {_fecha_es(ahora)}</b>"]
    hay_algo = False

    # 1. Crisis nuevas (creadas en las últimas 24 h)
    nuevas = [c for c in crisis if c.get("creada") in corte]
    if nuevas:
        hay_algo = True
        lineas.append("\n🆕 <b>CRISIS NUEVAS</b>")
        for c in nuevas[:3]:
            emoji = TYPE_EMOJI.get(c.get("type", "diplo"), "⚪")
            lineas.append(f"{emoji} <b>{c.get('title', '—')}</b> · 📍 {c.get('location', '—')}")

    # 2. Escaladas y desescaladas reales (diff del historial diario)
    escaladas, desescaladas = [], []
    for c in crisis:
        puntos = historial.get(c.get("id", ""), [])
        if len(puntos) >= 2 and puntos[-1].get("fecha") in corte:
            ant, act = puntos[-2]["severity"], puntos[-1]["severity"]
            if act > ant:
                escaladas.append((c, ant, act))
            elif act < ant:
                desescaladas.append((c, ant, act))
    if escaladas:
        hay_algo = True
        lineas.append("\n⬆️ <b>ESCALADAS</b>")
        for c, ant, act in escaladas[:4]:
            lineas.append(f"• {c.get('title', '—')}: {ant} → <b>{act}</b>/5")
    if desescaladas:
        hay_algo = True
        lineas.append("\n⬇️ <b>DESESCALADAS</b>")
        for c, ant, act in desescaladas[:4]:
            lineas.append(f"• {c.get('title', '—')}: {ant} → {act}/5")

    # 3. Crisis con actividad real en 24 h (noticias nuevas)
    con_actividad = []
    for c in crisis:
        if c.get("creada") in corte:
            continue  # ya salió en "nuevas"
        recientes = [t for t in c.get("timeline", []) if t.get("when") in corte]
        if recientes:
            con_actividad.append((c, recientes))
    con_actividad.sort(key=lambda x: (-len(x[1]), -x[0].get("severity", 0)))
    if con_actividad:
        hay_algo = True
        lineas.append("\n🔥 <b>CON ACTIVIDAD (24 H)</b>")
        for c, recientes in con_actividad[:5]:
            emoji = TYPE_EMOJI.get(c.get("type", "diplo"), "⚪")
            sev = c.get("severity", 1)
            lineas.append(
                f"{emoji} <b>{c.get('title', '—')}</b> "
                f"({SEV_BAR.get(sev, '?')} {sev}/5 · {len(recientes)} noticias)"
            )
            lineas.append(f"   <i>{recientes[0].get('what', '')[:110]}</i>")

    # 4. Relaciones rojas con eventos en 24 h
    rojas = [
        r for r in relaciones
        if r.get("nivel") == "rojo" and r.get("fecha") in corte
    ]
    if rojas:
        hay_algo = True
        lineas.append("\n🔴 <b>TENSIONES BILATERALES CRÍTICAS</b>")
        for r in rojas[:3]:
            o = r.get("origen", {}).get("nombre", "?")
            d = r.get("destino", {}).get("nombre", "?")
            lineas.append(f"• {o} ↔ {d}: <i>{r.get('titular', '')[:100]}</i>")

    if not hay_algo:
        lineas.append("\nSin cambios significativos en las últimas 24 horas.")

    # 5. Pie con totales
    activas = sum(1 for c in crisis if c.get("estado", "activa") == "activa")
    latentes = sum(1 for c in crisis if c.get("estado") == "latente")
    lineas.append(
        f"\n📊 {activas} crisis activas · {latentes} latentes · "
        f"{len(relaciones)} relaciones vigentes"
    )
    lineas.append("🌐 geopolitikapp.com")
    return "\n".join(lineas)


def briefing_diario() -> bool:
    return enviar_a_todos(briefing_texto())
