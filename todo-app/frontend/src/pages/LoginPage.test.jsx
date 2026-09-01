import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { test, expect, vi } from 'vitest';
import LoginPage from './LoginPage';

test('affiche le formulaire de connexion', () => {
  render(
    <MemoryRouter>
      <LoginPage setToken={() => {}} />
    </MemoryRouter>
  );

  expect(screen.getByPlaceholderText("Nom d'utilisateur")).toBeInTheDocument();
  expect(screen.getByPlaceholderText('Mot de passe')).toBeInTheDocument();
  expect(screen.getByText('Se connecter')).toBeInTheDocument();
});

test('le champ nom d utilisateur se met a jour quand on tape', () => {
  render(
    <MemoryRouter>
      <LoginPage setToken={() => {}} />
    </MemoryRouter>
  );

  const champ = screen.getByPlaceholderText("Nom d'utilisateur");
  fireEvent.change(champ, { target: { value: 'alice' } });

  expect(champ.value).toBe('alice');
});

test('affiche un lien vers la page d inscription', () => {
  render(
    <MemoryRouter>
      <LoginPage setToken={() => {}} />
    </MemoryRouter>
  );

  const lien = screen.getByText('Creer un compte');
  expect(lien).toBeInTheDocument();
  expect(lien.closest('a')).toHaveAttribute('href', '/register');
});
