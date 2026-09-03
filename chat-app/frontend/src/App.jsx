import { useState, useEffect, useRef, useMemo } from 'react';
import { io } from 'socket.io-client';
import {
  ThemeProvider, CssBaseline, Box, Typography, IconButton, Tooltip, TextField,
  Avatar, Fade, CircularProgress, List, ListItemButton, ListItemIcon, ListItemText,
  AvatarGroup,
} from '@mui/material';
import TagIcon from '@mui/icons-material/Tag';
import SendIcon from '@mui/icons-material/Send';
import LightModeIcon from '@mui/icons-material/LightMode';
import DarkModeIcon from '@mui/icons-material/DarkMode';
import ForumIcon from '@mui/icons-material/Forum';
import CircleIcon from '@mui/icons-material/Circle';
import { creerTheme } from './theme';

const COULEURS = ['#6750A4', '#386A20', '#984061', '#006A6A', '#8B5000', '#31538A'];

function couleurPour(pseudo) {
  let somme = 0;
  for (const c of pseudo) somme += c.charCodeAt(0);
  return COULEURS[somme % COULEURS.length];
}

function formaterHeure(iso) {
  return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}

function jouerSonNotification() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.value = 740;
    gain.gain.setValueAtTime(0.12, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.25);
  } catch {
    // audio non disponible, tant pis
  }
}

