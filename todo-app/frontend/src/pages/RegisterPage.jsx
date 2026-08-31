import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { register } from '../api';

function RegisterPage({ setToken }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [erreur, setErreur] = useState(null);
  const navigate = useNavigate();

  const creerCompte = () => {
    setErreur(null);
    register(username, password)
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
    <div>
      <h1>Creer un compte</h1>

      {erreur && <p style={{ color: "red" }}>{erreur}</p>}

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
      <button onClick={creerCompte}>Creer le compte</button>

      <p>
        Deja un compte ? <Link to="/login">Se connecter</Link>
      </p>
    </div>
  );
}

export default RegisterPage;
