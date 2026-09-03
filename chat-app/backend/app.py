import eventlet
eventlet.monkey_patch()

import os
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)

@app.after_request
def ajouter_cors(reponse):
    reponse.headers["Access-Control-Allow-Origin"] = "*"
    reponse.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    reponse.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return reponse

SECRET_KEY = os.environ["SECRET_KEY"]
MAILJET_API_KEY = os.environ["MAILJET_API_KEY"]
MAILJET_SECRET_KEY = os.environ["MAILJET_SECRET_KEY"]
MAIL_FROM = os.environ["MAIL_FROM"]
FRONTEND_URL = os.environ["FRONTEND_URL"]

app.config["SECRET_KEY"] = SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*")

engine = create_engine(os.environ["DATABASE_URL"])

with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            pseudo TEXT NOT NULL,
            texte TEXT NOT NULL,
            envoye_le TIMESTAMP DEFAULT NOW()
        )
    """))
    conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS salon TEXT NOT NULL DEFAULT 'general'"))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS messages_prives (
            id SERIAL PRIMARY KEY,
            expediteur TEXT NOT NULL,
            destinataire TEXT NOT NULL,
            texte TEXT NOT NULL,
            envoye_le TIMESTAMP DEFAULT NOW()
        )
    """))
    conn.commit()

def nom_conversation(a, b):
    return "dm_" + "_".join(sorted([a, b]))

SALONS = ["general", "aleatoire", "aide"]
utilisateurs_connectes = {}  # sid -> {"username": ..., "salon": ...}

# ---------- authentification (meme pattern que le todo-app) ----------

def generer_token(user_id):
    return jwt.encode(
        {"user_id": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=7)},
        SECRET_KEY,
        algorithm="HS256",
    )

def generer_token_reset(user_id):
    return jwt.encode(
        {"user_id": user_id, "type": "reset", "exp": datetime.now(timezone.utc) + timedelta(minutes=30)},
        SECRET_KEY,
        algorithm="HS256",
    )

def envoyer_email(destinataire, sujet, html):
    reponse = requests.post(
        "https://api.mailjet.com/v3.1/send",
        auth=(MAILJET_API_KEY, MAILJET_SECRET_KEY),
        json={"Messages": [{
            "From": {"Email": MAIL_FROM, "Name": "Chat"},
            "To": [{"Email": destinataire}],
            "Subject": sujet,
            "HTMLPart": html,
        }]},
        timeout=10,
    )
    reponse.raise_for_status()

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
    if not data or not data.get("username") or not data.get("email") or not data.get("password"):
        return jsonify({"erreur": "username, email et password requis"}), 400

    with engine.connect() as conn:
        existe = conn.execute(
            text("SELECT id FROM users WHERE username = :u OR email = :e"),
            {"u": data["username"], "e": data["email"]},
        ).fetchone()
        if existe:
            return jsonify({"erreur": "Ce nom d'utilisateur ou cet email existe deja"}), 400

        resultat = conn.execute(
            text("INSERT INTO users (username, email, password_hash) VALUES (:u, :e, :p) RETURNING id"),
            {"u": data["username"], "e": data["email"], "p": generate_password_hash(data["password"])},
        )
        conn.commit()
        user_id = resultat.fetchone()[0]

    return jsonify({"token": generer_token(user_id), "username": data["username"]}), 201

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"erreur": "username et password requis"}), 400

    with engine.connect() as conn:
        ligne = conn.execute(
            text("SELECT id, username, password_hash FROM users WHERE username = :u"),
            {"u": data["username"]},
        ).fetchone()

    if not ligne or not check_password_hash(ligne.password_hash, data["password"]):
        return jsonify({"erreur": "Identifiants invalides"}), 401

    return jsonify({"token": generer_token(ligne.id), "username": ligne.username})

@app.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json()
    if not data or not data.get("email"):
        return jsonify({"erreur": "email requis"}), 400

    with engine.connect() as conn:
        ligne = conn.execute(text("SELECT id FROM users WHERE email = :e"), {"e": data["email"]}).fetchone()

    if ligne:
        token = generer_token_reset(ligne.id)
        lien = f"{FRONTEND_URL}/reset-password?token={token}"
        envoyer_email(
            data["email"],
            "Reinitialisation de mot de passe - Chat",
            f'<p>Clique sur ce lien pour choisir un nouveau mot de passe (valable 30 minutes) :</p><p><a href="{lien}">{lien}</a></p>',
        )

    return jsonify({"message": "Si ce compte existe, un email a ete envoye."})

@app.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json()
    if not data or not data.get("token") or not data.get("password"):
        return jsonify({"erreur": "token et password requis"}), 400

    try:
        donnees = jwt.decode(data["token"], SECRET_KEY, algorithms=["HS256"])
        if donnees.get("type") != "reset":
            raise jwt.InvalidTokenError
    except jwt.InvalidTokenError:
        return jsonify({"erreur": "Lien invalide ou expire"}), 400

    with engine.connect() as conn:
        conn.execute(
            text("UPDATE users SET password_hash = :p WHERE id = :id"),
            {"p": generate_password_hash(data["password"]), "id": donnees["user_id"]},
        )
        conn.commit()

    return jsonify({"message": "Mot de passe mis a jour"})

@app.route("/salons", methods=["GET"])
def lister_salons():
    return jsonify(SALONS)

# ---------- websockets, maintenant securises par JWT ----------

def utilisateur_depuis_token(token):
    try:
        donnees = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
    with engine.connect() as conn:
        ligne = conn.execute(text("SELECT username FROM users WHERE id = :id"), {"id": donnees["user_id"]}).fetchone()
    return ligne.username if ligne else None

