"""Traçage des connexions : d'où (IP / lieu) et avec quel appareil un utilisateur se connecte.

Conçu pour ne JAMAIS impacter l'expérience de connexion :
- `client_ip()` / `client_user_agent()` extraient les infos depuis la requête (synchrone).
- `record_login()` est lancé en tâche de fond (FastAPI BackgroundTasks) : il parse le
  User-Agent, géolocalise l'IP (best-effort) puis insère une ligne `login_events`.
  Toute erreur est avalée — une connexion ne doit pas échouer parce qu'on n'a pas pu
  déterminer le lieu ou l'appareil.
"""
import logging
import re
from typing import Optional, Tuple

import httpx
from core.database import db_manager
from fastapi import Request
from models.login_events import LoginEvent

logger = logging.getLogger(__name__)


def client_ip(request: Request) -> str:
    """IP réelle du client, en tenant compte du proxy (Fly / Render / reverse proxy)."""
    fly_ip = request.headers.get("fly-client-ip")
    if fly_ip:
        return fly_ip.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def client_user_agent(request: Request) -> str:
    """User-Agent brut (tronqué) de la requête."""
    return (request.headers.get("user-agent") or "")[:400]


# --- Parsing User-Agent (léger, sans dépendance externe) ---

_TABLET_RE = re.compile(r"ipad|tablet|playbook|silk|(android(?!.*mobile))", re.I)
_MOBILE_RE = re.compile(r"mobi|iphone|ipod|android|blackberry|iemobile|opera mini", re.I)

# Ordre important : on teste du plus spécifique au plus générique.
_OS_PATTERNS = [
    (re.compile(r"android[ /]?([\d.]+)?", re.I), "Android"),
    (re.compile(r"(iphone|ipad|ipod).*?os ([\d_]+)", re.I), "iOS"),
    (re.compile(r"windows nt", re.I), "Windows"),
    (re.compile(r"mac os x", re.I), "macOS"),
    (re.compile(r"cros", re.I), "ChromeOS"),
    (re.compile(r"linux", re.I), "Linux"),
]

_BROWSER_PATTERNS = [
    (re.compile(r"edg(?:a|ios)?/", re.I), "Edge"),
    (re.compile(r"opr/|opera", re.I), "Opera"),
    (re.compile(r"samsungbrowser", re.I), "Samsung Internet"),
    (re.compile(r"firefox|fxios", re.I), "Firefox"),
    (re.compile(r"chrome|crios", re.I), "Chrome"),  # après Edge/Opera/Samsung (forks de Chrome)
    (re.compile(r"safari", re.I), "Safari"),        # après Chrome (Chrome contient "Safari")
]


def parse_user_agent(ua: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Déduit (appareil, OS, navigateur) d'un User-Agent. Valeurs None si inconnues."""
    if not ua:
        return None, None, None

    if _TABLET_RE.search(ua):
        device = "Tablette"
    elif _MOBILE_RE.search(ua):
        device = "Mobile"
    else:
        device = "Ordinateur"

    os_name = next((label for rx, label in _OS_PATTERNS if rx.search(ua)), None)
    browser = next((label for rx, label in _BROWSER_PATTERNS if rx.search(ua)), None)
    return device, os_name, browser


def _is_private_ip(ip: str) -> bool:
    """True pour les IP locales/privées (pas de géolocalisation possible)."""
    if not ip or ip == "unknown":
        return True
    return (
        ip.startswith(("10.", "192.168.", "127.", "172.16.", "172.17.", "172.18.",
                       "172.19.", "172.2", "172.30.", "172.31.", "::1", "fc", "fd"))
        or ip == "::1"
    )


async def _geolocate(ip: str) -> Tuple[Optional[str], Optional[str]]:
    """Lieu approximatif (pays, ville) à partir de l'IP, via ip-api.com (gratuit, sans clé).

    Best-effort : timeout court, échec silencieux (retourne (None, None)).
    """
    if _is_private_ip(ip):
        return None, None
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "status,country,city", "lang": "fr"},
            )
        if resp.status_code != 200:
            return None, None
        data = resp.json()
        if data.get("status") != "success":
            return None, None
        return (data.get("country") or None), (data.get("city") or None)
    except Exception as exc:  # noqa: BLE001 — la géoloc ne doit jamais casser le login
        logger.debug("geolocation failed for ip: %s", type(exc).__name__)
        return None, None


async def record_login(user_id: str, ip: str, user_agent: str, auth_type: str) -> None:
    """Enregistre une connexion (tâche de fond). Ouvre sa propre session DB.

    Ne lève jamais : toute erreur est journalisée puis ignorée.
    """
    try:
        device, os_name, browser = parse_user_agent(user_agent)
        country, city = await _geolocate(ip)

        event = LoginEvent(
            user_id=user_id,
            ip=(ip or None),
            country=country,
            city=city,
            device=device,
            os=os_name,
            browser=browser,
            user_agent=(user_agent or None),
            auth_type=auth_type,
        )
        async with db_manager.async_session_maker() as db:
            db.add(event)
            await db.commit()
        logger.info(
            "[login] user=%s depuis %s (%s) appareil=%s/%s/%s",
            user_id, ip, (city or country or "lieu inconnu"), device, os_name, browser,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("record_login failed: %s", type(exc).__name__)
