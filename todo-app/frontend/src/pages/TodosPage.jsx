import { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Container, AppBar, Toolbar, Typography, IconButton, Tooltip,
  TextField, Button, Stack, Card, CardContent, Checkbox, Chip,
  Tabs, Tab, Skeleton, Alert, Snackbar, Fade, Select, MenuItem, FormControl, InputLabel,
} from '@mui/material';
import LightModeIcon from '@mui/icons-material/LightMode';
import DarkModeIcon from '@mui/icons-material/DarkMode';
import LogoutIcon from '@mui/icons-material/Logout';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutlineOutlined';
import EventIcon from '@mui/icons-material/Event';
import ChecklistRtlIcon from '@mui/icons-material/ChecklistRtl';
import RepeatIcon from '@mui/icons-material/Repeat';
import AddIcon from '@mui/icons-material/Add';
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive';
import NotificationsNoneIcon from '@mui/icons-material/NotificationsNone';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import BarChartIcon from '@mui/icons-material/BarChart';
import { getTaches, creerTache, basculerTache, supprimerTache, getVapidPublicKey, pushSubscribe } from '../api';
import AssistantChat from '../AssistantChat';
import SousTaches from '../SousTaches';

function estEnRetard(tache) {
  if (!tache.date_echeance || tache.terminee) return false;
  return new Date(tache.date_echeance) < new Date();
}

function formaterDate(dateIso) {
  const date = new Date(dateIso);
  return date.toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function urlBase64ToUint8Array(base64) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const base64Safe = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const brut = atob(base64Safe);
  return Uint8Array.from([...brut].map((c) => c.charCodeAt(0)));
}

