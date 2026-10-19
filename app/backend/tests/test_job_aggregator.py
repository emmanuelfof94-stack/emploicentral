"""Agrégateur : fonctions PURES uniquement (aucun appel réseau)."""
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from services import job_aggregator as agg


# ---------- normalize_sector ----------
@pytest.mark.parametrize("title,raw,expected", [
    ("Développeur Full Stack", None, "Informatique / Tech"),
    ("Comptable senior", None, "Comptabilité / Audit"),
    ("Business Developer", None, "Commerce / Vente"),          # pas un poste de développeur
    ("Chef de projet informatique", None, "Informatique / Tech"),  # métier précis > fonction transverse
    ("Assistante de direction", None, "Administration / Secrétariat"),
    ("Infirmier diplômé d'État", None, "Santé"),
    ("Responsable", "Banque / Finance", "Finance / Banque"),     # libellé source en appoint
    ("Agent", None, "Autres"),
])
def test_normalize_sector(title, raw, expected):
    assert agg.normalize_sector(raw, title, "") == expected


def test_normalize_sector_empty_returns_none():
    assert agg.normalize_sector(None, "", "") is None


def test_normalize_sector_title_dominates_description():
    desc = "Maîtrise des outils informatiques, data, Excel, logiciel de gestion."
    assert agg.normalize_sector(None, "Chargé de recouvrement", desc) == "Finance / Banque"


def test_normalize_sector_whole_word_for_short_keywords():
    # « it » ne doit pas matcher « crédit » / « Kit » ; « rh » pas dans « rhum ».
    assert agg.normalize_sector(None, "Vendeur de kits solaires", "") != "Informatique / Tech"


# ---------- normalize_contract_type ----------
@pytest.mark.parametrize("raw,expected", [
    ("CDI", "CDI"),
    ("FULL_TIME", "CDI"),
    ("PART_TIME", "Temps partiel"),
    ("INTERN", "Stage"),
    ("CDD - CDI", "CDD"),                         # le premier dans la chaîne gagne
    ("Statutaire", "CDI"),
    ("CDI CDD Stage Intérim Freelance", "Non précisé"),  # liste de filtres aspirée par erreur
    ("", "Non précisé"),
    (None, "Non précisé"),
    ("whatever", "Non précisé"),
])
def test_normalize_contract_type(raw, expected):
    assert agg.normalize_contract_type(raw) == expected


# ---------- normalize_location ----------
@pytest.mark.parametrize("raw,expected", [
    ("Cocody, Abidjan", "Abidjan"),
    ("Abidjan, Côte d’Ivoire", "Abidjan, Côte d'Ivoire"),   # apostrophe typographique
    ("Dakar Senegal", "Dakar, Sénégal"),
    ("CI", "Côte d'Ivoire"),
    ("Lagos, Nigeria", "Lagos, Nigeria"),                  # « nigeria » avant « niger »
    ("Niamey, Niger", "Niamey, Niger"),
    ("Paris, Paris", "Paris"),                             # repli : dédoublonnage
    ("  ", None),
    (None, None),
])
def test_normalize_location(raw, expected):
    assert agg.normalize_location(raw) == expected


# ---------- infer_employer ----------
def test_infer_employer_from_html_description():
    desc = "<p><strong>Entreprise :</strong> LEADWAY ASSURANCE</p><p>Lieu : Abidjan</p>"
    assert agg.infer_employer("Comptable", desc) == "LEADWAY ASSURANCE"


def test_infer_employer_from_flattened_text():
    assert agg.infer_employer("Comptable", "Entreprise : LEADWAY ASSURANCELieu : Abidjan") == "LEADWAY ASSURANCE"


def test_infer_employer_confidential_name_normalized():
    assert agg.infer_employer("x", "Entreprise : Confidentiel") == agg.CONFIDENTIAL_EMPLOYER


@pytest.mark.parametrize("title,expected", [
    ("Wave recrute un comptable", "Wave"),
    ("Les Écoles Maarif recrutent des enseignants", "Écoles Maarif"),
    ("Comptable H/F", None),
])
def test_infer_employer_from_title(title, expected):
    assert agg.infer_employer(title, None) == expected


@pytest.mark.xfail(reason="BUG: _LEADING_ARTICLE_RE retire « L' » / « La » même quand il fait partie "
                          "du nom de marque (« L'Oréal recrute » → « Oréal »).", strict=True)
