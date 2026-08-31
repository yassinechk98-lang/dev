# Séance 27 (bonus, hors plan initial) — Authentification

## Théorie — le problème actuel

Toutes les tâches sont mélangées dans une seule table, accessible par n'importe qui
connaissant l'URL de l'API. Pour que chaque utilisateur ait ses propres tâches, il
faut : un système de comptes (inscription/connexion), et vérifier "qui fait cette
requête" avant de lister/créer/modifier/supprimer des tâches.

## Théorie — mots de passe : ne jamais les stocker en clair

Si la base de données fuite un jour, un mot de passe stocké tel quel serait
immédiatement utilisable par un attaquant (et beaucoup de gens réutilisent le même
mot de passe partout). On stocke à la place un **hash** : le résultat d'une fonction
à sens unique, impossible à "dé-hasher" pour retrouver le mot de passe original.

```python
from werkzeug.security import generate_password_hash, check_password_hash

hash_stocke = generate_password_hash("motdepasse123")
# on stocke hash_stocke en base, jamais "motdepasse123"

check_password_hash(hash_stocke, "motdepasse123")   # True
check_password_hash(hash_stocke, "mauvais")         # False
```

`werkzeug` est déjà installé (dépendance de Flask) — pas de nouveau paquet pour ça.

## Théorie — JWT (JSON Web Token)

Notre API est **stateless** (elle ne "se souvient" de rien entre deux requêtes,
contrairement à un site web classique avec des sessions serveur). Pour qu'un client
prouve "je suis bien connecté en tant qu'utilisateur X" à chaque requête, on utilise
un **JWT** : un jeton signé numériquement, que le serveur génère à la connexion et
que le client renvoie à chaque requête suivante.

```python
import jwt
from datetime import datetime, timedelta, timezone

# a la connexion : generer un token
token = jwt.encode(
    {"user_id": 1, "exp": datetime.now(timezone.utc) + timedelta(days=7)},
    "ma_cle_secrete",
    algorithm="HS256",
)

# a chaque requete protegee : verifier le token
donnees = jwt.decode(token, "ma_cle_secrete", algorithms=["HS256"])
donnees["user_id"]   # 1
```

- Le token est **signé** avec une clé secrète connue seulement du serveur — un client
  ne peut pas fabriquer un faux token valide sans connaître cette clé
- `exp` (expiration) : le token devient invalide après ce délai, pour limiter les
  risques si un token est volé
- Le client stocke ce token (ici : `localStorage` côté React) et le renvoie dans
  l'en-tête HTTP `Authorization: Bearer <token>` à chaque requête protégée

## Théorie — protéger une route Flask

```python
from functools import wraps
from flask import request, jsonify
import jwt

def token_requis(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"erreur": "Authentification requise"}), 401
        try:
            donnees = jwt.decode(auth[7:], SECRET_KEY, algorithms=["HS256"])
        except jwt.InvalidTokenError:
            return jsonify({"erreur": "Token invalide ou expire"}), 401
        return f(donnees["user_id"], *args, **kwargs)
    return wrapper

@app.route("/taches", methods=["GET"])
@token_requis
def lister_taches(user_id):
    return jsonify(lister_taches_db(user_id))
```

- `@token_requis` est un **décorateur** (comme `@app.route`) : il s'exécute avant la
  fonction qu'il décore, vérifie le token, et soit bloque avec une erreur `401`
  (Unauthorized), soit laisse passer en fournissant `user_id` à la fonction
- Chaque fonction `*_db` doit maintenant filtrer par `user_id`, pour que chacun ne
  voie/modifie que ses propres tâches

## Ce qui change en base de données

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);

ALTER TABLE taches ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id);
```

- `UNIQUE` sur `username` : PostgreSQL refuse deux comptes avec le même nom
- `REFERENCES users(id)` : une **clé étrangère**, garantit que `user_id` pointe
  toujours vers un utilisateur qui existe réellement

## Ce qui change côté frontend

- Un écran de connexion/inscription, affiché tant qu'aucun token valide n'est stocké
- Le token JWT stocké dans `localStorage` (survit au rechargement de la page)
- Chaque `fetch` vers l'API ajoute l'en-tête `Authorization: Bearer <token>`
- Un bouton "Déconnexion" qui supprime le token du `localStorage`

## Exercice

Vu la quantité de code (backend + frontend + migration de base de données),
l'assistant implémente cette fois directement l'ensemble, puis vous testez ensemble
étape par étape (inscription, connexion, création de tâche liée à l'utilisateur,
déconnexion/reconnexion, vérification qu'un autre compte ne voit pas les mêmes
tâches).
