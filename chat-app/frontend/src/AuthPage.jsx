import { useState } from 'react';
import {
  Box, Card, CardContent, Typography, TextField, Button, Stack, Alert, Link,
} from '@mui/material';
import ForumIcon from '@mui/icons-material/Forum';
import { inscrire, connecter, motDePasseOublie } from './api';

function AuthPage({ onConnecte }) {
  const [mode, setMode] = useState('login'); // login | register | oublie
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [erreur, setErreur] = useState(null);
  const [message, setMessage] = useState(null);
  const [enCours, setEnCours] = useState(false);

  const soumettre = async () => {
    setErreur(null);
    setMessage(null);
    setEnCours(true);
    try {
      if (mode === 'oublie') {
        const reponse = await motDePasseOublie(email);
        const donnees = await reponse.json();
        setMessage(donnees.message);
        return;
      }
      const reponse = mode === 'login' ? await connecter(username, password) : await inscrire(username, email, password);
      const donnees = await reponse.json();
      if (!reponse.ok) {
        setErreur(donnees.erreur || 'Erreur');
        return;
      }
      onConnecte(donnees.token, donnees.username);
    } catch {
      setErreur('Impossible de contacter le serveur');
    } finally {
      setEnCours(false);
    }
  };

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: 'grey.100' }}>
      <Card elevation={0} sx={{ width: 360, border: 1, borderColor: 'divider' }}>
        <CardContent sx={{ p: 3 }}>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
            <ForumIcon color="primary" />
            <Typography variant="h6" fontWeight={700}>
              {mode === 'login' ? 'Connexion' : mode === 'register' ? 'Inscription' : 'Mot de passe oublie'}
            </Typography>
          </Stack>

          {erreur && <Alert severity="error" sx={{ mb: 2 }}>{erreur}</Alert>}
          {message && <Alert severity="success" sx={{ mb: 2 }}>{message}</Alert>}

          <Stack spacing={2}>
            {mode !== 'oublie' && (
              <TextField
                label="Nom d'utilisateur"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                size="small"
                fullWidth
              />
            )}
            {(mode === 'register' || mode === 'oublie') && (
              <TextField
                label="Email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                size="small"
                fullWidth
              />
            )}
            {mode !== 'oublie' && (
              <TextField
                label="Mot de passe"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && soumettre()}
                size="small"
                fullWidth
              />
            )}

            <Button variant="contained" onClick={soumettre} disabled={enCours}>
              {mode === 'login' ? 'Se connecter' : mode === 'register' ? "S'inscrire" : 'Envoyer le lien'}
            </Button>

            {mode === 'login' && (
              <Stack direction="row" justifyContent="space-between">
                <Link component="button" variant="body2" onClick={() => setMode('register')}>
                  Creer un compte
                </Link>
                <Link component="button" variant="body2" onClick={() => setMode('oublie')}>
                  Mot de passe oublie ?
                </Link>
              </Stack>
            )}
            {mode !== 'login' && (
              <Link component="button" variant="body2" onClick={() => setMode('login')}>
                Retour a la connexion
              </Link>
            )}
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
}

export default AuthPage;
