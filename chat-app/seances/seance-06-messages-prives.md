# Séance 6 — Messages privés (DM)

## Théorie — une "room" par paire d'utilisateurs

Un salon a un nom fixe (`general`). Une conversation privee n'existe entre
que **deux** personnes precises — il faut donc un nom de room genere a la
volee, mais **identique** peu importe qui l'ouvre en premier :

```python
def nom_conversation(a, b):
    return "dm_" + "_".join(sorted([a, b]))
```

`sorted([a, b])` garantit que `nom_conversation("alice", "bob")` et
`nom_conversation("bob", "alice")` donnent exactement la meme chaine — les
deux utilisateurs rejoignent donc automatiquement la meme room, sans jamais
se mettre d'accord explicitement sur un identifiant.

## Théorie — pourquoi c'est deja securise

Un utilisateur ne peut rejoindre que `nom_conversation(SON_PROPRE_username, autre)`
— le serveur calcule toujours la room a partir de `infos["username"]`
(recupere du token JWT a la connexion), jamais d'une valeur envoyee
librement par le client. Impossible donc de rejoindre la conversation
d'quelqu'un d'autre en devinant/forgeant un nom de room.

## Pratique

- Nouvelle table `messages_prives` (expediteur, destinataire, texte,
  envoye_le)
- Evenements `rejoindre_conversation` / `message_prive_envoye` —
  quasiment le meme pattern que les salons (Seance 5), en reutilisant
  `join_room`/`leave_room`
- Frontend : cliquer sur un pseudo dans "EN LIGNE" ouvre la conversation
  privee (fleche retour pour revenir au salon)

## Exercice

1. Avec deux comptes (deuxieme fenetre en navigation privee), envoie-toi
   des messages prives, verifie qu'un troisieme compte ne les voit jamais
2. Recharge/reconnecte-toi, verifie que l'historique prive revient
3. Bonus : l'indicateur "en train d'ecrire" ne fonctionne actuellement que
   pour les salons (regarde `gererFrappe` dans `App.jsx` — elle s'arrete
   des qu'un DM est actif). Etends `en_train_ecrire`/`quelquun_ecrit` pour
   qu'ils marchent aussi en message prive (indice : il faudra les
   emettre/ecouter sur `infos["conversation"]` au lieu de
   `infos["salon"]`)
