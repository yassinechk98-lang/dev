import os
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

import json

import jwt
import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from pywebpush import webpush, WebPushException
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
CORS(app)

SECRET_KEY = os.environ["SECRET_KEY"]
MAILJET_API_KEY = os.environ["MAILJET_API_KEY"]
MAILJET_SECRET_KEY = os.environ["MAILJET_SECRET_KEY"]
MAIL_FROM = os.environ["MAIL_FROM"]
FRONTEND_URL = os.environ["FRONTEND_URL"]
VAPID_PRIVATE_KEY = os.environ["VAPID_PRIVATE_KEY"]
VAPID_PUBLIC_KEY = os.environ["VAPID_PUBLIC_KEY"]
CRON_SECRET = os.environ["CRON_SECRET"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)

def initialiser_schema():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT UNIQUE"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS taches (
                id SERIAL PRIMARY KEY,
                titre TEXT NOT NULL,
                terminee BOOLEAN DEFAULT FALSE
            )
        """))
        conn.execute(text("ALTER TABLE taches ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)"))
        conn.execute(text("ALTER TABLE taches ADD COLUMN IF NOT EXISTS date_echeance TIMESTAMP"))
        conn.execute(text("ALTER TABLE taches ALTER COLUMN date_echeance TYPE TIMESTAMP"))
        conn.execute(text("ALTER TABLE taches ADD COLUMN IF NOT EXISTS rappel_envoye BOOLEAN DEFAULT FALSE"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_taches_user_id ON taches (user_id)"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                endpoint TEXT UNIQUE NOT NULL,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL
            )
        """))
        conn.commit()

# Neon (base gratuite) peut mettre quelques secondes a "reveiller" la base au
# tout premier appel apres une periode d'inactivite. On retente plusieurs fois
# pour eviter qu'un demarrage lent ne fasse planter tout le deploiement.
for tentative in range(5):
    try:
        initialiser_schema()
        break
    except OperationalError:
        if tentative == 4:
            raise
        time.sleep(3)

# ---------- authentification ----------

def generer_token(user_id):
    return jwt.encode(
        {"user_id": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=7)},
        SECRET_KEY,
        algorithm="HS256",
    )

def generer_token_reset(user_id):
    return jwt.encode(
        {
            "user_id": user_id,
            "type": "reset",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        },
        SECRET_KEY,
        algorithm="HS256",
    )

