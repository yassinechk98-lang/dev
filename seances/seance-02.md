# Séance 2 — Configuration Git + premier commit + notion de dépôt

## Ce qui a été fait

- Identité Git configurée globalement (une seule fois pour toute la machine) :
  ```
  git config --global user.name "Yassine"
  git config --global user.email "ton-email"
  ```
- Dépôt Git initialisé dans `dev/` avec `git init`
- Fichier `.gitignore` créé pour ignorer les fichiers qu'on ne veut jamais versionner
  (dossiers `node_modules/`, environnements virtuels Python, config locale...)
- Premier commit fait : `Initialisation du depot : plan d'apprentissage et seance 1`

## Théorie — le cycle Git de base

Git suit toujours le même cycle pour sauvegarder du travail :

1. **`git status`** → voir ce qui a changé depuis le dernier commit
2. **`git add <fichier>`** → mettre un fichier dans la "zone de préparation" (staging)
   (`git add .` = tout ajouter d'un coup, à utiliser avec prudence)
3. **`git commit -m "message clair"`** → figer une photo de l'état du projet, avec un message
4. **`git log --oneline`** → voir l'historique des commits

Un bon message de commit décrit **ce qui a changé et pourquoi**, au présent :
`"Ajoute la fonction de calcul de moyenne"`, pas `"fix"` ou `"update"`.

## Exercice du jour

1. Termine l'exercice `dev/exercices/jour1.py` de la séance 1 si ce n'est pas fait
2. Lance `git status` dans le terminal → observe que le fichier apparaît en "untracked"
3. Fais toi-même :
   ```
   git add exercices/jour1.py
   git commit -m "Premier script Python : variables et f-strings"
   ```
4. Vérifie avec `git log --oneline` que ton commit apparaît

## À faire ensuite (séance suivante)

- Conditions (if/elif/else) en Python
