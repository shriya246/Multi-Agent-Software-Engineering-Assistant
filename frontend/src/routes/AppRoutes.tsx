import { Route, Routes } from "react-router-dom";
import { HomePage } from "../pages/HomePage";
import { LoginPage } from "../pages/LoginPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { RepositoriesPage } from "../pages/RepositoriesPage";
import { RegisterPage } from "../pages/RegisterPage";
import { ProtectedRoute } from "../auth/ProtectedRoute";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/repositories"
        element={
          <ProtectedRoute>
            <RepositoriesPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
