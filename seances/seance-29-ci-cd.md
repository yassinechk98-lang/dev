# Séance 29 (bonus, hors plan initial) — CI/CD avec GitHub Actions

## Théorie — c'est quoi CI/CD ?

- **CI** (Continuous Integration) : à chaque push, une machine distante (pas la
  tienne) installe le projet et lance les tests automatiquement. Si un test casse,
  tu le sais immédiatement, avant même que ça atteigne la production.
- **CD** (Continuous Deployment) : si les tests passent, le déploiement se fait
  **automatiquement**, sans commande manuelle.

Jusqu'ici, à chaque changement du frontend, il fallait faire `npm run build` puis
lancer le déploiement Netlify à la main. Avec CI/CD, un simple `git push` suffit
pour tout déclencher.

**Bonne nouvelle sur le backend** : Render est déjà connecté à GitHub et redéploie
automatiquement à chaque push sur `main` — c'est déjà du CD ! Aujourd'hui, on ajoute
la partie **CI** (tests automatiques) pour le backend, et le **CD** pour le frontend
(déploiement Netlify automatique).

## Théorie — GitHub Actions

Un **workflow** est un fichier YAML dans `.github/workflows/`, qui décrit une suite
d'étapes à exécuter automatiquement sur des événements (`push`, `pull_request`...).

```yaml
name: Tests backend

on:
  push:
    branches: [main]

jobs:
  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r todo-app/backend/requirements.txt
      - run: pytest todo-app/backend/
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          SECRET_KEY: ${{ secrets.SECRET_KEY }}
```

- `on: push: branches: [main]` : se déclenche à chaque push sur `main`
- `runs-on: ubuntu-latest` : GitHub fournit une machine Linux fraîche à chaque
  exécution
- `uses: ...` : réutilise une "action" toute faite (ex: cloner le dépôt, installer
  Python) — équivalent d'importer une bibliothèque plutôt que de tout réécrire
- `run: ...` : exécute une commande shell, comme dans ton terminal
- `${{ secrets.XXX }}` : injecte un **secret** GitHub (jamais visible dans les logs,
  jamais dans le code) — nos vraies valeurs `DATABASE_URL`/`SECRET_KEY`

## Théorie — les secrets GitHub

Comme `.env` en local, mais côté GitHub : des valeurs sensibles stockées de façon
chiffrée, accessibles seulement par les workflows, jamais affichées dans les logs
publics. On les configure dans **Settings → Secrets and variables → Actions** du
dépôt.

## Exercice

**Étape 1** — l'assistant crée les fichiers de workflow (tests backend + déploiement
frontend)

**Étape 2** — configure les secrets sur GitHub (Settings → Secrets and variables →
Actions → "New repository secret") :
- `DATABASE_URL` : la même valeur que ton `.env` local
- `SECRET_KEY` : la même valeur que ton `.env` local
- `NETLIFY_AUTH_TOKEN` : un nouveau token à générer sur Netlify (user settings →
  Applications → New access token)
- `NETLIFY_SITE_ID` : l'identifiant du site Netlify

**Étape 3** — push un petit changement, observe l'onglet **"Actions"** du dépôt
GitHub : les workflows se déclenchent, tests + déploiement automatiques, sans aucune
commande manuelle de ta part.
