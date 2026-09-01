# Séance 30 (bonus, hors plan initial) — Tests frontend avec Vitest

## Théorie — pourquoi tester des composants React ?

Comme `pytest` pour le backend, on veut vérifier automatiquement que les composants
React se comportent bien, sans les tester à la main dans le navigateur à chaque
changement.

- **Vitest** : l'équivalent de `pytest` côté JavaScript, très intégré à Vite
- **React Testing Library** : simule un composant React "monté" et permet de
  vérifier ce qui s'affiche, cliquer dessus, remplir des champs — comme un vrai
  utilisateur le ferait, plutôt que d'inspecter les détails internes du code

## Théorie — écrire un test de composant

```jsx
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from './pages/LoginPage';

test('affiche le formulaire de connexion', () => {
  render(
    <MemoryRouter>
      <LoginPage setToken={() => {}} />
    </MemoryRouter>
  );

  expect(screen.getByPlaceholderText("Nom d'utilisateur")).toBeInTheDocument();
  expect(screen.getByText('Se connecter')).toBeInTheDocument();
});
```

- `render(...)` : monte le composant dans un DOM virtuel, comme s'il s'affichait
  dans un navigateur
- `<MemoryRouter>` : requis car `LoginPage` utilise `useNavigate`/`Link`, qui ont
  besoin d'un contexte de routing pour fonctionner — même en test
- `screen.getByPlaceholderText(...)`, `screen.getByText(...)` : cherchent un élément
  affiché, exactement comme un utilisateur le repérerait visuellement
- `expect(...).toBeInTheDocument()` : équivalent d'un `assert` pytest

## Théorie — simuler un clic et une saisie

```jsx
import { render, screen, fireEvent } from '@testing-library/react';

test('le champ se met a jour quand on tape', () => {
  render(<MemoryRouter><LoginPage setToken={() => {}} /></MemoryRouter>);

  const champ = screen.getByPlaceholderText("Nom d'utilisateur");
  fireEvent.change(champ, { target: { value: "alice" } });

  expect(champ.value).toBe("alice");
});
```

- `fireEvent.change(...)` simule la saisie d'un utilisateur dans un champ
- `fireEvent.click(...)` simulerait un clic sur un bouton

## Exercice

1. Installer `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`
2. Configurer Vite pour les tests (`vite.config.js`)
3. Écrire quelques tests sur `LoginPage` et `RouteProtegee`
4. Ajouter les tests frontend au CI (GitHub Actions), avant le déploiement — si les
   tests échouent, le déploiement ne doit pas se faire

## Pieges rencontres

1. **Timeout de demarrage des workers Vitest** en local : passer par `pool: 'forks'`
   avec `fileParallelism: false` (syntaxe Vitest 4, `poolOptions` imbrique est
   deprecie) a regle le probleme.
2. **`webidl.util.markAsUncloneable is not a function`** sur GitHub Actions
   uniquement (jamais en local) : un bug de compatibilite entre `jsdom`
   (dependance de `undici`) et une version tres recente de Node.js (24, forcee par
   GitHub car Node 20 est deprecie sur les runners). Solution : fixer explicitement
   `node-version: "22"` (LTS stable) dans le workflow plutot que de laisser GitHub
   choisir une version potentiellement trop recente et moins testee.

**Lecon generale** : un test qui passe en local peut echouer en CI a cause de
differences d'environnement (version de Node, OS, variables...) — c'est justement
la valeur du CI, qui detecte ces divergences avant qu'elles n'affectent la
production.
