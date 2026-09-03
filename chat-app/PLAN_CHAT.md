# Plan d'apprentissage — Chat en temps reel (WebSockets)

Deuxieme grand projet, independant du todo-app : nouveau dossier, nouvelle
base de donnees, nouveaux comptes. Meme methode que pour le todo-app —
theorie courte + exercice pratique + commit a chaque seance — mais avec une
vraie nouveaute technique cette fois : les **WebSockets**.

Stack : Flask + Flask-SocketIO (backend), React + socket.io-client
(frontend), PostgreSQL sur un nouveau projet Neon separe.

## Pourquoi ce projet

Tout ce qu'on a construit jusqu'ici (todo-app) suit le meme schema HTTP :
le navigateur demande, le serveur repond, la connexion se ferme. Un chat
en temps reel a besoin d'autre chose — le serveur doit pouvoir **pousser**
un message vers le navigateur sans que celui-ci l'ait demande a l'instant
meme. C'est ce que permettent les WebSockets : une connexion qui reste
ouverte, dans les deux sens.

## Programme

- [x] Séance 1 — Théorie WebSockets (HTTP vs connexion permanente) + "Hello World" temps réel
- [x] Séance 2 — Salons : envoyer/recevoir un message en direct entre plusieurs onglets
- [x] Séance 3 — Persistance : sauvegarder les messages en base, les recharger a la connexion
- [x] Séance 4 — Interface React du chat (liste de messages, champ d'envoi)
- [x] Bonus — Relookage Material UI v9 (style Discord : barre laterale, utilisateurs en ligne, indicateur de frappe, son de notification, horodatage) — anticipe une partie de la Seance 7
- [x] Séance 5 — Authentification JWT sur les WebSockets + plusieurs salons distincts
- [ ] Séance 6 — Messages prives (DM) entre deux utilisateurs
- [ ] Séance 7 — Finitions : "X est en train d'ecrire...", utilisateurs en ligne
- [ ] Séance 8 — Deploiement (nouveau service Render + nouveau site Netlify)

## Structure du dossier chat-app/

```
chat-app/
  PLAN_CHAT.md       <- ce fichier
  seances/           <- comme pour le todo-app, une fiche par seance
  backend/           <- API Flask + Flask-SocketIO
  frontend/          <- app React (a creer en Seance 4)
```

Le venv Python reste partage avec le todo-app (`dev/venv`) — pas besoin
d'en recreer un, on installe juste les nouveaux paquets dedans.
