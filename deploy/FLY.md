# Déploiement EmploiCentral sur Fly.io (gratuit, URL HTTPS incluse)

Met en ligne **ta version locale** (auth locale, agrégation d'offres, IA heuristique,
stockage disque, marché FCFA) sans VPS ni domaine. Fly fournit l'URL `https://<app>.fly.dev`
et le HTTPS. Données conservées sur un **volume persistant** (SQLite + CV).

> Architecture : une seule appli. FastAPI sert l'API (`/api/*`) **et** le frontend
> buildé (servi depuis `static/`). Tout est défini dans `deploy/Dockerfile.fly` et
> `fly.toml` (à la racine du projet).

---

## Prérequis (une fois)

1. **Installer flyctl** (sur ton Mac) :
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```
   Puis ouvre un nouveau terminal (ou ajoute `~/.fly/bin` au PATH).

2. **Créer un compte / se connecter** :
   ```bash
   fly auth signup     # ou: fly auth login
   ```
   ⚠️ Fly demande une **carte bancaire en vérification** (non débitée pour un petit
   usage). C'est le prix du « gratuit avec données persistantes ».

---

## Déploiement (depuis la racine du projet `emploi/`)

> Le nom d'app doit être **unique sur Fly** et donne l'URL. Si `emploicentral-topjob`
> est déjà pris, choisis-en un autre **et** mets-le à jour dans `fly.toml`
> (`app = "..."` + `FRONTEND_URL = "https://....fly.dev"`).

```bash
# 1. Créer l'app (réutilise le fly.toml existant)
fly apps create emploicentral-topjob

# 2. Créer le volume persistant (1 Go gratuit suffit largement)
fly volumes create data --region cdg --size 1 -a emploicentral-topjob

# 3. Secrets (uniques à ce déploiement — déjà générés)
# Génère des secrets aléatoires (ne JAMAIS committer de vraies valeurs) :
#   python -c "import secrets; print(secrets.token_hex(32))"   # JWT_SECRET_KEY
#   python -c "import secrets; print(secrets.token_hex(16))"   # MASK_KEY
fly secrets set -a emploicentral-topjob \
  JWT_SECRET_KEY=CHANGE_ME \
  MASK_KEY=CHANGE_ME

# 4. Déployer (build des 2 étapes Docker + mise en ligne)
fly deploy

# 5. Ouvrir dans le navigateur
fly open
```

L'appli est en ligne sur `https://emploicentral-topjob.fly.dev`.
L'agrégateur s'exécute au démarrage (`AGGREGATOR_RUN_ON_STARTUP=true`).

---

## Exploitation

| Action | Commande |
|--------|----------|
| Logs en direct | `fly logs` |
| Redéployer après modif du code | `fly deploy` |
| Statut / machines | `fly status` |
| Passe d'agrégation manuelle | `fly ssh console -C "python run_aggregation.py"` |
| Console shell | `fly ssh console` |
| Sauvegarde DB | `fly ssh console -C "cat /data/app.db" > backup-app.db` |
| Voir/poser un secret | `fly secrets list` / `fly secrets set CLE=valeur` |

---

## Points importants (spécifiques au plan gratuit)

- **Mise en veille** : `auto_stop_machines` arrête la machine quand personne ne
  l'utilise → la **1re visite** après une pause prend quelques secondes (cold start).
  C'est normal et ça garde le coût ~nul. Pour rester toujours allumé (et faire tourner
  l'agrégation toutes les 6 h sans visite), passe `min_machines_running = 1` dans
  `fly.toml` (consomme un peu plus d'allocation).
- **SQLite = 1 seule machine** : ne scale pas au-delà de 1 (`fly scale count 1`),
  sinon plusieurs instances écriraient sur des copies différentes du volume.
- **Données** : tout ce qui doit survivre est sous `/data` (volume). Le reste du
  conteneur est éphémère et recréé à chaque `fly deploy`.
- **Mémoire** : 512 Mo configurés (256 Mo risquent l'OOM avec PyMuPDF). Si tu vois
  des kills mémoire dans `fly logs`, monte à 1 Go : `fly scale memory 1024`.
- **Si le build du front échoue** sur un paquet `@metagptx/*` (registre privé) :
  dis-le-moi, je te donne la variante qui embarque le `dist/` déjà buildé en local.
```
