# Séance 34 (cours bonus) — Les relations entre tables : clés étrangères et JOIN

## Théorie — pourquoi les donnees sont separees en plusieurs tables

Depuis le debut, `taches.user_id` pointe vers `users.id` (la contrainte
`REFERENCES` vue en Seance 32). Chaque tache ne connait que l'`id` de son
proprietaire, pas son `username`. C'est voulu : si `users.username`
changeait, il n'y aurait qu'une seule ligne a mettre a jour, pas des
milliers de lignes `taches` dupliquant ce nom partout. C'est le principe
de base du modele relationnel — chaque information n'existe qu'a un seul
endroit.

Le prix a payer : pour afficher "la tache de yassineadmin" (titre + nom
d'utilisateur ensemble), il faut recombiner les deux tables **au moment de
la lecture**. C'est exactement le role du `JOIN`.

## Théorie — INNER JOIN

```sql
SELECT taches.titre, users.username
FROM taches
JOIN users ON taches.user_id = users.id;
```

- `FROM taches` : la table de depart
- `JOIN users` : la table a recombiner avec
- `ON taches.user_id = users.id` : la regle de correspondance — pour
  chaque ligne de `taches`, PostgreSQL cherche la ligne de `users` dont
  `id` correspond a `user_id`
- Resultat : une ligne par tache, avec le `username` de son proprietaire
  colle a cote

`JOIN` tout court est un raccourci pour `INNER JOIN` : seules les lignes
qui ont une correspondance **des deux cotes** apparaissent. Si une tache
avait un `user_id` orphelin (impossible ici grace a la contrainte
`REFERENCES`, mais possible dans une base sans cette contrainte), elle
disparaitrait purement et simplement du resultat.

## Pratique

**Étape 1** — Dans l'editeur SQL Neon, efface tout et tape :

```sql
SELECT taches.titre, taches.terminee, users.username
FROM taches
JOIN users ON taches.user_id = users.id
ORDER BY users.username;
```

Regarde le resultat : chaque tache apparait avec le nom de son
proprietaire.

## Théorie — LEFT JOIN

`INNER JOIN` a un defaut : si une tache n'a **aucune** sous-tache, une
jointure `taches JOIN sous_taches` ne la fera pas apparaitre du tout
(puisqu'il n'y a aucune ligne `sous_taches` a lui associer). Pour garder
**toutes** les taches meme sans sous-tache, il faut un `LEFT JOIN` :

```sql
SELECT taches.titre, sous_taches.titre AS sous_tache
FROM taches
LEFT JOIN sous_taches ON sous_taches.tache_id = taches.id;
```

- `LEFT JOIN` : garde **toutes** les lignes de la table de gauche
  (`taches`), meme sans correspondance a droite
- Pour une tache sans sous-tache, la colonne `sous_tache` affiche `NULL`
  au lieu de disparaitre completement du resultat

C'est exactement le choix qu'on a fait cote code plus tot dans la session :
`SousTaches.jsx` charge les sous-taches d'une tache **a la demande**
(quand tu cliques pour deplier), plutot que de faire un `LEFT JOIN` sur
`/taches` a chaque chargement — un compromis volontaire pour eviter de
recalculer un aggregat sur toutes les taches a chaque fois. Mais rien
n'empeche de le faire en SQL, comme exercice.

## Exercice

1. Execute la requete `INNER JOIN` de l'etape 1
2. Execute la requete `LEFT JOIN` ci-dessus, repere au moins une tache
   avec `sous_tache = NULL` (aucune sous-tache)
3. Combine `LEFT JOIN` avec `COUNT()` et `GROUP BY` pour compter le
   nombre de sous-taches par tache (celles qui en ont) :
   ```sql
   SELECT taches.titre, COUNT(sous_taches.id) AS nb_sous_taches
   FROM taches
   LEFT JOIN sous_taches ON sous_taches.tache_id = taches.id
   GROUP BY taches.id
   ORDER BY nb_sous_taches DESC;
   ```
   Les taches sans sous-tache doivent afficher `0`, pas `NULL` — c'est
   `COUNT()` qui fait ce travail (il compte les lignes non-`NULL`, donc
   0 correspondances = 0)
4. Bonus : modifie la requete de l'etape 1 pour ne garder que les taches
   **non terminees** (ajoute un `WHERE` — revise la Seance 31 si besoin)
