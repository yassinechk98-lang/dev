import { createTheme } from '@mui/material';

export function creerTheme(mode) {
  return createTheme({
    palette: {
      mode,
      primary: { main: '#6750A4' },
    },
    shape: { borderRadius: 12 },
  });
}
