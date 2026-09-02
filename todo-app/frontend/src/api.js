const BASE_URL = "https://dev-tpob.onrender.com";

export function login(username, password) {
  return fetch(`${BASE_URL}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
}

export function register(username, email, password) {
  return fetch(`${BASE_URL}/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, email, password }),
  });
}

export function motDePasseOublie(email) {
  return fetch(`${BASE_URL}/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
}

export function reinitialiserMotDePasse(token, password) {
  return fetch(`${BASE_URL}/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, password }),
  });
}

export function getTaches(token) {
  return fetch(`${BASE_URL}/taches`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function creerTache(token, titre, dateEcheance) {
  return fetch(`${BASE_URL}/taches`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ titre, date_echeance: dateEcheance }),
  });
}

export function basculerTache(token, id) {
  return fetch(`${BASE_URL}/taches/${id}`, {
    method: "PUT",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function supprimerTache(token, id) {
  return fetch(`${BASE_URL}/taches/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function getVapidPublicKey() {
  return fetch(`${BASE_URL}/vapid-public-key`).then((r) => r.json());
}

export function pushSubscribe(token, subscription) {
  return fetch(`${BASE_URL}/push-subscribe`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(subscription),
  });
}

export function pushUnsubscribe(token, endpoint) {
  return fetch(`${BASE_URL}/push-unsubscribe`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ endpoint }),
  });
}

export function envoyerMessageAssistant(token, message, historique) {
  return fetch(`${BASE_URL}/assistant`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ message, historique }),
  });
}
