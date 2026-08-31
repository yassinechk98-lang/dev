# Séance 26 (bonus, hors plan initial) — Déploiement en ligne

## Théorie — pourquoi deux hébergeurs différents ?

Le frontend (React) est du contenu **statique** une fois construit (`npm run build`
génère du HTML/CSS/JS figé) — un CDN comme Netlify le sert très efficacement partout
dans le monde. Le backend (Flask) est un **serveur qui tourne en continu**, il lui
faut un hébergeur qui exécute du code Python en permanence — c'est le rôle de
**Render**. C'est l'architecture standard pour une app comme la tienne : frontend et
backend déployés séparément, communiquant via une URL d'API publique (comme en
local, sauf que `localhost:5000` devient une vraie URL sur internet).

## Étape 1 — déployer le backend sur Render

1. Va sur **render.com**, crée un compte (tu peux te connecter avec GitHub)
2. Clique sur **"New +"** → **"Web Service"**
3. Connecte ton dépôt GitHub (`yassinechk98-lang/dev`) — autorise Render à y accéder
4. Configure le service :
   - **Root Directory** : `todo-app/backend`
   - **Runtime** : Python 3
   - **Build Command** : `pip install -r requirements.txt`
   - **Start Command** : `gunicorn app:app`
5. Dans la section **Environment Variables**, ajoute `DATABASE_URL` avec la même
   valeur que ton fichier `.env` local (la connection string Neon) — Render a besoin
   de cette variable pour se connecter à la même base
6. Clique sur **"Create Web Service"** — le premier déploiement prend quelques
   minutes
7. Une fois déployé, Render te donne une URL du type
   `https://ton-app.onrender.com` — note-la, ce sera la nouvelle adresse de ton API

⚠️ Le plan gratuit de Render "endort" le service après 15 minutes d'inactivité — la
première requête après une pause peut prendre 30-60 secondes à répondre. Normal,
pas un bug.

## Étape 2 — préparer le code pour Render

Render a besoin de deux fichiers que le projet Flask n'a pas encore :
- `requirements.txt` : liste des paquets Python à installer (générée automatiquement
  depuis le venv)
- `gunicorn` installé : un vrai serveur de production (`app.run(debug=True)` n'est
  fait que pour le développement local, jamais pour la production)

## Étape 3 — déployer le frontend sur Netlify

Une fois l'URL du backend Render connue, remplacer dans `App.jsx` :
```js
const API_URL = "http://localhost:5000/taches";
```
par :
```js
const API_URL = "https://ton-app.onrender.com/taches";
```

Puis build et déployer sur Netlify (l'assistant s'en occupe directement dans cette
séance).

## Exercice

1. Génère `requirements.txt`, installe `gunicorn`, commit
2. Déploie le backend sur Render, récupère l'URL publique
3. Mets à jour `API_URL` dans `App.jsx` avec cette URL
4. Build + déploie le frontend sur Netlify
5. Teste l'app complète depuis son URL publique, sur un autre appareil si possible
   (téléphone) pour confirmer que c'est bien accessible depuis internet

## Résultat final

- **Frontend** : https://yassine-todo-app.netlify.app
- **Backend** : https://dev-tpob.onrender.com (connecté à Neon PostgreSQL)

## Piège rencontré : déployer le bon dossier

Un déploiement Netlify a d'abord échoué (page blanche) car il avait uploadé **tout
le dossier source** du frontend, y compris l'`index.html` de développement à la
racine (qui référence `/src/main.jsx` directement — illisible tel quel par un
navigateur, ça doit être transformé par le build). Netlify servait ce fichier non
buildé au lieu du vrai `dist/index.html`.

**Leçon** : toujours vérifier ce qu'un déploiement statique sert réellement — un
`index.html` qui référence `/src/...` au lieu de `/assets/...` est le signe qu'on a
déployé les sources plutôt que le résultat du build (`npm run build` → dossier
`dist/`). La correction a été de déployer spécifiquement le contenu de `dist/`,
pas tout `todo-app/frontend/`.
