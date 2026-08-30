# Séance 9 (Jour 7 du plan) — POO : classes et objets

## Théorie — c'est quoi une classe ?

Jusqu'ici, on a stocké des infos liées dans des dictionnaires (`{"nom": "Yassine",
"age": 27}`). Une **classe** est une autre façon de faire ça : un **plan/modèle**
pour créer des objets qui regroupent à la fois des données ET des fonctions qui
agissent sur ces données.

Un **objet** est une "instance" concrète créée à partir d'une classe — la classe est le
plan, l'objet est la chose construite à partir de ce plan (comme un plan de maison vs.
une vraie maison construite).

```python
class Tache:
    def __init__(self, titre, terminee=False):
        self.titre = titre
        self.terminee = terminee

    def marquer_terminee(self):
        self.terminee = True

    def afficher(self):
        statut = "faite" if self.terminee else "à faire"
        print(f"{self.titre} ({statut})")


# créer des objets à partir de la classe Tache
t1 = Tache("Acheter du pain")
t2 = Tache("Réviser Python")

t1.afficher()              # Acheter du pain (à faire)
t1.marquer_terminee()
t1.afficher()              # Acheter du pain (faite)
```

Points clés :
- `class Tache:` déclare la classe (convention : nom avec Majuscule)
- `__init__` est une méthode spéciale appelée automatiquement à la création d'un objet
  (`Tache("Acheter du pain")`) — elle initialise ses données
- `self` représente l'objet lui-même — c'est **toujours** le premier paramètre de
  chaque méthode d'une classe, Python le passe automatiquement (tu ne l'écris jamais
  en appelant la méthode, seulement en la définissant)
- `self.titre = titre` stocke une donnée **sur l'objet** — on y accède ensuite avec
  `t1.titre`
- Une méthode (`marquer_terminee`, `afficher`) est juste une fonction définie dans la
  classe, qui peut lire/modifier les données de l'objet via `self`

## Pourquoi utiliser une classe plutôt qu'un dictionnaire ?

Avec un dictionnaire, rien n'empêche des données incohérentes, et les fonctions qui
agissent dessus (comme "marquer terminée") vivent séparément. Avec une classe, les
données et les actions qui leur sont propres sont regroupées au même endroit, et on
peut créer autant d'objets `Tache` qu'on veut, tous garantis d'avoir la même structure
(`titre`, `terminee`) et les mêmes méthodes.

## Exercice du jour

1. Crée `dev/exercices/jour7.py`
2. Écris une classe `Tache` comme ci-dessus (`__init__`, `marquer_terminee`,
   `afficher`)
3. Crée une liste de 3 objets `Tache` avec des titres différents
4. Marque-en une comme terminée
5. Boucle sur la liste et appelle `.afficher()` pour chacune
6. Exécute le script, vérifie l'affichage
7. Fais toi-même `git add` + `git commit`

## À faire ensuite (séance suivante)

- Jour 8 : POO suite — méthodes supplémentaires, un peu d'héritage
