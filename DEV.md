# EmploiCentral — Guide de développement local

Plateforme d'emploi intelligente (marché ouest-africain) générée sur **atoms.world**.
Monorepo : backend FastAPI + frontend React/Vite.

## Stack
- **Backend** : FastAPI · SQLAlchemy (async) · SQLite en local (Postgres en prod) · JWT · OIDC (auth plateforme) · OpenAI-compatible (analyse CV/scoring) · Stripe
- **Frontend** : React 18 · Vite 5 · TypeScript · Tailwind · shadcn/ui · `@metagptx/web-sdk` (client API)

## Prérequis
- Python 3.9+ (venv déjà créé dans `app/.venv`)
- Node 20 + pnpm 9 (`corepack prepare pnpm@9.15.4 --activate`)

## Lancer en local

### Backend (port 8000)
```bash
cd app/backend
set -a; . ../.env; set +a            # charge les variables d'environnement
../.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```
- Santé : http://127.0.0.1:8000/health
- API entités : `GET /api/v1/entities/job_offers`
- La base SQLite (`app/backend/app.db`) est créée au 1er démarrage et seedée avec
  les offres de `app/backend/mock_data/job_offers.json` (12 offres).

### Frontend (port 3000)
```bash
cd app/frontend
BACKEND_PORT=8000 VITE_PORT=3000 pnpm dev
```
- App : http://localhost:3000
- Vite proxie `/api` → `http://localhost:8000`.

## Configuration (`app/.env`)
Variables **obligatoires en local** : `DATABASE_URL`, `JWT_SECRET_KEY`.

Intégrations couplées à la plateforme atoms.world (vides par défaut → fonctionnalités
désactivées tant que non renseignées) :

| Variable | Fonctionnalité |
|----------|----------------|
| `OIDC_ISSUER_URL` / `OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET` | Connexion / inscription (login OAuth) |
| `APP_AI_BASE_URL` / `APP_AI_KEY` | Analyse de CV + score de compatibilité (IA) |
| `OSS_SERVICE_URL` / `OSS_API_KEY` | Upload de CV (stockage objet) |
| `STRIPE_SECRET_KEY` | Paiements |

