import { useState } from 'react';
import { useSearchParams, useNavigate, Link as RouterLink } from 'react-router-dom';
import { Typography, TextField, Button, Alert, Link, Stack } from '@mui/material';
import LockResetIcon from '@mui/icons-material/LockReset';
import { reinitialiserMotDePasse } from '../api';
import AuthLayout from '../AuthLayout';

function ResetPasswordPage({ mode, basculerMode }) {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [password, setPassword] = useState("");
  const [erreur, setErreur] = useState(null);
  const [succes, setSucces] = useState(false);
  const [chargement, setChargement] = useState(false);
  const navigate = useNavigate();

  const valider = () => {
    setErreur(null);
    setChargement(true);
    reinitialiserMotDePasse(token, password)
      .then(async (reponse) => {
        const donnees = await reponse.json();
        if (!reponse.ok) throw new Error(donnees.erreur || "Erreur");
        setSucces(true);
        setTimeout(() => navigate("/login"), 2000);
      })
      .catch((err) => setErreur(err.message))
      .finally(() => setChargement(false));
  };

  if (!token) {
    return (
      <AuthLayout mode={mode} basculerMode={basculerMode}>
        <Typography variant="h5" fontWeight={700} gutterBottom>Lien invalide</Typography>
        <Link component={RouterLink} to="/forgot-password">Redemander un lien</Link>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout mode={mode} basculerMode={basculerMode}>
      <Stack spacing={0.5} alignItems="center" sx={{ mb: 3 }}>
        <LockResetIcon color="primary" sx={{ fontSize: 40 }} />
        <Typography variant="h5" fontWeight={700}>Nouveau mot de passe</Typography>
      </Stack>

      {erreur && <Alert severity="error" sx={{ mb: 2 }}>{erreur}</Alert>}

      {succes ? (
        <Alert severity="success">Mot de passe mis a jour ! Redirection vers la connexion...</Alert>
      ) : (
        <Stack spacing={2}>
          <TextField
            label="Nouveau mot de passe"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            fullWidth
            autoFocus
            onKeyDown={(e) => e.key === "Enter" && valider()}
          />
          <Button variant="contained" size="large" onClick={valider} loading={chargement} disabled={!password}>
            Valider
          </Button>
        </Stack>
      )}
    </AuthLayout>
  );
}

export default ResetPasswordPage;
