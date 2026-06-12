"""
Módulo de publicación en X (Twitter) para geopolitikapp.com.

Requiere en .env (y en Railway env vars):
  X_API_KEY
  X_API_SECRET
  X_ACCESS_TOKEN
  X_ACCESS_TOKEN_SECRET
"""
import os
import requests
from requests_oauthlib import OAuth1
from dotenv import load_dotenv

load_dotenv()

_API_KEY    = os.getenv("X_API_KEY", "")
_API_SECRET = os.getenv("X_API_SECRET", "")
_ACC_TOKEN  = os.getenv("X_ACCESS_TOKEN", "")
_ACC_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET", "")

_ENDPOINT = "https://api.twitter.com/2/tweets"

TYPE_EMOJI = {
    "armed": "🔴",
    "diplo": "🔵",
    "econ":  "🟡",
    "cyber": "🟣",
    "intel": "🟢",
}

SEV_BAR = {1: "▪︎░░░░", 2: "▪︎▪︎░░░", 3: "▪︎▪︎▪︎░░", 4: "▪︎▪︎▪︎▪︎░", 5: "▪︎▪︎▪︎▪︎▪︎"}


def _configurado():
    return all([_API_KEY, _API_SECRET, _ACC_TOKEN, _ACC_SECRET])


def _auth():
    return OAuth1(_API_KEY, _API_SECRET, _ACC_TOKEN, _ACC_SECRET)


_AVISO_DADO = False


def _publicar(texto: str) -> bool:
    global _AVISO_DADO
    if not _configurado():
        if not _AVISO_DADO:
            print("  ⚠️  Twitter: credenciales no configuradas (aviso único).")
            _AVISO_DADO = True
        return False
    # X API v2 limita a 280 caracteres en cuentas sin Premium o 4000 con Premium
    texto = texto[:4000]
    try:
        resp = requests.post(
            _ENDPOINT,
            auth=_auth(),
            json={"text": texto},
            timeout=15,
        )
        if resp.ok:
            tweet_id = resp.json().get("data", {}).get("id", "?")
            print(f"  🐦 Tweet publicado: https://x.com/Geopolitikapp/status/{tweet_id}")
            return True
        else:
            print(f"  ❌ Twitter error {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ Twitter excepción: {e}")
        return False


def tweet_nueva_crisis(crisis: dict) -> bool:
    tipo   = crisis.get("type", "diplo")
    emoji  = TYPE_EMOJI.get(tipo, "⚪")
    sev    = crisis.get("severity", 1)
    barra  = SEV_BAR.get(sev, "?")
    titulo = crisis.get("title", "—")
    loc    = crisis.get("location", "—")
    resumen = crisis.get("summary", "")

    # Recortar resumen para que el tweet quepa bien
    max_resumen = 200
    if len(resumen) > max_resumen:
        resumen = resumen[:max_resumen].rsplit(" ", 1)[0] + "…"

    texto = (
        f"{emoji} NUEVA CRISIS DETECTADA\n\n"
        f"{titulo}\n"
        f"📍 {loc} · Severidad {barra} ({sev}/5)\n\n"
        f"{resumen}\n\n"
        f"🌐 geopolitikapp.com"
    )
    return _publicar(texto)


def tweet_escalada(crisis: dict, sev_anterior: int, sev_nueva: int) -> bool:
    tipo   = crisis.get("type", "diplo")
    emoji  = TYPE_EMOJI.get(tipo, "⚪")
    titulo = crisis.get("title", "—")
    loc    = crisis.get("location", "—")
    antes  = SEV_BAR.get(sev_anterior, "?")
    ahora  = SEV_BAR.get(sev_nueva, "?")

    texto = (
        f"⬆️ ESCALADA DE CRISIS\n\n"
        f"{emoji} {titulo}\n"
        f"📍 {loc}\n\n"
        f"Severidad: {antes} ({sev_anterior}) → {ahora} ({sev_nueva})\n\n"
        f"🌐 geopolitikapp.com"
    )
    return _publicar(texto)


def tweet_tension_bilateral(origen: str, destino: str, titular: str) -> bool:
    if len(titular) > 200:
        titular = titular[:200].rsplit(" ", 1)[0] + "…"

    texto = (
        f"🔴 TENSIÓN BILATERAL CRÍTICA\n\n"
        f"{origen} ↔ {destino}\n\n"
        f"{titular}\n\n"
        f"🌐 geopolitikapp.com"
    )
    return _publicar(texto)
