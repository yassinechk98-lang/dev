import { useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { Typography, TextField, Button, Alert, Link, Stack } from '@mui/material';
import MailLockIcon from '@mui/icons-material/MailLock';
import { motDePasseOublie } from '../api';
import AuthLayout from '../AuthLayout';

function ForgotPasswordPage({ mode, basculerMode }) {
  const [email, setEmail] = useState("");
  const [envoye, setEnvoye] = useState(false);
  const [chargement, setChargement] = useState(false);

  const envoyer = () => {
    setChargement(true);
    motDePasseOublie(email)
      .then(() => setEnvoye(true))
      .finally(() => setChargement(false));
  };

  return (
    <AuthLayout mode={mode} basculerMode={basculerMode}>
      <Stack spacing={0.5} alignItems="center" sx={{ mb: 3 }}>
        <MailLockIcon color="primary" sx={{ fontSize: 40 }} />
        <Typography variant="h5" fontWeight={700}>Mot de passe oublie</Typography>
      </Stack>

      {envoye ? (
        <Alert severity="success">
          Si ce compte existe, un email de reinitialisation a ete envoye. Verifie ta boite mail (et les spams).
        </Alert>
      ) : (
        <Stack spacing={2}>
          <TextField
            label="Ton email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            fullWidth
            autoFocus
            onKeyDown={(e) => e.key === "Enter" && envoyer()}
          />
          <Button variant="contained" size="large" onClick={envoyer} loading={chargement} disabled={!email}>
            Envoyer le lien
          </Button>
        </Stack>
      )}

      <Stack sx={{ mt: 3 }} alignItems="center">
        <Link component={RouterLink} to="/login" variant="body2">
          Retour a la connexion
        </Link>
      </Stack>
    </AuthLayout>
  );
}

export default ForgotPasswordPage;
