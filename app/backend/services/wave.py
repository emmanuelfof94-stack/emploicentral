"""
Client minimal de l'API Wave Checkout (https://docs.wave.com/checkout).

Configuration (variables d'environnement, à renseigner sur Render) :
- `WAVE_API_KEY`        : clé API Wave Business (« Bearer »). Absente → paiement Wave désactivé,
                          le flux manuel (numéro mobile money + validation admin) reste seul.
- `WAVE_WEBHOOK_SECRET` : secret de signature des webhooks (stratégie « Signing Secret »).
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from typing import Dict, List, Optional, Tuple

import httpx

WAVE_API_BASE = "https://api.wave.com"
CURRENCY = "XOF"
# Wave rejette les signatures de plus de 5 minutes (anti-rejeu) : même tolérance ici.
SIGNATURE_TOLERANCE_SECONDS = 300


class WaveError(RuntimeError):
    """Appel à l'API Wave en échec (réseau, clé invalide, réponse inattendue)."""


def _api_key() -> str:
    return (os.environ.get("WAVE_API_KEY") or "").strip()


def webhook_secret() -> str:
    return (os.environ.get("WAVE_WEBHOOK_SECRET") or "").strip()


def wave_enabled() -> bool:
    return bool(_api_key())


def amount_xof(price: str) -> str:
    """« 20 000 FCFA » → « 20000 » (XOF : entier, sans décimales ni zéro initial)."""
    digits = re.sub(r"\D", "", price or "")
    value = int(digits) if digits else 0
    if value <= 0:
        raise ValueError(f"Montant invalide : {price!r}")
    return str(value)


async def _request(method: str, path: str, json: Optional[dict] = None) -> dict:
    headers = {"Authorization": f"Bearer {_api_key()}"}
    try:
        async with httpx.AsyncClient(base_url=WAVE_API_BASE, timeout=15.0) as client:
            resp = await client.request(method, path, json=json, headers=headers)
    except httpx.HTTPError as exc:
        raise WaveError(f"Wave injoignable : {exc}") from exc
    if resp.status_code >= 400:
        raise WaveError(f"Wave {resp.status_code} : {resp.text[:300]}")
    try:
        return resp.json()
    except ValueError as exc:
        raise WaveError("Réponse Wave illisible") from exc


async def create_checkout_session(amount: str, client_reference: str, success_url: str, error_url: str) -> dict:
    """Crée une session ; renvoie notamment `id` (cos-…) et `wave_launch_url`."""
    return await _request("POST", "/v1/checkout/sessions", json={
        "amount": amount,
        "currency": CURRENCY,
        "client_reference": client_reference,
        "success_url": success_url,
        "error_url": error_url,
    })


async def get_checkout_session(session_id: str) -> dict:
    return await _request("GET", f"/v1/checkout/sessions/{session_id}")


def _parse_signature_header(header: str) -> Tuple[Optional[str], List[str]]:
    timestamp, signatures = None, []
    for part in (header or "").split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1" and value:
            signatures.append(value)  # plusieurs v1 possibles pendant une rotation de clé
    return timestamp, signatures


def verify_webhook_signature(raw_body: bytes, header: str, secret: str, now: Optional[float] = None) -> bool:
    """Vérifie l'en-tête `Wave-Signature: t=<ts>,v1=<hex>` (HMAC-SHA256 de ts + corps brut)."""
    if not secret:
        return False
    timestamp, signatures = _parse_signature_header(header)
    if not timestamp or not signatures:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs((now if now is not None else time.time()) - ts) > SIGNATURE_TOLERANCE_SECONDS:
        return False
    expected = hmac.new(secret.encode(), timestamp.encode() + raw_body, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, sig) for sig in signatures)


def session_summary(session: Dict) -> Dict[str, Optional[str]]:
    """Champs utiles d'une session Wave (réponse API ou `data` d'un webhook)."""
    return {
        "id": session.get("id"),
        "amount": str(session.get("amount")) if session.get("amount") is not None else None,
        "currency": session.get("currency"),
        "client_reference": session.get("client_reference"),
        "checkout_status": session.get("checkout_status"),
        "payment_status": session.get("payment_status"),
        "transaction_id": session.get("transaction_id"),
        "wave_launch_url": session.get("wave_launch_url"),
    }
