import { Box, Paper, IconButton, Tooltip, useTheme } from '@mui/material';
import LightModeIcon from '@mui/icons-material/LightMode';
import DarkModeIcon from '@mui/icons-material/DarkMode';

function AuthLayout({ children, mode, basculerMode }) {
  const theme = useTheme();

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: 2,
        background:
          theme.palette.mode === 'light'
            ? 'linear-gradient(135deg, #a29bfe, #74b9ff)'
            : 'linear-gradient(135deg, #2d2a4a, #16213e)',
      }}
    >
      <Tooltip title={mode === 'light' ? 'Mode sombre' : 'Mode clair'}>
        <IconButton
          onClick={basculerMode}
          sx={{ position: 'fixed', top: 16, right: 16, color: 'white' }}
        >
          {mode === 'light' ? <DarkModeIcon /> : <LightModeIcon />}
        </IconButton>
      </Tooltip>

      <Paper
        elevation={0}
        sx={{
          width: '100%',
          maxWidth: 420,
          p: 4,
          borderRadius: 4,
          boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
        }}
      >
        {children}
      </Paper>
    </Box>
  );
}

export default AuthLayout;
