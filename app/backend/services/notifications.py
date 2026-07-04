"""
Notifications d'alerte emploi (in-app + email + WhatsApp).

Après chaque cycle d'agrégation, on compare les offres actives aux alertes des
candidats et on notifie les nouvelles correspondances. Canaux:
- **in-app** : toujours actif (table `notifications`, sert aussi de dédup user+job).
- **email** : actif si SMTP configuré (SMTP_HOST/USER/PASSWORD).
- **WhatsApp** : actif si Twilio (TWILIO_*) ou Meta Cloud API (META_WA_*) configuré.

Tout est best-effort : un canal non configuré ou en échec est simplement ignoré.
Compatible Python 3.9.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select

from core.database import db_manager
from models.alert_preferences import Alert_preferences
from models.job_offers import Job_offers
from models.notifications import Notification
from models.user_profiles import User_profiles
from services.cv_heuristic import score_profile_job

logger = logging.getLogger(__name__)

# Taille du « top » personnalisé envoyé par passe et par utilisateur : on classe
# les nouvelles offres correspondantes par score de compatibilité décroissant et
# on ne garde que les N meilleures (digest unique au lieu d'une liste brute).
ALERT_TOP_N = max(1, int(os.environ.get("ALERT_TOP_N", 3)))
# Plafond absolu de notifications créées par utilisateur et par passe (anti-flood).
MAX_NOTIFS_PER_USER = max(1, int(os.environ.get("ALERT_MAX_PER_USER", 15)))
# Seuil de compatibilité minimal pour figurer dans le digest (0 = désactivé). Laissé
# à 0 par défaut : `_matches` a déjà validé la pertinence selon les critères du
# candidat (un mot-clé explicite peut légitimement scorer bas sur le profil CV).
ALERT_MIN_SCORE = max(0, min(100, int(os.environ.get("ALERT_MIN_SCORE", 0))))


# --------------------------------------------------------------------------- #
# Disponibilité des canaux (selon config)
# --------------------------------------------------------------------------- #
def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def email_available() -> bool:
    return bool(_env("SMTP_HOST") and _env("SMTP_USER") and _env("SMTP_PASSWORD"))


def twilio_available() -> bool:
    return bool(_env("TWILIO_ACCOUNT_SID") and _env("TWILIO_AUTH_TOKEN") and _env("TWILIO_WHATSAPP_FROM"))


def meta_available() -> bool:
    return bool(_env("META_WA_TOKEN") and _env("META_WA_PHONE_ID"))


def whatsapp_available() -> bool:
    return twilio_available() or meta_available()


# --------------------------------------------------------------------------- #
# Matching offre / alerte (aligné sur le frontend jobMatches)
# --------------------------------------------------------------------------- #
def _csv(s: Optional[str]) -> List[str]:
    # Le frontend sépare secteurs/lieux/contrats par "|" et les mots-clés par ",".
    # On tolère les deux (le matching reste un test de sous-chaîne, donc sur-découper
    # "Dakar, Sénégal" est sans conséquence).
    return [x.strip().lower() for x in re.split(r"[|,;\n]", s or "") if x.strip()]


def _max_salary(rng: Optional[str]) -> int:
    nums = re.findall(r"\d+", (rng or "").replace(" ", ""))
    return max((int(n) for n in nums), default=0)


def _has_criteria(pref: Alert_preferences) -> bool:
    return bool(
        _csv(pref.sectors) or _csv(pref.locations) or _csv(pref.contract_types)
        or _csv(pref.keywords) or (pref.min_salary and pref.min_salary > 0)
    )


def _is_placeholder_email(email: str) -> bool:
    """Adresses de comptes de démo/test → à ne pas notifier par email."""
    low = (email or "").lower()
    return (not low) or low.endswith("@demo.com") or low.startswith("browser_")


def match_offer_to_profile(job: Job_offers, profile: User_profiles) -> bool:
    """Critères IMPLICITES depuis le profil (secteur + chevauchement de compétences)."""
    psector = (profile.sector or "").lower().strip()
    jsector = (job.sector or "").lower().strip()
    if psector and jsector and (psector in jsector or jsector in psector):
        return True
    skills = [s.strip().lower() for s in (profile.skills or "").split(",") if len(s.strip()) >= 3]
    if skills:
        hay = f"{job.title} {job.requirements or ''} {job.description or ''}".lower()
        if any(s in hay for s in skills):
            return True
    return False


def match_offer(job: Job_offers, pref: Alert_preferences) -> bool:
    if not job.is_active:
        return False
    sectors, locations = _csv(pref.sectors), _csv(pref.locations)
    contracts, keywords = _csv(pref.contract_types), _csv(pref.keywords)

    if sectors and not any(s in (job.sector or "").lower() for s in sectors):
        return False
    if locations and not any(l in (job.location or "").lower() for l in locations):
        return False
    if contracts and not any(c in (job.contract_type or "").lower() for c in contracts):
        return False
    if keywords:
        hay = f"{job.title} {job.description or ''} {job.requirements or ''}".lower()
        if not any(k in hay for k in keywords):
            return False
    # Salaire : on ne filtre QUE si l'offre affiche un salaire. Les offres agrégées
    # n'ont quasi jamais de salaire renseigné ; appliquer min_salary à celles-ci
    # viderait tout le feed (piège récurrent). On ne rejette donc que les offres
    # dont le salaire affiché est sous le seuil.
    if pref.min_salary and pref.min_salary > 0:
        offer_salary = _max_salary(job.salary_range)
        if offer_salary and offer_salary < pref.min_salary:
            return False
    return True


# --------------------------------------------------------------------------- #
# Envoi par canal (best-effort)
# --------------------------------------------------------------------------- #
def _send_email_sync(to_addr: str, subject: str, html: str) -> None:
    host, port = _env("SMTP_HOST"), int(_env("SMTP_PORT") or 587)
    user, password = _env("SMTP_USER"), _env("SMTP_PASSWORD")
    from_addr = _env("SMTP_FROM") or user
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.attach(MIMEText(re.sub(r"<[^>]+>", "", html), "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP(host, port, timeout=20) as server:
        if (_env("SMTP_USE_TLS") or "true").lower() in ("1", "true", "yes", "on"):
            server.starttls()
        server.login(user, password)
        server.sendmail(from_addr, [to_addr], msg.as_string())


async def send_email(to_addr: str, subject: str, html: str) -> bool:
    if not (email_available() and to_addr):
        return False
    try:
        await asyncio.to_thread(_send_email_sync, to_addr, subject, html)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Envoi email échoué (%s): %s", to_addr, exc)
        return False


def _normalize_phone(phone: str) -> str:
    """Met le numéro au format international E.164 (ex. +2250749109013).

    WhatsApp exige l'indicatif pays. Les numéros ivoiriens sont saisis en local
    (« 0749109013 ») → on préfixe l'indicatif par défaut (`WHATSAPP_DEFAULT_CC`,
    225 pour la Côte d'Ivoire) en conservant le 0 initial (format CI post-2021).
    """
    p = re.sub(r"[^\d+]", "", phone or "")
    if not p:
        return ""
    if p.startswith("+"):
        return p
    if p.startswith("00"):
        return "+" + p[2:]
    cc = _env("WHATSAPP_DEFAULT_CC") or "225"
    # Numéro déjà préfixé par l'indicatif sans "+" (ex. 2250749109013).
    if p.startswith(cc) and len(p) >= 12:
        return "+" + p
    # Numéro local (commence par 0 en CI) → on ajoute l'indicatif.
    return "+" + cc + p


async def _send_whatsapp_twilio(to_phone: str, body: str) -> bool:
    sid, token = _env("TWILIO_ACCOUNT_SID"), _env("TWILIO_AUTH_TOKEN")
    sender = _env("TWILIO_WHATSAPP_FROM")  # ex: whatsapp:+14155238886
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    data = {"From": sender, "To": f"whatsapp:{to_phone}", "Body": body}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(url, data=data, auth=(sid, token))
            if r.status_code >= 400:
                logger.warning("Twilio WhatsApp %s: HTTP %s %s", to_phone, r.status_code, r.text[:200])
                return False
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Twilio WhatsApp échoué (%s): %s", to_phone, exc)
        return False


async def _send_whatsapp_meta(to_phone: str, body: str) -> bool:
    token, phone_id = _env("META_WA_TOKEN"), _env("META_WA_PHONE_ID")
    url = f"https://graph.facebook.com/v20.0/{phone_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone.lstrip("+"),
        "type": "text",
        "text": {"body": body},
    }
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code >= 400:
                logger.warning("Meta WhatsApp %s: HTTP %s %s", to_phone, r.status_code, r.text[:200])
                return False
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Meta WhatsApp échoué (%s): %s", to_phone, exc)
        return False


async def _send_whatsapp_meta_template(to_phone: str, name: str, params: List[str], lang: str) -> bool:
    """Envoi d'un message *template* Meta (obligatoire pour un message proactif
    hors fenêtre de 24 h). `params` alimente les variables {{1}}, {{2}}… du corps."""
    token, phone_id = _env("META_WA_TOKEN"), _env("META_WA_PHONE_ID")
    url = f"https://graph.facebook.com/v20.0/{phone_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone.lstrip("+"),
        "type": "template",
        "template": {
            "name": name,
            "language": {"code": lang or "fr"},
            "components": [{
                "type": "body",
                "parameters": [{"type": "text", "text": str(p)} for p in params],
            }] if params else [],
        },
    }
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code >= 400:
                logger.warning("Meta WhatsApp template %s: HTTP %s %s", to_phone, r.status_code, r.text[:200])
                return False
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Meta WhatsApp template échoué (%s): %s", to_phone, exc)
        return False


async def send_whatsapp(to_phone: str, body: str, params: Optional[List[str]] = None) -> bool:
    phone = _normalize_phone(to_phone)
    if not phone:
        return False
    if twilio_available():
        return await _send_whatsapp_twilio(phone, body)
    if meta_available():
        # En production Meta, un message proactif DOIT passer par un template
        # approuvé. Si `META_WA_TEMPLATE` est défini, on l'utilise ; sinon on
        # retombe sur le texte libre (valable seulement en fenêtre 24 h / test).
        template = _env("META_WA_TEMPLATE")
        if template:
            return await _send_whatsapp_meta_template(
                phone, template, params or [], _env("META_WA_TEMPLATE_LANG") or "fr"
            )
        return await _send_whatsapp_meta(phone, body)
    return False


async def send_whatsapp_debug(to_phone: str, params: Optional[List[str]] = None) -> Dict[str, Any]:
    """Envoi de diagnostic (admin) : effectue l'envoi et renvoie le DÉTAIL de la
    réponse (statut HTTP + corps Meta), pour tester la config sans deviner."""
    phone = _normalize_phone(to_phone)
    out: Dict[str, Any] = {"to": phone, "provider": None, "ok": False}
    if not phone:
        out["error"] = "numéro vide ou invalide"
        return out
    if not whatsapp_available():
        out["error"] = "aucun fournisseur WhatsApp configuré (META_WA_TOKEN / META_WA_PHONE_ID absents)"
        return out
    if twilio_available():
        out["provider"] = "twilio"
        out["ok"] = await _send_whatsapp_twilio(phone, "Test EmploiCentral")
        return out
    out["provider"] = "meta"
    template = _env("META_WA_TEMPLATE")
    token, phone_id = _env("META_WA_TOKEN"), _env("META_WA_PHONE_ID")
    out["template"] = template or "(texte libre)"
    url = f"https://graph.facebook.com/v20.0/{phone_id}/messages"
    if template:
        payload = {
            "messaging_product": "whatsapp", "to": phone.lstrip("+"), "type": "template",
            "template": {
                "name": template, "language": {"code": _env("META_WA_TEMPLATE_LANG") or "fr"},
                "components": [{"type": "body", "parameters": [{"type": "text", "text": str(p)} for p in params]}] if params else [],
            },
        }
    else:
        payload = {"messaging_product": "whatsapp", "to": phone.lstrip("+"), "type": "text",
                   "text": {"body": "Test EmploiCentral"}}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(url, json=payload, headers={"Authorization": f"Bearer {token}"})
        out["status"] = r.status_code
        out["response"] = r.text[:600]
        out["ok"] = r.status_code < 400
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)[:300]
    return out


async def list_whatsapp_templates() -> Dict[str, Any]:
    """Liste les modèles WhatsApp du compte (nom + code langue + statut) pour
    diagnostiquer les erreurs de type « template does not exist in <lang> »."""
    token, phone_id = _env("META_WA_TOKEN"), _env("META_WA_PHONE_ID")
    out: Dict[str, Any] = {"templates": []}
    if not (token and phone_id):
        out["error"] = "META_WA_TOKEN / META_WA_PHONE_ID absents"
        return out
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            # 1) Trouver le compte WhatsApp Business (WABA) du numéro.
            r1 = await client.get(
                f"https://graph.facebook.com/v20.0/{phone_id}",
                params={"fields": "whatsapp_business_account", "access_token": token},
            )
            waba = (r1.json().get("whatsapp_business_account") or {}).get("id")
            out["waba_id"] = waba
            if not waba:
                out["error"] = f"WABA introuvable: {r1.text[:200]}"
                return out
            # 2) Lister ses modèles.
            r2 = await client.get(
                f"https://graph.facebook.com/v20.0/{waba}/message_templates",
                params={"fields": "name,language,status,category", "limit": 100, "access_token": token},
            )
            data = r2.json().get("data", [])
            out["templates"] = [
                {"name": t.get("name"), "language": t.get("language"),
                 "status": t.get("status"), "category": t.get("category")}
                for t in data
            ]
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)[:300]
    return out


# --------------------------------------------------------------------------- #
# Contenu des messages
# --------------------------------------------------------------------------- #
def _offer_email_html(offer: Dict[str, Any]) -> str:
    parts = [f"<h2>{offer['title']}</h2>"]
    meta = " — ".join(x for x in [offer.get("company"), offer.get("location"), offer.get("contract_type")] if x)
    if meta:
        parts.append(f"<p><b>{meta}</b></p>")
    if offer.get("salary_range"):
        parts.append(f"<p>💰 {offer['salary_range']}</p>")
    if offer.get("description"):
        parts.append(f"<p>{offer['description'][:400]}…</p>")
    if offer.get("source_url"):
        parts.append(f'<p><a href="{offer["source_url"]}">Voir l\'offre</a> (source : {offer.get("source","")})</p>')
    parts.append("<hr><p style='color:#888;font-size:12px'>EmploiCentral — alerte emploi</p>")
    return "".join(parts)


def _offer_whatsapp_text(offer: Dict[str, Any]) -> str:
    lines = [f"🔔 Nouvelle offre : {offer['title']}"]
    meta = " — ".join(x for x in [offer.get("company"), offer.get("location"), offer.get("contract_type")] if x)
    if meta:
        lines.append(meta)
    if offer.get("salary_range"):
        lines.append(f"💰 {offer['salary_range']}")
    if offer.get("source_url"):
        lines.append(offer["source_url"])
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Scoring de compatibilité (réutilise le moteur heuristique offline)
# --------------------------------------------------------------------------- #
def _profile_score_dict(profile: User_profiles) -> Dict[str, Any]:
    """Champs du profil attendus par score_profile_job."""
    return {
        "skills": profile.skills,
        "sector": profile.sector,
        "location": profile.location,
        "experience_years": profile.experience_years,
    }


def _job_score_dict(job: Job_offers) -> Dict[str, Any]:
    """Champs de l'offre attendus par score_profile_job."""
    return {
        "title": job.title,
        "requirements": job.requirements,
        "description": job.description,
        "sector": job.sector,
        "location": job.location,
    }


