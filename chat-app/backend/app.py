from flask import Flask
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config["SECRET_KEY"] = "temporaire-a-changer"
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route("/")
def index():
    with open("index.html", encoding="utf-8") as f:
        return f.read()

@socketio.on("ping_client")
def gerer_ping(data):
    print("recu du client:", data)
    emit("pong_serveur", {"message": "Pong depuis le serveur !"})

@socketio.on("message_envoye")
def gerer_message(data):
    print("message recu:", data)
    emit("nouveau_message", {"pseudo": data["pseudo"], "texte": data["texte"]}, broadcast=True)

if __name__ == "__main__":
    socketio.run(app, debug=True, port=5050)