def envoyer_email(destinataire, sujet, html):
    reponse = requests.post(
        "https://api.mailjet.com/v3.1/send",
        auth=(MAILJET_API_KEY, MAILJET_SECRET_KEY),
        json={
            "Messages": [
                {
                    "From": {"Email": MAIL_FROM, "Name": "Ma Todo-list"},
                    "To": [{"Email": destinataire}],
                    "Subject": sujet,
                    "HTMLPart": html,
                }
            ]
        },
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
    if not data or not data.get("username") or not data.get("password") or not data.get("email"):
        return jsonify({"erreur": "username, email et password requis"}), 400

    with engine.connect() as conn:
        existe = conn.execute(
            text("SELECT id FROM users WHERE username = :u OR email = :e"),
            {"u": data["username"], "e": data["email"]},
        ).fetchone()
        if existe:
            return jsonify({"erreur": "Ce nom d'utilisateur ou cet email existe deja"}), 400

        resultat = conn.execute(
            text("""
                INSERT INTO users (username, email, password_hash)
                VALUES (:u, :e, :p) RETURNING id
            """),
            {"u": data["username"], "e": data["email"], "p": generate_password_hash(data["password"])},
        )
        conn.commit()
        user_id = resultat.fetchone()[0]

    return jsonify({"token": generer_token(user_id)}), 201

@app.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json()
    if not data or not data.get("email"):
        return jsonify({"erreur": "email requis"}), 400

    with engine.connect() as conn:
        ligne = conn.execute(
            text("SELECT id FROM users WHERE email = :e"), {"e": data["email"]}
        ).fetchone()

    if ligne:
        token = generer_token_reset(ligne.id)
        lien = f"{FRONTEND_URL}/reset-password?token={token}"
        envoyer_email(
            data["email"],
            "Reinitialisation de mot de passe - Ma Todo-list",
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

def formater_tache(ligne):
    tache = dict(ligne._mapping)
    if tache.get("date_echeance"):
        tache["date_echeance"] = tache["date_echeance"].isoformat()
    return tache

def lister_taches_db(user_id):
    with engine.connect() as conn:
        resultat = conn.execute(
            text("SELECT id, titre, terminee, date_echeance FROM taches WHERE user_id = :uid ORDER BY id"),
            {"uid": user_id},
        )
        return [formater_tache(ligne) for ligne in resultat]

def creer_tache_db(user_id, titre, date_echeance):
    with engine.connect() as conn:
        resultat = conn.execute(
            text("""
                INSERT INTO taches (titre, terminee, user_id, date_echeance)
                VALUES (:titre, FALSE, :uid, :date_echeance)
                RETURNING id, titre, terminee, date_echeance
            """),
            {"titre": titre, "uid": user_id, "date_echeance": date_echeance},
        )
        conn.commit()
        return formater_tache(resultat.fetchone())

def basculer_tache_db(user_id, tache_id):
    with engine.connect() as conn:
        resultat = conn.execute(
            text("""
                UPDATE taches SET terminee = NOT terminee
                WHERE id = :id AND user_id = :uid
                RETURNING id, titre, terminee, date_echeance
            """),
            {"id": tache_id, "uid": user_id},
        )
        conn.commit()
        ligne = resultat.fetchone()
        return formater_tache(ligne) if ligne else None

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

    nouvelle_tache = creer_tache_db(user_id, data["titre"], data.get("date_echeance") or None)
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

# ---------- assistant ia ----------

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent"

FONCTIONS_ASSISTANT = [
    {
        "name": "lister_taches",
        "description": "Liste toutes les taches de l'utilisateur, avec leur id, titre, statut (terminee) et date d'echeance.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "creer_tache",
        "description": "Cree une nouvelle tache pour l'utilisateur.",
        "parameters": {
            "type": "object",
            "properties": {
                "titre": {"type": "string", "description": "Le titre de la tache"},
                "date_echeance": {
                    "type": "string",
                    "description": "Date et heure d'echeance au format ISO 8601 (ex: 2026-09-03T14:00:00). Omettre si aucune echeance n'est demandee.",
                },
            },
            "required": ["titre"],
        },
    },
    {
        "name": "basculer_tache",
        "description": "Inverse le statut d'une tache (termine une tache en cours, ou reouvre une tache terminee). Appelle lister_taches avant si tu ne connais pas deja l'id.",
        "parameters": {
            "type": "object",
            "properties": {"tache_id": {"type": "integer", "description": "L'id de la tache"}},
            "required": ["tache_id"],
        },
    },
    {
        "name": "supprimer_tache",
        "description": "Supprime definitivement une tache. Appelle lister_taches avant si tu ne connais pas deja l'id.",
        "parameters": {
            "type": "object",
            "properties": {"tache_id": {"type": "integer", "description": "L'id de la tache"}},
            "required": ["tache_id"],
        },
    },
]

def executer_fonction_assistant(user_id, nom, args):
    if nom == "lister_taches":
        return {"taches": lister_taches_db(user_id)}
    if nom == "creer_tache":
        tache = creer_tache_db(user_id, args["titre"], args.get("date_echeance") or None)
        return {"tache": tache}
    if nom == "basculer_tache":
        tache = basculer_tache_db(user_id, args["tache_id"])
        return {"tache": tache} if tache else {"erreur": "tache introuvable"}
    if nom == "supprimer_tache":
        return {"succes": supprimer_tache_db(user_id, args["tache_id"])}
    return {"erreur": f"fonction inconnue : {nom}"}

@app.route("/assistant", methods=["POST"])
@token_requis
def assistant(user_id):
    data = request.get_json()
    if not data or not data.get("message"):
        return jsonify({"erreur": "message requis"}), 400

    historique = data.get("historique") or []
    historique.append({"role": "user", "parts": [{"text": data["message"]}]})

    instruction_systeme = (
        "Tu es un assistant qui aide l'utilisateur a gerer sa todo-list en francais. "
        "Utilise les fonctions disponibles pour lister, creer, terminer/reouvrir ou supprimer des taches. "
        f"La date et l'heure actuelles sont : {datetime.now().strftime('%Y-%m-%dT%H:%M:%S')} ({datetime.now().strftime('%A')}). "
        "Quand l'utilisateur donne une date relative (demain, ce soir, lundi prochain...), calcule la date exacte. "
        "Reponds toujours de maniere breve et naturelle en francais apres avoir effectue les actions necessaires."
    )

    for _ in range(5):
        reponse = requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json={
                "contents": historique,
                "system_instruction": {"parts": [{"text": instruction_systeme}]},
                "tools": [{"functionDeclarations": FONCTIONS_ASSISTANT}],
            },
            timeout=30,
        )
        if not reponse.ok:
            return jsonify({"erreur": f"Erreur assistant IA ({reponse.status_code}) : {reponse.text[:500]}"}), 502
        candidat = reponse.json()["candidates"][0]
        parts = candidat["content"]["parts"]
        historique.append({"role": "model", "parts": parts})

        appels = [p for p in parts if "functionCall" in p]
        if not appels:
            texte = "".join(p.get("text", "") for p in parts)
            return jsonify({"reponse": texte, "historique": historique})

        parts_reponse = []
        for appel in appels:
            fc = appel["functionCall"]
            resultat_fonction = executer_fonction_assistant(user_id, fc["name"], fc.get("args", {}))
            part_reponse = {"functionResponse": {"name": fc["name"], "response": resultat_fonction}}
            if "id" in fc:
                part_reponse["functionResponse"]["id"] = fc["id"]
            parts_reponse.append(part_reponse)

        historique.append({"role": "user", "parts": parts_reponse})

    return jsonify({"erreur": "L'assistant n'a pas pu terminer la demande"}), 500

# ---------- notifications push ----------

@app.route("/vapid-public-key", methods=["GET"])
def vapid_public_key():
    return jsonify({"publicKey": VAPID_PUBLIC_KEY})

@app.route("/push-subscribe", methods=["POST"])
@token_requis
def push_subscribe(user_id):
    data = request.get_json()
    if not data or not data.get("endpoint") or not data.get("keys"):
        return jsonify({"erreur": "abonnement invalide"}), 400

    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth)
                VALUES (:uid, :endpoint, :p256dh, :auth)
                ON CONFLICT (endpoint) DO UPDATE
                SET user_id = :uid, p256dh = :p256dh, auth = :auth
            """),
            {
                "uid": user_id,
                "endpoint": data["endpoint"],
                "p256dh": data["keys"]["p256dh"],
                "auth": data["keys"]["auth"],
            },
        )
        conn.commit()

    return jsonify({"message": "Abonnement enregistre"}), 201

@app.route("/push-unsubscribe", methods=["POST"])
@token_requis
def push_unsubscribe(user_id):
    data = request.get_json()
    if not data or not data.get("endpoint"):
        return jsonify({"erreur": "endpoint requis"}), 400

    with engine.connect() as conn:
        conn.execute(
            text("DELETE FROM push_subscriptions WHERE endpoint = :endpoint AND user_id = :uid"),
            {"endpoint": data["endpoint"], "uid": user_id},
        )
        conn.commit()

    return "", 204

def envoyer_notification(subscription, titre, corps):
    subscription_info = {
        "endpoint": subscription.endpoint,
        "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
    }
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps({"title": titre, "body": corps}),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": f"mailto:{MAIL_FROM}"},
        )
        return True
    except WebPushException as e:
        statut = e.response.status_code if e.response is not None else None
        if statut in (404, 410):
            # abonnement expire ou desinstalle : on le supprime
            with engine.connect() as conn:
                conn.execute(
                    text("DELETE FROM push_subscriptions WHERE endpoint = :endpoint"),
                    {"endpoint": subscription.endpoint},
                )
                conn.commit()
        return False

@app.route("/check-reminders", methods=["POST"])
def check_reminders():
    if request.headers.get("X-Cron-Secret") != CRON_SECRET:
        return jsonify({"erreur": "non autorise"}), 401

    with engine.connect() as conn:
        taches_a_notifier = conn.execute(text("""
            SELECT id, user_id, titre FROM taches
            WHERE date_echeance IS NOT NULL
              AND date_echeance <= NOW()
              AND terminee = FALSE
              AND rappel_envoye = FALSE
        """)).fetchall()

        notifiees = 0
        for tache in taches_a_notifier:
            abonnements = conn.execute(
                text("SELECT endpoint, p256dh, auth FROM push_subscriptions WHERE user_id = :uid"),
                {"uid": tache.user_id},
            ).fetchall()

            for abonnement in abonnements:
                if envoyer_notification(abonnement, "Tache en retard", tache.titre):
                    notifiees += 1

            conn.execute(
                text("UPDATE taches SET rappel_envoye = TRUE WHERE id = :id"),
                {"id": tache.id},
            )
            conn.commit()

    return jsonify({"taches_verifiees": len(taches_a_notifier), "notifications_envoyees": notifiees})

if __name__ == "__main__":
    app.run(debug=True)
