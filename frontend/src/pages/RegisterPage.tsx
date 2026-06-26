import { type FormEvent, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { ApiClientError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export function RegisterPage() {
  const { register, user } = useAuth();
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  if (user) return <Navigate to="/repositories" replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register(email, password, displayName);
      navigate("/repositories", { replace: true });
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "Unable to create the account");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="auth-card">
      <h1 className="text-2xl font-semibold text-slate-50">Create account</h1>
      <p className="mt-2 text-sm text-slate-300">Passwords must contain at least 12 characters.</p>
      <form className="mt-6 space-y-4" onSubmit={(event) => void submit(event)}>
        <label className="field-label">Display name<input className="field-input" autoComplete="name" required maxLength={120} value={displayName} onChange={(e) => setDisplayName(e.target.value)} /></label>
        <label className="field-label">Email<input className="field-input" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label className="field-label">Password<input className="field-input" type="password" autoComplete="new-password" required minLength={12} value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        {error && <p className="error-message" role="alert">{error}</p>}
        <button className="button-primary w-full" disabled={submitting} type="submit">{submitting ? "Creating account..." : "Create account"}</button>
      </form>
    </section>
  );
}
