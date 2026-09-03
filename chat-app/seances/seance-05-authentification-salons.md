# Séance 5 — Authentification JWT sur les WebSockets + plusieurs salons

## Théorie — securiser une connexion WebSocket

Contrairement a une route Flask classique (`@token_requis` verifie le header
`Authorization` a chaque appel), un WebSocket ne s'ouvre **qu'une fois** —
il faut donc verifier l'identite **a la connexion**, pas a chaque message.

Le client passe le token au moment de se connecter :

```js
const socket = io(SOCKET_URL, { auth: { token } });
```

Cote serveur, le handler special `connect` recoit ces donnees et peut
**refuser** la connexion en retournant `False` :

```python
@socketio.on("connect")
def gerer_connexion(auth):
    username = utilisateur_depuis_token((auth or {}).get("token", ""))
    if not username:
        return False  # ferme la connexion immediatement
    utilisateurs_connectes[request.sid] = {"username": username, "salon": None}
```

Une fois connecte, le `username` est stocke cote serveur (associe au
`request.sid`, l'identifiant unique de cette connexion) — plus besoin de
faire confiance a un pseudo envoye par le client a chaque message (avant
cette seance, n'importe qui pouvait se faire passer pour n'importe qui en
changeant juste le champ pseudo).

## Théorie — les salons (rooms)

Flask-SocketIO groupe les connexions en "rooms" avec `join_room()`/`leave_room()`.
Un message envoye avec `to=nom_salon` n'atteint que les clients ayant
rejoint cette room — exactement l'equivalent WebSocket d'un `WHERE salon = ...`
en SQL.

```python
join_room(salon)
emit("nouveau_message", donnees, to=salon)
```

**Piege reel rencontre** : changer de salon sans faire `leave_room()` sur
l'ancien laisse l'utilisateur abonne aux **deux** — il continue de recevoir
les messages du salon qu'il vient de quitter. Corrige en appelant
`leave_room(ancien_salon)` avant de rejoindre le nouveau.

## Debogage — deux vrais bugs rencontres en testant

1. **`ConnectionError` a la mise a niveau WebSocket** : le serveur de
   developpement de Werkzeug (utilise par defaut par `socketio.run()`) a
   un support WebSocket fragile sur certaines configurations. Resolu en
   installant `eventlet` (`pip install eventlet`) et en ajoutant
   `eventlet.monkey_patch()` tout en haut de `app.py`, avant tout autre
   import — Flask-SocketIO detecte automatiquement eventlet et l'utilise
   a la place du serveur Werkzeug pour un support WebSocket robuste.

2. **`UndefinedColumn: column "salon" does not exist`** : la table
   `messages` existait deja depuis la Seance 3 (creee sans colonne
   `salon`). `CREATE TABLE IF NOT EXISTS` ne modifie jamais une table
   existante — il fallait un `ALTER TABLE messages ADD COLUMN IF NOT EXISTS salon ...`,
   exactement le meme piege que sur le todo-app a chaque fois qu'une
   colonne est ajoutee a une table qui existe deja en production.

Les deux ont ete diagnostiques en lisant les vrais tracebacks du serveur
(lance en tache de fond avec les logs captures), pas en devinant.

## Pratique

- Tables `users` (meme structure que le todo-app) et `messages.salon`
  ajoutees
- Routes `/register`, `/login`, `/forgot-password`, `/reset-password` —
  copiees du todo-app, meme pattern JWT + Mailjet (memes identifiants
  Mailjet reutilises, un compte email n'a pas besoin d'etre "separe" comme
  la base de donnees)
- 3 salons fixes cote serveur : `general`, `aleatoire`, `aide`
- Frontend : `AuthPage.jsx` (connexion/inscription/mot de passe oublie),
  le pseudo libre a disparu — c'est maintenant le vrai nom de compte,
  impossible a falsifier
- Verifie : inscription/connexion, refus d'un token invalide au niveau
  WebSocket, isolation totale entre salons (deux clients Python separes,
  un message dans "general" n'atteint jamais celui qui est dans "aleatoire")

## Exercice

1. Cree un compte, connecte-toi, change de salon plusieurs fois
2. Deconnecte-toi et reconnecte-toi — verifie que l'historique du salon
   revient
3. Bonus : ajoute un 4e salon cote serveur (liste `SALONS`) et verifie
   qu'il apparait automatiquement dans la barre laterale (le frontend
   affiche la liste codee en dur `SALONS` — pourquoi faudrait-il plutot
   la recuperer via `GET /salons`, deja presente dans le backend mais pas
   encore utilisee cote frontend ?)