def _compatibility_score(profile: User_profiles, job: Job_offers) -> int:
    """Score 0-100 (déterministe, sans appel externe) profil↔offre."""
    try:
        return int(score_profile_job(_profile_score_dict(profile), _job_score_dict(job)).get("score", 0))
    except Exception:  # noqa: BLE001 - le scoring ne doit jamais bloquer le dispatch
        return 0


# --------------------------------------------------------------------------- #
# Digest « top N » : un seul message regroupant les meilleures offres classées
# --------------------------------------------------------------------------- #
def _digest_subject(scored: List[Dict[str, Any]]) -> str:
    n = len(scored)
    best = scored[0]["score"] if scored else 0
    if n == 1:
        return f"🎯 1 offre faite pour vous ({best}%) — {scored[0]['title']}"
    return f"🎯 Vos {n} meilleures offres du moment ({best}% pour la 1ʳᵉ)"


def _score_badge(score: int) -> str:
    """Petit indicateur visuel selon le niveau de compatibilité."""
    if score >= 80:
        return "🟢"
    if score >= 60:
        return "🟡"
    return "🟠"


def _digest_email_html(first_name: str, scored: List[Dict[str, Any]]) -> str:
    hello = f"Bonjour {first_name}," if first_name else "Bonjour,"
    parts = [
        f"<p>{hello}</p>",
        f"<p>Voici <b>{len(scored)} offre(s)</b> classée(s) par compatibilité avec votre profil :</p>",
    ]
    for rank, item in enumerate(scored, start=1):
        offer, score = item["offer"], item["score"]
        meta = " — ".join(
            x for x in [offer.get("company"), offer.get("location"), offer.get("contract_type")] if x
        )
        parts.append(
            "<div style='margin:14px 0;padding:12px 14px;border:1px solid #eee;border-radius:8px'>"
            f"<div style='font-size:13px;color:#16a34a;font-weight:600'>{_score_badge(score)} "
            f"Compatibilité {score}%</div>"
            f"<div style='font-size:16px;font-weight:700;margin-top:2px'>#{rank} · {offer['title']}</div>"
        )
        if meta:
            parts.append(f"<div style='color:#555'>{meta}</div>")
        if offer.get("salary_range"):
            parts.append(f"<div>💰 {offer['salary_range']}</div>")
        if offer.get("source_url"):
            parts.append(
                f"<div style='margin-top:6px'><a href=\"{offer['source_url']}\">Voir l'offre</a>"
                f" (source : {offer.get('source', '')})</div>"
            )
        parts.append("</div>")
    parts.append("<hr><p style='color:#888;font-size:12px'>EmploiCentral — votre top offres personnalisé. "
                 "Vous pouvez ajuster vos critères dans l'onglet Alertes.</p>")
    return "".join(parts)


