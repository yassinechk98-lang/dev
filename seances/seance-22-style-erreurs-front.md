# Séance 22 (Jour 20 du plan) — Style et gestion d'erreurs côté front

## Théorie — le CSS de base en React

Le fichier `src/index.css` (importé dans `main.jsx`) s'applique à toute l'app. On
peut y mettre des styles simples en ciblant les balises HTML normales.

```css
body {
  font-family: sans-serif;
  max-width: 500px;
  margin: 40px auto;
  background: #f5f5f5;
}

h1 {
  color: #333;
}

ul {
  list-style: none;
  padding: 0;
}

li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: white;
  padding: 10px;
  margin-bottom: 8px;
  border-radius: 6px;
}

button {
  cursor: pointer;
}
```

## Théorie — gérer les erreurs réseau côté front

Actuellement, si le backend est éteint ou plante, `fetch` échoue silencieusement (ou
avec une erreur uniquement visible dans la console, comme tu l'as vu au Jour 19).
Un vrai utilisateur ne regarde jamais la console — il faut lui montrer un message.

```jsx
const [erreur, setErreur] = useState(null);

useEffect(() => {
  fetch(API_URL)
    .then((reponse) => {
      if (!reponse.ok) throw new Error("Erreur serveur");
      return reponse.json();
    })
    .then((donnees) => setTaches(donnees))
    .catch(() => setErreur("Impossible de charger les taches. Le serveur tourne-t-il ?"));
}, []);
```

Puis dans le JSX, afficher le message si présent :
```jsx
{erreur && <p style={{ color: "red" }}>{erreur}</p>}
```

- `.catch(...)` intercepte toute erreur survenue dans la chaîne de `.then()`
  précédente — équivalent du `except` Python, mais pour les promesses
  (`erreur && <p>...</p>` est un idiome JSX courant : affiche le `<p>` seulement si
  `erreur` n'est pas `null`/vide, sinon n'affiche rien — comme un `if erreur:` en
  une ligne)
- `reponse.ok` est `true` si le code HTTP est 2xx, `false` sinon (ex: 404, 500) —
  `fetch` ne considère **pas** un `404` comme une erreur automatiquement, il faut le
  vérifier soi-même

## Exercice du jour

1. Ajoute le CSS ci-dessus (ou le tien) dans `todo-app/frontend/src/index.css`
2. Dans `App.jsx`, ajoute un state `erreur` et gère le cas d'échec du chargement
   (comme ci-dessus)
3. Affiche le message d'erreur dans le JSX s'il y en a un
4. Teste : arrête le backend, recharge la page frontend → le message d'erreur doit
   s'afficher proprement au lieu d'une page vide
5. Relance le backend, recharge → l'erreur disparaît, les tâches se chargent
6. Fais toi-même `git add` + `git commit` + `git push`

## Fin de la Semaine 4 / du plan initial

Après ce jour, il reste : Jours 21-22 (polish global, nettoyage), Jour 23 (démo et
bilan) — plus libres, on avisera ensemble selon ce qui te semble utile à peaufiner.
