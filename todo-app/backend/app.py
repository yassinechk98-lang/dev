import json
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

FICHIER = os.path.join(os.path.dirname(__file__), "taches.json")

def charger_taches():
    try:
        with open(FICHIER, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def sauvegarder_taches(taches):
    with open(FICHIER, "w") as f:
        json.dump(taches, f, indent=2)

taches = charger_taches()
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
    sauvegarder_taches(taches)
    return jsonify(nouvelle_tache), 201

@app.route("/taches/<int:tache_id>", methods=["DELETE"])
def supprimer_tache(tache_id):
    global taches
    taches = [t for t in taches if t["id"] != tache_id]
    sauvegarder_taches(taches)
    return "", 204

if __name__ == "__main__":
    app.run(debug=True)
