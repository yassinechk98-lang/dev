import { useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { Typography, TextField, Button, Alert, Link, Stack, InputAdornment } from '@mui/material';
import ChecklistIcon from '@mui/icons-material/Checklist';
import { login } from '../api';
import AuthLayout from '../AuthLayout';

function LoginPage({ setToken, mode, basculerMode }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [erreur, setErreur] = useState(null);
  const [chargement, setChargement] = useState(false);
  const navigate = useNavigate();

  const seConnecter = () => {
    setErreur(null);
    setChargement(true);
    login(username, password)
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
        <ChecklistIcon color="primary" sx={{ fontSize: 40 }} />
        <Typography variant="h5" fontWeight={700}>Bon retour</Typography>
        <Typography variant="body2" color="text.secondary">Connecte-toi a ta Todo-list</Typography>
      </Stack>

      {erreur && <Alert severity="error" sx={{ mb: 2 }}>{erreur}</Alert>}

      <Stack spacing={2}>
        <TextField
          label="Nom d'utilisateur"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          fullWidth
          autoFocus
          onKeyDown={(e) => e.key === "Enter" && seConnecter()}
        />
        <TextField
          label="Mot de passe"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          fullWidth
          onKeyDown={(e) => e.key === "Enter" && seConnecter()}
        />
        <Button
          variant="contained"
          size="large"
          onClick={seConnecter}
          loading={chargement}
          disabled={!username || !password}
        >
          Se connecter
        </Button>
      </Stack>

      <Stack spacing={1} sx={{ mt: 3 }} alignItems="center">
        <Link component={RouterLink} to="/forgot-password" variant="body2">
          Mot de passe oublie ?
        </Link>
        <Typography variant="body2" color="text.secondary">
          Pas encore de compte ?{' '}
          <Link component={RouterLink} to="/register" fontWeight={600}>
            Creer un compte
          </Link>
        </Typography>
      </Stack>
    </AuthLayout>
  );
}

export default LoginPage;
