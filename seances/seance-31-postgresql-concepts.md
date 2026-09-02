# Séance 31 (cours bonus) — Qu'est-ce qu'une base relationnelle ? Premières requêtes SELECT

## Théorie — pourquoi pas juste un fichier ou un dictionnaire Python ?

Avant `taches.json` (Séance 13) puis PostgreSQL (Séance 25), on aurait pu tout
garder en mémoire dans une liste Python :

```python
taches = [
    {"id": 1, "titre": "Acheter du pain", "terminee": False},
    {"id": 2, "titre": "Appeler le dentiste", "terminee": True},
]
```

Ça marche tant que le programme tourne. Le problème : dès que le programme
s'arrête, tout disparaît (c'est pour ça qu'on est passé à un fichier JSON).
Et un fichier JSON a ses propres limites, qu'on a senties en Séance 25 :

- si deux requêtes écrivent en même temps, le fichier peut se corrompre
- pour trouver "les tâches de l'utilisateur 42", il faut recharger **tout**
  le fichier en mémoire et le parcourir à la main
- rien n'empêche un jour d'écrire `{"titre": "x", "termine": "oui"}` par
  erreur (faute de frappe sur la clé, `"oui"` au lieu de `True`) — un
  dictionnaire Python n'impose aucune structure

Une **base de données relationnelle** comme PostgreSQL résout ces trois
problèmes : les données sont sur disque (persistantes), un vrai moteur
optimise les recherches, et chaque table impose une structure stricte
(colonnes fixes, types fixes).

## Théorie — le modèle relationnel

Imagine un classeur Excel. Chaque **feuille** = une **table** (`taches`,
`users`...). Chaque **ligne** de la feuille = un **enregistrement** (une
tâche précise). Chaque **colonne** = un **champ**, avec un nom et un type
fixés à l'avance pour toute la table (`titre` est toujours du texte,
`terminee` est toujours vrai/faux).

```
table "taches"
+----+----------------------+----------+---------------------+
| id | titre                | terminee | date_echeance       |
+----+----------------------+----------+---------------------+
| 1  | Acheter du pain      | false    | 2026-09-03 09:00:00 |
| 2  | Appeler le dentiste  | true     | NULL                |
+----+----------------------+----------+---------------------+
```

Contrairement à une liste de dictionnaires Python, impossible d'avoir une
ligne avec une colonne en plus ou en moins, ou un type différent — c'est
justement ce qui garantit que les données restent cohérentes, même après des
milliers d'insertions par des dizaines de routes Flask différentes.

"Relationnel" ne veut pas encore dire grand-chose pour l'instant (ça viendra
en Séance 34, avec les liens entre tables `users` et `taches`) — retiens pour
l'instant juste "organisé en tables".

## Théorie — SQL, un langage différent de Python

**SQL** (Structured Query Language) sert à interroger et modifier les
données dans une base relationnelle. Grosse différence de mentalité avec
Python :

- **Python est impératif** : tu décris **comment** faire, étape par étape
  (`for tache in taches: if not tache["terminee"]: ...`)
- **SQL est déclaratif** : tu décris **quoi** obtenir, et c'est le moteur
  PostgreSQL qui décide comment aller chercher ça le plus efficacement
  possible (`SELECT * FROM taches WHERE terminee = false`)

C'est pour ça qu'on n'a jamais eu besoin d'écrire de boucle pour filtrer les
tâches non terminées dans `app.py` : le `WHERE` de la requête SQL fait ce
travail, à l'intérieur même de PostgreSQL, avant que Python ne reçoive quoi
que ce soit.

## Pratique — l'éditeur SQL de Neon

Jusqu'ici, on n'a jamais écrit de SQL directement — `app.py` le fait pour
nous via SQLAlchemy (`text("SELECT ...")`). Aujourd'hui, on va écrire du SQL
à la main, en lecture seule, directement sur les vraies tables de l'appli :

1. Va sur **console.neon.tech**, ouvre ton projet
2. Dans le menu de gauche, clique sur **SQL Editor**
3. Tu arrives sur une zone où taper une requête et un bouton "Run"

C'est exactement la même base que celle utilisée par le backend en
production (`DATABASE_URL`) — donc on reste en **lecture seule** (`SELECT`)
pour cette séance, pour ne rien modifier par erreur.

## Pratique — la requête SELECT

```sql
SELECT * FROM taches;
```

- `SELECT` : quelles colonnes je veux voir (`*` = toutes)
- `FROM taches` : dans quelle table
- Le `;` termine la requête (comme le `:` en Python annonce un bloc, mais
  ici c'est juste une convention de fin d'instruction)

Quelques variantes à essayer dans l'éditeur :

```sql
-- Seulement certaines colonnes
SELECT titre, terminee FROM taches;

-- Filtrer avec WHERE (comme un `if` mais côté base de données)
SELECT * FROM taches WHERE terminee = false;

-- Trier
SELECT * FROM taches ORDER BY date_echeance;

-- Limiter le nombre de résultats
SELECT * FROM taches ORDER BY id DESC LIMIT 5;

-- Compter (une fonction d'agrégation)
SELECT COUNT(*) FROM taches;
```

Équivalent Python de `SELECT * FROM taches WHERE terminee = false ORDER BY date_echeance`,
pour ancrer l'intuition :

```python
resultat = [t for t in taches if t["terminee"] == False]
resultat.sort(key=lambda t: t["date_echeance"])
```

Le SQL fait en une ligne déclarative ce que Python ferait en plusieurs lignes
impératives — et PostgreSQL le fait bien plus vite qu'une boucle Python dès
que la table contient des milliers de lignes, parce qu'il peut utiliser des
index (Séance 35).

## Exercice

Dans l'éditeur SQL de Neon, écris et exécute toi-même les requêtes
suivantes (pas de copier-coller — le but est de mémoriser la syntaxe) :

1. Affiche toutes les colonnes de la table `users`
2. Affiche uniquement les colonnes `username` et `email` de `users`
3. Affiche les tâches où `terminee = true`
4. Affiche les tâches triées par `id` décroissant, seulement les 3 premières
5. Compte combien d'utilisateurs existent au total (`COUNT(*)` sur `users`)
6. Bonus : affiche les tâches dont le `titre` contient le mot "test" (indice :
   l'opérateur `LIKE` avec `%test%` — cherche "SQL LIKE operator" si besoin)

Pas de commit git pour cette séance (rien n'a changé dans le code) — c'est de
la manipulation directe en base, à but pédagogique.
