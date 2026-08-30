# Séance 14 (Jour 12 du plan) — Endpoints CRUD pour les tâches

## Théorie — CRUD

**CRUD** = Create, Read, Update, Delete — les 4 opérations de base sur des données.
Pour notre ressource "tâches", ça donne classiquement :

| Opération | Méthode HTTP | URL | Ce que ça fait |
|---|---|---|---|
| Create | `POST` | `/taches` | crée une nouvelle tâche |
| Read (liste) | `GET` | `/taches` | renvoie toutes les tâches |
| Read (une seule) | `GET` | `/taches/<id>` | renvoie une tâche précise |
| Update | `PUT` | `/taches/<id>` | modifie une tâche existante |
| Delete | `DELETE` | `/taches/<id>` | supprime une tâche |

Aujourd'hui, on fait **Create**, **Read (liste)** et **Delete** — le strict minimum
pour avoir un backend utilisable. Update viendra plus tard.

## Théorie — stocker en mémoire

"En mémoire" veut dire que les données vivent seulement dans une variable Python,
tant que le serveur tourne. Si tu redémarres le serveur, tout est perdu (on réglera
ça au Jour 13 avec un vrai stockage persistant). Pour l'instant, une simple liste de
dictionnaires suffit :

```python
taches = [
    {"id": 1, "titre": "Acheter du pain", "terminee": False},
    {"id": 2, "titre": "Reviser Python", "terminee": False},
]
```

## Théorie — GET, POST, DELETE avec Flask

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

taches = [
    {"id": 1, "titre": "Acheter du pain", "terminee": False},
]
prochain_id = 2

@app.route("/taches", methods=["GET"])
def lister_taches():
    return jsonify(taches)

@app.route("/taches", methods=["POST"])
def creer_tache():
    global prochain_id
    data = request.get_json()
    nouvelle_tache = {"id": prochain_id, "titre": data["titre"], "terminee": False}
    taches.append(nouvelle_tache)
    prochain_id += 1
    return jsonify(nouvelle_tache), 201

@app.route("/taches/<int:tache_id>", methods=["DELETE"])
def supprimer_tache(tache_id):
    global taches
    taches = [t for t in taches if t["id"] != tache_id]
    return "", 204
```

Points clés :
- `methods=["GET"]` précise quelle(s) méthode(s) HTTP cette route accepte (par défaut,
  une route n'accepte que `GET`)
- `jsonify(...)` convertit une liste/dictionnaire Python en JSON, le format standard
  d'échange de données entre une API et son client (React plus tard)
- `<int:tache_id>` dans l'URL capture un nombre depuis l'URL et le passe en paramètre
  à la fonction (ex: `/taches/2` → `tache_id = 2`)
- `request.get_json()` lit les données envoyées par le client dans le corps de la
  requête `POST`
- Les codes de statut (`201` = "créé avec succès", `204` = "succès, pas de contenu à
  renvoyer") informent le client du résultat

## Tester une API avec curl (sans navigateur, car GET seul ne suffit pas pour POST/DELETE)

```bash
curl http://localhost:5000/taches
curl -X POST http://localhost:5000/taches -H "Content-Type: application/json" -d "{\"titre\": \"Nouvelle tache\"}"
curl -X DELETE http://localhost:5000/taches/1
```

## Exercice du jour

1. Modifie `todo-app/backend/app.py` : remplace le contenu par la version ci-dessus
   (garde aussi la route `/` si tu veux)
2. Lance le serveur : `python todo-app/backend/app.py`
3. Dans un **deuxième terminal** (laisse le serveur tourner dans le premier), teste
   avec les commandes `curl` ci-dessus, dans l'ordre :
   - `GET /taches` → doit lister la tâche existante
   - `POST /taches` → doit créer une nouvelle tâche, renvoyer son JSON
   - `GET /taches` à nouveau → doit maintenant montrer 2 tâches
   - `DELETE /taches/1` → supprime la première
   - `GET /taches` → ne montre plus que la tâche créée par POST
4. Arrête le serveur (Ctrl+C dans le premier terminal)
5. Fais toi-même `git add` + `git commit` + `git push`

## À faire ensuite (séance suivante)

- Jour 13 : Persistance des données (fichier JSON puis SQLite)
