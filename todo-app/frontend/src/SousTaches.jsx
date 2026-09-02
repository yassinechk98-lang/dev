import { useState } from 'react';
import {
  Box, Collapse, Stack, Checkbox, Typography, IconButton, TextField, Button,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import CloseIcon from '@mui/icons-material/Close';
import AddIcon from '@mui/icons-material/Add';
import { getSousTaches, creerSousTache, basculerSousTache, supprimerSousTache } from './api';

function SousTaches({ token, tacheId }) {
  const [ouvert, setOuvert] = useState(false);
  const [sousTaches, setSousTaches] = useState(null);
  const [nouveauTitre, setNouveauTitre] = useState('');

  const basculerOuverture = () => {
    if (!ouvert && sousTaches === null) {
      getSousTaches(token, tacheId)
        .then((reponse) => reponse.json())
        .then(setSousTaches);
    }
    setOuvert(!ouvert);
  };

  const ajouter = () => {
    const titre = nouveauTitre.trim();
    if (!titre) return;
    creerSousTache(token, tacheId, titre)
      .then((reponse) => reponse.json())
      .then((sousTache) => {
        setSousTaches((prev) => [...(prev || []), sousTache]);
        setNouveauTitre('');
      });
  };

  const basculer = (id) => {
    basculerSousTache(token, id)
      .then((reponse) => reponse.json())
      .then((maj) => {
        setSousTaches((prev) => prev.map((st) => (st.id === id ? maj : st)));
      });
  };

  const supprimer = (id) => {
    supprimerSousTache(token, id).then(() => {
      setSousTaches((prev) => prev.filter((st) => st.id !== id));
    });
  };

  const total = sousTaches?.length ?? 0;
  const terminees = sousTaches?.filter((st) => st.terminee).length ?? 0;

  return (
    <Box sx={{ mt: 0.5 }}>
      <Button
        size="small"
        onClick={basculerOuverture}
        startIcon={ouvert ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        sx={{ textTransform: 'none', color: 'text.secondary', px: 0.5, minWidth: 0 }}
      >
        Sous-taches{sousTaches !== null && ` (${terminees}/${total})`}
      </Button>

      <Collapse in={ouvert}>
        <Stack spacing={0.5} sx={{ pl: 2, pt: 0.5 }}>
          {sousTaches?.map((st) => (
            <Stack key={st.id} direction="row" alignItems="center" spacing={0.5}>
              <Checkbox
                size="small"
                checked={st.terminee}
                onChange={() => basculer(st.id)}
              />
              <Typography
                variant="body2"
                sx={{
                  flexGrow: 1,
                  textDecoration: st.terminee ? 'line-through' : 'none',
                  color: st.terminee ? 'text.secondary' : 'text.primary',
                }}
              >
                {st.titre}
              </Typography>
              <IconButton size="small" onClick={() => supprimer(st.id)}>
                <CloseIcon fontSize="small" />
              </IconButton>
            </Stack>
          ))}

          <Stack direction="row" spacing={0.5} alignItems="center">
            <TextField
              variant="standard"
              placeholder="Ajouter une sous-tache"
              value={nouveauTitre}
              onChange={(e) => setNouveauTitre(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && ajouter()}
              fullWidth
              size="small"
            />
            <IconButton size="small" onClick={ajouter} disabled={!nouveauTitre.trim()}>
              <AddIcon fontSize="small" />
            </IconButton>
          </Stack>
        </Stack>
      </Collapse>
    </Box>
  );
}

export default SousTaches;
