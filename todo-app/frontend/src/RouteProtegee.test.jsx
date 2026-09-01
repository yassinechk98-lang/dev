import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { test, expect } from 'vitest';
import RouteProtegee from './RouteProtegee';

function afficher(token) {
  render(
    <MemoryRouter initialEntries={['/taches']}>
      <Routes>
        <Route path="/login" element={<p>Page de connexion</p>} />
        <Route
          path="/taches"
          element={
            <RouteProtegee token={token}>
              <p>Contenu protege</p>
            </RouteProtegee>
          }
        />
      </Routes>
    </MemoryRouter>
  );
}

test('redirige vers /login si aucun token', () => {
  afficher(null);
  expect(screen.getByText('Page de connexion')).toBeInTheDocument();
  expect(screen.queryByText('Contenu protege')).not.toBeInTheDocument();
});

test('affiche le contenu si un token est present', () => {
  afficher('un-faux-token');
  expect(screen.getByText('Contenu protege')).toBeInTheDocument();
});