def _digest_whatsapp_text(first_name: str, scored: List[Dict[str, Any]]) -> str:
    head = f"🎯 EmploiCentral — vos {len(scored)} meilleures offres"
    if first_name:
        head += f", {first_name}"
    lines = [head, ""]
    for rank, item in enumerate(scored, start=1):
        offer, score = item["offer"], item["score"]
        lines.append(f"{rank}. {_score_badge(score)} {score}% · {offer['title']}")
        meta = " — ".join(
            x for x in [offer.get("company"), offer.get("location"), offer.get("contract_type")] if x
        )
        if meta:
            lines.append(f"   {meta}")
        if offer.get("source_url"):
            lines.append(f"   {offer['source_url']}")
        lines.append("")
    return "\n".join(lines).rstrip()


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
async def dispatch_new_offer_alerts() -> int:
    """Notifie chaque candidat de ses MEILLEURES nouvelles offres (top N personnalisé).

    Pour chaque candidat, les nouvelles offres correspondantes sont classées par
    score de compatibilité (moteur heuristique offline) et seules les ALERT_TOP_N
    meilleures sont retenues : une notification in-app par offre (portant le score)
    + un unique digest email/WhatsApp regroupant le classement, au lieu d'une liste
    brute. Email activé PAR DÉFAUT (opt-out via `notify_email=false`). Filtrage :
    critères d'alerte explicites s'ils existent, sinon critères implicites depuis le
    profil (secteur/compétences). Renvoie le nb de notifications créées."""
    if not db_manager.async_session_maker:
        return 0

    created = 0
    to_send: List[Dict[str, Any]] = []  # tâches d'envoi externe (hors session)

    async with db_manager.async_session_maker() as session:
        # Candidats = profils avec CV analysé (évite les comptes vides/de test).
        profiles = (await session.execute(
            select(User_profiles).where(User_profiles.cv_analyzed == True)
        )).scalars().all()

        prefs_rows = (await session.execute(select(Alert_preferences))).scalars().all()
        prefs_by_user: Dict[str, Alert_preferences] = {}
        for p in prefs_rows:
            prefs_by_user.setdefault(p.user_id, p)

        offers = (await session.execute(
            select(Job_offers).where(Job_offers.is_active == True).order_by(Job_offers.id.desc()).limit(300)
        )).scalars().all()

        for profile in profiles:
            user_id = profile.user_id
            email = (profile.email or "").strip()
            phone = (profile.phone or "").strip()
            pref = prefs_by_user.get(user_id)

            # Alertes mises en pause explicitement → on ignore ce candidat.
            if pref is not None and pref.is_active is False:
                continue

            # Canaux : email ON par défaut (opt-out via notify_email=false) ;
            # WhatsApp reste opt-in (nécessite numéro + fournisseur).
            email_on = True if (pref is None or pref.notify_email is None) else bool(pref.notify_email)
            whatsapp_on = bool(pref.notify_whatsapp) if pref is not None else False

            # Choix du matcher : critères explicites prioritaires, sinon profil.
            if pref is not None and _has_criteria(pref):
                def _matches(job, _pref=pref):
                    return match_offer(job, _pref)
            else:
                def _matches(job, _prof=profile):
                    return match_offer_to_profile(job, _prof)

            already = set((await session.execute(
                select(Notification.job_id).where(Notification.user_id == user_id)
            )).scalars().all())

            # 1) Rassemble toutes les NOUVELLES offres correspondantes, puis classe-les
            #    par score de compatibilité décroissant et ne garde que le top N.
            candidates: List[tuple] = []  # (score, job)
            for job in offers:
                if job.id in already or not _matches(job):
                    continue
                score = _compatibility_score(profile, job)
                if score < ALERT_MIN_SCORE:
                    continue
                candidates.append((score, job))
            if not candidates:
                continue
            # Tri par score décroissant ; à score égal, l'offre la plus récente (id) d'abord.
            candidates.sort(key=lambda sj: (sj[0], sj[1].id), reverse=True)
            top = candidates[: min(ALERT_TOP_N, MAX_NOTIFS_PER_USER)]

            # Canaux externes effectivement disponibles pour ce candidat.
            email_ok = bool(email_on and email_available() and email and not _is_placeholder_email(email))
            whatsapp_ok = bool(whatsapp_on and whatsapp_available() and phone)

            # 2) Une notification in-app par offre du top (sert de dédup + porte le score).
            scored_offers: List[Dict[str, Any]] = []  # pour le digest unique
            for score, job in top:
                offer_dict = {
                    "title": job.title, "company": job.company, "location": job.location,
                    "contract_type": job.contract_type, "salary_range": job.salary_range,
                    "description": job.description, "source": job.source, "source_url": job.source_url,
                }
                channels = ["in_app"]
                if email_ok:
                    channels.append("email")
                if whatsapp_ok:
                    channels.append("whatsapp")
                session.add(Notification(
                    user_id=user_id, job_id=job.id,
                    title=f"{_score_badge(score)} {score}% · {job.title}",
                    body=" — ".join(x for x in [job.company, job.location, job.contract_type] if x),
                    channels=",".join(channels), is_read=False,
                ))
                already.add(job.id)
                created += 1
                scored_offers.append({"score": score, "title": job.title, "offer": offer_dict})

            # 3) Un SEUL digest email + un SEUL WhatsApp regroupant le top N classé.
            first_name = (profile.full_name or "").strip().split(" ")[0] if profile.full_name else ""
            if email_ok:
                to_send.append({"type": "email", "to": email,
                                "subject": _digest_subject(scored_offers),
                                "html": _digest_email_html(first_name, scored_offers)})
            if whatsapp_ok:
                # Paramètres du template WhatsApp Meta : {{1}} prénom, {{2}} nb
                # d'offres, {{3}} lien. (Ignorés si envoi en texte libre.)
                wa_link = (_env("FRONTEND_URL") or "https://emploicentral.onrender.com").rstrip("/") + "/jobs"
                wa_params = [first_name or "candidat", str(len(scored_offers)), wa_link]
                to_send.append({"type": "whatsapp", "to": phone,
                                "body": _digest_whatsapp_text(first_name, scored_offers),
                                "params": wa_params})

        await session.commit()

    # Envois externes après commit (best-effort, n'impacte pas la dédup in-app).
    for task in to_send:
        if task["type"] == "email":
            await send_email(task["to"], task["subject"], task["html"])
        elif task["type"] == "whatsapp":
            await send_whatsapp(task["to"], task["body"], params=task.get("params"))

    if created:
        logger.info("Alertes: %d notification(s) créée(s) (%d envoi(s) externe(s))", created, len(to_send))
    return created
