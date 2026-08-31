# Séance 19 (Jour 17 du plan) — Créer le projet React (Vite), composants, JSX

## Théorie — c'est quoi React ?

**React** est une bibliothèque JavaScript pour construire des interfaces web en les
découpant en petits morceaux réutilisables appelés **composants** (un bouton, une
liste de tâches, une carte...). Chaque composant décrit à quoi il ressemble et
comment il réagit aux interactions.

**Vite** est l'outil qui crée et fait tourner le projet React pendant le
développement (équivalent de `flask run`, mais côté frontend) — rapide, avec
rechargement automatique du navigateur à chaque sauvegarde.

## Théorie — JSX

JSX est une syntaxe qui permet d'écrire du HTML **directement dans du JavaScript** :

```jsx
function Bonjour() {
    const nom = "Yassine";
    return (
        <div>
            <h1>Bonjour {nom} !</h1>
            <p>Bienvenue sur ton app de tâches.</p>
        </div>
    );
}
```

- Ça ressemble à du HTML, mais c'est en fait converti en JavaScript en coulisses
- `{nom}` insère une variable JavaScript au milieu du HTML — comme un template string
  mais dans du HTML
- Une fonction qui renvoie du JSX comme ça, c'est un **composant** React
- Règle stricte : un composant doit renvoyer **un seul** élément racine (ici la `<div>`
  qui contient tout)

## Exercice du jour

**Étape 1 — créer le projet**

Dans le terminal, à la racine de `dev/` :
```
npm create vite@latest todo-app/frontend -- --template react
```
Répond aux questions si elles apparaissent (généralement aucune avec `--template react`
déjà précisé).

**Étape 2 — installer les dépendances**
```
cd todo-app/frontend
npm install
```

**Étape 3 — lancer le serveur de développement**
```
npm run dev
```
Ça affiche une URL, généralement `http://localhost:5173`. Ouvre-la dans ton
navigateur : tu dois voir la page par défaut de Vite + React (logos qui tournent,
compteur qui clique).

**Étape 4 — explorer la structure du projet**

Regarde le dossier `todo-app/frontend/src/` — c'est là que vit ton code React :
- `main.jsx` : point d'entrée, affiche le composant `App` dans la page
- `App.jsx` : le composant principal (celui que tu vois affiché par défaut)

**Étape 5 — modifier `App.jsx`**

Ouvre `src/App.jsx`, remplace tout son contenu par :
```jsx
function App() {
  return (
    <div>
      <h1>Ma Todo-list</h1>
      <p>Bienvenue sur mon app de taches !</p>
    </div>
  );
}

export default App;
```
Sauvegarde — le navigateur doit se rafraîchir **automatiquement** (c'est le
rechargement à chaud de Vite) et afficher ton nouveau texte.

**Étape 6 — commit**

Arrête le serveur (Ctrl+C), puis :
```
git add todo-app/frontend seances/seance-19-react-vite-jsx.md
git commit -m "Init projet React (Vite) : composant App de base"
git push
```

## À faire ensuite (séance suivante)

- Jour 18 : State (useState), afficher la liste des tâches
