# Séance 35 (cours bonus) — Index et transactions

## Théorie — les index

Un index en base de données, c'est comme l'index alphabetique a la fin d'un
livre : au lieu de lire le livre page par page pour trouver un mot,
l'index te dit directement a quelle page aller. Sans index, PostgreSQL fait
un **sequential scan** : il lit **toutes** les lignes de la table une par
une pour verifier lesquelles correspondent.

En Seance 25/28, `app.py` a deja cree un index sans vraiment l'expliquer :

```sql
CREATE INDEX IF NOT EXISTS idx_taches_user_id ON taches (user_id)
```

Ca accelere specifiquement les requetes qui filtrent par `user_id` — exactement
ce que fait `lister_taches_db()` a chaque chargement de la page. Sans cet
index, avec des milliers de taches, PostgreSQL devrait scanner toute la
table a chaque fois qu'un utilisateur ouvre son appli.

## Pratique — voir la difference avec EXPLAIN

L'editeur SQL de Neon a un bouton **Explain** a cote de **Run** — il montre
le plan d'execution choisi par PostgreSQL, sans vraiment executer la
requete.

**Étape 1** — efface tout, tape cette requete, puis clique sur **Explain**
(pas Run) :

```sql
SELECT * FROM taches WHERE user_id = 8;
```

Cherche dans le resultat le mot `Index Scan` (utilise l'index) ou
`Seq Scan` (parcourt tout).

**Étape 2** — refais pareil avec une colonne qui n'a pas d'index :

```sql
SELECT * FROM taches WHERE titre = 'test';
```

Compare : cette fois tu devrais voir `Seq Scan` — il n'existe aucun index
sur `titre`, donc PostgreSQL n'a pas le choix, il doit tout lire.

## Théorie — les transactions

Une transaction regroupe plusieurs instructions SQL en un seul bloc
tout-ou-rien : soit **toutes** reussissent et sont validees ensemble
(`COMMIT`), soit une echoue et **tout** est annule (`ROLLBACK`) — aucun etat
intermediaire bancal n'est jamais visible par les autres requetes.

C'est le "A" et le "C" du sigle **ACID** (Atomicity, Consistency, Isolation,
Durability) qui decrit les garanties d'une vraie base de donnees
relationnelle. Chaque `conn.execute(...)` + `conn.commit()` qu'on ecrit
depuis le debut dans `app.py` est deja une transaction — juste qu'on ne l'a
jamais vue autrement que reussie.

## Pratique — BEGIN / ROLLBACK

**Étape 3** — copie ce bloc entier (les 5 lignes ensemble) dans l'editeur et
clique **Run une seule fois** — c'est important qu'elles s'executent
ensemble, dans la meme transaction :

```sql
BEGIN;
INSERT INTO taches (titre, user_id) VALUES ('Test transaction temporaire', 8);
SELECT COUNT(*) FROM taches WHERE titre = 'Test transaction temporaire';
ROLLBACK;
SELECT COUNT(*) FROM taches WHERE titre = 'Test transaction temporaire';
```

- `BEGIN` : demarre une transaction explicite
- L'`INSERT` cree la ligne
- Le premier `COUNT` doit afficher `1` — a l'interieur de la transaction,
  la ligne existe deja
- `ROLLBACK` : annule tout ce qui s'est passe depuis le `BEGIN`
- Le second `COUNT` doit afficher `0` — comme si l'`INSERT` n'avait jamais
  eu lieu

## Exercice

1. Fais l'Etape 1 et l'Etape 2 (comparaison Index Scan / Seq Scan)
2. Fais l'Etape 3 (BEGIN/ROLLBACK), verifie bien les deux resultats de
   `COUNT` (1 puis 0)
3. Bonus : remplace `ROLLBACK` par `COMMIT` dans le bloc precedent et
   relance — cette fois la ligne doit vraiment rester en base. Supprime-la
   ensuite avec un `DELETE` (Seance 33) pour ne pas polluer tes vraies
   donnees.
