# Séance 1 — Installer Git + variables Python

## Étape 1 : installer Git

Git n'était pas installé sur la machine. Commande à lancer dans le terminal :

```
winget install --id Git.Git -e --source winget
```

Après l'installation, fermer/rouvrir le terminal pour que la commande `git` soit reconnue.

## Étape 2 : théorie — les variables en Python

En Python, une **variable** est une étiquette qui pointe vers une valeur. Pas besoin
de déclarer le type, Python le déduit automatiquement :

```python
nom = "Yassine"        # str (texte)
age = 27                # int (entier)
taille = 1.75           # float (décimal)
est_etudiant = True     # bool (vrai/faux)
```

- Vérifier le type d'une variable : `type(nom)`
- Afficher une valeur : `print(nom)`
- Combiner du texte et des variables avec un **f-string** : `print(f"Je m'appelle {nom}")`

## Exercice du jour

1. Créer un dossier `dev/exercices/`
2. Créer un fichier `dev/exercices/jour1.py`
3. Déclarer 4 variables : ton prénom, ton âge, ta ville, et un booléen `apprend_python = True`
4. Afficher une phrase qui les combine avec un f-string
5. Exécuter le script : `python dev/exercices/jour1.py`

## À faire ensuite (séance suivante)

- Configurer Git (`git config user.name` / `user.email`)
- Faire le tout premier `git init` + premier commit du dossier `dev/`
