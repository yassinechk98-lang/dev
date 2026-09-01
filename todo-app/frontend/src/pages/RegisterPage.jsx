import { useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { Typography, TextField, Button, Alert, Link, Stack } from '@mui/material';
import PersonAddAlt1Icon from '@mui/icons-material/PersonAddAlt1';
import { register } from '../api';
import AuthLayout from '../AuthLayout';

function RegisterPage({ setToken, mode, basculerMode }) {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [erreur, setErreur] = useState(null);
  const [chargement, setChargement] = useState(false);
  const navigate = useNavigate();

  const creerCompte = () => {
    setErreur(null);
    setChargement(true);
    register(username, email, password)
      .then(async (reponse) => {
        const donnees = await reponse.json();
        if (!reponse.ok) throw new Error(donnees.erreur || "Erreur");
        localStorage.setItem("token", donnees.token);
        setToken(donnees.token);
        navigate("/taches");
      })
      .catch((err) => setErreur(err.message))
      .finally(() => setChargement(false));
  };

  return (
    <AuthLayout mode={mode} basculerMode={basculerMode}>
      <Stack spacing={0.5} alignItems="center" sx={{ mb: 3 }}>
        <PersonAddAlt1Icon color="primary" sx={{ fontSize: 40 }} />
        <Typography variant="h5" fontWeight={700}>Creer un compte</Typography>
        <Typography variant="body2" color="text.secondary">Rejoins ta Todo-list en quelques secondes</Typography>
      </Stack>

      {erreur && <Alert severity="error" sx={{ mb: 2 }}>{erreur}</Alert>}

      <Stack spacing={2}>
        <TextField
          label="Nom d'utilisateur"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          fullWidth
          autoFocus
        />
        <TextField
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          fullWidth
        />
        <TextField
          label="Mot de passe"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          fullWidth
          onKeyDown={(e) => e.key === "Enter" && creerCompte()}
        />
        <Button
          variant="contained"
          size="large"
          onClick={creerCompte}
          loading={chargement}
          disabled={!username || !email || !password}
        >
          Creer le compte
        </Button>
      </Stack>

      <Stack sx={{ mt: 3 }} alignItems="center">
        <Typography variant="body2" color="text.secondary">
          Deja un compte ?{' '}
          <Link component={RouterLink} to="/login" fontWeight={600}>
            Se connecter
          </Link>
        </Typography>
      </Stack>
    </AuthLayout>
  );
}

export default RegisterPage;
