import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";
import { apiRequest, getCookie, setAccessToken } from "../api/client";

export type CurrentUser = {
  id: string;
  email: string;
  display_name: string;
  role: string;
  is_active: boolean;
  email_verified: boolean;
  created_at: string;
};

type SessionResponse = {
  access_token: string;
  token_type: string;
  expires_at: string;
  user: CurrentUser;
};

type AuthContextValue = {
  user: CurrentUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    displayName: string
  ) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function csrfHeaders(): HeadersInit {
  const token = getCookie("codepilot_csrf");
  return token ? { "X-CSRF-Token": token } : {};
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const bootstrapped = useRef(false);

  const applySession = useCallback((session: SessionResponse) => {
    setAccessToken(session.access_token);
    setUser(session.user);
  }, []);

  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;
    apiRequest<SessionResponse>("/auth/refresh", {
      method: "POST",
      headers: csrfHeaders()
    })
      .then(applySession)
      .catch(() => {
        setAccessToken(null);
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, [applySession]);

  const login = useCallback(
    async (email: string, password: string) => {
      const session = await apiRequest<SessionResponse>("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      applySession(session);
    },
    [applySession]
  );

  const register = useCallback(
    async (email: string, password: string, displayName: string) => {
      const session = await apiRequest<SessionResponse>("/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, display_name: displayName })
      });
      applySession(session);
    },
    [applySession]
  );

  const logout = useCallback(async () => {
    try {
      await apiRequest<{ success: boolean }>("/auth/logout", {
        method: "POST",
        headers: csrfHeaders()
      });
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, register, logout }),
    [user, loading, login, register, logout]
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
