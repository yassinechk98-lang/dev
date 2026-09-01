import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { test, expect } from 'vitest';
import LoginPage from './LoginPage';

test('affiche le formulaire de connexion', () => {
  render(
    <MemoryRouter>
      <LoginPage setToken={() => {}} mode="light" basculerMode={() => {}} />
    </MemoryRouter>
  );

  expect(screen.getByLabelText("Nom d'utilisateur")).toBeInTheDocument();
  expect(screen.getByLabelText('Mot de passe')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Se connecter' })).toBeInTheDocument();
});

test('le champ nom d utilisateur se met a jour quand on tape', () => {
  render(
    <MemoryRouter>
      <LoginPage setToken={() => {}} mode="light" basculerMode={() => {}} />
    </MemoryRouter>
  );

  const champ = screen.getByLabelText("Nom d'utilisateur");
  fireEvent.change(champ, { target: { value: 'alice' } });

  expect(champ.value).toBe('alice');
});

test('affiche un lien vers la page d inscription', () => {
  render(
    <MemoryRouter>
      <LoginPage setToken={() => {}} mode="light" basculerMode={() => {}} />
    </MemoryRouter>
  );

  const lien = screen.getByText('Creer un compte');
  expect(lien).toBeInTheDocument();
  expect(lien.closest('a')).toHaveAttribute('href', '/register');
});
