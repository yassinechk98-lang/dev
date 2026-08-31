import { Navigate } from 'react-router-dom';

function RouteProtegee({ token, children }) {
  if (!token) return <Navigate to="/login" />;
  return children;
}

export default RouteProtegee;
