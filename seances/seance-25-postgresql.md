# Séance 25 (bonus, hors plan initial) — Migrer vers PostgreSQL

## Théorie — pourquoi PostgreSQL plutôt que JSON ?

Le fichier `taches.json` marche pour apprendre, mais a des limites réelles : pas de
recherche efficace, risque de corruption si deux requêtes écrivent en même temps,
tout doit être rechargé en mémoire à chaque lecture. **PostgreSQL** est un vrai
serveur de base de données relationnelle — le standard le plus utilisé dans
l'industrie pour ce genre de projet.

**Neon** (neon.tech) héberge un serveur PostgreSQL gratuitement pour toi dans le
cloud : pas d'installation locale, tu récupères juste une URL de connexion.

## Théorie — SQLAlchemy

Plutôt qu'écrire du SQL brut partout, on utilise **SQLAlchemy** (comme on a utilisé
Flask plutôt que gérer HTTP à la main) — une bibliothèque qui simplifie la
connexion et les requêtes, tout en restant proche du SQL.

```python
from sqlalchemy import create_engine, text

engine = create_engine("postgresql://user:password@host/dbname")

with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS taches (
            id SERIAL PRIMARY KEY,
            titre TEXT NOT NULL,
            terminee BOOLEAN DEFAULT FALSE
        )
    """))
    conn.commit()
```

- `create_engine(url)` : ouvre la connexion vers la base (l'URL contient utilisateur,
  mot de passe, adresse du serveur, nom de la base)
- `SERIAL PRIMARY KEY` : équivalent PostgreSQL de l'auto-incrémentation qu'on gérait
  nous-mêmes avec `prochain_id`
- `text("...")` : englobe une requête SQL brute
- `conn.commit()` : valide définitivement les changements (comme `git commit`, mais
  pour la base de données)

## Étape 1 — créer le compte et la base sur Neon

1. Va sur **neon.tech**, crée un compte (gratuit, tu peux utiliser GitHub pour te
   connecter puisque tu en as déjà un)
2. Crée un nouveau projet (il te proposera un nom de base par défaut, garde-le)
3. Sur le tableau de bord du projet, trouve la **Connection string** — une URL du
   type `postgresql://user:password@ep-xxx.neon.tech/dbname?sslmode=require`
4. Copie-la précieusement (c'est un secret, comme un mot de passe — ne la commite
   jamais dans Git !)

## Étape 2 — sécuriser la connection string avec .env

⚠️ Une connection string contient un mot de passe. On ne l'écrit **jamais** en dur
dans `app.py` (qui est versionné sur GitHub, donc public si le dépôt l'est). On la
met dans un fichier `.env`, qui est ignoré par Git.

1. Installe les paquets nécessaires (venv activé) :
   ```
   pip install sqlalchemy psycopg2-binary python-dotenv
   ```
2. Crée `todo-app/backend/.env` avec :
   ```
   DATABASE_URL=postgresql://user:password@ep-xxx.neon.tech/dbname?sslmode=require
   ```
   (remplace par ta vraie connection string copiée depuis Neon)
3. Ajoute `.env` dans `.gitignore` (à la racine de `dev/`)

## Étape 3 — adapter le backend

```python
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
engine = create_engine(os.environ["DATABASE_URL"])

with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS taches (
            id SERIAL PRIMARY KEY,
            titre TEXT NOT NULL,
            terminee BOOLEAN DEFAULT FALSE
        )
    """))
    conn.commit()

def lister_taches_db():
    with engine.connect() as conn:
        resultat = conn.execute(text("SELECT id, titre, terminee FROM taches ORDER BY id"))
        return [dict(row._mapping) for row in resultat]

def creer_tache_db(titre):
    with engine.connect() as conn:
        resultat = conn.execute(
            text("INSERT INTO taches (titre) VALUES (:titre) RETURNING id, titre, terminee"),
            {"titre": titre},
        )
        conn.commit()
        return dict(resultat.fetchone()._mapping)

def basculer_tache_db(tache_id):
    with engine.connect() as conn:
        resultat = conn.execute(
            text("""
                UPDATE taches SET terminee = NOT terminee
                WHERE id = :id
                RETURNING id, titre, terminee
            """),
            {"id": tache_id},
        )
        conn.commit()
        ligne = resultat.fetchone()
        return dict(ligne._mapping) if ligne else None

def supprimer_tache_db(tache_id):
    with engine.connect() as conn:
        resultat = conn.execute(text("DELETE FROM taches WHERE id = :id"), {"id": tache_id})
        conn.commit()
        return resultat.rowcount > 0
```

- `:titre`, `:id` : paramètres nommés — SQLAlchemy les insère de façon sécurisée
  (protection contre l'injection SQL, comme le `?` de SQLite au Jour 13)
- `RETURNING ...` : demande à PostgreSQL de renvoyer la ligne juste créée/modifiée,
  pratique pour avoir l'id généré automatiquement sans requête séparée
- Ces fonctions remplacent `charger_taches()`/`sauvegarder_taches()` — les routes
  Flask (`GET`, `POST`, `PUT`, `DELETE`) restent quasi identiques, elles appellent
  juste ces nouvelles fonctions à la place de manipuler la liste `taches` en mémoire

Le **frontend ne change pas du tout** — il continue à parler à `http://localhost:5000/taches`
exactement pareil, sans savoir si les données viennent d'un fichier JSON ou d'une
vraie base PostgreSQL. C'est tout l'intérêt de séparer le frontend et le backend
par une API.

## Exercice

1. Crée ton compte + projet Neon, récupère la connection string
2. Installe les paquets, crée `.env`, ajoute-le au `.gitignore`
3. Adapte `app.py` avec les fonctions ci-dessus, et modifie chaque route pour les
   utiliser à la place de `taches`/`sauvegarder_taches`
4. Teste avec `curl` (GET, POST, PUT, DELETE) comme au Jour 12
5. Relance le frontend, vérifie que tout fonctionne pareil qu'avant
6. Commit (sans `.env` !) + push
