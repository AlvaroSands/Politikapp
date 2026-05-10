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
"""
import json
import os
import requests
from datetime import date, datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

ARCHIVO_SUSCRIPTORES = "suscriptores.json"

TYPE_EMOJI = {
    "armed": "🔴",
    "diplo": "🔵",
    "econ":  "🟡",
    "cyber": "🟣",
    "intel": "🟢",
}

SEV_BAR = {1: "▪︎░░░░", 2: "▪︎▪︎░░░", 3: "▪︎▪︎▪︎░░", 4: "▪︎▪︎▪︎▪︎░", 5: "▪︎▪︎▪︎▪︎▪︎"}


def _configurado():
    return bool(_TOKEN)


def _cargar_suscriptores() -> list:
    ids = []
    try:
        with open(ARCHIVO_SUSCRIPTORES, "r", encoding="utf-8") as f:
            ids = json.load(f)
    except Exception:
        pass
    # El propietario siempre recibe aunque el archivo esté vacío
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
        with open(ARCHIVO_SUSCRIPTORES, "w", encoding="utf-8") as f:
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
    ids = _cargar_suscriptores()
    exito = False
    for chat_id in ids:
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


def alerta_nueva_crisis(crisis: dict) -> bool:
    tipo   = crisis.get("type", "diplo")
    emoji  = TYPE_EMOJI.get(tipo, "⚪")
    sev    = crisis.get("severity", 1)
    barra  = SEV_BAR.get(sev, "?")
    titulo = crisis.get("title", "—")
    loc    = crisis.get("location", "—")
    resumen = crisis.get("summary", "")[:200]

    msg = (
        f"{emoji} <b>NUEVA CRISIS DETECTADA</b>\n\n"
        f"<b>{titulo}</b>\n"
        f"📍 {loc}\n"
        f"⚠️ Severidad: {barra} ({sev}/5)\n"
        f"🏷 Tipo: {tipo.upper()}\n\n"
        f"{resumen}\n\n"
        f"🌐 geopolitikapp.com"
    )
    return enviar_a_todos(msg)


def alerta_escalada(crisis: dict, sev_anterior: int, sev_nueva: int) -> bool:
    tipo   = crisis.get("type", "diplo")
    emoji  = TYPE_EMOJI.get(tipo, "⚪")
    titulo = crisis.get("title", "—")
    loc    = crisis.get("location", "—")
    antes  = SEV_BAR.get(sev_anterior, "?")
    ahora  = SEV_BAR.get(sev_nueva, "?")

    msg = (
        f"⬆️ <b>ESCALADA DE CRISIS</b>\n\n"
        f"{emoji} <b>{titulo}</b>\n"
        f"📍 {loc}\n\n"
        f"Severidad: {antes} ({sev_anterior}) → {ahora} ({sev_nueva})\n\n"
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


def briefing_diario() -> bool:
    try:
        with open("datos.json", "r", encoding="utf-8") as f:
            db = json.load(f)
        crisis = db.get("crisis", [])
        relaciones = db.get("relaciones", [])
    except Exception:
        crisis, relaciones = [], []

    try:
        with open("historial_severidad.json", "r", encoding="utf-8") as f:
            historial = json.load(f)
    except Exception:
        historial = {}

    hoy = date.today().isoformat()

    crisis_ord = sorted(crisis, key=lambda c: -c.get("severity", 0))

    escaladas = []
    for c in crisis:
        cid = c.get("id", "")
        puntos = historial.get(cid, [])
        if len(puntos) >= 2:
            ultimo = puntos[-1]
            penultimo = puntos[-2]
            if ultimo.get("fecha") == hoy and ultimo["severity"] > penultimo["severity"]:
                escaladas.append((c, penultimo["severity"], ultimo["severity"]))

    rojas = [r for r in relaciones if r.get("nivel") == "rojo"]

    fecha_fmt = datetime.now().strftime("%-d de %B de %Y")
    lineas = [f"🌍 <b>BRIEFING GEOPOLÍTICO — {fecha_fmt}</b>\n"]

    criticas = [c for c in crisis_ord if c.get("severity", 0) >= 4]
    if criticas:
        lineas.append("🔥 <b>SITUACIONES CRÍTICAS</b>")
        for c in criticas[:5]:
            emoji = TYPE_EMOJI.get(c.get("type", "diplo"), "⚪")
            sev = c.get("severity", 1)
            barra = SEV_BAR.get(sev, "?")
            lineas.append(f"{emoji} <b>{c['title']}</b>\n   📍 {c.get('location','—')} · {barra} ({sev}/5)")
        lineas.append("")

    if escaladas:
        lineas.append("⬆️ <b>ESCALADAS EN LAS ÚLTIMAS 24H</b>")
        for c, ant, nva in escaladas[:3]:
            lineas.append(
                f"• {c.get('title','—')} "
                f"({SEV_BAR.get(ant,'?')} {ant} → {SEV_BAR.get(nva,'?')} {nva})"
            )
        lineas.append("")

    if rojas:
        lineas.append("🔴 <b>TENSIONES BILATERALES CRÍTICAS</b>")
        for r in rojas[:3]:
            origen = r.get("origen", {}).get("nombre", "?") if isinstance(r.get("origen"), dict) else r.get("origen", "?")
            destino = r.get("destino", {}).get("nombre", "?") if isinstance(r.get("destino"), dict) else r.get("destino", "?")
            lineas.append(f"• {origen} ↔ {destino}: <i>{r.get('titular','')[:100]}</i>")
        lineas.append("")

    n_armed = sum(1 for c in crisis if c.get("type") == "armed")
    n_diplo = sum(1 for c in crisis if c.get("type") == "diplo")
    n_econ  = sum(1 for c in crisis if c.get("type") == "econ")
    sev_media = round(sum(c.get("severity", 1) for c in crisis) / len(crisis), 1) if crisis else 0

    lineas.append("📊 <b>RESUMEN GLOBAL</b>")
    lineas.append(f"Crisis monitorizadas: <b>{len(crisis)}</b>")
    lineas.append(f"Severidad media: <b>{sev_media}/5</b>")
    lineas.append(f"🔴 Armadas: {n_armed}  🔵 Diplomáticas: {n_diplo}  🟡 Económicas: {n_econ}")
    lineas.append("")
    lineas.append("🌐 geopolitikapp.com")

    return enviar_a_todos("\n".join(lineas))
