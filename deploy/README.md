# Déploiement EmploiCentral — VPS + Docker

Met en ligne **ta version locale** (auth locale, agrégation d'offres, IA heuristique,
stockage disque, marché FCFA) sur un VPS, derrière Caddy (HTTPS automatique).

```
Internet ──HTTPS──> Caddy ──/api/*──> backend (uvicorn:8000)  [SQLite + scheduler + stockage]
                       └──tout le reste──> SPA React (dist/, fichiers statiques)
```

Tout est servi sous **un seul domaine** → le front appelle `/api` en same-origin (zéro CORS).

---

## Prérequis

- Un VPS Linux (Hetzner / OVH / DigitalOcean…), 1–2 vCPU / 2 Go RAM suffisent.
- Docker + Docker Compose installés sur le VPS :
  ```bash
  curl -fsSL https://get.docker.com | sh
  ```
- Un nom de domaine (ou sous-domaine) dont tu contrôles le DNS.

## 1. Sous-domaine DuckDNS (gratuit)

1. Va sur https://www.duckdns.org et connecte-toi (Google/GitHub…).
2. Crée un sous-domaine, ex. `topjob` → tu obtiens **`topjob.duckdns.org`**.
3. Dans le champ **current ip** de ce sous-domaine, mets l'**IP publique de ton VPS**,
   puis clique **update ip**.

Vérifie que ça résout vers ton VPS :
```bash
dig +short topjob.duckdns.org   # doit afficher l'IP du VPS
```

Caddy obtiendra un **vrai certificat HTTPS Let's Encrypt** pour ce sous-domaine
(challenge HTTP, ports 80/443 ouverts requis). Aucun token DuckDNS n'est nécessaire.

> **IP du VPS qui change ?** La plupart des VPS ont une IP fixe → rien à faire.
> Si jamais elle change, relance la mise à jour. Pour automatiser, ajoute un cron
> sur le VPS (remplace `TON_TOKEN` par le token affiché sur duckdns.org) :
> ```bash
> echo '*/5 * * * * curl -s "https://www.duckdns.org/update?domains=topjob&token=TON_TOKEN&ip="' | crontab -
> ```

## 2. Récupérer le code sur le VPS

Copie le dossier du projet sur le VPS (scp, rsync ou git). L'important : avoir
`app/` et `deploy/` côte à côte.

```bash
rsync -av --exclude node_modules --exclude .venv --exclude '*.zip' \
  ./emploi/ user@vps:/opt/emploi/
```

## 3. Configurer l'environnement

```bash
cd /opt/emploi/deploy
cp .env.example .env   # si pas déjà fait
nano .env
```

À remplir impérativement :
- `DOMAIN` → ton domaine exact (ex. `topjob.tondomaine.com`)
- `TLS_EMAIL` → ton email (alertes certificat)
- `FRONTEND_URL` → `https://<DOMAIN>`
- `JWT_SECRET_KEY`, `MASK_KEY` → secrets forts uniques :
  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"  # JWT
  python3 -c "import secrets; print(secrets.token_hex(16))"  # MASK
  ```

## 4. Lancer

```bash
cd /opt/emploi/deploy
docker compose up -d --build
```

- 1er build : quelques minutes (install pip + build Vite).
- Caddy obtient le certificat TLS automatiquement au 1er accès HTTPS.

Vérifier :
```bash
docker compose ps
docker compose logs -f backend   # doit montrer "startup completed" + scheduler
curl -I https://<DOMAIN>          # 200
```

Ouvre `https://<DOMAIN>` → l'appli. L'agrégateur tourne au démarrage
(`AGGREGATOR_RUN_ON_STARTUP=true`) puis toutes les 6 h.

---

## Exploitation

| Action | Commande (depuis `deploy/`) |
|--------|------------------------------|
| Logs backend | `docker compose logs -f backend` |
| Redéployer après modif du code | `docker compose up -d --build` |
| Passe d'agrégation manuelle | `docker compose exec backend python run_aggregation.py` |
| Stop / start | `docker compose down` / `docker compose up -d` |
| Sauvegarde DB | `docker compose cp backend:/data/app.db ./backup-app.db` |

### Données persistées (volumes Docker)
- `backend-db` → `/data/app.db` (SQLite)
- `backend-storage` → CV uploadés
- `caddy-data` → certificats TLS (ne pas perdre, sinon re-émission)

`docker compose down` **conserve** les volumes. `docker compose down -v` les **supprime**.

---

## Notes / pièges

- **Backend en Python 3.11** ici (la contrainte 3.9 était propre à ta machine).
  Du coup `routers/aihub.py` se charge sans souci — inutilisé mais sans erreur.
- **Intégrations plateforme vides** dans `.env` = les remplacements locaux restent actifs
  (auth PBKDF2, IA heuristique, stockage disque). Si un jour tu as une vraie clé IA,
  renseigne `APP_AI_BASE_URL` + `APP_AI_KEY` → bascule auto vers l'IA réelle.
- **Si le build frontend échoue** sur un paquet `@metagptx/*` (registre privé) :
  build le SPA en local (`cd app/frontend && pnpm build`) puis sers le `dist/` existant
  via Caddy au lieu de l'étape 1 du `Dockerfile.frontend`. Demande-moi la variante.
- **Pare-feu VPS** : ouvre les ports **80** et **443**.
