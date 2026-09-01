import { createTheme } from '@mui/material/styles';

export function creerTheme(mode) {
  return createTheme({
    palette: {
      mode,
      primary: { main: '#6c5ce7', light: '#a29bfe', dark: '#5849c2' },
      secondary: { main: '#47bfff' },
      background:
        mode === 'light'
          ? { default: '#f0f1f8', paper: '#ffffff' }
          : { default: '#14151f', paper: '#1c1d2b' },
    },
    shape: { borderRadius: 12 },
    typography: {
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      h1: { fontWeight: 700 },
    },
    components: {
      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: { root: { textTransform: 'none', fontWeight: 600 } },
      },
      MuiPaper: {
        styleOverrides: { root: { backgroundImage: 'none' } },
      },
    },
  });
}
