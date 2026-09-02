import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Container, AppBar, Toolbar, Typography, IconButton, TextField, Button,
  Stack, Card, CardContent, List, ListItem, ListItemText, ListItemButton,
  ListItemIcon, Divider, Skeleton, Snackbar, Alert,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutlineOutlined';
import VisibilityIcon from '@mui/icons-material/Visibility';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import { creerPartage, getPartages, supprimerPartage } from '../api';

function PartagesPage() {
  const [partages, setPartages] = useState(null);
  const [username, setUsername] = useState('');
  const [erreur, setErreur] = useState(null);
  const [notification, setNotification] = useState(null);
  const navigate = useNavigate();
  const token = localStorage.getItem('token');

  const rafraichir = () => {
    getPartages(token).then((r) => r.json()).then(setPartages);
  };

  useEffect(rafraichir, [token]);

  const partager = () => {
    if (!username.trim()) return;
    setErreur(null);
    creerPartage(token, username.trim())
      .then(async (reponse) => {
        if (!reponse.ok) {
          const donnees = await reponse.json();
          throw new Error(donnees.erreur);
        }
        setUsername('');
        setNotification('Liste partagee');
        rafraichir();
      })
      .catch((e) => setErreur(e.message));
  };

  const revoquer = (id) => {
    supprimerPartage(token, id).then(() => {
      setNotification('Partage retire');
      rafraichir();
    });
  };

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      <AppBar position="static" color="primary" elevation={0}>
        <Toolbar>
          <IconButton color="inherit" onClick={() => navigate('/taches')} sx={{ mr: 1.5 }}>
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h6" fontWeight={700}>
            Partage de liste
          </Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="sm" sx={{ py: 4 }}>
        <Card elevation={0} sx={{ mb: 3, border: 1, borderColor: 'divider' }}>
          <CardContent>
            <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1.5 }}>
              Partager ma liste (lecture seule)
            </Typography>
            {erreur && <Alert severity="error" sx={{ mb: 1.5 }}>{erreur}</Alert>}
            <Stack direction="row" spacing={1}>
              <TextField
                label="Nom d'utilisateur"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && partager()}
                size="small"
                fullWidth
              />
              <Button variant="contained" onClick={partager} startIcon={<PersonAddIcon />} sx={{ whiteSpace: 'nowrap' }}>
                Partager
              </Button>
            </Stack>
          </CardContent>
        </Card>

        {!partages ? (
          <Skeleton variant="rounded" height={200} />
        ) : (
          <Stack spacing={3}>
            <Card elevation={0} sx={{ border: 1, borderColor: 'divider' }}>
              <CardContent>
                <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>
                  Ma liste est visible par
                </Typography>
                {partages.mes_partages.length === 0 ? (
                  <Typography color="text.secondary" variant="body2">Personne pour l'instant</Typography>
                ) : (
                  <List dense>
                    {partages.mes_partages.map((p) => (
                      <ListItem
                        key={p.id}
                        secondaryAction={
                          <IconButton edge="end" onClick={() => revoquer(p.id)}>
                            <DeleteOutlineIcon />
                          </IconButton>
                        }
                      >
                        <ListItemText primary={p.username} />
                      </ListItem>
                    ))}
                  </List>
                )}
              </CardContent>
            </Card>

            <Card elevation={0} sx={{ border: 1, borderColor: 'divider' }}>
              <CardContent>
                <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>
                  Listes partagees avec moi
                </Typography>
                {partages.partages_avec_moi.length === 0 ? (
                  <Typography color="text.secondary" variant="body2">Aucune pour l'instant</Typography>
                ) : (
                  <List dense>
                    {partages.partages_avec_moi.map((p) => (
                      <ListItemButton key={p.id} onClick={() => navigate(`/partages/${p.proprietaire_id}`)}>
                        <ListItemIcon><VisibilityIcon fontSize="small" /></ListItemIcon>
                        <ListItemText primary={p.username} />
                      </ListItemButton>
                    ))}
                  </List>
                )}
              </CardContent>
            </Card>
          </Stack>
        )}
      </Container>

      <Snackbar
        open={!!notification}
        autoHideDuration={2500}
        onClose={() => setNotification(null)}
        message={notification}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      />
    </Box>
  );
}

export default PartagesPage;
