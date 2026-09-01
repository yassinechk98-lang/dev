import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { login } from '../api';

function LoginPage({ setToken }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [erreur, setErreur] = useState(null);
  const navigate = useNavigate();

  const seConnecter = () => {
    setErreur(null);
    login(username, password)
      .then(async (reponse) => {
        const donnees = await reponse.json();
        if (!reponse.ok) throw new Error(donnees.erreur || "Erreur");
        localStorage.setItem("token", donnees.token);
        setToken(donnees.token);
        navigate("/taches");
      })
      .catch((err) => setErreur(err.message));
  };

  return (
    <div className="carte">
      <h1>Connexion</h1>

      {erreur && <p className="message-erreur">{erreur}</p>}

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
      <button onClick={seConnecter}>Se connecter</button>

      <p className="lien">
        <Link to="/forgot-password">Mot de passe oublie ?</Link>
      </p>
      <p className="lien">
        Pas encore de compte ? <Link to="/register">Creer un compte</Link>
      </p>
    </div>
  );
}

export default LoginPage;
