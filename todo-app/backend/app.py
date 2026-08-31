import json
import os
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

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
prochain_id = max([t["id"] for t in taches], default=0) + 1

@app.route("/taches", methods=["GET"])
def lister_taches():
    return jsonify(taches)

@app.route("/taches", methods=["POST"])
def creer_tache():
    global prochain_id
    data = request.get_json()

    if not data or "titre" not in data or not data["titre"].strip():
        return jsonify({"erreur": "Le champ 'titre' est requis"}), 400

    nouvelle_tache = {"id": prochain_id, "titre": data["titre"], "terminee": False}
    taches.append(nouvelle_tache)
    prochain_id += 1
    sauvegarder_taches(taches)
    return jsonify(nouvelle_tache), 201

@app.route("/taches/<int:tache_id>", methods=["PUT"])
def modifier_tache(tache_id):
    tache = next((t for t in taches if t["id"] == tache_id), None)
    if tache is None:
        return jsonify({"erreur": f"Aucune tache avec l'id {tache_id}"}), 404

    tache["terminee"] = not tache["terminee"]
    sauvegarder_taches(taches)
    return jsonify(tache)

@app.route("/taches/<int:tache_id>", methods=["DELETE"])
def supprimer_tache(tache_id):
    global taches
    if not any(t["id"] == tache_id for t in taches):
        return jsonify({"erreur": f"Aucune tache avec l'id {tache_id}"}), 404

    taches = [t for t in taches if t["id"] != tache_id]
    sauvegarder_taches(taches)
    return "", 204

if __name__ == "__main__":
    app.run(debug=True)