@socketio.on("connect")
def gerer_connexion(auth):
    username = utilisateur_depuis_token((auth or {}).get("token", ""))
    if not username:
        return False  # refuse la connexion : pas de token valide
    utilisateurs_connectes[request.sid] = {"username": username, "salon": None}

@socketio.on("disconnect")
def gerer_deconnexion():
    infos = utilisateurs_connectes.pop(request.sid, None)
    if infos and infos["salon"]:
        emit("systeme", {"texte": f"{infos['username']} a quitte le salon"}, to=infos["salon"])
        emit("utilisateurs_en_ligne", _pseudos_du_salon(infos["salon"]), to=infos["salon"])

def _pseudos_du_salon(salon):
    return [v["username"] for v in utilisateurs_connectes.values() if v["salon"] == salon]

@socketio.on("rejoindre_salon")
def gerer_rejoindre(data):
    salon = data.get("salon")
    if salon not in SALONS:
        return
    infos = utilisateurs_connectes.get(request.sid)
    if not infos:
        return

    ancien_salon = infos["salon"]
    if ancien_salon and ancien_salon != salon:
        leave_room(ancien_salon)
        infos["salon"] = None
        emit("systeme", {"texte": f"{infos['username']} a quitte le salon"}, to=ancien_salon)
        emit("utilisateurs_en_ligne", _pseudos_du_salon(ancien_salon), to=ancien_salon)

    infos["salon"] = salon
    join_room(salon)

    with engine.connect() as conn:
        resultat = conn.execute(
            text("SELECT pseudo, texte, envoye_le FROM messages WHERE salon = :s ORDER BY id DESC LIMIT 30"),
            {"s": salon},
        )
        derniers_messages = [dict(ligne._mapping) for ligne in resultat]
    for m in derniers_messages:
        m["envoye_le"] = m["envoye_le"].isoformat()
    derniers_messages.reverse()
    emit("historique", derniers_messages)

    emit("systeme", {"texte": f"{infos['username']} a rejoint le salon"}, to=salon, include_self=False)
    emit("utilisateurs_en_ligne", _pseudos_du_salon(salon), to=salon)

@socketio.on("en_train_ecrire")
def gerer_ecriture():
    infos = utilisateurs_connectes.get(request.sid)
    if infos and infos["salon"]:
        emit("quelquun_ecrit", {"pseudo": infos["username"]}, to=infos["salon"], include_self=False)

@socketio.on("arrete_ecrire")
def gerer_arret_ecriture():
    infos = utilisateurs_connectes.get(request.sid)
    if infos and infos["salon"]:
        emit("plus_personne_ecrit", {"pseudo": infos["username"]}, to=infos["salon"], include_self=False)

@socketio.on("message_envoye")
def gerer_message(data):
    infos = utilisateurs_connectes.get(request.sid)
    if not infos or not infos["salon"]:
        return
    with engine.connect() as conn:
        resultat = conn.execute(
            text("INSERT INTO messages (pseudo, texte, salon) VALUES (:pseudo, :texte, :salon) RETURNING envoye_le"),
            {"pseudo": infos["username"], "texte": data["texte"], "salon": infos["salon"]},
        )
        envoye_le = resultat.fetchone()[0]
        conn.commit()
    emit(
        "nouveau_message",
        {"pseudo": infos["username"], "texte": data["texte"], "envoye_le": envoye_le.isoformat()},
        to=infos["salon"],
    )

# ---------- messages prives ----------

@socketio.on("rejoindre_conversation")
def gerer_rejoindre_conversation(data):
    autre = data.get("avec")
    infos = utilisateurs_connectes.get(request.sid)
    if not infos or not autre:
        return

    ancienne = infos.get("conversation")
    if ancienne:
        leave_room(ancienne)

    conversation = nom_conversation(infos["username"], autre)
    infos["conversation"] = conversation
    infos["conversation_avec"] = autre
    join_room(conversation)

    with engine.connect() as conn:
        resultat = conn.execute(
            text("""
                SELECT expediteur, destinataire, texte, envoye_le FROM messages_prives
                WHERE (expediteur = :moi AND destinataire = :autre) OR (expediteur = :autre AND destinataire = :moi)
                ORDER BY id DESC LIMIT 30
            """),
            {"moi": infos["username"], "autre": autre},
        )
        derniers_messages = [dict(ligne._mapping) for ligne in resultat]
    for m in derniers_messages:
        m["envoye_le"] = m["envoye_le"].isoformat()
    derniers_messages.reverse()
    emit("historique_prive", derniers_messages)

@socketio.on("message_prive_envoye")
def gerer_message_prive(data):
    infos = utilisateurs_connectes.get(request.sid)
    if not infos or not infos.get("conversation"):
        return
    autre = infos["conversation_avec"]
    with engine.connect() as conn:
        resultat = conn.execute(
            text("""
                INSERT INTO messages_prives (expediteur, destinataire, texte)
                VALUES (:e, :d, :t) RETURNING envoye_le
            """),
            {"e": infos["username"], "d": autre, "t": data["texte"]},
        )
        envoye_le = resultat.fetchone()[0]
        conn.commit()
    emit(
        "nouveau_message_prive",
        {
            "expediteur": infos["username"],
            "destinataire": autre,
            "texte": data["texte"],
            "envoye_le": envoye_le.isoformat(),
        },
        to=infos["conversation"],
    )

if __name__ == "__main__":
    socketio.run(app, debug=True, port=5050)
