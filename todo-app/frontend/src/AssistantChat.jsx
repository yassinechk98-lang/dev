import { useState, useRef, useEffect } from 'react';
import {
  Drawer, Box, Typography, IconButton, TextField, Stack, Paper,
  CircularProgress, Divider,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import SendIcon from '@mui/icons-material/Send';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import { envoyerMessageAssistant } from './api';

function AssistantChat({ token, ouvert, fermer, onTachesChangees }) {
  const [messages, setMessages] = useState([
    { role: 'assistant', texte: "Bonjour ! Dis-moi quoi faire avec tes taches (ex. \"ajoute une tache pour demain 18h : appeler le dentiste\")." },
  ]);
  const [historique, setHistorique] = useState([]);
  const [saisie, setSaisie] = useState('');
  const [envoiEnCours, setEnvoiEnCours] = useState(false);
  const finRef = useRef(null);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, envoiEnCours]);

  const envoyer = () => {
    const texte = saisie.trim();
    if (!texte || envoiEnCours) return;

    setMessages((m) => [...m, { role: 'user', texte }]);
    setSaisie('');
    setEnvoiEnCours(true);

    envoyerMessageAssistant(token, texte, historique)
      .then((reponse) => {
        if (!reponse.ok) throw new Error('Erreur serveur');
        return reponse.json();
      })
      .then((donnees) => {
        setMessages((m) => [...m, { role: 'assistant', texte: donnees.reponse }]);
        setHistorique(donnees.historique);
        onTachesChangees();
      })
      .catch(() => {
        setMessages((m) => [...m, { role: 'assistant', texte: "Desole, une erreur est survenue. Reessaie." }]);
      })
      .finally(() => setEnvoiEnCours(false));
  };

  return (
    <Drawer anchor="right" open={ouvert} onClose={fermer}>
      <Box sx={{ width: { xs: '100vw', sm: 380 }, height: '100%', display: 'flex', flexDirection: 'column' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', px: 2, py: 1.5 }}>
          <SmartToyIcon color="primary" sx={{ mr: 1.5 }} />
          <Typography variant="h6" sx={{ flexGrow: 1 }} fontWeight={700}>
            Assistant
          </Typography>
          <IconButton onClick={fermer}>
            <CloseIcon />
          </IconButton>
        </Box>
        <Divider />

        <Stack spacing={1.5} sx={{ flexGrow: 1, overflowY: 'auto', p: 2 }}>
          {messages.map((message, i) => (
            <Paper
              key={i}
              elevation={0}
              sx={{
                px: 1.5,
                py: 1,
                maxWidth: '85%',
                alignSelf: message.role === 'user' ? 'flex-end' : 'flex-start',
                bgcolor: message.role === 'user' ? 'primary.main' : 'action.hover',
                color: message.role === 'user' ? 'primary.contrastText' : 'text.primary',
                borderRadius: 2,
              }}
            >
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                {message.texte}
              </Typography>
            </Paper>
          ))}
          {envoiEnCours && (
            <Paper elevation={0} sx={{ px: 1.5, py: 1, alignSelf: 'flex-start', bgcolor: 'action.hover', borderRadius: 2 }}>
              <CircularProgress size={16} />
            </Paper>
          )}
          <div ref={finRef} />
        </Stack>

        <Divider />
        <Stack direction="row" spacing={1} sx={{ p: 1.5 }}>
          <TextField
            fullWidth
            size="small"
            placeholder="Ecris ta demande..."
            value={saisie}
            onChange={(e) => setSaisie(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && envoyer()}
            disabled={envoiEnCours}
          />
          <IconButton color="primary" onClick={envoyer} disabled={!saisie.trim() || envoiEnCours}>
            <SendIcon />
          </IconButton>
        </Stack>
      </Box>
    </Drawer>
  );
}

export default AssistantChat;
