# Cours bonus — Comprendre PostgreSQL et l'architecture Python / BDD / Web

La Séance 25 (`seances/seance-25-postgresql.md`) a fait la migration vers
PostgreSQL rapidement, pour que l'appli marche. Ce cours revient dessus
posément : comprendre **pourquoi** une base relationnelle est construite comme
ça, savoir écrire du SQL toi-même (pas juste copier du code SQLAlchemy), et
surtout bien situer chaque techno — Python, PostgreSQL, le navigateur — dans
le trajet complet d'une requête.

Méthode identique au reste du cursus : théorie courte, exemples concrets sur
**la vraie base de l'appli** (Neon), exercices pratiques, une trace écrite par
séance dans `seances/`.

## Programme

- [x] Séance 31 — Qu'est-ce qu'une base relationnelle ? Premières requêtes SELECT
- [x] Séance 32 — Modéliser les données : tables, types, contraintes
- [x] Séance 33 — Manipuler les données en SQL pur (INSERT/UPDATE/DELETE/WHERE)
- [x] Séance 34 — Les relations entre tables : clés étrangères et JOIN
- [x] Séance 35 — Index, transactions, et pourquoi ça protège les données
- [ ] Séance 36 — L'architecture complète : du clic React à la ligne PostgreSQL et retour

## Pourquoi cet ordre

Les séances 31-33 restent **dans PostgreSQL uniquement** (l'éditeur SQL de
Neon, pas de Python) — l'idée est de désapprendre le réflexe "je copie le code
Python" et de vraiment lire/écrire du SQL. La séance 34 ajoute la notion
centrale du relationnel (relier des tables entre elles au lieu de tout
dupliquer). La séance 35 explique deux choses déjà utilisées sans être
expliquées (`idx_taches_user_id`, `conn.commit()`). La séance 36 referme la
boucle : on reprend `app.py` et `TodosPage.jsx` ligne par ligne pour tracer
qui fait quoi.
