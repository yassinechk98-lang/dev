from flask import Flask, request, jsonify

app = Flask(__name__)

taches = [{"id": 1, "titre": "Acheter du pain", "terminee": False}]
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

if __name__ == "__main__":
    app.run(debug=True)
