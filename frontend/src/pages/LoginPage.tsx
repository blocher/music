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
      <section className="login-art"><div><span>Behind the songs</span><h1>Welcome to the family studio!</h1><p>This is where we get the music ready to share.</p></div><img src="/images/locher-family-band.webp" alt="The illustrated Locher family making music" /></section>
      <section className="login-panel">
        <LockKeyhole />
        <span className="eyebrow">Family studio</span>
        <h2>Come on in.</h2>
        <p>Sign in to keep the songs moving.</p>
        <form onSubmit={submit}>
          <label>Username<input autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} /></label>
          <label>Password<input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
          {error && <div className="form-error">{error}</div>}
          <button className="primary-button" disabled={busy}>{busy ? "Opening…" : "Sign in"}<ArrowRight /></button>
        </form>
      </section>
    </main>
  );
}
