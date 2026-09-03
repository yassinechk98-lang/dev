import os

from dotenv import load_dotenv
from flask import Flask
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

@app.route("/")
def index():
    with open("index.html", encoding="utf-8") as f:
        return f.read()

@socketio.on("connect")
def gerer_connexion():
    with engine.connect() as conn:
        resultat = conn.execute(text("""
            SELECT pseudo, texte FROM messages
            ORDER BY id DESC LIMIT 20
        """))
        derniers_messages = [dict(ligne._mapping) for ligne in resultat]
    derniers_messages.reverse()
    emit("historique", derniers_messages)

@socketio.on("message_envoye")
def gerer_message(data):
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO messages (pseudo, texte) VALUES (:pseudo, :texte)"),
            {"pseudo": data["pseudo"], "texte": data["texte"]},
        )
        conn.commit()
    emit("nouveau_message", {"pseudo": data["pseudo"], "texte": data["texte"]}, broadcast=True)

if __name__ == "__main__":
    socketio.run(app, debug=True, port=5050)
