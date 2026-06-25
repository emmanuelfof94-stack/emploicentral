"""
Génération de parcours de formation personnalisés.

Hybride, comme l'analyse de CV : si une IA est configurée (`APP_AI_BASE_URL` +
`APP_AI_KEY`), on lui demande un programme structuré ; sinon on retombe sur un
moteur de templating local (sans clé) qui produit un parcours cohérent à partir
de la thématique et du niveau.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

from core.config import settings
from schemas.aihub import ChatMessage, GenTxtRequest
from services.aihub import AIHubService

logger = logging.getLogger(__name__)

# Thématiques suggérées (le candidat peut aussi en saisir une libre).
SUGGESTED_THEMES: List[str] = [
    "Bureautique (Word, Excel, PowerPoint)",
    "Excel avancé",
    "Marketing digital",
    "Community management",
    "Anglais professionnel",
    "Comptabilité / Gestion",
    "Gestion de projet",
    "Vente et négociation commerciale",
    "Service client",
    "Ressources humaines",
    "Développement web",
    "Analyse de données",
    "Cybersécurité",
    "Communication professionnelle",
    "Leadership et management",
    "Logistique et supply chain",
    "Entrepreneuriat",
]

LEVELS: List[str] = ["Débutant", "Intermédiaire", "Avancé"]

# Bibliothèque de vraies ressources de formation gratuites (URLs réelles). Le
# générateur en sélectionne les plus pertinentes selon la thématique, et le prompt
# IA les fournit pour éviter que l'IA invente des liens.
_R = {
    "openclassrooms": ("OpenClassrooms", "https://openclassrooms.com", "cours en français, beaucoup gratuits, certifiants"),
    "coursera": ("Coursera", "https://www.coursera.org", "audit gratuit (vidéos sans le certificat)"),
    "funmooc": ("FUN MOOC", "https://www.fun-mooc.fr", "MOOC universitaires en français, gratuits"),
    "youtube": ("YouTube", "https://www.youtube.com", "chaînes spécialisées et tutoriels gratuits"),
    "alison": ("Alison", "https://alison.com", "cours et certificats gratuits"),
    "khan": ("Khan Academy", "https://fr.khanacademy.org", "fondamentaux, en français, gratuit"),
    "mslearn": ("Microsoft Learn", "https://learn.microsoft.com/fr-fr/training/", "Office, Excel, Azure, IA — gratuit"),
    "gcf": ("GCFGlobal", "https://edu.gcfglobal.org/fr/", "tutoriels bureautique en français, gratuit"),
    "google_ateliers": ("Google Ateliers Numériques", "https://learndigital.withgoogle.com/ateliersnumeriques", "marketing digital, certifs gratuites"),
    "hubspot": ("HubSpot Academy", "https://academy.hubspot.com", "marketing, vente, service client — certifs gratuites"),
    "meta": ("Meta Blueprint", "https://www.facebook.com/business/learn", "publicité et réseaux sociaux, gratuit"),
    "bbc": ("BBC Learning English", "https://www.bbc.co.uk/learningenglish", "anglais gratuit, tous niveaux"),
    "britishcouncil": ("British Council LearnEnglish", "https://learnenglish.britishcouncil.org", "anglais gratuit"),
    "freecodecamp": ("freeCodeCamp", "https://www.freecodecamp.org/francais/", "développement web, 100% gratuit"),
    "cisco": ("Cisco Networking Academy", "https://www.netacad.com", "réseaux, cybersécurité, Python — gratuit"),
    "ibm": ("IBM SkillsBuild", "https://skillsbuild.org", "compétences numériques en français, badges"),
    "elementsofai": ("Elements of AI", "https://www.elementsofai.com/fr", "intro à l'IA en français, certifiée"),
    "googleai": ("Google AI Essentials", "https://grow.google/ai-essentials/", "fondamentaux de l'IA"),
    "anthropic": ("Anthropic Academy", "https://www.anthropic.com/learn", "cours gratuits sur l'IA et l'usage de Claude (API, MCP, Claude Code)"),
    "openai_academy": ("OpenAI Academy", "https://academy.openai.com", "ateliers en direct, tutoriels et ressources IA gratuits"),
    "objectif_ia": ("Objectif IA (OpenClassrooms)", "https://openclassrooms.com/fr/courses/7050006-objectif-ia", "5h pour comprendre l'IA, en français, sans prérequis"),
    "edx": ("edX", "https://www.edx.org", "cours universitaires (ex. « AI For Everyone »), audit gratuit"),
}

# (mots-clés de thématique) -> clés de ressources prioritaires
_RESOURCE_RULES = [
    (("excel", "bureautique", "word", "powerpoint", "office"), ["mslearn", "gcf", "openclassrooms", "youtube"]),
    (("marketing", "community", "digital", "communication", "réseaux", "reseaux"), ["google_ateliers", "hubspot", "meta", "openclassrooms"]),
    (("anglais", "english", "langue"), ["bbc", "britishcouncil", "youtube"]),
    (("comptab", "gestion", "finance", "audit", "paie"), ["openclassrooms", "alison", "funmooc", "coursera"]),
    (("projet", "management", "leadership", "ressources humaines", "rh"), ["coursera", "openclassrooms", "alison"]),
    (("web", "dévelop", "develop", "data", "données", "donnees", "informatique", "cyber", "program", "code"), ["freecodecamp", "cisco", "openclassrooms", "coursera"]),
    (("vente", "commercial", "négoci", "negoci", "client"), ["hubspot", "openclassrooms", "coursera", "alison"]),
    (("ia", "intelligence artificielle", "machine learning", "data science"), ["anthropic", "openai_academy", "googleai", "elementsofai", "objectif_ia", "ibm", "coursera", "mslearn", "edx"]),
    (("entrepreneur", "création", "creation", "business"), ["coursera", "openclassrooms", "funmooc", "alison"]),
]

_GENERAL_RESOURCES = ["openclassrooms", "coursera", "funmooc", "youtube", "alison"]


def _curated_resource_keys(theme: str) -> List[str]:
    low = (theme or "").lower()
    keys: List[str] = []
    for keywords, res_keys in _RESOURCE_RULES:
        # limite de mot en début de mot-clé : "ia" ne matche plus "négociation",
        # tout en gardant les préfixes ("dévelop" matche "développement").
        if any(re.search(r"\b" + re.escape(k), low) for k in keywords):
            keys.extend(res_keys)
    if not keys:
        keys = list(_GENERAL_RESOURCES)
    # dédup en conservant l'ordre, max 8 (les thématiques IA ont une liste plus riche)
    seen, ordered = set(), []
    for k in keys:
        if k not in seen:
            seen.add(k)
            ordered.append(k)
    return ordered[:8]


def _resources_markdown(theme: str) -> str:
    lines = []
    for k in _curated_resource_keys(theme):
        name, url, note = _R[k]
        lines.append(f"- [{name}]({url}) — {note}")
    return "\n".join(lines)


def ai_available() -> bool:
    return bool(
        getattr(settings, "app_ai_base_url", "") and getattr(settings, "app_ai_key", "")
    )


def _ai_model() -> str:
    """Modèle de génération de texte, configurable selon le fournisseur branché.

    Défaut = modèle de la plateforme atoms (`deepseek-v4-pro`). Avec un autre
    fournisseur (Groq, Gemini…), poser `APP_AI_MODEL` (ex. `llama-3.3-70b-versatile`).
    """
    return (getattr(settings, "app_ai_model", "") or "").strip() or "deepseek-v4-pro"


def _ai_instruction(theme: str, level: str, objective: str, profile_summary: str) -> str:
    ctx = []
    if level:
        ctx.append(f"Niveau visé : {level}.")
    if objective:
        ctx.append(f"Objectif du candidat : {objective}.")
    if profile_summary:
        ctx.append(f"Profil du candidat : {profile_summary}.")
    context = " ".join(ctx)
    resources = _resources_markdown(theme)
    return (
        "Tu es un conseiller en formation pour le marché de l'emploi ouest-africain. "
        f"Conçois un parcours de formation complet et concret sur la thématique : « {theme} ». "
        f"{context}\n\n"
        "Rédige en français, au format Markdown, avec ces sections :\n"
        "1. **Objectifs pédagogiques** (3 à 5 puces)\n"
        "2. **Prérequis**\n"
        "3. **Programme par modules** : pour chaque module, un titre, une durée estimée, "
        "et 2 à 4 points clés abordés\n"
        "4. **Projet pratique** à réaliser pour ancrer les acquis\n"
        "5. **Ressources recommandées** : utilise EN PRIORITÉ ces plateformes gratuites "
        "réelles (garde les liens exacts, n'en invente pas d'autres) :\n"
        f"{resources}\n"
        "6. **Durée totale estimée** et rythme conseillé\n\n"
        "Sois concret, adapté au contexte africain francophone, et réaliste pour un "
        "apprenant en autonomie. N'ajoute aucun texte hors du parcours."
    )


async def _generate_ai(theme: str, level: str, objective: str, profile_summary: str) -> str:
    service = AIHubService()
    request = GenTxtRequest(
        messages=[
            ChatMessage(
                role="system",
                content="Tu es un expert en ingénierie de formation. Tu produis des parcours "
                "structurés, concrets et réalistes, uniquement en Markdown.",
            ),
            ChatMessage(
                role="user",
                content=_ai_instruction(theme, level, objective, profile_summary),
            ),
        ],
        model=_ai_model(),
        temperature=0.6,
        max_tokens=2000,
    )
    response = await service.gentxt(request)
    content = (response.content or "").strip()
    if not content:
        raise RuntimeError("Réponse IA vide.")
    return content


def _generate_local(theme: str, level: str, objective: str) -> str:
    """Parcours générique mais structuré, sans appel externe."""
    level = level or "Débutant"
    lvl_low = level.lower()
    if "avanc" in lvl_low:
        modules = [
            ("Module 1 — Consolidation des fondamentaux", "1 semaine"),
            ("Module 2 — Techniques avancées", "2 semaines"),
            ("Module 3 — Cas pratiques complexes", "2 semaines"),
            ("Module 4 — Optimisation et bonnes pratiques", "1 semaine"),
            ("Module 5 — Projet professionnel complet", "2 semaines"),
        ]
    elif "interm" in lvl_low:
        modules = [
            ("Module 1 — Rappels essentiels", "1 semaine"),
            ("Module 2 — Approfondissement des concepts", "2 semaines"),
            ("Module 3 — Mise en pratique guidée", "2 semaines"),
            ("Module 4 — Projet appliqué", "1 semaine"),
        ]
    else:
        modules = [
            ("Module 1 — Découverte et vocabulaire", "1 semaine"),
            ("Module 2 — Notions de base pas à pas", "2 semaines"),
            ("Module 3 — Premiers exercices guidés", "1 semaine"),
            ("Module 4 — Mini-projet d'application", "1 semaine"),
        ]

    lines: List[str] = []
    lines.append(f"# Parcours de formation : {theme}")
    lines.append(f"\n*Niveau : {level}*")
    if objective:
        lines.append(f"\n> 🎯 Objectif visé : {objective}")
    lines.append("\n## 1. Objectifs pédagogiques")
    lines.append(
        f"- Acquérir des bases solides en {theme.lower()}\n"
        f"- Être capable de mettre en pratique sur des cas concrets\n"
        f"- Gagner en autonomie et en confiance sur le sujet\n"
        f"- Valoriser cette compétence sur votre CV et en entretien"
    )
    lines.append("\n## 2. Prérequis")
    lines.append(
        "- Motivation et régularité\n"
        "- Un ordinateur ou smartphone avec connexion internet\n"
        "- Aucune connaissance préalable requise pour démarrer au niveau débutant"
    )
    lines.append("\n## 3. Programme par modules")
    for title, dur in modules:
        lines.append(f"\n### {title} _({dur})_")
        lines.append(
            "- Concepts clés et terminologie\n"
            "- Démonstrations et exemples concrets\n"
            "- Exercices d'application corrigés"
        )
    lines.append("\n## 4. Projet pratique")
    lines.append(
        f"Réalisez un projet personnel mobilisant **{theme}** de bout en bout "
        "(par exemple un livrable réutilisable dans votre futur poste), à présenter "
        "comme preuve de compétence."
    )
    lines.append("\n## 5. Ressources recommandées (gratuites)")
    lines.append(_resources_markdown(theme))
    total = sum(int(d.split()[0]) for _, d in modules)
    lines.append("\n## 6. Durée totale estimée")
    lines.append(
        f"Environ **{total} semaines** à raison de 5 à 7 h par semaine. "
        "Adaptez le rythme à vos disponibilités."
    )
    lines.append(
        "\n---\n*Parcours généré automatiquement par EmploiCentral. "
        "Notre équipe a été notifiée de votre demande et pourra vous recontacter "
        "avec des ressources complémentaires.*"
    )
    return "\n".join(lines)


# Packs de formation « maison » mis en avant (dossiers Drive partagés). Affichés
# EN PLUS du parcours quand la thématique correspond. ⚠️ Chaque dossier doit être
# partagé en « Tout utilisateur disposant du lien » pour être accessible aux candidats.
FEATURED_PACKS = [
    {
        "title": "Pack Data Analyst",
        "url": "https://drive.google.com/drive/folders/1oPP1M7MNkHgg10ChU-NS18T8JX1QcbFM",
        "desc": "Pack complet Data Analyst (Excel, Power BI, SQL…) — supports et exercices fournis",
        "keywords": [
            "data", "données", "donnees", "analyst", "analyse de données", "analyse de donnees",
            "excel", "power bi", "powerbi", "sql", "business intelligence", "tableau de bord",
        ],
    },
]


def _matching_packs(theme: str) -> List[Dict[str, str]]:
    low = (theme or "").lower()
    out = []
    for p in FEATURED_PACKS:
        if any(re.search(r"\b" + re.escape(k), low) for k in p["keywords"]):
            out.append(p)
    return out


def _packs_markdown(theme: str) -> str:
    packs = _matching_packs(theme)
    if not packs:
        return ""
    lines = ["\n## 📦 Formation recommandée par EmploiCentral"]
    for p in packs:
        lines.append(f"- [{p['title']}]({p['url']}) — {p['desc']}")
    return "\n".join(lines)


async def generate_program(
    theme: str,
    level: str = "",
    objective: str = "",
    profile_summary: str = "",
) -> Dict[str, object]:
    """Renvoie {'program': markdown, 'ai_generated': bool}."""
    theme = (theme or "").strip()
    if not theme:
        raise ValueError("Thématique requise.")
    ai_generated = False
    program = None
    if ai_available():
        try:
            program = await _generate_ai(theme, level, objective, profile_summary)
            ai_generated = True
        except Exception as exc:  # noqa: BLE001 - dégradation gracieuse
            logger.warning("Génération IA du parcours échouée (%s); repli local", exc)
    if program is None:
        program = _generate_local(theme, level, objective)
    # Ajoute les packs maison pertinents (Drive) après le parcours, IA ou local.
    packs = _packs_markdown(theme)
    if packs:
        program = program.rstrip() + "\n\n" + packs
    return {"program": program, "ai_generated": ai_generated}
