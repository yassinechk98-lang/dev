# Séance 6 (Jour 4 du plan) — Fonctions et dictionnaires

## Théorie — les fonctions

Une fonction regroupe du code réutilisable sous un nom, pour éviter de le réécrire.

```python
def saluer(nom):
    return f"Bonjour {nom} !"

message = saluer("Yassine")
print(message)   # Bonjour Yassine !
```

- `def nom_fonction(parametres):` déclare la fonction
- `return` renvoie une valeur au code qui a appelé la fonction (sans `return`, la
  fonction renvoie `None`)
- On peut avoir plusieurs paramètres, et des valeurs par défaut :

```python
def saluer(nom, politesse="Bonjour"):
    return f"{politesse} {nom} !"

print(saluer("Yassine"))               # Bonjour Yassine !
print(saluer("Yassine", "Salut"))      # Salut Yassine !
```

## Théorie — les dictionnaires

Un dictionnaire stocke des paires **clé → valeur** (contrairement à une liste, indexée
par position).

```python
personne = {
    "nom": "Yassine",
    "age": 27,
    "ville": "Monastir"
}

print(personne["nom"])          # Yassine (accès par clé)
personne["age"] = 28            # modifier une valeur
personne["email"] = "..."       # ajouter une nouvelle clé
del personne["ville"]           # supprimer une clé

for cle, valeur in personne.items():
    print(f"{cle} : {valeur}")  # parcourir tout le dictionnaire
```

## Exercice du jour

1. Crée `dev/exercices/jour4.py`
2. Écris une fonction `calculer_moyenne(notes)` qui prend une **liste** de notes et
   renvoie leur moyenne (indice : `sum(notes) / len(notes)`)
3. Teste-la avec une liste de notes, affiche le résultat
4. Crée un dictionnaire `etudiant` avec au moins 3 clés (`nom`, `notes`, `ville`...)
5. Affiche chaque clé/valeur du dictionnaire avec une boucle `for` et `.items()`
6. Exécute le script, puis fais toi-même `git add` + `git commit`

## À faire ensuite (séance suivante)

- Jour 5 du plan : fichiers texte, gestion d'erreurs (try/except)
