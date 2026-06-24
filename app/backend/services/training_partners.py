"""
Correspondance partenaire ↔ thématique de formation.

Logique légère et sans dépendance : on segmente la thématique demandée et les
`domains` du partenaire en mots significatifs, et on compte les recoupements.
Le tri privilégie d'abord la pertinence, puis les organismes gratuits (consigne
produit : « gratuit en premier, payant ensuite »).
"""
from __future__ import annotations

import re
from typing import List

# Mots vides ignorés pour ne garder que les termes porteurs de sens.
_STOPWORDS = {
    "de", "des", "du", "la", "le", "les", "et", "en", "un", "une", "pour",
    "avec", "sur", "au", "aux", "dans", "par", "professionnel", "professionnelle",
    "formation", "cours", "niveau", "base", "bases",
}


def _tokens(text: str) -> set[str]:
    """Mots significatifs (minuscules, sans accents simples, longueur >= 3)."""
    if not text:
        return set()
    lowered = text.lower()
    # Normalisation accents la plus courante pour fiabiliser les recoupements.
    for a, b in (("à", "a"), ("â", "a"), ("é", "e"), ("è", "e"), ("ê", "e"),
                 ("ï", "i"), ("î", "i"), ("ô", "o"), ("ù", "u"), ("û", "u"), ("ç", "c")):
        lowered = lowered.replace(a, b)
    words = re.split(r"[^a-z0-9]+", lowered)
    return {w for w in words if len(w) >= 3 and w not in _STOPWORDS}


def relevance_score(partner_domains: str, partner_name: str, theme: str) -> int:
    """Score de correspondance entre un partenaire et une thématique."""
    theme_tokens = _tokens(theme)
    if not theme_tokens:
        return 0
    domain_tokens = _tokens(partner_domains) | _tokens(partner_name)
    return len(theme_tokens & domain_tokens)


def rank_partners(partners: List, theme: str) -> List:
    """Trie les partenaires pour une thématique : pertinents d'abord, gratuits ensuite.

    `partners` est une liste d'objets exposant `.domains`, `.name`, `.pricing`.
    Tous les partenaires sont conservés (un organisme sans correspondance reste
    proposé en fin de liste) afin que le candidat ait toujours des options.
    """
    def sort_key(p):
        score = relevance_score(p.domains or "", p.name or "", theme)
        is_free = 1 if (p.pricing or "").lower() == "free" else 0
        # Pertinence décroissante, puis gratuit avant payant, puis nom stable.
        return (-score, -is_free, (p.name or "").lower())

    return sorted(partners, key=sort_key)
