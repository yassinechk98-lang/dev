import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getTaches, creerTache, basculerTache, supprimerTache } from '../api';

function estEnRetard(tache) {
  if (!tache.date_echeance || tache.terminee) return false;
  const aujourdhui = new Date().toISOString().slice(0, 10);
  return tache.date_echeance < aujourdhui;
}

function formaterDate(dateIso) {
  const [annee, mois, jour] = dateIso.split("-");
  return `${jour}/${mois}/${annee}`;
}

function TodosPage({ token, setToken }) {
  const [taches, setTaches] = useState([]);
  const [nouveauTitre, setNouveauTitre] = useState("");
  const [nouvelleDate, setNouvelleDate] = useState("");
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

    creerTache(token, nouveauTitre, nouvelleDate)
      .then((reponse) => reponse.json())
      .then((tache) => {
        setTaches([...taches, tache]);
        setNouveauTitre("");
        setNouvelleDate("");
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
        <input
          type="date"
          className="champ-date"
          value={nouvelleDate}
          onChange={(e) => setNouvelleDate(e.target.value)}
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
                {tache.date_echeance && (
                  <span className={`date-echeance${estEnRetard(tache) ? " en-retard" : ""}`}>
                    {" "}
                    {formaterDate(tache.date_echeance)}
                  </span>
                )}
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
