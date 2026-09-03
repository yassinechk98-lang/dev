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
import LogoutIcon from '@mui/icons-material/Logout';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { creerTheme } from './theme';
import { SOCKET_URL } from './api';
import AuthPage from './AuthPage';

const COULEURS = ['#6750A4', '#386A20', '#984061', '#006A6A', '#8B5000', '#31538A'];
const SALONS = ['general', 'aleatoire', 'aide'];

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

function ChatApp({ token, pseudo, deconnexion }) {
  const [mode, setMode] = useState(() => localStorage.getItem('chat-theme') || 'light');
  const [salonActif, setSalonActif] = useState('general');
  const [dmActif, setDmActif] = useState(null);
  const [texte, setTexte] = useState('');
  const [messages, setMessages] = useState([]);
  const [messagesPrivees, setMessagesPrivees] = useState([]);
  const [charge, setCharge] = useState(false);
  const [enLigne, setEnLigne] = useState([]);
  const [quiEcrit, setQuiEcrit] = useState({});
  const [connecte, setConnecte] = useState(true);
  const [nonLus, setNonLus] = useState(0);

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
    const socket = io(SOCKET_URL, { auth: { token } });
    socketRef.current = socket;

    socket.on('connect', () => {
      setConnecte(true);
      socket.emit('rejoindre_salon', { salon: salonActif });
    });

    socket.on('disconnect', () => setConnecte(false));

    socket.on('historique', (anciens) => {
      setMessages(anciens);
      setCharge(true);
    });

    socket.on('nouveau_message', (message) => {
      setMessages((precedents) => [...precedents, message]);
      if (message.pseudo !== pseudoRef.current) {
        jouerSonNotification();
        if (document.hidden) setNonLus((n) => n + 1);
      }
    });

    socket.on('systeme', ({ texte }) => {
      setMessages((precedents) => [...precedents, { systeme: true, texte }]);
    });

    socket.on('historique_prive', (anciens) => {
      setMessagesPrivees(anciens);
      setCharge(true);
    });

    socket.on('nouveau_message_prive', (message) => {
      setMessagesPrivees((precedents) => [...precedents, message]);
      if (message.expediteur !== pseudoRef.current) {
        jouerSonNotification();
        if (document.hidden) setNonLus((n) => n + 1);
      }
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // change de salon : previens le serveur, vide l'affichage en attendant le nouvel historique
  useEffect(() => {
    if (!socketRef.current?.connected || dmActif) return;
    setCharge(false);
    setMessages([]);
    setQuiEcrit({});
    socketRef.current.emit('rejoindre_salon', { salon: salonActif });
  }, [salonActif, dmActif]);

  const ouvrirDm = (avec) => {
    if (avec === pseudo) return;
    setCharge(false);
    setMessagesPrivees([]);
    setDmActif(avec);
    socketRef.current.emit('rejoindre_conversation', { avec });
  };

  const revenirAuSalon = () => {
    setDmActif(null);
    setCharge(false);
    setMessages([]);
    socketRef.current.emit('rejoindre_salon', { salon: salonActif });
  };

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
  }, [messages, messagesPrivees]);

  useEffect(() => {
    inputRef.current?.focus();
  }, [salonActif, dmActif]);

  useEffect(() => {
    document.title = nonLus > 0 ? `(${nonLus}) Chat` : 'Chat';
  }, [nonLus]);

  useEffect(() => {
    const remettreAZero = () => {
      if (!document.hidden) setNonLus(0);
    };
    document.addEventListener('visibilitychange', remettreAZero);
    return () => document.removeEventListener('visibilitychange', remettreAZero);
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
    if (dmActif) return;
    if (!enTrainDecrireRef.current) {
      enTrainDecrireRef.current = true;
      socketRef.current.emit('en_train_ecrire');
    }
    clearTimeout(timeoutFrappeRef.current);
    timeoutFrappeRef.current = setTimeout(() => {
      enTrainDecrireRef.current = false;
      socketRef.current.emit('arrete_ecrire');
    }, 1500);
  };

  const envoyer = () => {
    if (!texte.trim()) return;
    if (dmActif) {
      socketRef.current.emit('message_prive_envoye', { texte: texte.trim() });
    } else {
      socketRef.current.emit('message_envoye', { texte: texte.trim() });
      clearTimeout(timeoutFrappeRef.current);
      enTrainDecrireRef.current = false;
      socketRef.current.emit('arrete_ecrire');
    }
    setTexte('');
  };

  const messagesAffiches = dmActif
    ? messagesPrivees.map((m) => ({ pseudo: m.expediteur, texte: m.texte, envoye_le: m.envoye_le }))
    : messages;

  const groupes = [];
  for (const m of messagesAffiches) {
    if (m.systeme) {
      groupes.push({ systeme: true, texte: m.texte });
      continue;
    }
    const dernier = groupes[groupes.length - 1];
    if (dernier && !dernier.systeme && dernier.pseudo === m.pseudo) {
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
            {SALONS.map((salon) => (
              <ListItemButton
                key={salon}
                selected={!dmActif && salon === salonActif}
                onClick={() => { setSalonActif(salon); setDmActif(null); }}
                sx={{ borderRadius: 2 }}
              >
                <ListItemIcon sx={{ minWidth: 32 }}><TagIcon fontSize="small" /></ListItemIcon>
                <ListItemText primary={salon} />
              </ListItemButton>
            ))}
          </List>

          <Box sx={{ px: 2, pt: 2, pb: 1 }}>
            <Typography variant="caption" color="text.secondary" fontWeight={700}>
              EN LIGNE — {enLigne.length}
            </Typography>
          </Box>
          <List sx={{ px: 1, flexGrow: 1, overflowY: 'auto' }}>
            {enLigne.map((p) => (
              <ListItemButton
                key={p}
                selected={dmActif === p}
                onClick={() => ouvrirDm(p)}
                disabled={p === pseudo}
                sx={{ borderRadius: 2, py: 0.5 }}
              >
                <Avatar sx={{ width: 24, height: 24, fontSize: 12, bgcolor: couleurPour(p), mr: 1 }}>
                  {p.slice(0, 1).toUpperCase()}
                </Avatar>
                <ListItemText primary={p === pseudo ? `${p} (toi)` : p} slotProps={{ primary: { noWrap: true } }} />
                <CircleIcon sx={{ fontSize: 8, color: 'success.main' }} />
              </ListItemButton>
            ))}
          </List>

          <Box sx={{ px: 2, py: 1.5, borderTop: 1, borderColor: 'divider', display: 'flex', alignItems: 'center', gap: 1 }}>
            <Avatar sx={{ width: 30, height: 30, fontSize: 14, bgcolor: couleurPour(pseudo) }}>
              {pseudo.slice(0, 1).toUpperCase()}
            </Avatar>
            <Typography variant="body2" noWrap sx={{ flexGrow: 1 }} fontWeight={600}>{pseudo}</Typography>
            <Tooltip title={mode === 'light' ? 'Mode sombre' : 'Mode clair'}>
              <IconButton size="small" onClick={basculerMode}>
                {mode === 'light' ? <DarkModeIcon fontSize="small" /> : <LightModeIcon fontSize="small" />}
              </IconButton>
            </Tooltip>
            <Tooltip title="Deconnexion">
              <IconButton size="small" onClick={deconnexion}>
                <LogoutIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          {!connecte && (
            <Box sx={{ bgcolor: 'warning.main', color: 'warning.contrastText', px: 2, py: 0.75, display: 'flex', alignItems: 'center', gap: 1 }}>
              <CircularProgress size={14} color="inherit" />
              <Typography variant="caption">Connexion perdue — reconnexion en cours...</Typography>
            </Box>
          )}
          <Box sx={{ px: 2, py: 1.5, borderBottom: 1, borderColor: 'divider', display: 'flex', alignItems: 'center', gap: 1 }}>
            {dmActif ? (
              <>
                <IconButton size="small" onClick={revenirAuSalon}><ArrowBackIcon fontSize="small" /></IconButton>
                <Avatar sx={{ width: 26, height: 26, fontSize: 12, bgcolor: couleurPour(dmActif) }}>
                  {dmActif.slice(0, 1).toUpperCase()}
                </Avatar>
                <Typography variant="subtitle1" fontWeight={700}>{dmActif}</Typography>
              </>
            ) : (
              <>
                <TagIcon color="action" />
                <Typography variant="subtitle1" fontWeight={700}>{salonActif}</Typography>
                {enLigne.length > 0 && (
                  <AvatarGroup max={5} sx={{ ml: 'auto', '& .MuiAvatar-root': { width: 24, height: 24, fontSize: 11 } }}>
                    {enLigne.map((p) => (
                      <Avatar key={p} sx={{ bgcolor: couleurPour(p) }}>{p.slice(0, 1).toUpperCase()}</Avatar>
                    ))}
                  </AvatarGroup>
                )}
              </>
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
              groupes.map((g, i) => g.systeme ? (
                <Fade in key={i}>
                  <Typography variant="caption" color="text.disabled" sx={{ textAlign: 'center', fontStyle: 'italic', py: 0.5 }}>
                    {g.texte}
                  </Typography>
                </Fade>
              ) : (
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
                        <Tooltip key={j} title={item.envoye_le ? formaterHeure(item.envoye_le) : ''} placement="left" arrow>
                          <Typography variant="body2" sx={{ wordBreak: 'break-word', lineHeight: 1.6, width: 'fit-content', whiteSpace: 'pre-wrap' }}>
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
            <Fade in={!dmActif && autresQuiEcrivent.length > 0}>
              <Typography variant="caption" color="text.secondary" fontStyle="italic">
                {autresQuiEcrivent.join(', ')} {autresQuiEcrivent.length > 1 ? 'sont' : 'est'} en train d'écrire...
              </Typography>
            </Fade>
          </Box>

          <Box sx={{ px: 2, pb: 2, pt: 0.5 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, bgcolor: mode === 'light' ? 'grey.100' : 'grey.900', borderRadius: 3, px: 1.5 }}>
              <TextField
                fullWidth
                multiline
                maxRows={5}
                variant="standard"
                placeholder={dmActif ? `Message a ${dmActif} (Maj+Entrée pour un retour à la ligne)` : `Envoyer un message dans #${salonActif} (Maj+Entrée pour un retour à la ligne)`}
                value={texte}
                onChange={(e) => gererFrappe(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    envoyer();
                  }
                }}
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

function App() {
  const [token, setToken] = useState(() => localStorage.getItem('chat-token'));
  const [pseudo, setPseudo] = useState(() => localStorage.getItem('chat-username'));

  const seConnecter = (nouveauToken, nouveauPseudo) => {
    localStorage.setItem('chat-token', nouveauToken);
    localStorage.setItem('chat-username', nouveauPseudo);
    setToken(nouveauToken);
    setPseudo(nouveauPseudo);
  };

  const deconnexion = () => {
    localStorage.removeItem('chat-token');
    localStorage.removeItem('chat-username');
    setToken(null);
    setPseudo(null);
  };

  if (!token || !pseudo) {
    return <AuthPage onConnecte={seConnecter} />;
  }

  return <ChatApp token={token} pseudo={pseudo} deconnexion={deconnexion} />;
}

export default App;
