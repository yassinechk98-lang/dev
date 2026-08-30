# Séance 17 (Jour 15 du plan) — Tests de l'API + récap Semaine 3

Dernier jour de la Semaine 3 !

## Théorie — tester une API Flask avec pytest

Pas besoin de lancer le serveur manuellement pour la tester : Flask fournit un
**client de test** qui simule des requêtes HTTP directement en Python, très rapide,
sans réseau.

```python
# test_app.py (dans todo-app/backend/)
import pytest
from app import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_lister_taches(client):
    reponse = client.get("/taches")
    assert reponse.status_code == 200

def test_creer_tache(client):
    reponse = client.post("/taches", json={"titre": "Tache de test"})
    assert reponse.status_code == 201
    assert reponse.get_json()["titre"] == "Tache de test"

def test_creer_tache_sans_titre(client):
    reponse = client.post("/taches", json={})
    assert reponse.status_code == 400

def test_supprimer_tache_inexistante(client):
    reponse = client.delete("/taches/999999")
    assert reponse.status_code == 404
```

Points clés :
- `@pytest.fixture` : une fonction "préparatoire" que pytest exécute avant chaque
  test qui la demande en paramètre (ici `client`) — évite de répéter le même code
  d'installation dans chaque test
- `app.test_client()` crée un faux client HTTP qui appelle directement les routes
  Flask, sans vraiment démarrer un serveur réseau
- `client.get(...)`, `client.post(..., json=...)`, `client.delete(...)` simulent les
  requêtes
- `reponse.status_code` et `reponse.get_json()` inspectent la réponse, exactement
  comme avec `curl` mais directement testable automatiquement

⚠️ Ces tests utilisent le vrai `taches.json` du projet (pas un fichier séparé) — ce
n'est pas la pratique idéale sur un vrai projet (on isolerait les tests avec des
données jetables), mais suffisant pour s'entraîner aujourd'hui.

## Exercice du jour

1. Crée `todo-app/backend/test_app.py` avec le code ci-dessus
2. Lance les tests depuis `todo-app/backend/` : `pytest`
3. Vérifie que les 4 tests passent
4. Fais toi-même `git add` + `git commit` + `git push`

## Récap Semaine 3 — Backend complet

Tu as construit un vrai backend web : Flask, routes GET/POST/DELETE, persistance
JSON, validation et gestion d'erreurs, tests automatisés. `todo-app/backend/` est
maintenant une petite API fonctionnelle et testée.

## À faire ensuite (Semaine 4)

- Jour 16 : Bases JavaScript moderne (const/let, fonctions fléchées, fetch/promesses)
  — début du frontend React !
