# Séance 20 (Jour 18 du plan) — State (useState), afficher la liste des tâches

## Théorie — c'est quoi le "state" ?

Le **state** (état) d'un composant, c'est une donnée qui peut **changer dans le temps**
et qui, quand elle change, doit faire **réafficher** le composant à l'écran
automatiquement. C'est le cœur de React : au lieu de manipuler le HTML à la main
(comme en JavaScript "classique"), tu décris à quoi le composant ressemble **pour une
valeur donnée du state**, et React se charge de mettre à jour l'affichage tout seul
dès que cette valeur change.

## Théorie — useState

```jsx
import { useState } from 'react';

function Compteur() {
  const [count, setCount] = useState(0);

  return (
    <div>
      <p>Compteur : {count}</p>
      <button onClick={() => setCount(count + 1)}>+1</button>
    </div>
  );
}
```

- `useState(0)` déclare un state qui démarre à `0`
- Ça renvoie **deux choses** (déstructurées avec `[a, b] = ...`, comme en Python avec
  les tuples) : `count` (la valeur actuelle) et `setCount` (la fonction pour la
  changer)
- On ne modifie **jamais** `count` directement (`count = count + 1` ne marcherait
  pas) — il faut **toujours** passer par `setCount(...)`, sinon React ne sait pas
  qu'il doit réafficher le composant
- `onClick={() => setCount(count + 1)}` : à chaque clic sur le bouton, on appelle
  `setCount` avec la nouvelle valeur — React réaffiche automatiquement le `<p>` avec
  le nouveau `count`

## Théorie — afficher une liste avec .map()

Pour transformer un array de données en une liste d'éléments JSX, on utilise
`.map()` (l'équivalent JS d'une compréhension de liste Python) :

```jsx
function ListeTaches() {
  const [taches, setTaches] = useState([
    { id: 1, titre: "Acheter du pain", terminee: false },
    { id: 2, titre: "Reviser React", terminee: false },
  ]);

  return (
    <ul>
      {taches.map((tache) => (
        <li key={tache.id}>{tache.titre}</li>
      ))}
    </ul>
  );
}
```

- `taches.map((tache) => (...))` transforme chaque tâche en un `<li>` — exactement
  comme `[transformer(t) for t in taches]` en Python
- `key={tache.id}` est **obligatoire** sur chaque élément d'une liste JSX — React
  l'utilise pour savoir quel élément a changé/été ajouté/supprimé efficacement.
  Utilise toujours un identifiant stable (comme `id`), jamais l'index de la boucle si
  la liste peut changer d'ordre

## Exercice du jour

1. Dans `todo-app/frontend/src/App.jsx`, importe `useState` depuis `'react'`
2. Déclare un state `taches` avec `useState([...])`, initialisé avec 3 tâches
   codées en dur (comme dans l'exemple), chacune avec `id`, `titre`, `terminee`
3. Affiche la liste avec `<ul>` et `.map()`, en utilisant `key={tache.id}`
4. Pour chaque tâche, affiche aussi si elle est terminée ou non (ex:
   `{tache.titre} {tache.terminee ? "✅" : "❌"}`  — `condition ? siVrai : siFaux` est
   l'opérateur ternaire JS, équivalent du `x if condition else y` de Python)
5. Sauvegarde, vérifie dans le navigateur (`npm run dev`) que les 3 tâches
   s'affichent avec leur statut
6. Fais toi-même `git add` + `git commit` + `git push`

## À faire ensuite (séance suivante)

- Jour 19 : Connexion au backend Flask (fetch), ajouter/supprimer des tâches — les
  deux moitiés du projet vont enfin se parler !
