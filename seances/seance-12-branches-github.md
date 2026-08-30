# Séance 12 (Jour 10 du plan) — Branches, merge, GitHub, push

Dernier jour de la Semaine 2 — après ça, Semaine 3 : le backend Flask commence !

## Théorie — les branches Git

Une branche est une ligne de développement indépendante. Jusqu'ici, tu as tout fait
directement sur `main`. En pratique, on développe souvent une nouvelle fonctionnalité
sur une branche séparée, pour ne pas toucher à `main` tant que ce n'est pas prêt.

```bash
git branch                       # liste les branches (celle active a une *)
git switch -c ma-fonctionnalite  # crée ET bascule sur une nouvelle branche
# ... tu travailles, tu fais des commits normalement sur cette branche ...
git switch main                  # reviens sur main
git merge ma-fonctionnalite      # fusionne le travail de la branche dans main
git branch -d ma-fonctionnalite  # supprime la branche, son travail est déjà dans main
```

**Pourquoi c'est utile** : si ta fonctionnalité casse quelque chose en cours de route,
`main` reste intact et fonctionnel pendant que tu corriges sur la branche. Une fois que
tout marche, tu fusionnes (`merge`) proprement.

## Théorie — un conflit de merge (juste pour comprendre, pas à faire aujourd'hui)

Si `main` et ta branche ont modifié **la même ligne** d'un fichier différemment, Git ne
sait pas laquelle garder et te demande de trancher toi-même (un "conflit"). On
pratiquera ça concrètement plus tard sur un vrai cas.

## Théorie — GitHub (le remote)

GitHub héberge une copie de ton dépôt en ligne. Ça sert de sauvegarde (si ton PC
crash, ton code est en sécurité ailleurs) et ça permet de montrer/partager ton travail.

```bash
git remote add origin https://github.com/ton-pseudo/ton-depot.git
git push -u origin main     # envoie tes commits vers GitHub (1re fois seulement)
git push                    # les fois suivantes, juste ça suffit
git pull                    # récupère les changements distants
```

## Exercice du jour

**Partie A — pratiquer une branche**
1. Crée une branche : `git switch -c exercice-branche`
2. Crée `dev/exercices/jour10.py` avec un petit script simple (ex: affiche "Test
   branche" avec `print()`)
3. Commit sur cette branche : `git add` + `git commit -m "..."`
4. Reviens sur main : `git switch main`
5. Fusionne : `git merge exercice-branche`
6. Vérifie avec `git log --oneline` que le commit de la branche est bien dans `main`
7. Supprime la branche (plus utile) : `git branch -d exercice-branche`

**Partie B — connecter GitHub (si tu n'as pas encore de compte)**
1. Crée un compte sur github.com (si pas déjà fait)
2. Crée un nouveau dépôt **vide** sur GitHub (sans README, sans .gitignore — on en a
   déjà un), note son URL (ex: `https://github.com/ton-pseudo/dev.git`)
3. Relie ton dépôt local : `git remote add origin <ton-URL>`
4. Envoie tout ton historique : `git push -u origin main`
5. Rafraîchis la page GitHub : tu dois voir tous tes fichiers et tout ton historique
   de commits en ligne !

## À faire ensuite (séance suivante)

- Semaine 3, Jour 11 : Concepts HTTP/REST, Flask, "Hello World" API — le vrai début
  du projet Todo-list !
