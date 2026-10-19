"""Génère une paire de clés VAPID pour les notifications push (à faire UNE fois).

Usage (depuis la racine du dépôt, avec le venv du backend) :
    app/.venv/bin/python scripts/generate_vapid_keys.py

Puis poser sur Render (Environment) :
    VAPID_PUBLIC_KEY=<public>   VAPID_PRIVATE_KEY=<private>   VAPID_SUBJECT=mailto:<votre e-mail>
⚠️ Changer de clés invalide tous les abonnements existants : ne les régénérez pas.
"""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


key = ec.generate_private_key(ec.SECP256R1())
private = key.private_numbers().private_value.to_bytes(32, "big")
public = key.public_key().public_bytes(
    serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
)
print("VAPID_PUBLIC_KEY=" + b64url(public))
print("VAPID_PRIVATE_KEY=" + b64url(private))
