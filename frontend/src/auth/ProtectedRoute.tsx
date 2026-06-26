import type { PropsWithChildren } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function ProtectedRoute({ children }: PropsWithChildren) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <p role="status">Loading your session...</p>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}
