import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box, Container, AppBar, Toolbar, Typography, IconButton, Stack, Card,
  CardContent, Checkbox, Chip, Skeleton, Alert,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import EventIcon from '@mui/icons-material/Event';
import ChecklistRtlIcon from '@mui/icons-material/ChecklistRtl';
import { getTachesPartagees } from '../api';

function formaterDate(dateIso) {
  return new Date(dateIso).toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

function SharedListPage() {
  const { proprietaireId } = useParams();
  const [taches, setTaches] = useState(null);
  const [erreur, setErreur] = useState(null);
  const navigate = useNavigate();
  const token = localStorage.getItem('token');

  useEffect(() => {
    getTachesPartagees(token, proprietaireId)
      .then((reponse) => {
        if (reponse.status === 403) throw new Error('acces');
        if (!reponse.ok) throw new Error('serveur');
        return reponse.json();
      })
      .then(setTaches)
      .catch((e) => setErreur(e.message));
  }, [token, proprietaireId]);

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      <AppBar position="static" color="primary" elevation={0}>
        <Toolbar>
          <IconButton color="inherit" onClick={() => navigate('/partages')} sx={{ mr: 1.5 }}>
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h6" fontWeight={700}>
            Liste partagee (lecture seule)
          </Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="sm" sx={{ py: 4 }}>
        {erreur === 'acces' && <Alert severity="error">Cette liste n'est plus partagee avec toi.</Alert>}
        {erreur === 'serveur' && <Alert severity="error">Impossible de charger la liste.</Alert>}

        {!erreur && !taches && (
          <Stack spacing={1.5}>
            {[1, 2, 3].map((i) => <Skeleton key={i} variant="rounded" height={64} />)}
          </Stack>
        )}

        {!erreur && taches && taches.length === 0 && (
          <Box sx={{ textAlign: 'center', py: 6, color: 'text.secondary' }}>
            <ChecklistRtlIcon sx={{ fontSize: 48, opacity: 0.4, mb: 1 }} />
            <Typography>Aucune tache</Typography>
          </Box>
        )}

        {!erreur && taches && taches.length > 0 && (
          <Stack spacing={1.5}>
            {taches.map((tache) => (
              <Card key={tache.id} elevation={0} sx={{ border: 1, borderColor: 'divider' }}>
                <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 1, '&:last-child': { pb: 2 } }}>
                  <Checkbox checked={tache.terminee} disabled />
                  <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                    <Typography
                      sx={{
                        textDecoration: tache.terminee ? 'line-through' : 'none',
                        color: tache.terminee ? 'text.secondary' : 'text.primary',
                      }}
                    >
                      {tache.titre}
                    </Typography>
                    {tache.date_echeance && (
                      <Chip icon={<EventIcon />} label={formaterDate(tache.date_echeance)} size="small" variant="outlined" sx={{ mt: 0.5 }} />
                    )}
                  </Box>
                </CardContent>
              </Card>
            ))}
          </Stack>
        )}
      </Container>
    </Box>
  );
}

export default SharedListPage;
