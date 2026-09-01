import { useState, useMemo, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, CssBaseline, Box, CircularProgress } from '@mui/material';
import RouteProtegee from './RouteProtegee';
import { creerTheme } from './theme';

const LoginPage = lazy(() => import('./pages/LoginPage'));
const RegisterPage = lazy(() => import('./pages/RegisterPage'));
const TodosPage = lazy(() => import('./pages/TodosPage'));
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage'));
const ResetPasswordPage = lazy(() => import('./pages/ResetPasswordPage'));

function Chargement() {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
      <CircularProgress />
    </Box>
  );
}

function App() {
  const [token, setToken] = useState(localStorage.getItem("token"));
  const [mode, setMode] = useState(() => localStorage.getItem("theme-mode") || "light");

  const basculerMode = () => {
    setMode((m) => {
      const nouveau = m === "light" ? "dark" : "light";
      localStorage.setItem("theme-mode", nouveau);
      return nouveau;
    });
  };

  const theme = useMemo(() => creerTheme(mode), [mode]);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <Suspense fallback={<Chargement />}>
          <Routes>
            <Route path="/login" element={<LoginPage setToken={setToken} mode={mode} basculerMode={basculerMode} />} />
            <Route path="/register" element={<RegisterPage setToken={setToken} mode={mode} basculerMode={basculerMode} />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage mode={mode} basculerMode={basculerMode} />} />
            <Route path="/reset-password" element={<ResetPasswordPage mode={mode} basculerMode={basculerMode} />} />
            <Route
              path="/taches"
              element={
                <RouteProtegee token={token}>
                  <TodosPage token={token} setToken={setToken} mode={mode} basculerMode={basculerMode} />
                </RouteProtegee>
              }
            />
            <Route path="*" element={<Navigate to="/taches" />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
