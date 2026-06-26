"""
Coach d'entretien : prépare le candidat à un entretien pour une offre précise.

Hybride, comme la génération de CV / parcours de formation :
- moteur LOCAL sans clé (questions types personnalisées + méthode STAR + conseils),
- bascule automatique vers l'IA si `APP_AI_BASE_URL` + `APP_AI_KEY` sont configurés
  (sinon repli local).

Renvoie {'prep': markdown, 'ai_generated': bool}.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from core.config import settings
from schemas.aihub import ChatMessage, GenTxtRequest
from services.aihub import AIHubService, default_text_model
from services.cv_generator import _split_skills, match_profile_to_job

logger = logging.getLogger(__name__)


def ai_available() -> bool:
    return bool(
        getattr(settings, "app_ai_base_url", "") and getattr(settings, "app_ai_key", "")
    )


def _ai_instruction(profile: Dict[str, Any], job: Dict[str, Any], matched: List[str], missing: List[str]) -> str:
    return (
        "Tu es un coach carrière expert en entretiens d'embauche, pour le marché de "
        "l'emploi ouest-africain (francophone). Prépare le candidat ci-dessous à un "
        "entretien pour l'offre indiquée.\n\n"
        f"POSTE : {job.get('title')} chez {job.get('company')} (secteur {job.get('sector')}).\n"
        f"EXIGENCES DE L'OFFRE : {job.get('requirements')}\n"
        f"DESCRIPTION : {job.get('description')}\n"
        f"CANDIDAT : poste actuel {profile.get('job_title')}, "
        f"{profile.get('experience_years')} an(s) d'expérience, formation "
        f"{profile.get('education')}. Compétences correspondantes : {', '.join(matched) or '—'}. "
        f"Compétences à renforcer : {', '.join(missing) or '—'}.\n\n"
        "Rédige en français, au format Markdown, ces sections :\n"
        "1. **Questions générales probables** (3-4) — pour chacune, un angle de réponse conseillé.\n"
        "2. **Questions techniques / métier** (3-5) — tirées des exigences de l'offre, avec ce que "
        "le recruteur cherche à vérifier.\n"
        "3. **Questions comportementales** (2-3) — explique d'y répondre avec la méthode **STAR** "
        "(Situation, Tâche, Action, Résultat), avec un mini-exemple.\n"
        "4. **Tes atouts à mettre en avant** — d'après le profil.\n"
        "5. **Points de vigilance** — compétences à renforcer et comment les présenter positivement.\n"
        "6. **Questions à poser au recruteur** (3).\n"
        "7. **Conseils pratiques** (ponctualité, tenue, langage corporel, suivi après l'entretien).\n\n"
        "Sois concret, bienveillant et adapté au contexte africain francophone. "
        "N'ajoute aucun texte hors de la préparation."
    )


async def _generate_ai(profile: Dict[str, Any], job: Dict[str, Any], matched: List[str], missing: List[str]) -> str:
    service = AIHubService()
    request = GenTxtRequest(
        messages=[
            ChatMessage(
                role="system",
                content="Tu es un coach carrière expert en entretiens d'embauche. Tu produis "
                "des préparations structurées, concrètes et encourageantes, uniquement en Markdown.",
            ),
            ChatMessage(role="user", content=_ai_instruction(profile, job, matched, missing)),
        ],
        model=default_text_model(),
        temperature=0.6,
        max_tokens=2200,
    )
    response = await service.gentxt(request)
    content = (response.content or "").strip()
    if not content:
        raise RuntimeError("Réponse IA vide.")
    return content


def _generate_local(profile: Dict[str, Any], job: Dict[str, Any], matched: List[str], missing: List[str]) -> str:
    title = job.get("title") or "le poste"
    company = job.get("company") or "l'entreprise"
    reqs = [s.strip() for s in _split_skills(job.get("requirements")) if s.strip()][:5]

    lines: List[str] = []
    lines.append(f"# Préparation à l'entretien — {title}")
    lines.append(f"\n*Chez {company}. Prends 20-30 min pour préparer des réponses à voix haute.*")

    lines.append("\n## 1. Questions générales probables")
    lines.append(
        "- **« Parlez-moi de vous. »** → Présente en 1 min : ton métier actuel, "
        "ton expérience clé et pourquoi ce poste t'intéresse.\n"
        "- **« Pourquoi ce poste / cette entreprise ? »** → Relie tes compétences à l'offre "
        f"(« {title} ») et montre que tu connais {company}.\n"
        "- **« Quelles sont vos forces et vos faiblesses ? »** → Une force prouvée par un exemple ; "
        "une faiblesse + ce que tu fais pour progresser.\n"
        "- **« Où vous voyez-vous dans 3 ans ? »** → Montre de l'ambition réaliste, alignée avec le poste."
    )

    lines.append("\n## 2. Questions techniques / métier")
    if reqs:
        for r in reqs:
            lines.append(f"- Sur **{r}** : attends-toi à une question concrète. Prépare un exemple où tu l'as utilisé.")
    else:
        lines.append("- Prépare 2-3 exemples concrets de réalisations en lien direct avec le poste.")

    lines.append("\n## 3. Questions comportementales — méthode STAR")
    lines.append(
        "Pour « Parlez-moi d'une fois où… », structure ta réponse en **STAR** :\n"
        "- **S**ituation : le contexte en une phrase.\n"
        "- **T**âche : ce que tu devais accomplir.\n"
        "- **A**ction : ce que TU as fait concrètement.\n"
        "- **R**ésultat : l'impact, si possible chiffré.\n\n"
        "_Exemple_ : « Un client mécontent (S) ; je devais le retenir (T) ; j'ai analysé son "
        "problème et proposé une solution sous 24 h (A) ; il est resté et a recommandé nos services (R). »"
    )

    lines.append("\n## 4. Tes atouts à mettre en avant")
    if matched:
        lines.append("Insiste sur ces compétences qui collent à l'offre : **" + ", ".join(matched[:8]) + "**.")
    else:
        lines.append("Mets en avant tes réalisations concrètes et ta motivation pour ce poste précis.")

    lines.append("\n## 5. Points de vigilance")
    if missing:
        lines.append(
            "Le recruteur pourrait creuser : **" + ", ".join(missing[:6]) + "**. "
            "Sois honnête : montre ta capacité à apprendre vite et cite un exemple d'apprentissage rapide. "
            "_Astuce_ : nos formations peuvent t'aider à combler ces points."
        )
    else:
        lines.append("Ton profil couvre bien l'offre — reste concret et confiant.")

    lines.append("\n## 6. Questions à poser au recruteur")
    lines.append(
        "- À quoi ressemblerait une journée type à ce poste ?\n"
        "- Quels sont les défis prioritaires des 3 premiers mois ?\n"
        "- Comment l'équipe mesure-t-elle la réussite à ce poste ?"
    )

    lines.append("\n## 7. Conseils pratiques")
    lines.append(
        "- Arrive **10 min en avance**, tenue soignée et adaptée au secteur.\n"
        "- Regarde ton interlocuteur, souris, poignée de main ferme.\n"
        "- Apporte plusieurs CV imprimés et de quoi noter.\n"
        "- Après l'entretien, envoie un court message de remerciement.\n"
    )
    lines.append(
        "\n---\n*Préparation générée par EmploiCentral. Entraîne-toi à voix haute : "
        "c'est ce qui fait la différence le jour J. Bonne chance !*"
    )
    return "\n".join(lines)


async def generate_prep(profile: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, object]:
    """Renvoie {'prep': markdown, 'ai_generated': bool}."""
    match = match_profile_to_job(_split_skills(profile.get("skills")), job)
    matched, missing = match["matched"], match["missing"]

    if ai_available():
        try:
            prep = await _generate_ai(profile, job, matched, missing)
            return {"prep": prep, "ai_generated": True}
        except Exception as exc:  # noqa: BLE001 - dégradation gracieuse
            logger.warning("Génération IA du coaching échouée (%s); repli local", exc)
    return {"prep": _generate_local(profile, job, matched, missing), "ai_generated": False}
