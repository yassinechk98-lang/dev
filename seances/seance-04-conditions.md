# Séance 4 — Les conditions en Python (if/elif/else)

## Théorie

Une condition permet à un programme de prendre des décisions : exécuter un bloc de
code seulement si une certaine expression est vraie.

```python
age = 27

if age < 18:
    print("Tu es mineur")
elif age < 65:
    print("Tu es majeur")
else:
    print("Tu es senior")
```

- `if` : testé en premier
- `elif` (= "else if") : testé seulement si le `if` précédent était faux. On peut en
  mettre plusieurs à la suite
- `else` : exécuté seulement si aucune condition précédente n'était vraie (pas de
  condition sur cette ligne)
- L'**indentation** (4 espaces) définit ce qui appartient au bloc — contrairement à
  d'autres langages, Python n'utilise pas d'accolades `{}`

### Opérateurs de comparaison

| Opérateur | Signification |
|---|---|
| `==` | égal à |
| `!=` | différent de |
| `<` / `>` | plus petit / plus grand que |
| `<=` / `>=` | plus petit ou égal / plus grand ou égal |

⚠️ Piège fréquent : `=` sert à assigner une valeur (`age = 27`), `==` sert à comparer
(`age == 27`). Ne pas confondre !

### Opérateurs logiques (combiner des conditions)

```python
if age >= 18 and apprend_python:
    print("Majeur et en train d'apprendre Python")

if ville == "monastir" or ville == "tunis":
    print("Tu es en Tunisie")

if not apprend_python:
    print("Tu n'apprends pas Python")
```

- `and` : vrai seulement si les deux conditions sont vraies
- `or` : vrai si au moins une des conditions est vraie
- `not` : inverse une condition (vrai devient faux et inversement)

## Exercice du jour

1. Crée un fichier `dev/exercices/jour2.py`
2. Déclare une variable `note = 14` (une note sur 20, choisis la valeur que tu veux)
3. Écris un `if/elif/else` qui affiche :
   - `"Excellent"` si la note est >= 16
   - `"Bien"` si la note est >= 10 et < 16
   - `"Insuffisant"` si la note est < 10
4. Exécute le script : `python dev/exercices/jour2.py`
5. Fais toi-même le cycle Git : `git status` → `git add` → `git commit -m "..."`

## À faire ensuite (séance suivante)

- Les boucles en Python (`for`, `while`)
