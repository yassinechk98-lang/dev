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
    <div className="carte">
      <div className="entete-taches">
        <h1>Ma Todo-list</h1>
        <button className="bouton-deconnexion" onClick={deconnexion}>
          Deconnexion
        </button>
      </div>

      {erreur && <p className="message-erreur">{erreur}</p>}

      <div className="ajout-tache">
        <input
          type="text"
          value={nouveauTitre}
          onChange={(e) => setNouveauTitre(e.target.value)}
          placeholder="Nouvelle tache"
          onKeyDown={(e) => e.key === "Enter" && ajouterTache()}
        />
        <button onClick={ajouterTache}>Ajouter</button>
      </div>

      {chargement ? (
        <div className="chargement">
          <div className="spinner"></div>
          <p>Chargement des taches...</p>
        </div>
      ) : (
        <ul>
          {taches.map((tache) => (
            <li key={tache.id}>
              <span className="texte-tache" onClick={() => basculer(tache.id)}>
                {tache.titre}{" "}
                <span className="emoji">{tache.terminee ? "✅" : "❌"}</span>
              </span>
              <button className="bouton-supprimer" onClick={() => supprimer(tache.id)}>
                Supprimer
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default TodosPage;
