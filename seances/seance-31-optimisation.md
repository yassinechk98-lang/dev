# Séance 31 (bonus, hors plan initial) — Optimisation

## Théorie — index de base de données

Une base de données cherche par défaut en parcourant toutes les lignes une par une
("full scan") — rapide sur quelques dizaines de lignes, très lent sur des millions.
Un **index** est une structure annexe (un peu comme l'index d'un livre) qui permet
de retrouver directement les lignes correspondant à une valeur, sans tout parcourir.

Toutes nos requêtes de tâches filtrent par `user_id`
(`WHERE user_id = :uid`) — c'est exactement le genre de colonne qu'on indexe :

```sql
CREATE INDEX IF NOT EXISTS idx_taches_user_id ON taches (user_id);
```

Sur notre petite base (quelques lignes), l'effet est invisible. Mais c'est une
habitude professionnelle importante : indexer les colonnes utilisées dans les
`WHERE`/`JOIN` fréquents, avant que ça ne devienne un problème de performance à
grande échelle.

## Théorie — code-splitting (chargement différé)

Actuellement, `npm run build` génère **un seul** gros fichier JavaScript contenant
tout le code (login, inscription, liste de tâches...), téléchargé en entier même si
le visiteur ne voit qu'une seule page au départ. Le **code-splitting** découpe ce
fichier en plusieurs morceaux, chargés seulement quand nécessaire.

```jsx
import { lazy, Suspense } from 'react';

const LoginPage = lazy(() => import('./pages/LoginPage'));
const TodosPage = lazy(() => import('./pages/TodosPage'));

function App() {
  return (
    <Suspense fallback={<p>Chargement...</p>}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/taches" element={<TodosPage />} />
      </Routes>
    </Suspense>
  );
}
```

- `lazy(() => import(...))` : au lieu d'importer le composant immédiatement, on
  fournit une fonction qui l'importera **seulement** quand ce composant doit
  s'afficher — Vite le sépare alors en son propre fichier `.js`
- `<Suspense fallback={...}>` : pendant que le morceau se télécharge (généralement
  quelques millisecondes), affiche `fallback` à la place de planter

## Théorie — état de chargement (UX perçue)

Actuellement, entre l'affichage de la page et l'arrivée des tâches depuis l'API, rien
n'indique à l'utilisateur que ça charge — la liste est juste vide un court instant.
Un indicateur de chargement rend l'attente moins confuse :

```jsx
const [chargement, setChargement] = useState(true);

useEffect(() => {
  getTaches(token)
    .then(...)
    .finally(() => setChargement(false));
}, [token]);

// dans le JSX :
{chargement ? <p>Chargement des taches...</p> : <ul>...</ul>}
```

- `.finally(...)` s'exécute après un `.then()` ou un `.catch()`, que la requête ait
  réussi ou échoué — parfait pour "dans tous les cas, on n'est plus en train de
  charger"

## Exercice

1. Ajoute l'index SQL sur `taches.user_id` dans `app.py`
2. Ajoute le code-splitting (`lazy`/`Suspense`) dans `App.jsx`
3. Ajoute un état de chargement dans `TodosPage.jsx`
4. Vérifie que tout marche toujours pareil (juste plus rapide/plus clair à l'usage)
5. Commit + push (CI/CD s'occupe du reste)