function App() {
  const [mode, setMode] = useState(() => localStorage.getItem('chat-theme') || 'light');
  const [pseudo, setPseudo] = useState(() => localStorage.getItem('chat-pseudo') || 'Anonyme');
  const [texte, setTexte] = useState('');
  const [messages, setMessages] = useState([]);
  const [charge, setCharge] = useState(false);
  const [enLigne, setEnLigne] = useState([]);
  const [quiEcrit, setQuiEcrit] = useState({});

  const socketRef = useRef(null);
  const finRef = useRef(null);
  const inputRef = useRef(null);
  const pseudoRef = useRef(pseudo);
  const enTrainDecrireRef = useRef(false);
  const timeoutFrappeRef = useRef(null);

  const theme = useMemo(() => creerTheme(mode), [mode]);

  useEffect(() => {
    pseudoRef.current = pseudo;
  }, [pseudo]);

  useEffect(() => {
    const socket = io('http://127.0.0.1:5050');
    socketRef.current = socket;

    socket.on('connect', () => {
      socket.emit('entrer_salon', { pseudo: pseudoRef.current });
    });

    socket.on('historique', (anciens) => {
      setMessages(anciens);
      setCharge(true);
    });

    socket.on('nouveau_message', (message) => {
      setMessages((precedents) => [...precedents, message]);
      if (message.pseudo !== pseudoRef.current) jouerSonNotification();
    });

    socket.on('utilisateurs_en_ligne', (liste) => setEnLigne(liste));

    socket.on('quelquun_ecrit', ({ pseudo: p }) => {
      setQuiEcrit((prev) => ({ ...prev, [p]: Date.now() }));
    });

    socket.on('plus_personne_ecrit', ({ pseudo: p }) => {
      setQuiEcrit((prev) => {
        const copie = { ...prev };
        delete copie[p];
        return copie;
      });
    });

    return () => socket.disconnect();
  }, []);

  // nettoie les indicateurs de frappe restes bloques (securite si l'evenement d'arret est rate)
  useEffect(() => {
    const interval = setInterval(() => {
      setQuiEcrit((prev) => {
        const maintenant = Date.now();
        const copie = {};
        for (const [p, t] of Object.entries(prev)) {
          if (maintenant - t < 3000) copie[p] = t;
        }
        return copie;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    localStorage.setItem('chat-pseudo', pseudo);
    socketRef.current?.emit('entrer_salon', { pseudo });
  }, [pseudo]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const basculerMode = () => {
    setMode((m) => {
      const nouveau = m === 'light' ? 'dark' : 'light';
      localStorage.setItem('chat-theme', nouveau);
      return nouveau;
    });
  };

  const gererFrappe = (valeur) => {
    setTexte(valeur);
    if (!enTrainDecrireRef.current) {
      enTrainDecrireRef.current = true;
      socketRef.current.emit('en_train_ecrire', { pseudo });
    }
    clearTimeout(timeoutFrappeRef.current);
    timeoutFrappeRef.current = setTimeout(() => {
      enTrainDecrireRef.current = false;
      socketRef.current.emit('arrete_ecrire', { pseudo });
    }, 1500);
  };

  const envoyer = () => {
    if (!texte.trim()) return;
    socketRef.current.emit('message_envoye', { pseudo: pseudo || 'Anonyme', texte: texte.trim() });
    setTexte('');
    clearTimeout(timeoutFrappeRef.current);
    enTrainDecrireRef.current = false;
    socketRef.current.emit('arrete_ecrire', { pseudo });
  };

  // Regroupe les messages consecutifs du meme pseudo, comme Discord
  const groupes = [];
  for (const m of messages) {
    const dernier = groupes[groupes.length - 1];
    if (dernier && dernier.pseudo === m.pseudo) {
      dernier.items.push(m);
    } else {
      groupes.push({ pseudo: m.pseudo, items: [m] });
    }
  }

  const autresQuiEcrivent = Object.keys(quiEcrit).filter((p) => p !== pseudo);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ height: '100vh', display: 'flex', bgcolor: 'background.default' }}>
        {/* Barre laterale des salons */}
        <Box
          sx={{
            width: 260,
            flexShrink: 0,
            bgcolor: mode === 'light' ? 'grey.100' : 'grey.900',
            borderRight: 1,
            borderColor: 'divider',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, py: 2 }}>
            <ForumIcon color="primary" />
            <Typography variant="h6" fontWeight={700}>Chat</Typography>
          </Box>
          <List sx={{ px: 1 }}>
            <ListItemButton selected sx={{ borderRadius: 2 }}>
              <ListItemIcon sx={{ minWidth: 32 }}><TagIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="Général" />
            </ListItemButton>
          </List>

          <Box sx={{ px: 2, pt: 2, pb: 1 }}>
            <Typography variant="caption" color="text.secondary" fontWeight={700}>
              EN LIGNE — {enLigne.length}
            </Typography>
          </Box>
          <List sx={{ px: 1, flexGrow: 1, overflowY: 'auto' }}>
            {enLigne.map((p) => (
              <Box key={p} sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 1, py: 0.5 }}>
                <Avatar sx={{ width: 24, height: 24, fontSize: 12, bgcolor: couleurPour(p) }}>
                  {p.slice(0, 1).toUpperCase()}
                </Avatar>
                <Typography variant="body2" noWrap sx={{ flexGrow: 1 }}>{p}</Typography>
                <CircleIcon sx={{ fontSize: 8, color: 'success.main' }} />
              </Box>
            ))}
          </List>

          <Box sx={{ px: 2, py: 1.5, borderTop: 1, borderColor: 'divider', display: 'flex', alignItems: 'center', gap: 1 }}>
            <Avatar sx={{ width: 30, height: 30, fontSize: 14, bgcolor: couleurPour(pseudo || 'A') }}>
              {(pseudo || 'A').slice(0, 1).toUpperCase()}
            </Avatar>
            <TextField
              value={pseudo}
              onChange={(e) => setPseudo(e.target.value)}
              size="small"
              variant="standard"
              placeholder="Ton pseudo"
              sx={{ flexGrow: 1 }}
              slotProps={{ input: { disableUnderline: true } }}
            />
            <Tooltip title={mode === 'light' ? 'Mode sombre' : 'Mode clair'}>
              <IconButton size="small" onClick={basculerMode}>
                {mode === 'light' ? <DarkModeIcon fontSize="small" /> : <LightModeIcon fontSize="small" />}
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {/* Zone de chat */}
        <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <Box sx={{ px: 2, py: 1.5, borderBottom: 1, borderColor: 'divider', display: 'flex', alignItems: 'center', gap: 1 }}>
            <TagIcon color="action" />
            <Typography variant="subtitle1" fontWeight={700}>Général</Typography>
            {enLigne.length > 0 && (
              <AvatarGroup max={5} sx={{ ml: 'auto', '& .MuiAvatar-root': { width: 24, height: 24, fontSize: 11 } }}>
                {enLigne.map((p) => (
                  <Avatar key={p} sx={{ bgcolor: couleurPour(p) }}>{p.slice(0, 1).toUpperCase()}</Avatar>
                ))}
              </AvatarGroup>
            )}
          </Box>

          <Box sx={{ flexGrow: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', px: 2, py: 1.5, gap: 1.5 }}>
            {!charge ? (
              <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <CircularProgress size={28} />
              </Box>
            ) : groupes.length === 0 ? (
              <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Typography color="text.secondary">Aucun message pour l'instant — lance la discussion !</Typography>
              </Box>
            ) : (
              groupes.map((g, i) => (
                <Fade in key={i}>
                  <Box sx={{ display: 'flex', gap: 1.5 }}>
                    <Avatar sx={{ width: 36, height: 36, fontSize: 14, bgcolor: couleurPour(g.pseudo), mt: 0.5 }}>
                      {g.pseudo.slice(0, 1).toUpperCase()}
                    </Avatar>
                    <Box sx={{ minWidth: 0 }}>
                      <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
                        <Typography variant="subtitle2" fontWeight={700}>{g.pseudo}</Typography>
                        {g.items[0].envoye_le && (
                          <Typography variant="caption" color="text.disabled">
                            {formaterHeure(g.items[0].envoye_le)}
                          </Typography>
                        )}
                      </Box>
                      {g.items.map((item, j) => (
                        <Tooltip
                          key={j}
                          title={item.envoye_le ? formaterHeure(item.envoye_le) : ''}
                          placement="left"
                          arrow
                        >
                          <Typography variant="body2" sx={{ wordBreak: 'break-word', lineHeight: 1.6, width: 'fit-content' }}>
                            {item.texte}
                          </Typography>
                        </Tooltip>
                      ))}
                    </Box>
                  </Box>
                </Fade>
              ))
            )}
            <div ref={finRef} />
          </Box>

          <Box sx={{ px: 2, height: 22 }}>
            <Fade in={autresQuiEcrivent.length > 0}>
              <Typography variant="caption" color="text.secondary" fontStyle="italic">
                {autresQuiEcrivent.join(', ')} {autresQuiEcrivent.length > 1 ? 'sont' : 'est'} en train d'écrire...
              </Typography>
            </Fade>
          </Box>

          <Box sx={{ px: 2, pb: 2, pt: 0.5 }}>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                bgcolor: mode === 'light' ? 'grey.100' : 'grey.900',
                borderRadius: 3,
                px: 1.5,
              }}
            >
              <TextField
                fullWidth
                variant="standard"
                placeholder="Envoyer un message dans #Général"
                value={texte}
                onChange={(e) => gererFrappe(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && envoyer()}
                slotProps={{ input: { disableUnderline: true } }}
                inputRef={inputRef}
                sx={{ py: 1 }}
              />
              <IconButton color="primary" onClick={envoyer} disabled={!texte.trim()}>
                <SendIcon />
              </IconButton>
            </Box>
          </Box>
        </Box>
      </Box>
    </ThemeProvider>
  );
}

export default App;
