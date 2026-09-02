# Séance 33 (cours bonus) — Manipuler les données en SQL pur

## Théorie — INSERT

```sql
INSERT INTO taches (titre, terminee) VALUES ('Exemple', false);
```

`INSERT INTO table (colonnes...) VALUES (valeurs...)` — l'ordre des valeurs
doit correspondre à l'ordre des colonnes indiquées entre parenthèses. Les
colonnes non listées (comme `id`) reçoivent leur `DEFAULT` automatiquement
(le `nextval()` vu en Séance 32).

On peut demander à PostgreSQL de renvoyer directement la ligne créée, avec
son `id` généré :

```sql
INSERT INTO taches (titre, terminee) VALUES ('Exemple', false)
RETURNING id, titre, terminee;
```

C'est exactement ce que fait `creer_tache_db()` dans `app.py` — c'est comme
ça que l'API peut répondre au frontend avec l'id de la tâche fraîchement
créée, sans requête supplémentaire.

## Théorie — UPDATE

```sql
UPDATE taches SET terminee = true WHERE id = 999;
```

`UPDATE table SET colonne = valeur WHERE condition` — modifie les lignes qui
correspondent à la condition.

**Danger réel** : si tu oublies le `WHERE`, `UPDATE taches SET terminee = true`
tout court modifierait **toutes** les lignes de la table, d'un coup. Pas
d'annulation automatique. C'est pour ça qu'on prend toujours l'habitude de
faire d'abord un `SELECT` avec la même condition, pour vérifier ce qui va
être touché, avant de lancer l'`UPDATE`.

## Théorie — DELETE

```sql
DELETE FROM taches WHERE id = 999;
```

Même logique, même danger : `DELETE FROM taches` sans `WHERE` viderait
**toute** la table, pas seulement une ligne. C'est irréversible (pas de
corbeille en SQL). D'où la règle d'or :

> Avant un `UPDATE` ou un `DELETE`, fais toujours le `SELECT` équivalent
> avec le même `WHERE` en premier, regarde ce qui apparaît, et seulement
> ensuite lance la vraie modification.

## Pratique — s'entraîner sur une ligne à toi

**Étape 1** — Crée une ligne de test, en te renvoyant son id :

```sql
INSERT INTO taches (titre, terminee) VALUES ('Ma ligne de pratique', false)
RETURNING id, titre, terminee;
```

Note bien l'`id` qui s'affiche (par exemple 71) — tu vas t'en servir tout de
suite pour les étapes suivantes.

**Étape 2** — Remplace `TON_ID` par le vrai id noté à l'étape 1, puis modifie
ta ligne :

```sql
UPDATE taches SET terminee = true WHERE id = TON_ID;
```

**Étape 3** — Vérifie le changement :

```sql
SELECT * FROM taches WHERE id = TON_ID;
```

**Étape 4** — Supprime ta ligne de pratique :

```sql
DELETE FROM taches WHERE id = TON_ID;
```

**Étape 5** — Confirme qu'elle a bien disparu :

```sql
SELECT * FROM taches WHERE id = TON_ID;
```

(Zéro ligne = supprimée avec succès.)

## Pratique — un vrai nettoyage utile

Toutes les séances précédentes ont accumulé des dizaines de comptes de test
jetables. Ils suivent tous le même motif de nom généré automatiquement par
les tests (`test_` suivi d'un code aléatoire) — un cas parfait pour un
`DELETE` ciblé et sûr.

**Étape 6** — D'abord, prévisualiser avec un `SELECT` (règle d'or ci-dessus) :

```sql
SELECT username FROM users WHERE username LIKE 'test\_%';
```

(le `\_` avec un antislash veut dire "un underscore littéral", pas
"n'importe quel caractère" — sinon `LIKE 'test_%'` matcherait aussi des
noms comme "testX...")

**Étape 7** — Si la liste te semble correcte (uniquement des comptes de
test, pas de comptes réels comme le tien), supprime d'abord leurs tâches
(à cause de la contrainte `REFERENCES` vue en Séance 32 — impossible de
supprimer un utilisateur tant que des tâches pointent encore vers lui) :

```sql
DELETE FROM taches WHERE user_id IN (
    SELECT id FROM users WHERE username LIKE 'test\_%'
);
```

**Étape 8** — Puis supprime les comptes eux-mêmes :

```sql
DELETE FROM users WHERE username LIKE 'test\_%';
```

**Étape 9** — Vérifie le résultat :

```sql
SELECT COUNT(*) FROM users;
```

## Exercice

1. Fais les étapes 1 à 5 (pratique isolée sur ta propre ligne)
2. Fais les étapes 6 à 9 (nettoyage réel, avec prévisualisation avant
   suppression)
3. Bonus : pourquoi l'étape 7 doit obligatoirement se faire **avant**
   l'étape 8, et pas l'inverse ? (indice : relis la contrainte
   `REFERENCES` de la Séance 32)
