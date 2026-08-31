# Séance 24 (Jour 23 du plan) — Démo finale et bilan

## Démo finale

Lance l'app complète une dernière fois et refais le parcours utilisateur en entier,
comme si tu la présentais à quelqu'un :

1. `python todo-app/backend/app.py` (Terminal 1)
2. `cd todo-app/frontend && npm run dev` (Terminal 2)
3. Ouvre le navigateur, et déroule : voir la liste → ajouter une tâche → la cocher
   terminée → la supprimer → recharger la page (persistance) → couper le backend
   pour voir le message d'erreur → le rallumer

## Bilan — le chemin parcouru

Point de départ (Séance 1) : Git n'était pas installé, premières variables Python.

**Semaine 1 — Bases Python** : variables/types, conditions, boucles, listes,
fonctions, dictionnaires, fichiers, `try/except`, et le cycle Git de base
(`status`/`add`/`commit`/`log`).

**Semaine 2 — Python intermédiaire + Git avancé** : modules/imports, environnement
virtuel (venv), POO (classes, objets, héritage), tests avec `pytest`, branches Git,
GitHub et `push`.

**Semaine 3 — Backend** : concepts HTTP/REST, Flask, routes CRUD complètes (GET,
POST, PUT, DELETE), persistance JSON, validation et codes d'erreur HTTP (400, 404),
tests d'API avec le client de test Flask.

**Semaine 4 — Frontend** : JavaScript moderne (const/let, arrow functions,
async/await), React + Vite, JSX, composants, `useState`, `useEffect`, connexion
complète au backend (CORS, fetch), gestion d'erreur réseau.

**Résultat** : une application full-stack fonctionnelle — `todo-app/backend/` (API
Flask testée) + `todo-app/frontend/` (interface React) qui communiquent en temps
réel, avec tout l'historique versionné sur GitHub.

## Et après ?

Le plan initial de 23 jours est terminé. Pistes naturelles pour la suite, si tu veux
continuer à progresser (pas de pression, à ton rythme) :
- Remplacer le fichier JSON par une vraie base SQLite (théorie déjà vue au Jour 13)
- Déployer l'app en ligne pour la rendre accessible depuis n'importe où
- Ajouter une authentification (plusieurs utilisateurs, chacun ses tâches)
- Approfondir React : gestion de plusieurs pages (routing), styles plus poussés
