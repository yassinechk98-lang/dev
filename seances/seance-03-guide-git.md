# Séance 3 — Guide Git de A à Z

Ton dépôt `dev/` a déjà 2 commits :
```
e395793 Ajoute la seance 2 : cycle git de base
7ee069d Initialisation du depot : plan d'apprentissage et seance 1
```
Ce guide reprend tout depuis le début pour que tu aies une référence complète.

## A. C'est quoi Git ?

Git prend des "photos" (**commits**) de l'état de ton projet à chaque étape. Tu peux
revenir en arrière, voir l'historique, travailler sur des versions parallèles (branches),
et synchroniser ton travail avec un serveur distant (GitHub).

## B. Le vocabulaire de base

| Terme | Signification |
|---|---|
| **Dépôt (repository / repo)** | Le dossier suivi par Git (`dev/` chez toi) |
| **Commit** | Une photo figée de l'état du projet, avec un message |
| **Staging area** | Zone d'attente où tu places les fichiers avant de commit |
| **Branche (branch)** | Une ligne de développement indépendante (par défaut : `main`) |
| **Remote** | Une copie du dépôt hébergée ailleurs (ex: GitHub) |

## C. Déjà fait (config une fois pour toutes)

```bash
git config --global user.name "Yassine"
git config --global user.email "ton-email"
git init                    # a créé le dépôt dans dev/
```

## D. Le cycle quotidien (le plus important)

```bash
git status                  # 1. Que s'est-il passé depuis le dernier commit ?
git add <fichier>           # 2. Je choisis ce que je veux sauvegarder
git commit -m "message"     # 3. Je fige une photo avec un message clair
git log --oneline           # 4. Je vois l'historique
```

- `git add .` ajoute TOUT ce qui a changé — pratique mais vérifie toujours `git status`
  avant pour ne rien ajouter par erreur (mot de passe, fichier temporaire...)
- Un commit = **un changement logique**. Ne mélange pas "j'ajoute une fonctionnalité"
  et "je corrige une faute de frappe ailleurs" dans le même commit.
- Message de commit : verbe d'action + quoi + (pourquoi si utile).
  Bon : `"Ajoute la validation du formulaire de connexion"`
  Mauvais : `"fix"`, `"update"`, `"ça marche"`

## E. Voir ce qui a changé

```bash
git diff                    # différences non encore ajoutées (staging)
git diff --staged           # différences déjà ajoutées, prêtes à commit
git show <hash>             # contenu exact d'un commit précis (ex: git show 7ee069d)
```

## F. Annuler / corriger

```bash
git restore <fichier>              # annule les modifs non commitées d'un fichier
git restore --staged <fichier>     # retire un fichier du staging (sans perdre les modifs)
git commit --amend -m "nouveau message"  # corrige le dernier commit (message ou contenu)
```

⚠️ `git reset --hard` supprime définitivement des modifications. On l'utilisera plus
tard, avec précaution, jamais sans vérifier `git status` avant.

## G. Les branches (travailler en parallèle)

Une branche te permet de développer une fonctionnalité sans toucher à `main` tant
qu'elle n'est pas prête.

```bash
git branch                         # liste les branches (celle active a une *)
git switch -c ma-fonctionnalite    # crée ET bascule sur une nouvelle branche
git switch main                    # revient sur main
git merge ma-fonctionnalite        # (depuis main) fusionne le travail de la branche
git branch -d ma-fonctionnalite    # supprime la branche une fois fusionnée
```

On pratiquera ça concrètement à la Semaine 2 (Jour 10) avec un vrai exemple.

## H. .gitignore

Le fichier `.gitignore` (déjà créé chez toi) liste ce que Git doit **ignorer** :
environnements virtuels Python, `node_modules/`, fichiers de config locale...
Ces fichiers n'apparaîtront jamais dans `git status`.

## I. Travailler avec GitHub (le remote)

GitHub héberge une copie de ton dépôt en ligne : ça sert de sauvegarde et ça te
permet de montrer/partager ton code. Étapes (on les fera ensemble le moment venu,
prévu au Jour 10 du plan) :

1. Créer un compte sur github.com
2. Créer un nouveau dépôt vide sur GitHub (sans README, on en a déjà un projet)
3. Relier ton dépôt local :
   ```bash
   git remote add origin https://github.com/ton-pseudo/ton-depot.git
   git push -u origin main       # envoie tes commits vers GitHub (1re fois)
   git push                      # les fois suivantes
   git pull                      # récupère les changements distants
   ```
4. Cloner un dépôt existant ailleurs : `git clone <url>`

## J. Résumé — les 5 commandes que tu utiliseras 90% du temps

```bash
git status
git add <fichier>
git commit -m "message"
git log --oneline
git push
```

## Exercice du jour

1. Modifie `dev/exercices/jour1.py` (ajoute une ligne, par exemple un 5e print)
2. Fais `git status` → observe que le fichier est "modified", pas "untracked"
3. Fais `git diff` → observe la ligne que tu as ajoutée (en vert)
4. Fais `git add` puis `git commit -m "..."` toi-même
5. Vérifie avec `git log --oneline`

## À faire ensuite (séance suivante)

- Retour au plan : conditions (if/elif/else) en Python
