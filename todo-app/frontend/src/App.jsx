import { useState, useEffect } from 'react';

const API_URL = "http://localhost:5000/taches";

function App() {
  const [taches, setTaches] = useState([]);
  const [nouveauTitre, setNouveauTitre] = useState("");

  useEffect(() => {
    fetch(API_URL)
      .then((reponse) => reponse.json())
      .then((donnees) => setTaches(donnees));
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

  const supprimerTache = (id) => {
    fetch(`${API_URL}/${id}`, { method: "DELETE" }).then(() => {
      setTaches(taches.filter((t) => t.id !== id));
    });
  };

  return (
    <div>
      <h1>Ma Todo-list</h1>

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
            {tache.titre} {tache.terminee ? "✅" : "❌"}
            <button onClick={() => supprimerTache(tache.id)}>Supprimer</button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default App;
