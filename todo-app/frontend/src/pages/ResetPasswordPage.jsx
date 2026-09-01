import { useState } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { reinitialiserMotDePasse } from '../api';

function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [password, setPassword] = useState("");
  const [erreur, setErreur] = useState(null);
  const [succes, setSucces] = useState(false);
  const navigate = useNavigate();

  const valider = () => {
    setErreur(null);
    reinitialiserMotDePasse(token, password)
      .then(async (reponse) => {
        const donnees = await reponse.json();
        if (!reponse.ok) throw new Error(donnees.erreur || "Erreur");
        setSucces(true);
        setTimeout(() => navigate("/login"), 2000);
      })
      .catch((err) => setErreur(err.message));
  };

  if (!token) {
    return (
      <div className="carte">
        <h1>Lien invalide</h1>
        <p className="lien">
          <Link to="/forgot-password">Redemander un lien</Link>
        </p>
      </div>
    );
  }

  return (
    <div className="carte">
      <h1>Nouveau mot de passe</h1>

      {erreur && <p className="message-erreur">{erreur}</p>}

      {succes ? (
        <p>Mot de passe mis a jour ! Redirection vers la connexion...</p>
      ) : (
        <>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Nouveau mot de passe"
          />
          <button onClick={valider}>Valider</button>
        </>
      )}
    </div>
  );
}

export default ResetPasswordPage;
