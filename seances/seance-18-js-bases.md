# Séance 18 (Jour 16 du plan) — Bases JavaScript moderne

Début de la Semaine 4 — le frontend ! JavaScript est le langage qui tourne dans le
navigateur (et avec Node.js, aussi en dehors). Beaucoup de concepts te seront
familiers depuis Python, avec une syntaxe différente.

## Théorie — variables : const et let

```javascript
const nom = "Yassine";   // valeur qui ne changera jamais
let age = 27;             // valeur qui peut changer

age = 28;   // OK, age est "let"
nom = "Autre";   // ERREUR, nom est "const"
```

- `const` : par défaut, à utiliser dans la grande majorité des cas
- `let` : seulement quand tu sais que la variable va être réassignée
- (`var` existe aussi mais est l'ancienne façon de faire — on ne l'utilise plus)
- Pas de `print()` : on utilise `console.log(...)`

## Théorie — types et petites différences avec Python

```javascript
const texte = "Bonjour";           // string
const nombre = 27;                  // number (pas de distinction int/float)
const actif = true;                 // boolean (minuscule, pas "True")
const liste = ["a", "b", "c"];      // array (équivalent d'une liste Python)
const objet = { nom: "Yassine", age: 27 };   // object (équivalent d'un dict Python)

console.log(`Je m'appelle ${objet.nom}`);   // template string, comme un f-string !
```

- Les **template strings** (avec des backticks `` ` `` et `${...}`) remplacent les
  f-strings Python
- Un `object` s'accède avec `.propriete` (comme un objet Python) ou `["propriete"]`
  (comme un dict Python) — les deux marchent

## Théorie — fonctions fléchées (arrow functions)

```javascript
// fonction "classique"
function additionner(a, b) {
    return a + b;
}

// fonction fléchée (arrow function) — équivalente, syntaxe plus moderne
const additionner2 = (a, b) => {
    return a + b;
};

// version courte : si le corps est une seule expression avec return implicite
const additionner3 = (a, b) => a + b;
```

Les fonctions fléchées sont la norme en React — tu les verras partout dans les
prochaines séances.

## Théorie — fetch et les promesses (async/await)

`fetch` est la fonction JavaScript pour faire des requêtes HTTP — exactement ce qu'on
fera pour appeler notre backend Flask. Une requête réseau prend du temps, donc
`fetch` est **asynchrone** : elle renvoie une "promesse" (`Promise`) plutôt que le
résultat immédiatement.

```javascript
// avec async/await (la façon moderne et lisible)
async function recupererTaches() {
    const reponse = await fetch("http://localhost:5000/taches");
    const donnees = await reponse.json();
    console.log(donnees);
}

recupererTaches();
```

- `async function` : déclare que cette fonction contient du code asynchrone
- `await` : "attends que cette promesse se termine avant de continuer" — évite
  d'avoir à gérer des callbacks imbriqués compliqués
- `await reponse.json()` : convertit la réponse HTTP en objet JavaScript (équivalent
  de `response.json()` côté Python avec `requests`, ou l'inverse de `jsonify()` côté
  Flask)

## Exercice du jour

1. Crée `dev/exercices/jour16.js`
2. Déclare une `const` (ton prénom) et un `let` (un compteur à 0), affiche-les avec
   `console.log` et un template string
3. Crée un array de 3 tâches (juste des strings), boucle dessus avec
   `for (const t of taches) { console.log(t); }` (équivalent JS du `for...in` Python)
4. Écris une fonction fléchée `estMajeur = (age) => age >= 18`, teste-la avec deux
   âges différents
5. Bonus : si ton backend Flask tourne (Jour 15), écris une fonction
   `async function` qui `fetch` `http://localhost:5000/taches` et affiche le résultat
   avec `console.log` (attention : il faudra activer CORS côté Flask pour que ça
   marche depuis Node — normal si ça bloque, on réglera ça au Jour 19, pas grave si
   tu passes cette partie aujourd'hui)
6. Exécute avec : `node exercices/jour16.js`
7. Fais toi-même `git add` + `git commit` + `git push`

## À faire ensuite (séance suivante)

- Jour 17 : créer le projet React (Vite), composants, JSX
