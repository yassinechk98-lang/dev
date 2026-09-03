# Séance 2 — Salons : messages en direct entre plusieurs onglets

## Théorie — broadcast

Jusqu'ici (Séance 1), le serveur répondait uniquement à celui qui avait
envoyé l'événement (`emit(...)` tout court = réponse au client courant
seulement). Pour un chat, il faut **diffuser** le message à tout le monde
de connecté :

```python
@socketio.on("message_envoye")
def gerer_message(data):
    emit("nouveau_message", {"pseudo": data["pseudo"], "texte": data["texte"]}, broadcast=True)
```

- `broadcast=True` : envoie l'événement `nouveau_message` à **tous** les
  clients connectés, y compris l'expéditeur lui-même (c'est volontaire —
  ça garantit que le message affiché vient toujours du serveur, jamais
  d'un simple "je l'affiche localement en plus", ce qui évite tout
  décalage si le serveur venait à refuser/modifier le message)

## Pratique

`index.html` a maintenant : un champ pseudo, une zone de messages, un
champ de saisie + bouton Envoyer. Chaque message tapé envoie
`message_envoye`, et chaque client (y compris celui qui vient d'envoyer)
reçoit `nouveau_message` en retour et l'affiche.

Testé avec deux onglets ouverts simultanément sur la même page — un
message tapé dans l'un apparaît instantanément dans l'autre, sans recharger
la page.

## Exercice

1. Ouvre deux onglets, envoie un message depuis chacun, vérifie qu'ils
   apparaissent bien dans les deux
2. Bonus : ajoute un événement `utilisateur_connecte` envoyé (en broadcast)
   quand quelqu'un se connecte — affiche "Quelqu'un a rejoint le salon"
   dans tous les onglets ouverts. Indice : `@socketio.on("connect")` est
   un événement spécial, déclenché automatiquement par Flask-SocketIO à
   chaque nouvelle connexion, sans que le client ait besoin de l'envoyer
   lui-même.