function TodosPage({ token, setToken, mode, basculerMode }) {
  const [taches, setTaches] = useState([]);
  const [nouveauTitre, setNouveauTitre] = useState("");
  const [nouvelleDate, setNouvelleDate] = useState("");
  const [nouvelleRecurrence, setNouvelleRecurrence] = useState("");
  const [erreur, setErreur] = useState(null);
  const [chargement, setChargement] = useState(true);
  const [filtre, setFiltre] = useState("toutes");
  const [aRestaurer, setARestaurer] = useState(null);
  const suppressionTimeoutRef = useRef(null);
  const [notification, setNotification] = useState(null);
  const [notifsActivees, setNotifsActivees] = useState(false);
  const [notifsSupportees, setNotifsSupportees] = useState(true);
  const [assistantOuvert, setAssistantOuvert] = useState(false);
  const navigate = useNavigate();

  const rafraichirTaches = () => {
    getTaches(token)
      .then((reponse) => reponse.json())
      .then((donnees) => setTaches(donnees))
      .catch(() => {});
  };

  useEffect(() => {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      setNotifsSupportees(false);
      return;
    }
    navigator.serviceWorker.ready
      .then((registration) => registration.pushManager.getSubscription())
      .then((subscription) => setNotifsActivees(!!subscription))
      .catch(() => {});
  }, []);

  const activerNotifications = async () => {
    if (Notification.permission === "denied") {
      setNotification("Notifications bloquees dans les reglages du navigateur");
      return;
    }
    const permission = await Notification.requestPermission();
    if (permission !== "granted") return;

    const registration = await navigator.serviceWorker.ready;
    const { publicKey } = await getVapidPublicKey();
    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    });

    await pushSubscribe(token, subscription.toJSON());
    setNotifsActivees(true);
    setNotification("Notifications activees");
  };

  useEffect(() => {
    getTaches(token)
      .then((reponse) => {
        if (!reponse.ok) throw new Error("Erreur serveur");
        return reponse.json();
      })
      .then((donnees) => {
        setTaches(donnees);
        setErreur(null);
      })
      .catch(() => setErreur("Impossible de charger les taches. Le serveur tourne-t-il ?"))
      .finally(() => setChargement(false));
  }, [token]);

  const deconnexion = () => {
    localStorage.removeItem("token");
    setToken(null);
    navigate("/login");
  };

  const ajouterTache = () => {
    if (!nouveauTitre.trim()) return;

    creerTache(token, nouveauTitre, nouvelleDate, nouvelleRecurrence)
      .then((reponse) => reponse.json())
      .then((tache) => {
        setTaches([...taches, tache]);
        setNouveauTitre("");
        setNouvelleDate("");
        setNouvelleRecurrence("");
        setNotification("Tache ajoutee");
      });
  };

  const basculer = (id) => {
    basculerTache(token, id)
      .then((reponse) => reponse.json())
      .then((tacheMaj) => {
        if (tacheMaj.recurrence) {
          rafraichirTaches();
        } else {
          setTaches((prev) => prev.map((t) => (t.id === id ? tacheMaj : t)));
        }
      });
  };

  useEffect(() => {
    return () => clearTimeout(suppressionTimeoutRef.current);
  }, []);

  const supprimerAvecUndo = (tache) => {
    setTaches((prev) => prev.filter((t) => t.id !== tache.id));
    setARestaurer(tache);
    suppressionTimeoutRef.current = setTimeout(() => {
      supprimerTache(token, tache.id);
      setARestaurer(null);
    }, 5000);
  };

  const annulerSuppression = () => {
    clearTimeout(suppressionTimeoutRef.current);
    setTaches((prev) => [...prev, aRestaurer].sort((a, b) => a.id - b.id));
    setARestaurer(null);
  };

  const tachesFiltrees = useMemo(() => {
    if (filtre === "actives") return taches.filter((t) => !t.terminee);
    if (filtre === "terminees") return taches.filter((t) => t.terminee);
    return taches;
  }, [taches, filtre]);

  const nbActives = taches.filter((t) => !t.terminee).length;

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      <AppBar position="static" color="primary" elevation={0}>
        <Toolbar>
          <ChecklistRtlIcon sx={{ mr: 1.5 }} />
          <Typography variant="h6" sx={{ flexGrow: 1 }} fontWeight={700}>
            Ma Todo-list
          </Typography>
          <Tooltip title="Statistiques">
            <IconButton color="inherit" onClick={() => navigate('/stats')}>
              <BarChartIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="Assistant">
            <IconButton color="inherit" onClick={() => setAssistantOuvert(true)}>
              <SmartToyIcon />
            </IconButton>
          </Tooltip>
          {notifsSupportees && (
            <Tooltip title={notifsActivees ? "Rappels actives" : "Activer les rappels"}>
              <span>
                <IconButton color="inherit" onClick={activerNotifications} disabled={notifsActivees}>
                  {notifsActivees ? <NotificationsActiveIcon /> : <NotificationsNoneIcon />}
                </IconButton>
              </span>
            </Tooltip>
          )}
          <Tooltip title={mode === 'light' ? 'Mode sombre' : 'Mode clair'}>
            <IconButton color="inherit" onClick={basculerMode}>
              {mode === 'light' ? <DarkModeIcon /> : <LightModeIcon />}
            </IconButton>
          </Tooltip>
          <Tooltip title="Deconnexion">
            <IconButton color="inherit" onClick={deconnexion}>
              <LogoutIcon />
            </IconButton>
          </Tooltip>
        </Toolbar>
      </AppBar>

      <Container maxWidth="sm" sx={{ py: 4 }}>
        {erreur && <Alert severity="error" sx={{ mb: 3 }}>{erreur}</Alert>}

        <Card elevation={0} sx={{ mb: 3, border: 1, borderColor: 'divider' }}>
          <CardContent>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
              <TextField
                label="Nouvelle tache"
                value={nouveauTitre}
                onChange={(e) => setNouveauTitre(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && ajouterTache()}
                fullWidth
                size="small"
              />
              <TextField
                label="Echeance"
                type="datetime-local"
                value={nouvelleDate}
                onChange={(e) => setNouvelleDate(e.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
                size="small"
                sx={{ minWidth: { sm: 210 } }}
              />
              <FormControl size="small" sx={{ minWidth: { sm: 150 } }}>
                <InputLabel>Repetition</InputLabel>
                <Select
                  label="Repetition"
                  value={nouvelleRecurrence}
                  onChange={(e) => setNouvelleRecurrence(e.target.value)}
                >
                  <MenuItem value="">Aucune</MenuItem>
                  <MenuItem value="quotidien">Quotidienne</MenuItem>
                  <MenuItem value="hebdomadaire">Hebdomadaire</MenuItem>
                </Select>
              </FormControl>
              <Button
                variant="contained"
                onClick={ajouterTache}
                disabled={!nouveauTitre.trim()}
                startIcon={<AddIcon />}
                sx={{ whiteSpace: 'nowrap' }}
              >
                Ajouter
              </Button>
            </Stack>
          </CardContent>
        </Card>

        {!chargement && taches.length > 0 && (
          <Tabs
            value={filtre}
            onChange={(e, v) => setFiltre(v)}
            sx={{ mb: 2 }}
            variant="fullWidth"
          >
            <Tab value="toutes" label={`Toutes (${taches.length})`} />
            <Tab value="actives" label={`A faire (${nbActives})`} />
            <Tab value="terminees" label={`Terminees (${taches.length - nbActives})`} />
          </Tabs>
        )}

        {chargement ? (
          <Stack spacing={1.5}>
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} variant="rounded" height={64} />
            ))}
          </Stack>
        ) : tachesFiltrees.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 6, color: 'text.secondary' }}>
            <ChecklistRtlIcon sx={{ fontSize: 48, opacity: 0.4, mb: 1 }} />
            <Typography>
              {taches.length === 0 ? "Aucune tache pour l'instant" : "Rien ici pour ce filtre"}
            </Typography>
          </Box>
        ) : (
          <Stack spacing={1.5}>
            {tachesFiltrees.map((tache) => (
              <Fade in key={tache.id}>
                <Card elevation={0} sx={{ border: 1, borderColor: 'divider' }}>
                  <CardContent sx={{ '&:last-child': { pb: 2 } }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Checkbox checked={tache.terminee} onChange={() => basculer(tache.id)} />
                      <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                        <Typography
                          sx={{
                            textDecoration: tache.terminee ? 'line-through' : 'none',
                            color: tache.terminee ? 'text.secondary' : 'text.primary',
                            wordBreak: 'break-word',
                          }}
                        >
                          {tache.titre}
                        </Typography>
                        <Stack direction="row" spacing={0.5} sx={{ mt: 0.5, flexWrap: 'wrap' }}>
                          {tache.date_echeance && (
                            <Chip
                              icon={<EventIcon />}
                              label={formaterDate(tache.date_echeance)}
                              size="small"
                              color={estEnRetard(tache) ? "error" : "default"}
                              variant={estEnRetard(tache) ? "filled" : "outlined"}
                            />
                          )}
                          {tache.recurrence && (
                            <Chip
                              icon={<RepeatIcon />}
                              label={tache.recurrence === "hebdomadaire" ? "Chaque semaine" : "Chaque jour"}
                              size="small"
                              variant="outlined"
                            />
                          )}
                        </Stack>
                      </Box>
                      <IconButton color="error" onClick={() => supprimerAvecUndo(tache)}>
                        <DeleteOutlineIcon />
                      </IconButton>
                    </Box>
                    <Box sx={{ pl: 6 }}>
                      <SousTaches token={token} tacheId={tache.id} />
                    </Box>
                  </CardContent>
                </Card>
              </Fade>
            ))}
          </Stack>
        )}
      </Container>

      <Snackbar
        open={!!aRestaurer}
        autoHideDuration={5000}
        onClose={(e, raison) => raison !== 'clickaway' && setARestaurer(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        message="Tache supprimee"
        action={
          <Button color="inherit" size="small" onClick={annulerSuppression}>
            ANNULER
          </Button>
        }
      />

      <Snackbar
        open={!!notification}
        autoHideDuration={2500}
        onClose={() => setNotification(null)}
        message={notification}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      />

      <AssistantChat
        token={token}
        ouvert={assistantOuvert}
        fermer={() => setAssistantOuvert(false)}
        onTachesChangees={rafraichirTaches}
      />
    </Box>
  );
}

export default TodosPage;
