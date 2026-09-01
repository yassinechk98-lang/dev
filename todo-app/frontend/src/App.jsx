import { useState, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import RouteProtegee from './RouteProtegee';

const LoginPage = lazy(() => import('./pages/LoginPage'));
const RegisterPage = lazy(() => import('./pages/RegisterPage'));
const TodosPage = lazy(() => import('./pages/TodosPage'));
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage'));
const ResetPasswordPage = lazy(() => import('./pages/ResetPasswordPage'));

function App() {
  const [token, setToken] = useState(localStorage.getItem("token"));

  return (
    <BrowserRouter>
      <Suspense fallback={<p>Chargement...</p>}>
        <Routes>
          <Route path="/login" element={<LoginPage setToken={setToken} />} />
          <Route path="/register" element={<RegisterPage setToken={setToken} />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route
            path="/taches"
            element={
              <RouteProtegee token={token}>
                <TodosPage token={token} setToken={setToken} />
              </RouteProtegee>
            }
          />
          <Route path="*" element={<Navigate to="/taches" />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}

export default App;
