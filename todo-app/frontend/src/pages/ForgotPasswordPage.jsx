import { useState } from 'react';
import { Link } from 'react-router-dom';
import { motDePasseOublie } from '../api';

function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState(null);

  const envoyer = () => {
    motDePasseOublie(email).then(() => {
      setMessage("Si ce compte existe, un email de reinitialisation a ete envoye. Verifie ta boite mail (et les spams).");
    });
  };

  return (
    <div className="carte">
      <h1>Mot de passe oublie</h1>

      {message ? (
        <p>{message}</p>
      ) : (
        <>
          <input
            type="text"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Ton email"
          />
          <button onClick={envoyer}>Envoyer le lien de reinitialisation</button>
        </>
      )}

      <p className="lien">
        <Link to="/login">Retour a la connexion</Link>
      </p>
    </div>
  );
}

export default ForgotPasswordPage;
