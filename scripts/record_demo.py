#!/usr/bin/env python3
"""
🎥 Enregistreur automatique de démo — EmploiCentral
===================================================

Pilote un navigateur Chromium (Playwright) qui parcourt l'application déployée
en suivant le storyboard (docs/script-video-presentation.md) et ENREGISTRE une
vidéo du parcours. La vidéo est muette (b-roll) : tu ajoutes la voix-off par-dessus
au montage (CapCut / iMovie), ou via le text-to-speech d'un outil.

------------------------------------------------------------------------------
INSTALLATION (une seule fois)
------------------------------------------------------------------------------
    cd /Users/MAFAHOLDING/Documents/emploi
    python3 -m venv .venv-demo && source .venv-demo/bin/activate   # (ou réutilise app/.venv)
    pip install playwright
    playwright install chromium

------------------------------------------------------------------------------
LANCEMENT
------------------------------------------------------------------------------
    # Identifiants d'un compte CANDIDAT de démo (CV déjà analysé = démo plus vivante)
    export EC_EMAIL="candidat-demo@exemple.com"
    export EC_PASSWORD="motdepasse"
    # (facultatif) compte recruteur pour la scène recruteur
    export EC_RECRUITER_EMAIL="recruteur-demo@exemple.com"
    export EC_RECRUITER_PASSWORD="motdepasse"

    python scripts/record_demo.py

    # Options via env :
    #   EC_BASE_URL   (défaut https://emploicentral.onrender.com)
    #   EC_HEADLESS   ("0" pour voir le navigateur tourner ; défaut "1")
    #   EC_OUT_DIR    (dossier de sortie ; défaut ./demo-video)

La vidéo .webm finale est affichée en fin d'exécution. Pour la convertir en .mp4 :
    ffmpeg -i demo-video/<fichier>.webm -c:v libx264 -pix_fmt yuv420p demo-video/demo.mp4
"""
from __future__ import annotations

import os
import sys

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    sys.exit("Playwright n'est pas installé. Fais : pip install playwright && playwright install chromium")


BASE = os.environ.get("EC_BASE_URL", "https://emploicentral.onrender.com").rstrip("/")
EMAIL = os.environ.get("EC_EMAIL", "")
PASSWORD = os.environ.get("EC_PASSWORD", "")
REC_EMAIL = os.environ.get("EC_RECRUITER_EMAIL", "")
REC_PASSWORD = os.environ.get("EC_RECRUITER_PASSWORD", "")
HEADLESS = os.environ.get("EC_HEADLESS", "1") != "0"
OUT_DIR = os.environ.get("EC_OUT_DIR", "demo-video")

VIEWPORT = {"width": 1280, "height": 720}


def log(msg: str) -> None:
    print(f"  🎬 {msg}", flush=True)


def beat(page, seconds: float = 2.5) -> None:
    """Pause « le temps de lire » — laisse la scène respirer pour la vidéo."""
    page.wait_for_timeout(int(seconds * 1000))


def smooth_scroll(page, total: int = 700, step: int = 100, pause: float = 0.18) -> None:
    """Scroll progressif (plus agréable à l'œil qu'un saut)."""
    done = 0
    while done < total:
        page.mouse.wheel(0, step)
        page.wait_for_timeout(int(pause * 1000))
        done += step


def scene(name: str):
    """Décorateur léger : isole chaque scène (une erreur n'arrête pas la vidéo)."""
    def deco(fn):
        def wrapper(page):
            log(f"Scène : {name}")
            try:
                fn(page)
            except Exception as exc:  # noqa: BLE001 - on continue malgré une scène ratée
                log(f"  ⚠️  scène « {name} » ignorée ({type(exc).__name__}: {exc})")
        return wrapper
    return deco


def goto(page, path: str, wait_text: str | None = None) -> None:
    page.goto(BASE + path, wait_until="domcontentloaded", timeout=90_000)
    if wait_text:
        try:
            page.get_by_text(wait_text, exact=False).first.wait_for(timeout=20_000)
        except PWTimeout:
            pass


def login(page, email: str, password: str) -> bool:
    log("Connexion…")
    goto(page, "/login")
    # Réveil possible (cold start Render) : on patiente sur le formulaire.
    try:
        page.locator("input[type=email]").first.wait_for(timeout=90_000)
    except PWTimeout:
        log("  ⚠️  page de connexion introuvable")
        return False
    page.locator("input[type=email]").first.fill(email)
    page.locator("input[type=password]").first.fill(password)
    beat(page, 1)
    # Bouton « Se connecter »
    try:
        page.get_by_role("button", name="Se connecter").click()
    except Exception:
        page.locator("button[type=submit]").first.click()
    # Attend l'arrivée sur le tableau de bord
    try:
        page.wait_for_url("**/dashboard", timeout=30_000)
    except PWTimeout:
        page.wait_for_timeout(4000)
    beat(page, 2)
    return True


