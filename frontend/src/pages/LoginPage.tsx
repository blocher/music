import { useEffect, useState, type FormEvent } from "react";
import { ArrowRight, LockKeyhole } from "lucide-react";
import { Navigate, useNavigate } from "react-router-dom";

import { api, post } from "../api";
import type { Session } from "../types";

export function LoginPage() {
  const [session, setSession] = useState<Session | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  useEffect(() => { void api<Session>("/api/auth/session/").then(setSession); }, []);
  if (session?.authenticated && session.is_admin) return <Navigate to="/studio" replace />;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await post<Session>("/api/auth/login/", { username, password });
      navigate("/studio");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to sign in.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="login-page">
      <section className="login-art"><span>Private release desk</span><h1>From first spark<br />to finished record.</h1><p>Benjamin Locher / independent sounds</p></section>
      <section className="login-panel">
        <LockKeyhole />
        <span className="eyebrow">Release Studio</span>
        <h2>Welcome back.</h2>
        <p>Sign in to sync, shape, and deliver the next record.</p>
        <form onSubmit={submit}>
          <label>Username<input autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} /></label>
          <label>Password<input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
          {error && <div className="form-error">{error}</div>}
          <button className="primary-button" disabled={busy}>{busy ? "Opening…" : "Enter the studio"}<ArrowRight /></button>
        </form>
      </section>
    </main>
  );
}
