import { useState, useEffect } from 'react';

const API_URL = "http://localhost:5000/taches";

function App() {
  const [taches, setTaches] = useState([]);
  const [nouveauTitre, setNouveauTitre] = useState("");
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    fetch(API_URL)
      .then((reponse) => {
        if (!reponse.ok) throw new Error("Erreur serveur");
        return reponse.json();
      })
      .then((donnees) => {
        setTaches(donnees);
        setErreur(null);
      })
      .catch(() => setErreur("Impossible de charger les taches. Le serveur tourne-t-il ?"));
  }, []);

  const ajouterTache = () => {
    if (!nouveauTitre.trim()) return;

    fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titre: nouveauTitre }),
    })
      .then((reponse) => reponse.json())
      .then((tache) => {
        setTaches([...taches, tache]);
        setNouveauTitre("");
      });
  };

  const basculerTache = (id) => {
    fetch(`${API_URL}/${id}`, { method: "PUT" })
      .then((reponse) => reponse.json())
      .then((tacheMaj) => {
        setTaches(taches.map((t) => (t.id === id ? tacheMaj : t)));
      });
  };

  const supprimerTache = (id) => {
    fetch(`${API_URL}/${id}`, { method: "DELETE" }).then(() => {
      setTaches(taches.filter((t) => t.id !== id));
    });
  };

  return (
    <div>
      <h1>Ma Todo-list</h1>

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