# --------------------------------------------------------------------------- #
# Scènes (suivent docs/script-video-presentation.md)
# --------------------------------------------------------------------------- #
@scene("Tableau de bord")
def s_dashboard(page):
    goto(page, "/dashboard")
    beat(page, 3)
    smooth_scroll(page, 400)
    beat(page, 1.5)


@scene("Offres centralisées")
def s_jobs(page):
    goto(page, "/jobs", wait_text="Emplois")
    beat(page, 2.5)
    smooth_scroll(page, 900)
    beat(page, 1.5)


@scene("Fiche offre + score IA + compétences à acquérir")
def s_offer(page):
    goto(page, "/jobs")
    beat(page, 1.5)
    # Ouvre la 1re carte d'offre cliquable
    card = page.locator("[class*='cursor-pointer']").first
    card.click(timeout=15_000)
    beat(page, 3)
    smooth_scroll(page, 500)   # fait défiler vers le score + points forts
    beat(page, 2.5)
    smooth_scroll(page, 500)   # vers « Compétences à acquérir »
    beat(page, 3)


@scene("Galerie de modèles de CV")
def s_cv_templates(page):
    # En supposant qu'une fiche d'offre est ouverte ; sinon on en rouvre une.
    try:
        page.get_by_role("button", name="Choisir").first.click(timeout=5_000)
    except Exception:
        page.get_by_text("Modèle de CV", exact=False).first.click(timeout=5_000)
    beat(page, 3)            # la galerie de vignettes s'affiche
    page.keyboard.press("Escape")
    beat(page, 1)


@scene("Coach d'entretien IA")
def s_interview(page):
    page.get_by_role("button", name="Préparer l'entretien").first.click(timeout=10_000)
    # Génération (IA) : laisse le temps
    beat(page, 6)
    smooth_scroll(page, 700)
    beat(page, 3)
    page.keyboard.press("Escape")
    beat(page, 1)


@scene("Tendances du marché")
def s_market(page):
    goto(page, "/market", wait_text="Tendances")
    beat(page, 3)
    smooth_scroll(page, 700)
    beat(page, 2.5)


@scene("Formations")
def s_trainings(page):
    goto(page, "/trainings", wait_text="Formations")
    beat(page, 3)
    smooth_scroll(page, 700)
    beat(page, 2)


@scene("Alertes")
def s_alerts(page):
    goto(page, "/alerts")
    beat(page, 3)


@scene("Espace recruteur")
def s_recruiter(page):
    goto(page, "/recruiter", wait_text="recruteur")
    beat(page, 3)
    smooth_scroll(page, 500)
    beat(page, 2)


def run():
    if not EMAIL or not PASSWORD:
        sys.exit("Définis EC_EMAIL et EC_PASSWORD (compte candidat de démo).")

    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"\n=== Enregistrement démo EmploiCentral ===\nCible : {BASE}\nSortie : {OUT_DIR}/\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            viewport=VIEWPORT,
            record_video_dir=OUT_DIR,
            record_video_size=VIEWPORT,
            locale="fr-FR",
        )
        page = context.new_page()

        # --- Parcours candidat ---
        if login(page, EMAIL, PASSWORD):
            s_dashboard(page)
            s_jobs(page)
            s_offer(page)
            s_cv_templates(page)
            s_interview(page)
            s_market(page)
            s_trainings(page)
            s_alerts(page)

        # --- Parcours recruteur (si identifiants fournis) ---
        if REC_EMAIL and REC_PASSWORD:
            log("Déconnexion puis connexion recruteur…")
            try:
                page.get_by_role("button", name="Déconnexion").first.click(timeout=5_000)
            except Exception:
                goto(page, "/login")
            beat(page, 2)
            if login(page, REC_EMAIL, REC_PASSWORD):
                s_recruiter(page)

        beat(page, 1)
        video_path = page.video.path() if page.video else None
        context.close()  # IMPORTANT : finalise l'écriture de la vidéo
        browser.close()

    print("\n✅ Terminé.")
    if video_path:
        print(f"🎞️  Vidéo : {video_path}")
        print("   Convertir en mp4 :")
        print(f"   ffmpeg -i '{video_path}' -c:v libx264 -pix_fmt yuv420p {OUT_DIR}/demo.mp4")
    else:
        print(f"🎞️  Vidéo dans : {OUT_DIR}/ (fichier .webm)")


if __name__ == "__main__":
    run()
