import { Link, NavLink } from "react-router-dom";
import type { PropsWithChildren } from "react";
import { useAuth } from "../auth/AuthContext";

const navItems = [
  { label: "Home", to: "/" },
  { label: "Repositories", to: "/repositories" }
];

export function AppShell({ children }: PropsWithChildren) {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
          <Link
            to="/"
            className="text-lg font-semibold tracking-tight text-slate-50"
          >
            CodePilot
          </Link>
          <nav aria-label="Primary" className="flex items-center gap-2">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  [
                    "rounded-md px-3 py-2 text-sm transition",
                    isActive
                      ? "bg-sky-400/15 text-sky-200"
                      : "text-slate-300 hover:bg-slate-900 hover:text-slate-50"
                  ].join(" ")
                }
              >
                {item.label}
              </NavLink>
            ))}
            {user ? (
              <div className="ml-2 flex items-center gap-2 border-l border-slate-700 pl-4">
                <span className="text-sm text-slate-300">{user.display_name}</span>
                <button className="button-secondary" type="button" onClick={() => void logout()}>
                  Logout
                </button>
              </div>
            ) : (
              <>
                <NavLink className="nav-link" to="/login">Login</NavLink>
                <NavLink className="nav-link" to="/register">Register</NavLink>
              </>
            )}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        {children}
      </main>
    </div>
  );
}
