# Séance 4 — Interface React du chat

## Théorie — un WebSocket dans un composant React

Une connexion WebSocket doit s'ouvrir **une seule fois** quand la page se
charge, pas à chaque re-render de React. C'est exactement le rôle du
`useEffect` avec un tableau de dépendances vide :

```jsx
useEffect(() => {
  const socket = io('http://127.0.0.1:5050');
  socketRef.current = socket;

  socket.on('nouveau_message', (message) => {
    setMessages((precedents) => [...precedents, message]);
  });

  return () => {
    socket.disconnect();
  };
}, []);
```

- `[]` (tableau vide) : l'effet ne s'exécute qu'au tout premier rendu
- La fonction retournée (`return () => {...}`) est le **nettoyage** —
  React l'appelle automatiquement si le composant est retiré de l'écran,
  pour fermer la connexion proprement (sinon elle resterait ouverte pour
  rien, une vraie fuite de ressources)
- `socketRef.current` (un `useRef`, pas un `useState`) : on veut *garder
  une reference* vers le socket pour pouvoir l'utiliser dans `envoyer()`,
  sans provoquer de re-render a chaque fois — exactement le bon outil
  pour une valeur qui doit survivre entre les rendus sans redeclencher
  d'affichage

## Piège courant (pour info, pas forcement rencontre ici)

En React 18/19 avec `<StrictMode>` (present par defaut dans le template
Vite), React execute chaque effet deux fois en developpement
(monte → demonte → remonte) pour t'aider a detecter les effets mal
nettoyes. Ca peut donner l'impression que la connexion se fait deux fois
au chargement — normal, c'est desactive en production.

## Pratique

Nouveau dossier `chat-app/frontend/` (Vite + React), paquet
`socket.io-client` installe. `App.jsx` reprend exactement la meme logique
que `index.html` (Seance 1-3) mais en React : `useState` pour les
messages/pseudo/texte, `useEffect` pour la connexion, gestion des
evenements `historique` et `nouveau_message` identique cote serveur (rien
change dans `app.py`).

## Exercice

1. Teste dans deux onglets, verifie le temps reel comme en Seance 2
2. Recharge la page, verifie l'historique comme en Seance 3
3. Bonus : ajoute un `<p>Connecte...</p>` qui s'affiche tant que
   l'historique n'est pas encore arrive (state `charge` initialise a
   `false`, passe a `true` dans le handler `historique`)