def test_infer_employer_keeps_article_that_is_part_of_brand():
    assert agg.infer_employer("L'Oréal recrute un chef de produit", None) == "L'Oréal"


@pytest.mark.xfail(reason="BUG: _DESC_EMPLOYER_RE n'est pas ancrée en tête de description : "
                          "« Présentation de l'entreprise : Nous sommes… » est pris pour l'employeur.",
                   strict=True)
def test_infer_employer_ignores_entreprise_label_inside_prose():
    desc = "<p>Présentation de l'entreprise : Nous sommes un cabinet de conseil</p>"
    assert agg.infer_employer("Consultant junior", desc) is None


# ---------- _html_to_text / _strip_html ----------
def test_html_to_text_keeps_paragraphs_and_bullets():
    html = "<p>Bonjour&nbsp;&amp; bienvenue</p><ul><li>Python</li><li><ul><li>SQL</li></ul></li></ul><br>Fin"
    assert agg._html_to_text(html) == "Bonjour & bienvenue\n• Python\n• SQL\nFin"


def test_html_to_text_empty_and_collapses_blank_lines():
    assert agg._html_to_text("") == ""
    assert agg._html_to_text(None) == ""
    assert "\n\n\n" not in agg._html_to_text("<p>a</p><p></p><p></p><p></p><p>b</p>")


def test_strip_html_decodes_entities():
    assert agg._strip_html("<b>L&rsquo;équipe</b>  &amp;  co") == "L’équipe & co"


# ---------- _extract_prose ----------
def test_extract_prose_returns_inner_html_with_nested_divs():
    page = '<div class="x"><div class="prose max-w-none"><p>A</p><div>B</div></div><div>after</div></div>'
    assert agg._extract_prose(page) == "<p>A</p><div>B</div>"


@pytest.mark.parametrize("page", ["<div>rien</div>", '<div class="prose"><p>non fermé', "", None])
def test_extract_prose_missing_or_unterminated(page):
    assert agg._extract_prose(page) is None


# ---------- JSON-LD : _all_job_postings / _map_to_offer ----------
def _page(*blocks) -> str:
    scripts = "".join(
        f'<script type="application/ld+json">{json.dumps(b, ensure_ascii=False)}</script>' for b in blocks
    )
    return f"<html><head>{scripts}</head><body>…</body></html>"


TODAY = date.today()
RECENT = (TODAY - timedelta(days=3)).isoformat()
FUTURE = (TODAY + timedelta(days=30)).isoformat()
PAST = (TODAY - timedelta(days=2)).isoformat()

GRAPH_PAGE = _page(
    {"@context": "https://schema.org", "@type": "Organization", "name": "Site"},
    {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebPage", "name": "Offre"},
            {
                "@type": "JobPosting",
                "title": "Comptable confirmé",
                "hiringOrganization": {"@type": "Organization", "name": "Orange Côte d'Ivoire"},
                "jobLocation": {"@type": "Place", "address": {
                    "addressLocality": "Cocody", "addressRegion": "Abidjan", "addressCountry": "CI"}},
                "employmentType": ["FULL_TIME"],
                "description": "<p>Tenue de la <b>comptabilité</b></p><ul><li>SYSCOHADA</li></ul>",
                "qualifications": "<p>BAC+3 en comptabilité</p>",
                "industry": "Niveau BAC+3",
                "baseSalary": {"currency": "XOF", "value": {"value": 450000, "unitText": "MONTH"}},
                "datePosted": RECENT,
                "validThrough": FUTURE + "T23:59:59",
            },
        ],
    },
)

ITEMLIST_PAGE = _page({
    "@context": "https://schema.org",
    "@type": "ItemList",
    "itemListElement": [
        {"@type": "ListItem", "position": 1, "item": {"@type": "JobPosting", "title": "Développeur Python",
                                                      "hiringOrganization": "Wave"}},
        {"@type": "ListItem", "position": 2, "item": {"@type": "JobPosting", "title": "Chauffeur",
                                                      "hiringOrganization": {"name": "Bolloré"}}},
    ],
})

EFASO_POSTING = {
    "@type": "JobPosting",
    "title": "Assistant comptable",
    "hiringOrganization": {"@type": "Organization", "name": "E-Faso"},
    "description": "<p><strong>Entreprise :</strong> SOTRA</p><p>Lieu : Abidjan</p><p>Missions…</p>",
    "employmentType": "CDD",
    "datePosted": RECENT,
}


