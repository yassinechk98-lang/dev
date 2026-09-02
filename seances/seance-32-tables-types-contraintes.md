# Séance 32 (cours bonus) — Modéliser les données : tables, types, contraintes

## Théorie — les types de données SQL

Chaque colonne d'une table a un type fixe, décidé à la création de la table.
Correspondance avec ce que tu connais en Python :

| SQL (PostgreSQL) | Python équivalent | Exemple dans l'appli |
|---|---|---|
| `TEXT` | `str` | `titre`, `username`, `email` |
| `INTEGER` | `int` | `user_id` |
| `BOOLEAN` | `bool` | `terminee`, `rappel_envoye` |
| `TIMESTAMP` | `datetime` | `date_echeance` |
| `SERIAL` | pas d'équivalent direct | `id` — un `INTEGER` qui s'auto-incrémente tout seul à chaque `INSERT` (1, 2, 3...) |

`SERIAL` est spécifique aux bases de données : en Python, tu gérais ça
toi-même avant (une variable `prochain_id` qu'on incrémentait). PostgreSQL le
fait pour toi et garantit qu'il n'y aura jamais deux lignes avec le même id,
même si plusieurs requêtes arrivent en même temps.

## Théorie — les contraintes

Une contrainte, c'est une règle que PostgreSQL impose et vérifie **avant**
d'accepter d'écrire une ligne. Si la règle n'est pas respectée, la requête
échoue avec une erreur — la donnée invalide n'est jamais enregistrée.

- **`PRIMARY KEY`** : identifiant unique de la ligne (jamais deux lignes avec
  la même valeur, jamais `NULL`). `id SERIAL PRIMARY KEY` = les deux à la fois.
- **`NOT NULL`** : cette colonne ne peut jamais être vide. Exemple :
  `titre TEXT NOT NULL` — impossible de créer une tâche sans titre, même par
  erreur dans le code Python (la base refuserait la ligne).
- **`UNIQUE`** : deux lignes ne peuvent pas avoir la même valeur dans cette
  colonne. Exemple : `username TEXT UNIQUE` — empêche deux comptes avec le
  même nom d'utilisateur.
- **`DEFAULT valeur`** : si aucune valeur n'est fournie à l'`INSERT`, PostgreSQL
  met celle-ci automatiquement. Exemple : `terminee BOOLEAN DEFAULT FALSE` —
  une tâche est "à faire" par défaut à sa création.
- **`REFERENCES autre_table(colonne)`** (clé étrangère / foreign key) : la
  valeur doit obligatoirement exister dans l'autre table. Exemple :
  `user_id INTEGER REFERENCES users(id)` — impossible de créer une tâche
  pour un `user_id` qui n'existe pas dans `users`. On creusera ça en détail
  en Séance 34 (les JOIN).

Toutes ces règles existent pour une seule raison : **empêcher les données
incohérentes d'entrer dans la base**, plutôt que de compter sur le code
Python pour ne jamais se tromper (il se trompera un jour — mieux vaut que la
base elle-même refuse).

## Pratique — relire le vrai schéma de l'appli

Ouvre `todo-app/backend/app.py` et retrouve la fonction `initialiser_schema()`
(vers la ligne 34). C'est du SQL brut, exécuté une fois au démarrage du
serveur — exactement ce qu'on vient de voir en théorie, en vrai :

```sql
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
)
```

Relis-la et repère, pour chaque colonne de `users`, `taches` et
`push_subscriptions` : son type, et les contraintes qui lui sont appliquées.

## Pratique — interroger le schéma depuis SQL

`\d nom_table` est la commande classique pour voir la structure d'une table,
mais c'est une commande **psql** (le client en ligne de commande), pas du SQL
standard — ça ne marche pas dans l'éditeur web de Neon. La vraie requête SQL
équivalente interroge une table système, `information_schema.columns`, qui
existe dans **toute** base PostgreSQL et décrit sa propre structure :

```sql
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'taches';
```

- `column_name` : le nom de la colonne
- `data_type` : son type (tu verras `character varying`/`text`,
  `integer`, `boolean`, `timestamp without time zone` — les noms internes
  de PostgreSQL pour `TEXT`, `INTEGER`, etc.)
- `is_nullable` : `YES`/`NO` — si `NOT NULL` a été appliqué
- `column_default` : la valeur par défaut (`DEFAULT`), si définie

## Exercice

1. Exécute la requête `information_schema.columns` ci-dessus sur `taches`,
   compare avec ce que tu as lu dans `initialiser_schema()`
2. Refais la même requête pour `users`, puis pour `push_subscriptions`
3. Repère dans le résultat de `users` la colonne où `is_nullable = NO` pour
   `username` — c'est la contrainte `NOT NULL` qu'on a vue en théorie
4. Essaie volontairement de casser une contrainte, pour voir le message
   d'erreur de PostgreSQL (ça ne modifiera rien, la requête va juste
   échouer) :
   ```sql
   INSERT INTO taches (terminee) VALUES (false);
   ```
   Regarde le message d'erreur renvoyé — quelle contrainte il mentionne, et
   pourquoi
5. Bonus : dans `app.py`, trouve la ligne qui ajoute la contrainte
   `REFERENCES users(id)` sur `taches.user_id`, et explique avec tes mots ce
   qu'elle empêche
