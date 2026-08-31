import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import create_engine, text

load_dotenv()

app = Flask(__name__)
CORS(app)

engine = create_engine(os.environ["DATABASE_URL"])

with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS taches (
            id SERIAL PRIMARY KEY,
            titre TEXT NOT NULL,
            terminee BOOLEAN DEFAULT FALSE
        )
    """))
    conn.commit()

def lister_taches_db():
    with engine.connect() as conn:
        resultat = conn.execute(text("SELECT id, titre, terminee FROM taches ORDER BY id"))
        return [dict(row._mapping) for row in resultat]

def creer_tache_db(titre):
    with engine.connect() as conn:
        resultat = conn.execute(
            text("INSERT INTO taches (titre) VALUES (:titre) RETURNING id, titre, terminee"),
            {"titre": titre},
        )
        conn.commit()
        return dict(resultat.fetchone()._mapping)

def basculer_tache_db(tache_id):
    with engine.connect() as conn:
        resultat = conn.execute(
            text("""
                UPDATE taches SET terminee = NOT terminee
                WHERE id = :id
                RETURNING id, titre, terminee
            """),
            {"id": tache_id},
        )
        conn.commit()
        ligne = resultat.fetchone()
        return dict(ligne._mapping) if ligne else None

def supprimer_tache_db(tache_id):
    with engine.connect() as conn:
        resultat = conn.execute(text("DELETE FROM taches WHERE id = :id"), {"id": tache_id})
        conn.commit()
        return resultat.rowcount > 0

@app.route("/taches", methods=["GET"])
def lister_taches():
    return jsonify(lister_taches_db())

@app.route("/taches", methods=["POST"])
def creer_tache():
    data = request.get_json()

    if not data or "titre" not in data or not data["titre"].strip():
        return jsonify({"erreur": "Le champ 'titre' est requis"}), 400

    nouvelle_tache = creer_tache_db(data["titre"])
    return jsonify(nouvelle_tache), 201

@app.route("/taches/<int:tache_id>", methods=["PUT"])
def modifier_tache(tache_id):
    tache = basculer_tache_db(tache_id)
    if tache is None:
        return jsonify({"erreur": f"Aucune tache avec l'id {tache_id}"}), 404

    return jsonify(tache)

@app.route("/taches/<int:tache_id>", methods=["DELETE"])
def supprimer_tache(tache_id):
    supprime = supprimer_tache_db(tache_id)
    if not supprime:
        return jsonify({"erreur": f"Aucune tache avec l'id {tache_id}"}), 404

    return "", 204

if __name__ == "__main__":
    app.run(debug=True)
