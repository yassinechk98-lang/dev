# Séance 7 (Jour 5 du plan) — Fichiers texte et gestion d'erreurs

Dernier jour de la Semaine 1 — récap ensuite.

## Théorie — lire et écrire des fichiers texte

```python
# écrire dans un fichier (le crée s'il n'existe pas, écrase s'il existe déjà)
with open("notes.txt", "w") as f:
    f.write("Bonjour\n")
    f.write("Deuxième ligne\n")

# lire tout le contenu d'un fichier
with open("notes.txt", "r") as f:
    contenu = f.read()
    print(contenu)

# lire ligne par ligne
with open("notes.txt", "r") as f:
    for ligne in f:
        print(ligne.strip())   # .strip() enlève le \n de fin de ligne

# ajouter à la fin d'un fichier existant sans l'écraser
with open("notes.txt", "a") as f:
    f.write("Ligne ajoutée\n")
```

- `with open(...) as f:` ouvre le fichier et le referme **automatiquement** à la fin
  du bloc — c'est la façon standard de faire en Python, à utiliser systématiquement
- Modes : `"w"` (write, écrase), `"r"` (read, lecture), `"a"` (append, ajoute à la fin)

## Théorie — gestion d'erreurs avec try/except

Sans gestion d'erreur, une erreur fait planter tout le programme. `try/except` permet
de la "rattraper" et de continuer.

```python
try:
    nombre = int(input("Entre un nombre : "))
    resultat = 10 / nombre
    print(resultat)
except ValueError:
    print("Ce n'est pas un nombre valide")
except ZeroDivisionError:
    print("Impossible de diviser par zéro")
except FileNotFoundError:
    print("Le fichier n'existe pas")
```

- Le code dans `try:` est exécuté ; si une erreur du type précisé se produit,
  Python saute directement au `except` correspondant au lieu de planter
- On peut avoir plusieurs `except` pour gérer différents types d'erreurs
  spécifiquement
- `except Exception as e:` attrape n'importe quelle erreur et te donne le détail
  dans `e` (utile en dernier recours, mais moins précis)

## Exercice du jour

1. Crée `dev/exercices/jour5.py`
2. Écris dans un fichier `dev/exercices/notes.txt` 3 lignes de notes (une par ligne,
   ex: "Maths: 15", "Français: 12"...) avec `open(..., "w")`
3. Relis le fichier ligne par ligne et affiche chaque ligne avec `print()`
4. Utilise un `try/except` pour tenter d'ouvrir un fichier qui n'existe pas
   (ex: `"fichier_inexistant.txt"`) et affiche un message clair au lieu de planter
5. Exécute le script, vérifie qu'il ne plante pas
6. Fais toi-même `git add` + `git commit`

## Récap Semaine 1 (à faire après l'exercice)

Tu as vu : variables/types, conditions, boucles, listes, fonctions, dictionnaires,
fichiers, gestion d'erreurs, et le cycle Git de base (`status`/`add`/`commit`/`log`).
C'est la base de tout le reste du programme.

## À faire ensuite (Semaine 2, Jour 6)

- Modules/imports, environnement virtuel (venv), pip
