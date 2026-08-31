import os
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
CORS(app)

SECRET_KEY = os.environ["SECRET_KEY"]
engine = create_engine(os.environ["DATABASE_URL"])

with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS taches (
            id SERIAL PRIMARY KEY,
            titre TEXT NOT NULL,
            terminee BOOLEAN DEFAULT FALSE
        )
    """))
    conn.execute(text("ALTER TABLE taches ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)"))
    conn.commit()

# ---------- authentification ----------

def generer_token(user_id):
    return jwt.encode(
        {"user_id": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=7)},
        SECRET_KEY,
        algorithm="HS256",
    )

def token_requis(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"erreur": "Authentification requise"}), 401
        try:
            donnees = jwt.decode(auth[7:], SECRET_KEY, algorithms=["HS256"])
        except jwt.InvalidTokenError:
            return jsonify({"erreur": "Token invalide ou expire"}), 401
        return f(donnees["user_id"], *args, **kwargs)
    return wrapper

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"erreur": "username et password requis"}), 400

    with engine.connect() as conn:
        existe = conn.execute(
            text("SELECT id FROM users WHERE username = :u"), {"u": data["username"]}
        ).fetchone()
        if existe:
            return jsonify({"erreur": "Ce nom d'utilisateur existe deja"}), 400

        resultat = conn.execute(
            text("INSERT INTO users (username, password_hash) VALUES (:u, :p) RETURNING id"),
            {"u": data["username"], "p": generate_password_hash(data["password"])},
        )
        conn.commit()
        user_id = resultat.fetchone()[0]

    return jsonify({"token": generer_token(user_id)}), 201

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"erreur": "username et password requis"}), 400

    with engine.connect() as conn:
        ligne = conn.execute(
            text("SELECT id, password_hash FROM users WHERE username = :u"),
            {"u": data["username"]},
        ).fetchone()

    if not ligne or not check_password_hash(ligne.password_hash, data["password"]):
        return jsonify({"erreur": "Identifiants invalides"}), 401

    return jsonify({"token": generer_token(ligne.id)})

# ---------- taches (scopees par utilisateur) ----------

def lister_taches_db(user_id):
    with engine.connect() as conn:
        resultat = conn.execute(
            text("SELECT id, titre, terminee FROM taches WHERE user_id = :uid ORDER BY id"),
            {"uid": user_id},
        )
        return [dict(row._mapping) for row in resultat]

def creer_tache_db(user_id, titre):
    with engine.connect() as conn:
        resultat = conn.execute(
            text("""
                INSERT INTO taches (titre, terminee, user_id)
                VALUES (:titre, FALSE, :uid)
                RETURNING id, titre, terminee
            """),
            {"titre": titre, "uid": user_id},
        )
        conn.commit()
        return dict(resultat.fetchone()._mapping)

def basculer_tache_db(user_id, tache_id):
    with engine.connect() as conn:
        resultat = conn.execute(
            text("""
                UPDATE taches SET terminee = NOT terminee
                WHERE id = :id AND user_id = :uid
                RETURNING id, titre, terminee
            """),
            {"id": tache_id, "uid": user_id},
        )
        conn.commit()
        ligne = resultat.fetchone()
        return dict(ligne._mapping) if ligne else None

def supprimer_tache_db(user_id, tache_id):
    with engine.connect() as conn:
        resultat = conn.execute(
            text("DELETE FROM taches WHERE id = :id AND user_id = :uid"),
            {"id": tache_id, "uid": user_id},
        )
        conn.commit()
        return resultat.rowcount > 0

@app.route("/taches", methods=["GET"])
@token_requis
def lister_taches(user_id):
    return jsonify(lister_taches_db(user_id))

@app.route("/taches", methods=["POST"])
@token_requis
def creer_tache(user_id):
    data = request.get_json()

    if not data or "titre" not in data or not data["titre"].strip():
        return jsonify({"erreur": "Le champ 'titre' est requis"}), 400

    nouvelle_tache = creer_tache_db(user_id, data["titre"])
    return jsonify(nouvelle_tache), 201

@app.route("/taches/<int:tache_id>", methods=["PUT"])
@token_requis
def modifier_tache(user_id, tache_id):
    tache = basculer_tache_db(user_id, tache_id)
    if tache is None:
        return jsonify({"erreur": f"Aucune tache avec l'id {tache_id}"}), 404

    return jsonify(tache)

@app.route("/taches/<int:tache_id>", methods=["DELETE"])
@token_requis
def supprimer_tache(user_id, tache_id):
    supprime = supprimer_tache_db(user_id, tache_id)
    if not supprime:
        return jsonify({"erreur": f"Aucune tache avec l'id {tache_id}"}), 404

    return "", 204

if __name__ == "__main__":
    app.run(debug=True)
