# Séance 36 (cours bonus) — L'architecture complète : du clic React a PostgreSQL et retour

## Théorie — trois langages, trois couches

Tout au long du cursus, trois technologies bien distinctes ont ete
utilisees, chacune dans son role :

- **Le navigateur (React/JavaScript)** — affiche l'interface, reagit aux
  clics, ne sait absolument rien de PostgreSQL
- **Flask (Python)** — recoit des requetes HTTP, parle SQL a la base,
  renvoie du JSON. Le pont entre le navigateur et la base
- **PostgreSQL (SQL)** — stocke et retrouve les donnees, ne sait rien de
  React ni de HTTP

Aucune de ces trois couches ne "voit" les deux autres directement — chacune
ne parle que le langage de sa voisine immediate : React parle JSON via HTTP
a Flask, Flask parle SQL a Postgres. C'est ce decoupage qui permet, par
exemple, de changer completement l'interface (on l'a refaite en Material
UI) sans jamais toucher au backend ni a la base.

## Pratique — tracer une action de bout en bout

Prenons une action simple et deja construite : **cocher une tache pour la
marquer terminee**. Ouvre `todo-app/frontend/src/pages/TodosPage.jsx` et
`todo-app/backend/app.py` cote a cote, et suis ce chemin.

**Étape 1 — le clic (navigateur)**
Dans `TodosPage.jsx`, cherche (`Ctrl+F`) la fonction `basculer`. Elle est
appelee par le `onChange` de la `Checkbox` de chaque tache. Elle appelle
`basculerTache(token, id)`.

**Étape 2 — l'appel reseau (navigateur -> serveur)**
Ouvre `todo-app/frontend/src/api.js`, cherche `basculerTache`. C'est un
`fetch()` qui envoie une requete HTTP `PUT` vers
`/taches/<id>`, avec le token JWT dans l'en-tete `Authorization`. A partir
de cet instant, React n'a plus la main — la requete voyage sur le reseau
sous forme de texte brut (HTTP), plus du JavaScript.

**Étape 3 — la reception (serveur, Python)**
Dans `app.py`, cherche la route `@app.route("/taches/<int:tache_id>", methods=["PUT"])`.
Le decorateur `@token_requis` (juste au-dessus) verifie d'abord le JWT
avant meme que la fonction ne s'execute — si le token est invalide, la
requete s'arrete la, la base de donnees n'est jamais contactee.

**Étape 4 — Python parle SQL**
La route appelle `basculer_tache_db(user_id, tache_id)`. Cherche cette
fonction : c'est le seul endroit ou du texte SQL brut apparait
(`text("UPDATE taches SET ...")`). C'est la frontiere exacte entre Python
et PostgreSQL — tout ce qui est avant cette fonction est du Python pur,
tout ce qui est dans le `text("...")` est du SQL pur.

**Étape 5 — PostgreSQL execute et repond**
PostgreSQL modifie la ligne, calcule `terminee_le` (Seance 35... enfin,
vue en cours de route au fil des fonctionnalites), et renvoie la ligne
mise a jour grace au `RETURNING`.

**Étape 6 — Python retraduit en JSON**
De retour dans `basculer_tache_db`, `formater_tache(ligne)` transforme la
ligne PostgreSQL (un objet Python special de SQLAlchemy) en dictionnaire
Python simple. La route fait ensuite `jsonify(tache)` — c'est la ligne
exacte ou les donnees redeviennent du JSON, le seul format que le
navigateur sait lire.

**Étape 7 — retour au navigateur**
Dans `api.js`, le `fetch()` recoit la reponse. Dans `TodosPage.jsx`, la
fonction `basculer` fait `.then((reponse) => reponse.json())` puis
`setTaches(...)` — React detecte que l'etat a change et re-affiche
automatiquement la case cochee, sans qu'on ait ecrit une seule ligne de
code pour "redessiner" quoi que ce soit.

## Exercice

1. Ouvre les deux fichiers et retrouve toi-meme, en cherchant les noms de
   fonctions ci-dessus, chacune des 7 etapes
2. Repere la ligne exacte de `app.py` ou le texte passe de Python a SQL
   (le premier caractere a l'interieur d'un `text("...")`)
3. Repere la ligne exacte ou les donnees redeviennent du JSON
   (`jsonify(...)`)
4. Bonus — refais le meme exercice avec une action plus recente : la
   creation d'une tache recurrente. Retrouve le moment ou `basculer_tache_db`
   decide, cote Python, de generer une nouvelle ligne PostgreSQL — cette
   decision (si `recurrence` n'est pas vide) n'existe dans aucune des trois
   couches seule : c'est de la logique metier, ecrite en Python, qui pilote
   a la fois le SQL et (indirectement) ce que React affichera ensuite
