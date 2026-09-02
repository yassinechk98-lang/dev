import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Container, AppBar, Toolbar, Typography, IconButton, Tooltip,
  Stack, Card, CardContent, Skeleton,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import LocalFireDepartmentIcon from '@mui/icons-material/LocalFireDepartment';
import { getStats } from '../api';

function derniers14Jours() {
  const jours = [];
  for (let i = 13; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    jours.push(d.toISOString().slice(0, 10));
  }
  return jours;
}

function StatsPage() {
  const [stats, setStats] = useState(null);
  const navigate = useNavigate();
  const token = localStorage.getItem('token');

  useEffect(() => {
    getStats(token)
      .then((reponse) => reponse.json())
      .then(setStats);
  }, [token]);

  const jours = derniers14Jours();
  const parJourMap = Object.fromEntries((stats?.par_jour || []).map((j) => [j.date, j.total]));
  const max = Math.max(1, ...jours.map((j) => parJourMap[j] || 0));

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      <AppBar position="static" color="primary" elevation={0}>
        <Toolbar>
          <IconButton color="inherit" onClick={() => navigate('/taches')} sx={{ mr: 1.5 }}>
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h6" fontWeight={700}>
            Statistiques
          </Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="sm" sx={{ py: 4 }}>
        {!stats ? (
          <Stack spacing={2}>
            <Skeleton variant="rounded" height={100} />
            <Skeleton variant="rounded" height={220} />
          </Stack>
        ) : (
          <Stack spacing={2}>
            <Stack direction="row" spacing={2}>
              <Card elevation={0} sx={{ flex: 1, border: 1, borderColor: 'divider' }}>
                <CardContent sx={{ textAlign: 'center' }}>
                  <Stack direction="row" spacing={0.5} justifyContent="center" alignItems="center">
                    <LocalFireDepartmentIcon color={stats.serie_en_cours > 0 ? 'warning' : 'disabled'} />
                    <Typography variant="h4" fontWeight={700}>{stats.serie_en_cours}</Typography>
                  </Stack>
                  <Typography variant="body2" color="text.secondary">
                    jour{stats.serie_en_cours !== 1 ? 's' : ''} de suite
                  </Typography>
                </CardContent>
              </Card>
              <Card elevation={0} sx={{ flex: 1, border: 1, borderColor: 'divider' }}>
                <CardContent sx={{ textAlign: 'center' }}>
                  <Typography variant="h4" fontWeight={700}>{stats.taches_actives}</Typography>
                  <Typography variant="body2" color="text.secondary">taches actives</Typography>
                </CardContent>
              </Card>
              <Card elevation={0} sx={{ flex: 1, border: 1, borderColor: 'divider' }}>
                <CardContent sx={{ textAlign: 'center' }}>
                  <Typography variant="h4" fontWeight={700}>{stats.taches_terminees}</Typography>
                  <Typography variant="body2" color="text.secondary">terminees au total</Typography>
                </CardContent>
              </Card>
            </Stack>

            <Card elevation={0} sx={{ border: 1, borderColor: 'divider' }}>
              <CardContent>
                <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>
                  Taches terminees — 14 derniers jours
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'flex-end', gap: 0.75, height: 160 }}>
                  {jours.map((jour) => {
                    const total = parJourMap[jour] || 0;
                    const date = new Date(jour + 'T00:00:00');
                    return (
                      <Tooltip key={jour} title={`${date.toLocaleDateString('fr-FR')} : ${total}`}>
                        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%', justifyContent: 'flex-end' }}>
                          <Box
                            sx={{
                              width: '100%',
                              height: `${Math.max(4, (total / max) * 100)}%`,
                              bgcolor: total > 0 ? 'primary.main' : 'action.hover',
                              borderRadius: 1,
                              transition: 'height 0.2s',
                            }}
                          />
                          <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, fontSize: '0.65rem' }}>
                            {date.toLocaleDateString('fr-FR', { weekday: 'narrow' })}
                          </Typography>
                        </Box>
                      </Tooltip>
                    );
                  })}
                </Box>
              </CardContent>
            </Card>
          </Stack>
        )}
      </Container>
    </Box>
  );
}

export default StatsPage;
