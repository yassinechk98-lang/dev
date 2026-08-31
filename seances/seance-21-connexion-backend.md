# Séance 21 (Jour 19 du plan) — Connexion au backend Flask

Le grand jour : le frontend React va enfin parler au backend Flask !

## Théorie — CORS

Par défaut, un navigateur **bloque** les requêtes JavaScript d'un site vers un autre
"site" différent (même si c'est juste un port différent sur ta propre machine) —
c'est une protection de sécurité appelée **CORS** (Cross-Origin Resource Sharing).
Ton frontend tourne sur `localhost:5173`, ton backend sur `localhost:5000` : ce sont
deux origines différentes pour le navigateur, donc `fetch` serait bloqué sans
autorisation explicite du serveur.

(C'est pour ça que le `fetch` depuis Node au Jour 16 marchait sans souci — Node
n'applique pas cette règle, seuls les **navigateurs** le font.)

**Solution** : dire à Flask d'autoriser les requêtes venant d'autres origines, avec
la bibliothèque `flask-cors` :

```python
from flask_cors import CORS
app = Flask(__name__)
CORS(app)   # autorise toutes les origines (pratique en développement)
```

## Théorie — useEffect : charger les données au démarrage

`useState` gère une donnée qui change, mais comment déclencher un `fetch` **une
seule fois**, quand le composant apparaît à l'écran ? C'est le rôle de `useEffect`.

```jsx
import { useState, useEffect } from 'react';

function App() {
  const [taches, setTaches] = useState([]);

  useEffect(() => {
    fetch("http://localhost:5000/taches")
      .then((reponse) => reponse.json())
      .then((donnees) => setTaches(donnees));
  }, []);   // <- tableau vide = exécute une seule fois, au montage du composant

  // ...
}
```

- `useEffect(fonction, [])` exécute `fonction` une seule fois, juste après le premier
  affichage du composant
- Le tableau `[]` s'appelle le tableau de **dépendances** — vide, ça veut dire "ne
  redéclenche jamais" ; on y reviendra plus tard pour des cas plus avancés
- `.then(...)` est une autre façon d'utiliser une promesse (sans `async/await`) —
  "quand ce résultat arrive, fais ceci"

## Théorie — ajouter et supprimer via l'API

```jsx
const ajouterTache = (titre) => {
  fetch("http://localhost:5000/taches", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titre }),
  })
    .then((reponse) => reponse.json())
    .then((nouvelleTache) => setTaches([...taches, nouvelleTache]));
};

const supprimerTache = (id) => {
  fetch(`http://localhost:5000/taches/${id}`, { method: "DELETE" })
    .then(() => setTaches(taches.filter((t) => t.id !== id)));
};
```

- `JSON.stringify(...)` convertit un objet JS en texte JSON (l'inverse de
  `.json()`), pour l'envoyer dans le corps de la requête — comme `json.dumps()` en
  Python
- `[...taches, nouvelleTache]` : crée un **nouveau** tableau avec toutes les tâches
  existantes + la nouvelle — on ne modifie **jamais** `taches` directement
  (`taches.push(...)` ne déclencherait pas de réaffichage), toujours via `setTaches`
  avec un nouveau tableau
- `taches.filter((t) => t.id !== id)` : garde toutes les tâches sauf celle avec cet
  id — équivalent de la compréhension `[t for t in taches if t["id"] != id]` vue
  côté Python

## Exercice du jour

**Backend**
1. Installe `flask-cors` (venv activé) : `pip install flask-cors`
2. Dans `todo-app/backend/app.py`, ajoute `from flask_cors import CORS` et
   `CORS(app)` juste après la création de `app`

**Frontend**
3. Dans `App.jsx` : remplace le state initial `taches` par un tableau vide `[]`
4. Ajoute `useEffect` pour charger les tâches depuis l'API au démarrage
5. Ajoute un formulaire simple (un `<input>` + un bouton) pour créer une tâche, qui
   appelle `ajouterTache`
6. Ajoute un bouton "Supprimer" sur chaque tâche de la liste, qui appelle
   `supprimerTache(tache.id)`

**Test**
7. Lance le backend (`python todo-app/backend/app.py`) ET le frontend
   (`npm run dev`) **en même temps**, dans deux terminaux différents
8. Dans le navigateur : vérifie que la liste se charge depuis l'API, ajoute une
   tâche, supprime-en une — tout doit se refléter immédiatement à l'écran
9. Fais toi-même `git add` + `git commit` + `git push`

## À faire ensuite (séance suivante)

- Jour 20 : Style, finitions, gestion des erreurs côté front
