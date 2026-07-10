# 📈 BRVM Explorer

[![CI](https://github.com/Marco-espirito/BRVM/actions/workflows/ci.yml/badge.svg)](https://github.com/Marco-espirito/BRVM/actions/workflows/ci.yml)

Dashboard d'exploration de la **BRVM** (Bourse Régionale des Valeurs Mobilières,
Abidjan) — la bourse commune aux 8 pays de l'UEMOA. Scraping quotidien
automatisé des cotations, suivi des dividendes, score de sélection transparent
et portefeuille virtuel d'apprentissage.

<!-- TODO: ajouter un screenshot -> ![Dashboard](docs/screenshot.png) -->

> ⚠️ Projet d'apprentissage. Données publiques (brvm.org, sikafinance.com),
> différées. **Ceci n'est pas un conseil en investissement.** Pour investir
> réellement en BRVM, il faut passer par une SGI agréée.

## Fonctionnalités

- **47 actions cotées** : cours, variation, volume, mises à jour quotidiennes
- **Dividendes** : historique 2022-2025, calendrier des détachements,
  rendement recalculé sur le cours du jour, alerte ⚠️ dividende exceptionnel
- **Score /100 transparent** (rendement 40 + liquidité 30 + historique du
  dividende 30) avec Top 10 **diversifié par secteur**
- **Filtres croisés** pays × secteurs (7 secteurs officiels BRVM) avec tri
  automatique des meilleures actions
- **Fiche par action** : analyse comparée face au marché (jauges, classements,
  interprétations pédagogiques personnalisées au montant investi)
- **Simulateur de dividendes** (FCFA + € — parité fixe 1 € = 655,957 FCFA)
- **Portefeuille virtuel** (paper trading) : achats fictifs au cours du jour,
  évolution jour par jour, plus/moins-value, dividendes annuels estimés
- **Comptes synchronisés** : sessions sécurisées, watchlist serveur et plusieurs
  portefeuilles par utilisateur
- **Analyse avancée** : performances multi-périodes, MM20/MM50, RSI, volatilité,
  comparaison BRVM Composite/BRVM 30, screener et comparateur
- **Outils pédagogiques** : calendrier, alertes, objectif de dividendes,
  journal des transactions et backtesting de trois stratégies

## Architecture

```
Scrapers (brvm.org + sikafinance) → SQLite (SQLAlchemy) → API FastAPI → React (Vite)
        ↑ tâche planifiée quotidienne (18h30, lun-ven)
```

- **backend/** — scrapers, base, API. Doc interactive : http://localhost:8000/docs
- **frontend/** — dashboard React (react-router, recharts)

## Démarrage rapide

```bash
# 1. Backend
cd backend
pip install -r requirements.txt
python -m app.ingest                      # premier scraping (cotations + dividendes + secteurs)
python -m uvicorn app.main:app --reload   # API sur http://localhost:8000

# 2. Frontend (second terminal)
cd frontend
npm install
npm run dev                               # dashboard sur http://localhost:5173
```

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

La suite couvre le parsing des scrapers (fixtures HTML réalistes — c'est ce
qui casse en premier quand un site change), les règles métier (score, liquidité,
tendance des dividendes, pays) et l'API (cotations, top actions, cycle
achat/vente du portefeuille). La CI GitHub Actions les exécute à chaque push,
plus le build du front.

## API

| Méthode | Route                          | Description                                    |
| ------- | ------------------------------ | ---------------------------------------------- |
| GET     | `/actions`                     | Liste des actions (cours, dividende, secteur…) |
| GET     | `/actions/{sym}`               | Détail + historique + dividendes               |
| GET     | `/top-actions?limit=10`        | Classement par score, diversifié par secteur   |
| POST    | `/auth/inscription`            | Création de compte et session HttpOnly         |
| POST    | `/auth/connexion`              | Connexion                                      |
| POST    | `/refresh`                     | Relance le scraping (authentification requise) |
| GET     | `/mes-portefeuilles`           | Portefeuilles de l'utilisateur                 |
| GET     | `/watchlist`                   | Watchlist synchronisée                         |
| GET     | `/dividendes/calendrier`       | Calendrier et revenus estimés                   |
| POST    | `/backtest`                    | Comparaison des stratégies                     |
| GET     | `/portefeuille`                | Portefeuille virtuel + valeur jour par jour    |
| POST    | `/portefeuille/positions`      | Achat fictif au dernier cours                  |
| DELETE  | `/portefeuille/positions/{id}` | Vente fictive                                  |

## Scraping automatique

**☁️ Dans le cloud (source de vérité)** — un cron GitHub Actions
([scraping.yml](.github/workflows/scraping.yml)) scrape chaque jour de semaine
à 18h UTC (après la clôture d'Abidjan) et committe les données en JSON dans
[`data/`](data/) : un fichier de cotations par jour + dividendes + secteurs.
Le dépôt devient la mémoire du projet (pattern « git scraping ») — aucun PC
allumé n'est nécessaire, et tout l'historique est versionné et diffable.

Pour rattraper l'historique en local après quelques jours d'absence :

```bash
git pull
cd backend && python -m app.import_data   # upsert idempotent dans SQLite
```

**💻 En local (optionnel)** — une tâche planifiée Windows exécute aussi
`backend/scripts/daily_ingest.bat` (lun-ven 18h30, rattrapage au démarrage),
journal dans `backend/ingest_log.txt`.

- Config : variable d'environnement `BRVM_DB_PATH` pour changer la base

## Configuration

Copier `backend/.env.example` et `frontend/.env.example` dans la configuration
du service de déploiement. Variables importantes :

- `VITE_API_URL` : URL publique de l'API utilisée lors du build du frontend
- `BRVM_CORS_ORIGINS` : origines frontend autorisées, séparées par des virgules
- `COOKIE_SECURE=1` : obligatoire en production HTTPS
- `BRVM_CLAIM_LEGACY_DATA=1` : migration volontaire des anciennes transactions
  vers le premier compte ; laisser à `0` sur une installation neuve
- `BRVM_ADMIN_EMAILS` : comptes autorisés à lancer `/refresh`
- `SMTP_*` : paramètres optionnels pour les alertes par e-mail

## Docker

```bash
docker compose up --build
```

Le frontend est alors disponible sur `http://localhost:8080` et l'API sur
`http://localhost:8000`. En production, utiliser HTTPS, `COOKIE_SECURE=1`, une
origine CORS explicite et un volume persistant pour la base.

## Roadmap

- [x] Scraping cloud (cron GitHub Actions) pour ne plus dépendre du PC
- [x] Performances multi-périodes et moyennes mobiles
- [x] Docker et configuration par environnement
- [x] Alertes de prix, dividendes et détachements
- [ ] Accumuler au moins 50 séances réelles pour activer tous les indicateurs
- [ ] Remplacer les mini-migrations SQLite par Alembic avant montée en charge
