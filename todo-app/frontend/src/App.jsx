import { useState, useEffect } from 'react';

const BASE_URL = "https://dev-tpob.onrender.com";

function App() {
  const [token, setToken] = useState(localStorage.getItem("token"));
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [authErreur, setAuthErreur] = useState(null);

  const [taches, setTaches] = useState([]);
  const [nouveauTitre, setNouveauTitre] = useState("");
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    if (!token) return;

    fetch(`${BASE_URL}/taches`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((reponse) => {
        if (!reponse.ok) throw new Error("Erreur serveur");
        return reponse.json();
      })
      .then((donnees) => {
        setTaches(donnees);
        setErreur(null);
      })
      .catch(() => setErreur("Impossible de charger les taches. Le serveur tourne-t-il ?"));
  }, [token]);

  const connexion = (chemin) => {
    setAuthErreur(null);
    fetch(`${BASE_URL}/${chemin}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    })
      .then(async (reponse) => {
        const donnees = await reponse.json();
        if (!reponse.ok) throw new Error(donnees.erreur || "Erreur");
        localStorage.setItem("token", donnees.token);
        setToken(donnees.token);
      })
      .catch((err) => setAuthErreur(err.message));
  };

  const deconnexion = () => {
    localStorage.removeItem("token");
    setToken(null);
    setTaches([]);
  };

  const ajouterTache = () => {
    if (!nouveauTitre.trim()) return;

    fetch(`${BASE_URL}/taches`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ titre: nouveauTitre }),
    })
      .then((reponse) => reponse.json())
      .then((tache) => {
        setTaches([...taches, tache]);
        setNouveauTitre("");
      });
  };

  const basculerTache = (id) => {
    fetch(`${BASE_URL}/taches/${id}`, {
      method: "PUT",
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((reponse) => reponse.json())
      .then((tacheMaj) => {
        setTaches(taches.map((t) => (t.id === id ? tacheMaj : t)));
      });
  };

  const supprimerTache = (id) => {
    fetch(`${BASE_URL}/taches/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    }).then(() => {
      setTaches(taches.filter((t) => t.id !== id));
    });
  };

  if (!token) {
    return (
      <div>
        <h1>Ma Todo-list</h1>

        {authErreur && <p style={{ color: "red" }}>{authErreur}</p>}

        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Nom d'utilisateur"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Mot de passe"
        />
        <div>
          <button onClick={() => connexion("login")}>Se connecter</button>
          <button onClick={() => connexion("register")}>Creer un compte</button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1>Ma Todo-list</h1>

      <button onClick={deconnexion}>Deconnexion</button>

      {erreur && <p style={{ color: "red" }}>{erreur}</p>}

      <input
        type="text"
        value={nouveauTitre}
        onChange={(e) => setNouveauTitre(e.target.value)}
        placeholder="Nouvelle tache"
      />
      <button onClick={ajouterTache}>Ajouter</button>

      <ul>
        {taches.map((tache) => (
          <li key={tache.id}>
            <span onClick={() => basculerTache(tache.id)} style={{ cursor: "pointer" }}>
              {tache.titre} {tache.terminee ? "✅" : "❌"}
            </span>
            <button onClick={() => supprimerTache(tache.id)}>Supprimer</button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default App;
