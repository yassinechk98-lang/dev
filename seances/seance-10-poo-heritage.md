# Séance 10 (Jour 8 du plan) — POO suite : méthodes et héritage

## Théorie — plus de méthodes sur une classe

On peut ajouter autant de méthodes que nécessaire à une classe. Reprenons `Tache` de
la séance précédente et enrichissons-la :

```python
class Tache:
    def __init__(self, titre, priorite="normale", terminee=False):
        self.titre = titre
        self.priorite = priorite
        self.terminee = terminee

    def marquer_terminee(self):
        self.terminee = True

    def changer_priorite(self, nouvelle_priorite):
        self.priorite = nouvelle_priorite

    def afficher(self):
        statut = "faite" if self.terminee else "à faire"
        print(f"[{self.priorite}] {self.titre} ({statut})")
```

## Théorie — l'héritage

L'héritage permet de créer une classe qui **réutilise** tout ce qu'une autre classe
sait déjà faire, et d'y ajouter ou modifier des choses spécifiques. Ça évite de
dupliquer du code entre des classes proches.

```python
class TacheUrgente(Tache):
    def __init__(self, titre, deadline):
        super().__init__(titre, priorite="urgente")   # appelle __init__ du parent
        self.deadline = deadline

    def afficher(self):
        statut = "faite" if self.terminee else "à faire"
        print(f"[URGENT - deadline {self.deadline}] {self.titre} ({statut})")


t = TacheUrgente("Rendre le rapport", "demain 18h")
t.afficher()             # [URGENT - deadline demain 18h] Rendre le rapport (à faire)
t.marquer_terminee()     # méthode héritée de Tache, pas besoin de la réécrire
t.afficher()             # [URGENT - deadline demain 18h] Rendre le rapport (faite)
```

Points clés :
- `class TacheUrgente(Tache):` — le `(Tache)` dit "hérite de Tache" : `TacheUrgente`
  a accès à tout ce que `Tache` sait faire (`marquer_terminee`, `changer_priorite`...)
- `super().__init__(...)` appelle le `__init__` de la classe parente (`Tache`), pour
  ne pas réécrire `self.titre = titre` etc.
- **Redéfinir une méthode** (ici `afficher`) dans la classe enfant remplace celle du
  parent, seulement pour les objets de ce type — c'est ce qu'on appelle
  l'**overriding**
- Une méthode non redéfinie (ici `marquer_terminee`) reste celle du parent, héritée
  automatiquement

## Exercice du jour

1. Dans `dev/exercices/jour8.py`, reprends la classe `Tache` enrichie (avec
   `priorite`) ci-dessus
2. Crée une classe `TacheUrgente` qui hérite de `Tache`, avec un attribut `deadline`
   en plus, et sa propre méthode `afficher` (comme dans l'exemple)
3. Crée une liste contenant 2 `Tache` normales et 1 `TacheUrgente`
4. Boucle sur la liste et appelle `.afficher()` sur chacune — remarque que ça marche
   pour les deux types d'objets sans code spécial
5. Exécute le script, vérifie l'affichage
6. Fais toi-même `git add` + `git commit`

## À faire ensuite (séance suivante)

- Jour 9 : Tests avec pytest (bases)