def test_all_job_postings_in_graph():
    found = agg._all_job_postings(GRAPH_PAGE)
    assert [p["title"] for p in found] == ["Comptable confirmé"]


def test_all_job_postings_in_itemlist():
    found = agg._all_job_postings(ITEMLIST_PAGE)
    assert [p["title"] for p in found] == ["Développeur Python", "Chauffeur"]


def test_all_job_postings_skips_invalid_json_and_tolerates_control_chars():
    page = ('<script type="application/ld+json">{ pas du json }</script>'
            '<script type="application/ld+json">{"@type": "JobPosting", "title": "A\tB",'
            ' "description": "ligne1\nligne2"}</script>')
    found = agg._all_job_postings(page)
    assert len(found) == 1 and found[0]["title"] == "A\tB"


def test_parse_job_posting_none_when_absent():
    assert agg._parse_job_posting("<html></html>") is None


def test_map_to_offer_full_graph_posting():
    posting = agg._all_job_postings(GRAPH_PAGE)[0]
    offer = agg._map_to_offer(posting, "https://src/1", "Emploi.ci")
    assert offer["title"] == "Comptable confirmé"
    assert offer["company"] == "Orange Côte d'Ivoire"
    assert offer["location"] == "Abidjan, Côte d'Ivoire"
    assert offer["contract_type"] == "CDI"
    assert offer["sector"] == "Comptabilité / Audit"   # « Niveau BAC+3 » ignoré comme secteur
    assert offer["description"] == "Tenue de la comptabilité\n• SYSCOHADA"
    assert offer["requirements"] == "BAC+3 en comptabilité"
    assert offer["salary_range"] == "450000 XOF MONTH"
    assert offer["posted_date"] == RECENT
    assert offer["valid_through"] == FUTURE
    assert offer["is_active"] is True
    assert offer["source"] == "Emploi.ci" and offer["source_url"] == "https://src/1"


def test_map_to_offer_string_hiring_organization():
    postings = agg._all_job_postings(ITEMLIST_PAGE)
    offers = [agg._map_to_offer(p, f"https://src/{i}", "X") for i, p in enumerate(postings)]
    assert [o["company"] for o in offers] == ["Wave", "Bolloré"]
    assert offers[0]["contract_type"] == "Non précisé"


def test_map_to_offer_efaso_operator_replaced_by_real_employer():
    offer = agg._map_to_offer(EFASO_POSTING, "https://e-faso/1", "E-Faso")
    assert offer["company"] == "SOTRA"
    assert offer["contract_type"] == "CDD"


def test_map_to_offer_efaso_without_hint_becomes_confidential():
    posting = dict(EFASO_POSTING, description="<p>Missions…</p>")
    offer = agg._map_to_offer(posting, "https://e-faso/2", "E-Faso")
    assert offer["company"] == agg.CONFIDENTIAL_EMPLOYER


def test_map_to_offer_missing_company_inferred_from_title():
    offer = agg._map_to_offer({"@type": "JobPosting", "title": "Wave recrute un comptable"}, "u", "S")
    assert offer["company"] == "Wave"
    offer2 = agg._map_to_offer({"@type": "JobPosting", "title": "Comptable"}, "u", "S")
    assert offer2["company"] == "Non précisé"


def test_map_to_offer_without_title_is_skipped():
    assert agg._map_to_offer({"@type": "JobPosting", "title": "  "}, "u", "S") is None
    assert agg._map_to_offer({"@type": "JobPosting"}, "u", "S") is None


def test_map_to_offer_expired_posting_created_inactive():
    offer = agg._map_to_offer({"@type": "JobPosting", "title": "Comptable", "validThrough": PAST}, "u", "S")
    assert offer["is_active"] is False and offer["valid_through"] == PAST


@pytest.mark.parametrize("raw,expected", [
    (RECENT, RECENT),
    ((TODAY + timedelta(days=1)).isoformat(), None),      # futur
    ("2020-01-01", None),                                 # trop vieille
    ("01/02/2026", None),                                 # format inattendu
    (None, None),
])
def test_sane_posted_date(raw, expected):
    assert agg._sane_posted_date(raw) == expected
