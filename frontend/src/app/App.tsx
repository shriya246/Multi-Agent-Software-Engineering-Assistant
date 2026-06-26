import { AppShell } from "./AppShell";
import { AppRoutes } from "../routes/AppRoutes";
import { AuthProvider } from "../auth/AuthContext";

export default function App() {
  return (
    <AuthProvider>
      <AppShell>
        <AppRoutes />
      </AppShell>
    </AuthProvider>
  );
}
