# Séance 28 (bonus, hors plan initial) — React Router : plusieurs pages

## Théorie — le problème actuel

Aujourd'hui, `App.jsx` fait **tout** : c'est un seul composant géant qui affiche soit
l'écran de connexion, soit la liste de tâches, avec un `if` au milieu du JSX. Ça
marche pour une petite app, mais ne scale pas : pas d'URL différente par page (pas
moyen de partager un lien direct vers "/login"), pas de bouton retour du navigateur
cohérent, code de plus en plus mélangé.

## Théorie — React Router

`react-router-dom` ajoute la notion de **routes** : associer une URL à un composant
à afficher.

```jsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/taches" element={<TodosPage />} />
        <Route path="/" element={<Navigate to="/taches" />} />
      </Routes>
    </BrowserRouter>
  );
}
```

- `<BrowserRouter>` active le routing pour toute l'app (à mettre une seule fois, tout
  en haut)
- `<Routes>` regarde l'URL actuelle et affiche le **premier** `<Route>` qui
  correspond
- `<Navigate to="...">` redirige automatiquement (équivalent d'un `redirect()` côté
  serveur, mais côté client)
- `useNavigate()` : un hook pour rediriger **après une action** (ex: après une
  connexion réussie, aller vers `/taches`)

```jsx
import { useNavigate } from 'react-router-dom';

function LoginPage() {
  const navigate = useNavigate();

  const seConnecter = () => {
    // ... logique de connexion ...
    navigate("/taches");
  };
}
```

## Théorie — routes protégées

On ne veut pas qu'un visiteur non connecté puisse afficher `/taches` juste en tapant
l'URL. On enveloppe la route dans un composant qui vérifie le token avant d'afficher
son contenu :

```jsx
function RouteProtegee({ token, children }) {
  if (!token) return <Navigate to="/login" />;
  return children;
}

// utilisation :
<Route path="/taches" element={<RouteProtegee token={token}><TodosPage /></RouteProtegee>} />
```

- Si `token` est absent, on redirige immédiatement vers `/login` au lieu d'afficher
  `children` (le contenu protégé)
- C'est le même principe que le décorateur `@token_requis` côté Flask, mais côté
  frontend cette fois — **attention** : ça empêche juste l'affichage, ça ne
  remplace pas la vraie protection côté backend (qui reste indispensable, un
  utilisateur malin pourrait contourner le frontend et appeler l'API directement)

## Ce qui change dans le projet

Découpage en plusieurs fichiers, un composant = un fichier = une responsabilité :
```
src/
  App.jsx              <- juste la config des routes
  pages/
    LoginPage.jsx
    RegisterPage.jsx
    TodosPage.jsx       <- l'ancienne logique de liste de taches
  RouteProtegee.jsx
```

## Exercice

Vu la restructuration (nouveaux fichiers, routing), l'assistant l'implémente
directement, puis vous testez ensemble : accéder à `/taches` sans être connecté
(doit rediriger vers `/login`), se connecter (doit rediriger vers `/taches`),
naviguer entre connexion et inscription.
