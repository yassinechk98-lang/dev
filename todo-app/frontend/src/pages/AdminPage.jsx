import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Container, AppBar, Toolbar, Typography, IconButton, Alert,
  Tabs, Tab, Table, TableHead, TableBody, TableRow, TableCell,
  TableContainer, Paper, Skeleton, Chip,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { getAdminTables, getAdminLignes } from '../api';

function AdminPage() {
  const [tables, setTables] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [tableActive, setTableActive] = useState(null);
  const [donnees, setDonnees] = useState(null);
  const navigate = useNavigate();
  const token = localStorage.getItem('token');

  useEffect(() => {
    getAdminTables(token)
      .then((reponse) => {
        if (reponse.status === 403) throw new Error('acces');
        if (!reponse.ok) throw new Error('serveur');
        return reponse.json();
      })
      .then((liste) => {
        setTables(liste);
        setTableActive(liste[0]?.nom || null);
      })
      .catch((e) => setErreur(e.message === 'acces' ? 'acces' : 'serveur'));
  }, [token]);

  useEffect(() => {
    if (!tableActive) return;
    setDonnees(null);
    getAdminLignes(token, tableActive)
      .then((reponse) => reponse.json())
      .then(setDonnees);
  }, [tableActive, token]);

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      <AppBar position="static" color="primary" elevation={0}>
        <Toolbar>
          <IconButton color="inherit" onClick={() => navigate('/taches')} sx={{ mr: 1.5 }}>
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h6" fontWeight={700}>
            Base de donnees
          </Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="md" sx={{ py: 4 }}>
        {erreur === 'acces' && (
          <Alert severity="error">Acces reserve — ce compte n'est pas autorise a voir cette page.</Alert>
        )}
        {erreur === 'serveur' && (
          <Alert severity="error">Impossible de charger les donnees. Le serveur tourne-t-il ?</Alert>
        )}

        {!erreur && !tables && (
          <Skeleton variant="rounded" height={300} />
        )}

        {!erreur && tables && (
          <>
            <Tabs value={tableActive} onChange={(e, v) => setTableActive(v)} sx={{ mb: 2 }}>
              {tables.map((t) => (
                <Tab key={t.nom} value={t.nom} label={`${t.nom} (${t.total})`} />
              ))}
            </Tabs>

            {!donnees ? (
              <Skeleton variant="rounded" height={300} />
            ) : donnees.lignes.length === 0 ? (
              <Typography color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
                Table vide
              </Typography>
            ) : (
              <TableContainer component={Paper} elevation={0} sx={{ border: 1, borderColor: 'divider' }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      {donnees.colonnes.map((c) => (
                        <TableCell key={c} sx={{ fontWeight: 700 }}>{c}</TableCell>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {donnees.lignes.map((ligne, i) => (
                      <TableRow key={i}>
                        {donnees.colonnes.map((c) => (
                          <TableCell key={c}>
                            {typeof ligne[c] === 'boolean' ? (
                              <Chip
                                size="small"
                                label={ligne[c] ? 'oui' : 'non'}
                                color={ligne[c] ? 'success' : 'default'}
                                variant="outlined"
                              />
                            ) : ligne[c] === null ? (
                              <Typography component="span" color="text.disabled">—</Typography>
                            ) : (
                              String(ligne[c])
                            )}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </>
        )}
      </Container>
    </Box>
  );
}

export default AdminPage;
