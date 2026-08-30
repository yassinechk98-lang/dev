# Séance 8 (Jour 6 du plan) — Modules/imports, environnement virtuel (venv), pip

Début de la Semaine 2.

## Théorie — modules et imports

Un **module** est simplement un fichier `.py` qui contient du code réutilisable
(fonctions, variables...). Python en fournit beaucoup "prêts à l'emploi" (la
**bibliothèque standard**), et on peut aussi créer les siens.

```python
import math
print(math.sqrt(16))     # 4.0 — utilise la fonction sqrt() du module math

from math import sqrt
print(sqrt(16))           # 4.0 — importe juste sqrt(), pas besoin du préfixe math.

import random
print(random.randint(1, 10))  # un nombre aléatoire entre 1 et 10
```

On peut aussi importer ses propres fichiers : si tu as `outils.py` avec une fonction
`saluer()`, un autre fichier dans le même dossier peut faire `from outils import saluer`.

## Théorie — qu'est-ce qu'un environnement virtuel (venv) ?

**Définition simple** : un environnement virtuel est un **dossier isolé** qui contient
sa propre copie de Python et ses propres bibliothèques installées, complètement séparée
du reste de ta machine et de tes autres projets.

**Pourquoi c'est nécessaire — le problème que ça résout** :

Sans venv, tout ce que tu installes avec `pip install` va dans un seul endroit
**partagé par tout ton ordinateur**. Ça pose un problème concret : imagine que le
Projet A a besoin de la version 1.0 d'une bibliothèque, mais le Projet B (sur la même
machine) a besoin de la version 2.0 de cette même bibliothèque. Comme il n'y a qu'un
seul endroit global, tu ne peux pas avoir les deux versions en même temps —
installer l'une casse l'autre projet.

Un environnement virtuel règle ça : chaque projet a son propre "coffre" de
bibliothèques, indépendant des autres. Tu peux avoir 10 projets sur ta machine, chacun
avec ses propres versions de bibliothèques, sans aucun conflit entre eux.

**Analogie** : c'est comme donner à chaque projet sa propre boîte à outils, plutôt que
de forcer tous les projets à partager une seule boîte à outils commune où tout le monde
se marche dessus.

**En pratique**, un venv c'est juste un dossier (souvent nommé `venv/` ou `.venv/`)
créé dans ton projet, qu'on "active" pour dire à Python "utilise cette copie isolée, pas
celle de la machine".

## Théorie — pip

`pip` est l'outil qui installe des bibliothèques externes (créées par d'autres
développeurs) que Python n'inclut pas par défaut — par exemple `flask` ou `requests`.
Une fois un venv activé, tout ce que `pip install` installe va **dans ce venv**, pas
ailleurs.

## Exercice du jour

1. Crée un environnement virtuel dans `dev/` :
   ```
   python -m venv venv
   ```
2. Active-le :
   - PowerShell : `.\venv\Scripts\Activate.ps1`
   - Git Bash : `source venv/Scripts/activate`

   Une fois activé, tu dois voir `(venv)` apparaître au début de ta ligne de commande.
3. Vérifie que pip fonctionne : `pip --version`
4. Installe une petite bibliothèque de test : `pip install requests`
5. Crée `dev/exercices/jour6.py` qui utilise le module `random` de la bibliothèque
   standard (pas besoin de venv pour celui-là, il est déjà inclus) :
   ```python
   import random
   nombre = random.randint(1, 100)
   print(f"Nombre aléatoire : {nombre}")
   ```
6. Ajoute un fichier `dev/.gitignore` s'il n'existe pas déjà, et vérifie qu'il contient
   une ligne `venv/` — **on ne commite jamais le dossier venv** (il est gros et
   régénérable, chacun le recrée localement avec la commande de l'étape 1)
7. Exécute le script, puis fais toi-même `git add` + `git commit` (seulement pour
   `jour6.py`, pas pour le dossier `venv/`)

## À faire ensuite (séance suivante)

- Jour 7 : Programmation orientée objet — classes et objets
