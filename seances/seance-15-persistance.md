# Séance 15 (Jour 13 du plan) — Persistance des données

## Théorie — le problème actuel

Rappel du Jour 12 : `taches = [...]` est une simple variable Python, "en mémoire".
Dès que tu arrêtes le serveur (Ctrl+C) ou qu'il redémarre (le mode `debug=True` le
fait automatiquement à chaque modification de code), **tout est perdu** — la liste
revient à son état de départ. Ce n'est pas utilisable pour une vraie application.

**Persister** les données veut dire les sauvegarder quelque part qui survit à l'arrêt
du programme : un fichier, ou une base de données.

## Partie A — persistance avec un fichier JSON

JSON est le même format que celui renvoyé par `jsonify()` — un fichier texte qui
représente des listes/dictionnaires. On va lire ce fichier au démarrage, et le
réécrire à chaque modification.

```python
import json

FICHIER = "taches.json"

def charger_taches():
    try:
        with open(FICHIER, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []   # premier lancement, pas encore de fichier

def sauvegarder_taches(taches):
    with open(FICHIER, "w") as f:
        json.dump(taches, f, indent=2)
```

- `json.load(f)` lit un fichier JSON et le convertit en liste/dict Python (l'inverse
  de `jsonify`)
- `json.dump(taches, f, indent=2)` écrit une liste/dict Python dans un fichier au
  format JSON, `indent=2` pour que ce soit lisible
- On retrouve le `try/except FileNotFoundError` vu au Jour 5 !

Dans les routes qui modifient les tâches (`POST`, `DELETE`), il faut appeler
`sauvegarder_taches(taches)` après chaque changement, pour que ce soit écrit sur le
disque immédiatement.

## Partie B — introduction à SQLite (théorie, pour plus tard)

Un fichier JSON marche pour un petit projet, mais devient vite limité (pas de
recherche efficace, risque de corruption si deux écritures en même temps...). Une
**base de données** résout ça avec un vrai moteur de stockage structuré.

**SQLite** est une base de données qui vit dans un simple fichier `.db` (pas besoin
d'installer un serveur séparé) — parfaite pour apprendre et pour de petits projets.

```python
import sqlite3

conn = sqlite3.connect("taches.db")
cur = conn.cursor()

cur.execute("""
    CREATE TABLE IF NOT EXISTS taches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titre TEXT NOT NULL,
        terminee INTEGER DEFAULT 0
    )
""")

cur.execute("INSERT INTO taches (titre) VALUES (?)", ("Acheter du pain",))
conn.commit()

cur.execute("SELECT * FROM taches")
print(cur.fetchall())

conn.close()
```

- **SQL** est le langage utilisé pour interroger une base de données (`CREATE TABLE`,
  `INSERT`, `SELECT`...)
- Le `?` dans `INSERT ... VALUES (?)` évite d'insérer directement une variable dans la
  requête (ça protège contre une faille de sécurité appelée injection SQL)
- On intégrera vraiment SQLite dans le backend Flask plus tard dans le programme,
  aujourd'hui c'est juste pour comprendre le principe

## Exercice du jour

**Partie A (obligatoire)**
1. Dans `todo-app/backend/app.py`, ajoute `import json` et les deux fonctions
   `charger_taches()` / `sauvegarder_taches()` ci-dessus
2. Remplace `taches = [...]` par `taches = charger_taches()`
3. Dans la route `POST` (création), ajoute `sauvegarder_taches(taches)` juste avant
   le `return`
4. Dans la route `DELETE` (suppression), fais pareil
5. Lance le serveur, crée une tâche avec `curl -X POST ...`, vérifie qu'un fichier
   `todo-app/backend/taches.json` est apparu avec le bon contenu
6. **Arrête le serveur, relance-le**, refais `curl http://localhost:5000/taches` →
   la tâche doit **toujours être là** (preuve que ça persiste vraiment !)

**Partie B (bonus, juste pour manipuler SQLite une fois)**
1. Crée `dev/exercices/jour13_sqlite.py` avec le code SQLite ci-dessus
2. Ajoute une deuxième insertion et un deuxième `SELECT` pour voir les 2 lignes
3. Exécute-le, observe le résultat

## Fin de séance

⚠️ `taches.json` contient des **données**, pas du code — on ne le commite pas (il va
changer à chaque test, ça pollue l'historique). Ajoute une ligne `taches.json` dans
`.gitignore` (à la racine de `dev/`) avant de committer.

Fais toi-même `git add` + `git commit` + `git push`.

## À faire ensuite (séance suivante)

- Jour 14 : Validation des données, gestion des erreurs API
