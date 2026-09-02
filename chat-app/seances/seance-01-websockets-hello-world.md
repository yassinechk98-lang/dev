# Séance 1 — Théorie WebSockets + "Hello World" temps réel

## Théorie — HTTP vs WebSocket

Avec **HTTP** (todo-app, tout le cursus jusqu'ici) : le navigateur envoie une
requete, le serveur repond, la connexion se referme. Comme une lettre — un
aller-retour, puis c'est fini. Si tu veux savoir "il y a du nouveau ?", il
faut renvoyer une nouvelle lettre.

Avec un **WebSocket** : la connexion reste ouverte en permanence, dans les
deux sens. Comme un appel telephonique — n'importe lequel des deux peut
parler a tout moment, sans que l'autre ait rien demande. C'est ce qu'il
faut pour qu'un message tape par quelqu'un d'autre apparaisse chez toi
instantanement.

## Théorie — Flask-SocketIO

`flask-socketio` ajoute la gestion des WebSockets a Flask. Au lieu de
routes (`@app.route(...)`), on ecrit des **evenements** :

```python
from flask_socketio import SocketIO, emit

socketio = SocketIO(app)

@socketio.on("ping_client")
def gerer_ping(data):
    emit("pong_serveur", {"message": "Pong depuis le serveur !"})
```

- `@socketio.on("ping_client")` : declenche cette fonction des que le
  navigateur envoie un evenement nomme `ping_client`
- `emit(...)` : renvoie un evenement au navigateur — pas de `return`
  comme avec Flask classique, la reponse part quand elle est prete
- Cote navigateur (JavaScript, via `socket.io-client`) :
  ```js
  const socket = io();
  socket.emit("ping_client", { texte: "salut" });
  socket.on("pong_serveur", (data) => console.log(data.message));
  ```

## Pratique

Fichiers crees dans `chat-app/backend/` : `app.py` (serveur Flask-SocketIO
minimal) et `index.html` (page servie directement par Flask, avec un bouton
qui envoie `ping_client` et affiche la reponse `pong_serveur`).

Lancer le serveur :
```
cd chat-app/backend
python app.py
```
Puis ouvrir http://localhost:5000 et cliquer sur le bouton.

**Bonus** : `F12` → onglet Network → filtre `WS` → recharger la page. La
connexion WebSocket reste "ouverte" en continu, contrairement aux requetes
HTTP classiques qui apparaissent et se terminent une par une.

## Exercice

1. Lance le serveur, clique le bouton, confirme que "Pong depuis le
   serveur !" s'affiche
2. Observe la connexion WebSocket dans l'onglet Network (bonus ci-dessus)
3. Modifie `index.html` : ajoute un deuxieme bouton qui envoie
   `ping_client` avec un texte different (ex: `{"texte": "deuxieme test"}`),
   et modifie `gerer_ping` cote Python pour que le message de retour
   inclue le texte recu (`data["texte"]`)
