import { Route, Routes } from "react-router-dom";
import { HomePage } from "../pages/HomePage";
import { LoginPage } from "../pages/LoginPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { RepositoriesPage } from "../pages/RepositoriesPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/repositories" element={<RepositoriesPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
