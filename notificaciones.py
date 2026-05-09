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
import os
import requests
from dotenv import load_dotenv

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


def _configurado():
    return bool(_TOKEN and _CHAT_ID)


def enviar_telegram(mensaje: str) -> bool:
    """Envía un mensaje al chat configurado. Retorna True si tuvo éxito."""
    if not _configurado():
        return False
    try:
        url = f"https://api.telegram.org/bot{_TOKEN}/sendMessage"
        resp = requests.post(
            url,
            json={"chat_id": _CHAT_ID, "text": mensaje, "parse_mode": "HTML"},
            timeout=10,
        )
        return resp.ok
    except Exception:
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
    return enviar_telegram(msg)


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
    return enviar_telegram(msg)


def alerta_relacion_bilateral(origen: str, destino: str, nivel: str, titular: str) -> bool:
    if nivel != "rojo":
        return False
    msg = (
        f"🔴 <b>TENSIÓN BILATERAL CRÍTICA</b>\n\n"
        f"<b>{origen} ↔ {destino}</b>\n\n"
        f"<i>{titular[:200]}</i>\n\n"
        f"🌐 geopolitikapp.com"
    )
    return enviar_telegram(msg)