> Sans OIDC, la navigation publique (landing, liste d'offres) fonctionne mais
> la connexion et les pages protégées (Dashboard, Profile, Alerts) ne sont pas accessibles.
> Voir les pistes de remplacement local dans la section ci-dessous.

## Auth locale (email / mot de passe) — ✅ implémentée
Login local activé sans dépendre de l'OIDC plateforme. Coexiste avec le flux OIDC
(qui reste utilisable si les variables `OIDC_*` sont renseignées).

- **Backend** (`routers/auth.py`, `services/auth.py`, `models/auth.py`)
  - `POST /api/v1/auth/register` `{email, password, name?}` → `{token, expires_at, token_type}`
  - `POST /api/v1/auth/login` `{email, password}` → `{token, expires_at, token_type}`
  - Mots de passe hachés en PBKDF2-HMAC-SHA256 (stdlib, colonne `users.password_hash`).
  - Le JWT applicatif est identique à celui de l'OIDC (mêmes claims), donc `/me` et
    toutes les routes protégées fonctionnent pareil.
- **Frontend** : page `src/pages/Login.tsx` (route `/login`, bascule connexion/inscription).
  Le token est stocké dans `localStorage['token']` (clé lue par le web-sdk pour le
  header `Authorization: Bearer`). Les boutons « Connexion / S'inscrire » de la landing
  et `ProtectedRoute` pointent désormais vers `/login`.

> ⚠️ Ajout de la colonne `password_hash` : `create_tables` n'altère pas une table existante.
> Si tu pars d'une ancienne `app.db`, supprime-la (`rm app/backend/app.db`) pour qu'elle
> soit recréée avec la colonne (les offres mock sont reseedées automatiquement).

## Analyse de CV + scoring — ✅ hybride local (sans clé) + IA optionnelle
Fonctionne **sans aucun accès externe**. Si une clé IA est présente, elle est utilisée
automatiquement ; sinon (ou en cas d'échec), un moteur heuristique local prend le relais.

- **Heuristique** (`services/cv_heuristic.py`) : extraction du texte PDF via PyMuPDF,
  parsing regex (nom, email, téléphone, expérience), détection de compétences/secteur/
  localisation/formation par dictionnaires, et scoring de compatibilité
  (compétences ⨯ secteur ⨯ localisation ⨯ expérience).
- **Bascule** (`services/cv_analysis.py`) : `ai_available = APP_AI_BASE_URL && APP_AI_KEY`.
  → renseigne ces 2 variables dans `app/.env` pour activer une vraie IA
  (endpoint compatible OpenAI : OpenAI, DeepSeek, ou proxy Anthropic).
- Endpoints : `POST /api/v1/jobs/analyze-cv`, `/compatibility-score`, `/batch-scores`.

## Stockage de CV — ✅ disque local (sans clé)
Bascule OSS↔local automatique (`routers/storage.py:get_storage_service`) :
si `OSS_*` non configuré → backend disque (`services/local_storage.py`).

- Fichiers stockés sous `app/backend/storage/<bucket>/<clé>` (gitignored).
- Endpoints « blob » non authentifiés (`PUT`/`GET /api/v1/storage/blob/{bucket}/{key}`)
  qui imitent une URL présignée : le web-sdk y PUT/GET le fichier directement.
  Garde-fous : sanitization des chemins (anti-traversal) + plafond 10 Mo.

## ⚠️ Compatibilité Python 3.9 (machine locale)
- `services/aihub.py` utilisait `str | list[str]` (PEP 604, Python 3.10+) → corrigé via
  `from __future__ import annotations`. Sans ça, les routers `cv_analysis` et `aihub`
  ne se chargeaient pas (analyse CV silencieusement indisponible).
- `routers/aihub.py` contient encore du PEP 604 et reste **non chargé** sur 3.9, mais il
  n'est **pas utilisé** par le frontend (qui passe par `/api/v1/jobs/*`). Pour l'activer,
  ajouter `from __future__ import annotations` en tête + Python 3.10+.
- Bug préexistant corrigé dans `/compatibility-score` : accès à un objet ORM après
  `db.rollback()` (erreur greenlet) — valeurs désormais capturées avant le rollback.

## Agrégation automatique d'offres (multi-sources)
Le backend récupère périodiquement de vraies offres depuis plusieurs sites et les insère
dans `job_offers` (sans doublon), via un planificateur APScheduler démarré dans le
`lifespan` de `main.py`.

**Sources** (liste `SOURCES` dans `services/job_aggregator.py`) :
- **Emploi.ci** (Côte d'Ivoire) — crawl liste + pages détail (JSON-LD).
- **Emploi.sn** (Sénégal, même plateforme qu'Emploi.ci) — implémenté ; le site peut être
  injoignable selon le réseau (échec géré proprement → 0 offre, pas de crash).
- **Novojob** (Côte d'Ivoire) — crawl liste + pages détail (JSON-LD en quotes simples).
- **AfriqueEmplois** (`/ci`) — mode `listing_jsonld` : la page liste embarque un `ItemList`
  de ~10 `JobPosting`, donc 1 requête = 10 offres (pas de crawl détail). Note : leur
  `hiringOrganization` = l'opérateur du site ; l'employeur réel est dans le **titre**.

Ajouter une source = une entrée dans `SOURCES` (`name`, `base`, `listing_path`, `offer_re`,
`id_re`, `paginate`, ou `mode: "listing_jsonld"`). Le même parseur JSON-LD est réutilisé
(recherche en profondeur : gère `@graph` et `ItemList`).

- `services/job_aggregator.py` — récupération, parsing JSON-LD `JobPosting`, mapping vers
  `job_offers`, **dédup** par identifiant externe ET par `source_url` complet (certaines
  URLs n'ont pas d'ID extractible). `normalize_contract_type` (→ CDI/CDD/Stage/… ; les
  listes de filtres deviennent « Non précisé ») et `normalize_sector` (consolide le label
  ou **infère** le secteur depuis le titre/description).
- `services/scheduler.py` — démarre/arrête le job périodique (`start_scheduler`/`stop_scheduler`).
- Politesse/légalité : `User-Agent` identifiable non déguisé (les `robots.txt` autorisent
  `User-agent: *` ; les `Disallow: /` ne visent que des bots d'IA), délai entre requêtes,
  limite d'insertions par passe et par source.
- ⚠️ Pas agrégeable : **pages/groupes Facebook** (ex. « CV PRO ABIDJAN ») — contenu derrière
  auth, pas de données structurées, et interdit par les CGU de Facebook.

Réglages (variables d'environnement, à mettre dans `.env`) :
- `AGGREGATOR_ENABLED` (défaut `true`) — active l'agrégation.
- `AGGREGATOR_INTERVAL_MINUTES` (défaut `360`) — fréquence.
- `AGGREGATOR_MAX_PER_RUN` (défaut `20`) — nb max de nouvelles offres par passe **et par source**.
- `AGGREGATOR_PAGES` (défaut `1`) — nb de pages de liste à parcourir.
- `AGGREGATOR_SOURCES` (défaut : toutes) — filtre, ex. `"Emploi.ci,Novojob"`.
- `AGGREGATOR_RUN_ON_STARTUP` (défaut `false`) — lance une 1re passe ~15 s après le boot.

Lancer une passe à la main :
```
cd app/backend && set -a; . ../.env; set +a && ../.venv/bin/python run_aggregation.py
```
Dépendance ajoutée : `apscheduler` dans `requirements.txt`.

## Génération de CV optimisé ATS (adapté à une offre)
Le candidat génère, depuis une offre, un **CV PDF optimisé ATS** basé sur son profil analysé.

- `services/cv_generator.py` — extrait les mots-clés de l'offre, met en avant les
  compétences du profil qui correspondent, et **enrichit le CV avec le contenu réel du CV
  uploadé** : `load_cv_text` lit le PDF stocké (`local_storage.resolve_blob_path("cvs",
  cv_object_key)` + PyMuPDF) et `parse_cv_sections` le découpe en sections (Expérience,
  Formation, Certifications, Langues) par détection d'en-têtes. Rendu en **PDF
  mono-colonne** (reportlab), sans tableaux ni images (lisible par les ATS).
  Hybride : accroche rédigée par IA si `APP_AI_*` configuré, sinon templating local.
- **Modèles de CV** : `TEMPLATES` dans `cv_generator.py` — `mon_cv` (calqué sur le CV
  d'Emmanuel : bleu nuit `#1f4e79` nom/titres/employeurs, gris `#595959` sous-titre/dates ;
  défaut côté UI), `sobre` (ATS classique noir/gris), `bleu`, `compact`. Param `template`.
  Le rendu de l'Expérience classe chaque ligne (employeur gras / dates italique gris /
  descriptions en puces) via `_classify_exp_line` pour ressembler à un vrai CV.
  `mon_cv` utilise la police **Carlito** (bundlée dans `app/backend/assets/fonts/`,
  enregistrée via `_register_carlito`, repli Helvetica si absente) ; les autres modèles
  restent en Helvetica (sûr pour ATS).
- **Lettre de motivation** : `build_cover_letter_content`/`build_cover_letter_pdf` +
  `CvGeneratorService.generate_cover_letter` (corps IA si dispo, sinon 3 paragraphes locaux).
- Endpoints (`routers/cv_analysis.py`) — `POST /api/v1/jobs/generate-cv` et
  `POST /api/v1/jobs/generate-cover-letter`, body `{profile_id, job_id, template}`, contrôle
  d'appartenance du profil, renvoient le PDF en téléchargement (`application/pdf`).
- Frontend (`src/pages/Jobs.tsx`, détail d'offre) : sélecteur de **modèle** + boutons
  **« CV (ATS) »** et **« Lettre de motivation »** — fetch direct avec le JWT (binaire),
  download du blob (helper `downloadPdf`).
- Dépendance ajoutée : `reportlab`.

## Notifications d'alerte (in-app / email / WhatsApp)
Après chaque cycle d'agrégation, `services/notifications.py:dispatch_new_offer_alerts` compare
les offres actives aux alertes (`alert_preferences`) et notifie les nouvelles correspondances.

- **Piloté par les candidats** : on itère les profils avec `cv_analyzed=true` (pas seulement
  les alertes configurées). Filtrage = critères d'alerte explicites si définis, **sinon
  critères implicites du profil** (secteur + chevauchement de compétences via
  `match_offer_to_profile`). **Email activé par défaut (opt-out)** : envoyé sauf si
  `notify_email=false`. Les emails de comptes démo/test (`@demo.com`, `browser_*`) sont ignorés.
- **Canaux** : **in-app** toujours actif (table `notifications`, sert aussi de dédup user+job) ;
  **email** si SMTP configuré (`SMTP_HOST/USER/PASSWORD`) ; **WhatsApp** (opt-in) si **Twilio**
  (`TWILIO_*`) ou **Meta Cloud API** (`META_WA_*`) configuré. Contact = email/téléphone du profil.
  Anti-flood `ALERT_MAX_PER_USER` (défaut 15/cycle).
- **Déclenchement** : le job du scheduler exécute désormais `_aggregate_and_notify`
  (agrégation puis dispatch). Matching = port de `lib/matching` (séparateurs `|` ET `,`).
- **API in-app** : `GET /api/v1/notifications` (+ `unread`), `POST /api/v1/notifications/mark-read`.
- **Frontend** : page Alertes → toggles **Email** / **WhatsApp** (`notify_email`/`notify_whatsapp`) ;
  badge de nouvelles correspondances déjà géré par `useAlertMatches`.
- Config dans `.env` (placeholders commentés, canaux inactifs tant que vides).

## Structure
```
app/backend/   FastAPI (routers/ services/ models/ core/ mock_data/)
app/frontend/  React/Vite (src/pages, src/components, src/lib/api.ts = web-sdk)
.atoms/        Docs de génération (ARCHITECTURE.md, PROGRESS.md)
```
