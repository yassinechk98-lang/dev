import os

from dotenv import load_dotenv
from flask import Flask, request
from flask_socketio import SocketIO, emit
from sqlalchemy import create_engine, text

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = "temporaire-a-changer"
socketio = SocketIO(app, cors_allowed_origins="*")

engine = create_engine(os.environ["DATABASE_URL"])

with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            pseudo TEXT NOT NULL,
            texte TEXT NOT NULL,
            envoye_le TIMESTAMP DEFAULT NOW()
        )
    """))
    conn.commit()

utilisateurs_connectes = {}  # sid -> pseudo

@app.route("/")
def index():
    with open("index.html", encoding="utf-8") as f:
        return f.read()

@socketio.on("connect")
def gerer_connexion():
    with engine.connect() as conn:
        resultat = conn.execute(text("""
            SELECT pseudo, texte, envoye_le FROM messages
            ORDER BY id DESC LIMIT 20
        """))
        derniers_messages = [dict(ligne._mapping) for ligne in resultat]
    for m in derniers_messages:
        m["envoye_le"] = m["envoye_le"].isoformat()
    derniers_messages.reverse()
    emit("historique", derniers_messages)

@socketio.on("disconnect")
def gerer_deconnexion():
    utilisateurs_connectes.pop(request.sid, None)
    emit("utilisateurs_en_ligne", list(utilisateurs_connectes.values()), broadcast=True)

@socketio.on("entrer_salon")
def gerer_entree(data):
    utilisateurs_connectes[request.sid] = data["pseudo"]
    emit("utilisateurs_en_ligne", list(utilisateurs_connectes.values()), broadcast=True)

@socketio.on("en_train_ecrire")
def gerer_ecriture(data):
    emit("quelquun_ecrit", {"pseudo": data["pseudo"]}, broadcast=True, include_self=False)

@socketio.on("arrete_ecrire")
def gerer_arret_ecriture(data):
    emit("plus_personne_ecrit", {"pseudo": data["pseudo"]}, broadcast=True, include_self=False)

@socketio.on("message_envoye")
def gerer_message(data):
    with engine.connect() as conn:
        resultat = conn.execute(
            text("INSERT INTO messages (pseudo, texte) VALUES (:pseudo, :texte) RETURNING envoye_le"),
            {"pseudo": data["pseudo"], "texte": data["texte"]},
        )
        envoye_le = resultat.fetchone()[0]
        conn.commit()
    emit(
        "nouveau_message",
        {"pseudo": data["pseudo"], "texte": data["texte"], "envoye_le": envoye_le.isoformat()},
        broadcast=True,
    )

if __name__ == "__main__":
    socketio.run(app, debug=True, port=5050)
