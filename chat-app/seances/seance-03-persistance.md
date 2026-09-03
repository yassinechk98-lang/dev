# Séance 3 — Persistance des messages

## Théorie

Jusqu'ici, tous les messages n'existaient qu'en mémoire — un rechargement
de page (ou un redémarrage du serveur) effaçait tout. Comme pour le
todo-app (Séance 25 du premier cursus), on branche PostgreSQL.

Cette fois, base **complètement séparée** — nouveau compte GitHub, nouveau
compte Neon, nouveau projet — pour garder le chat-app totalement
indépendant du todo-app.

## Pratique — schéma

```python
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
```

## Pratique — sauvegarder à l'envoi, recharger à la connexion

```python
@socketio.on("connect")
def gerer_connexion():
    with engine.connect() as conn:
        resultat = conn.execute(text("SELECT pseudo, texte FROM messages ORDER BY id DESC LIMIT 20"))
        derniers_messages = [dict(ligne._mapping) for ligne in resultat]
    derniers_messages.reverse()
    emit("historique", derniers_messages)

@socketio.on("message_envoye")
def gerer_message(data):
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO messages (pseudo, texte) VALUES (:pseudo, :texte)"), data)
        conn.commit()
    emit("nouveau_message", data, broadcast=True)
```

- `@socketio.on("connect")` : événement spécial, déclenché automatiquement
  à chaque nouvelle connexion (pas besoin que le client l'envoie)
  — parfait pour "donner l'historique dès l'arrivée"
- `emit("historique", ...)` **sans** `broadcast=True` : n'envoie qu'au
  client qui vient de se connecter, pas à tout le monde (sinon chacun
  recevrait l'historique de chacun, en boucle)
- `ORDER BY id DESC LIMIT 20` puis `.reverse()` en Python : récupère les
  20 *derniers* messages (les plus récents), puis les remet dans l'ordre
  chronologique pour l'affichage

## Vérifié

Testé avec deux scripts Python successifs : le premier envoie un message
et confirme sa réception en broadcast ; le second se connecte séparément
et reçoit bien ce message dans son `historique` — preuve que la
persistance fonctionne entre deux connexions distinctes. Puis vérifié en
vrai : message envoyé dans le navigateur, page rechargée (`F5`), message
toujours là.

## Exercice

1. Envoie plusieurs messages, recharge la page, vérifie qu'ils sont tous
   là et dans le bon ordre
2. Bonus : affiche aussi `envoye_le` a côté de chaque message (il faudra
   l'ajouter au `SELECT` et le transmettre dans l'événement, comme pour
   `pseudo`/`texte`)
