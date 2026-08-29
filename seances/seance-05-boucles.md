# Séance 5 — Les boucles en Python (for / while)

## Théorie

Une boucle permet de répéter un bloc de code plusieurs fois, sans le réécrire à la main.

### La boucle `for`

Utilisée quand on connaît à l'avance sur quoi on veut itérer (une liste, une plage de
nombres...).

```python
for i in range(5):
    print(i)
# affiche 0, 1, 2, 3, 4 (range(5) = de 0 à 4, 5 exclu)

fruits = ["pomme", "banane", "kiwi"]
for fruit in fruits:
    print(fruit)
# affiche pomme, banane, kiwi
```

- `range(5)` génère les nombres de 0 à 4 (5 valeurs, s'arrête avant 5)
- `range(2, 8)` génère de 2 à 7
- `range(0, 10, 2)` génère de 0 à 8 par pas de 2 (0, 2, 4, 6, 8)
- On peut boucler directement sur les éléments d'une liste (`fruits`), pas besoin
  d'index

### La boucle `while`

Utilisée quand on répète tant qu'une condition reste vraie, sans savoir à l'avance
combien de fois.

```python
compteur = 0
while compteur < 3:
    print(f"tour numéro {compteur}")
    compteur += 1   # équivaut à : compteur = compteur + 1
```

⚠️ Piège fréquent : oublier d'incrémenter la variable (`compteur += 1`) → boucle
infinie qui ne s'arrête jamais. Toujours vérifier que la condition finira par devenir
fausse.

### `break` et `continue`

```python
for i in range(10):
    if i == 5:
        break        # arrête complètement la boucle
    print(i)

for i in range(5):
    if i == 2:
        continue     # saute cette itération, passe à la suivante
    print(i)
```

## Exercice du jour

1. Crée `dev/exercices/jour3.py`
2. Avec une boucle `for` et `range()`, affiche les nombres de 1 à 10
3. Avec la même boucle, affiche seulement les nombres pairs (indice : `if i % 2 == 0`
   — `%` donne le reste d'une division)
4. Bonus : avec une boucle `while`, affiche un compte à rebours de 5 à 1, puis
   "Décollage !"
5. Exécute le script : `python dev/exercices/jour3.py`
6. Fais toi-même le cycle Git : `git status` → `git add` → `git commit -m "..."`

## À faire ensuite (séance suivante)

- Les listes en profondeur (méthodes : `.append()`, `.remove()`, slicing...)
