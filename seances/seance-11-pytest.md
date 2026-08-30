# Séance 11 (Jour 9 du plan) — Tests avec pytest

## Théorie — pourquoi tester son code ?

Jusqu'ici, tu as vérifié que ton code marchait en l'exécutant et en regardant le
résultat à l'œil. Ça devient vite impossible à faire à la main quand un projet grossit
(comme le Todo-list qu'on va construire) : à chaque petit changement, il faudrait
retester manuellement toutes les fonctionnalités.

Un **test automatisé** est un petit bout de code qui vérifie qu'une fonction fait bien
ce qu'elle est censée faire, et qui peut être relancé en une seconde à tout moment.
`pytest` est l'outil le plus utilisé en Python pour écrire et lancer ces tests.

## Théorie — écrire un test avec pytest

Convention : les fichiers de test s'appellent `test_*.py`, et chaque fonction de test
commence par `test_`.

```python
# calculs.py
def additionner(a, b):
    return a + b

def diviser(a, b):
    if b == 0:
        raise ValueError("Division par zéro impossible")
    return a / b
```

```python
# test_calculs.py
from calculs import additionner, diviser

def test_additionner():
    assert additionner(2, 3) == 5
    assert additionner(-1, 1) == 0

def test_diviser():
    assert diviser(10, 2) == 5

def test_diviser_par_zero():
    try:
        diviser(10, 0)
        assert False, "aurait dû lever une erreur"
    except ValueError:
        pass   # c'est le comportement attendu
```

- `assert expression` : si l'expression est fausse, le test échoue avec une erreur
  claire ; si elle est vraie, rien ne se passe (le test continue/réussit)
- Un fichier de test importe le code qu'il teste (ici `from calculs import ...`)
- Pour tester qu'une erreur est bien levée, `pytest` propose une syntaxe plus propre :
  `with pytest.raises(ValueError): diviser(10, 0)` (on la voit dans l'exercice)

## Lancer les tests

Dans le terminal (venv activé) :
```
pip install pytest
pytest
```
`pytest` détecte automatiquement tous les fichiers `test_*.py` du dossier et lance
toutes les fonctions `test_*` qu'il trouve. Il affiche un résumé : combien ont réussi
(vert), combien ont échoué (rouge), avec le détail de chaque échec.

## Exercice du jour

1. Installe pytest (venv activé) : `pip install pytest`
2. Crée `dev/exercices/calculs.py` avec les deux fonctions `additionner` et `diviser`
   ci-dessus
3. Crée `dev/exercices/test_calculs.py` avec :
   - `test_additionner` (comme ci-dessus)
   - `test_diviser`
   - `test_diviser_par_zero`, en utilisant cette fois la syntaxe pytest :
     ```python
     import pytest
     from calculs import additionner, diviser

     def test_diviser_par_zero():
         with pytest.raises(ValueError):
             diviser(10, 0)
     ```
4. Lance `pytest` depuis `dev/exercices/` (ou `pytest exercices/` depuis `dev/`) et
   vérifie que tous les tests passent (en vert)
5. Bonus : casse volontairement `additionner` (ex: `return a - b`), relance `pytest`,
   observe le message d'erreur rouge, puis annule ta modification
6. Fais toi-même `git add` + `git commit`

## À faire ensuite (séance suivante)

- Jour 10 : Branches Git, merge, .gitignore, compte GitHub + dépôt distant + push
  (dernier jour de la Semaine 2 !)
