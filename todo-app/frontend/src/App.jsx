import { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import TodosPage from './pages/TodosPage';
import RouteProtegee from './RouteProtegee';

function App() {
  const [token, setToken] = useState(localStorage.getItem("token"));

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage setToken={setToken} />} />
        <Route path="/register" element={<RegisterPage setToken={setToken} />} />
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
    </BrowserRouter>
  );
}

export default App;
