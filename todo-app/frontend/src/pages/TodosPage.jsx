import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getTaches, creerTache, basculerTache, supprimerTache } from '../api';

function TodosPage({ token, setToken }) {
  const [taches, setTaches] = useState([]);
  const [nouveauTitre, setNouveauTitre] = useState("");
  const [erreur, setErreur] = useState(null);
  const [chargement, setChargement] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    getTaches(token)
      .then((reponse) => {
        if (!reponse.ok) throw new Error("Erreur serveur");
        return reponse.json();
      })
      .then((donnees) => {
        setTaches(donnees);
        setErreur(null);
      })
      .catch(() => setErreur("Impossible de charger les taches. Le serveur tourne-t-il ?"))
      .finally(() => setChargement(false));
  }, [token]);

  const deconnexion = () => {
    localStorage.removeItem("token");
    setToken(null);
    navigate("/login");
  };

  const ajouterTache = () => {
    if (!nouveauTitre.trim()) return;

    creerTache(token, nouveauTitre)
      .then((reponse) => reponse.json())
      .then((tache) => {
        setTaches([...taches, tache]);
        setNouveauTitre("");
      });
  };

  const basculer = (id) => {
    basculerTache(token, id)
      .then((reponse) => reponse.json())
      .then((tacheMaj) => {
        setTaches(taches.map((t) => (t.id === id ? tacheMaj : t)));
      });
  };

  const supprimer = (id) => {
    supprimerTache(token, id).then(() => {
      setTaches(taches.filter((t) => t.id !== id));
    });
  };

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

      {chargement ? (
        <p>Chargement des taches...</p>
      ) : (
        <ul>
          {taches.map((tache) => (
            <li key={tache.id}>
              <span onClick={() => basculer(tache.id)} style={{ cursor: "pointer" }}>
                {tache.titre} {tache.terminee ? "✅" : "❌"}
              </span>
              <button onClick={() => supprimer(tache.id)}>Supprimer</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default TodosPage;
