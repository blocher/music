import { useEffect, useState, type FormEvent } from "react";
import { ArrowLeft, CheckCircle2, ExternalLink, KeyRound, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { api } from "../api";

type Integration = { connected: boolean; values?: Record<string, string>; display_label?: string; last_error?: string };

function IntegrationForm({ service, title, children, fields }: { service: string; title: string; children: React.ReactNode; fields: Array<{ key: string; label: string; secret?: boolean; placeholder?: string }> }) {
  const [status, setStatus] = useState<Integration | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { void api<Integration>(`/api/studio/integrations/${service}/`).then(setStatus); }, [service]);
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      const result = await api<Integration>(`/api/studio/integrations/${service}/`, { method: "PUT", body: JSON.stringify({ values, display_label: title }) });
      setStatus(result); setValues({}); setMessage("Credentials saved securely.");
    } catch (reason) { setMessage(reason instanceof Error ? reason.message : "Unable to save."); }
    finally { setBusy(false); }
  };
  const verify = async () => {
    setBusy(true); setMessage("");
    try { await api(`/api/studio/integrations/${service}/verify/`, { method: "POST", body: "{}" }); setMessage("Connection verified."); }
    catch (reason) { setMessage(reason instanceof Error ? reason.message : "Verification failed."); }
    finally { setBusy(false); }
  };
  return (
    <section className="integration-card">
      <header><KeyRound /><div><span className="eyebrow">Integration</span><h2>{title}</h2></div><span className={status?.connected ? "status-pill success" : "status-pill"}>{status?.connected ? "Connected" : "Not connected"}</span></header>
      <div className="integration-help">{children}</div>
      <form onSubmit={submit}>
        {fields.map((field) => <label key={field.key}>{field.label}<input type={field.secret ? "password" : "text"} placeholder={status?.values?.[field.key] || field.placeholder} value={values[field.key] || ""} onChange={(event) => setValues({ ...values, [field.key]: event.target.value })} /></label>)}
        {message && <p className="form-message">{message}</p>}
        <div className="form-actions"><button className="primary-button" disabled={busy}>Save credentials</button>{status?.connected && <button type="button" className="secondary-button" onClick={verify} disabled={busy}>Verify connection</button>}</div>
      </form>
    </section>
  );
}

export function IntegrationsPage() {
  return (
    <div className="integrations-page">
      <Link className="back-link" to="/studio"><ArrowLeft /> Back to releases</Link>
      <header className="page-intro"><span className="eyebrow">Studio settings</span><h1>Connections you control.</h1><p>Secrets are encrypted before they reach the database and are never shown again.</p></header>
      <div className="integration-grid">
        <IntegrationForm service="suno" title="Suno" fields={[{ key: "session_id", label: "Clerk session ID", secret: true, placeholder: "sess_…" }, { key: "cookie", label: "Suno Cookie request header", secret: true, placeholder: "Paste the complete Cookie header" }, { key: "account_email", label: "Account email (for your reference)" }, { key: "monthly_download_limit", label: "Monthly song-download allowance", placeholder: "20" }]}>
          <p>Sign in at <a href="https://suno.com" target="_blank" rel="noreferrer">suno.com <ExternalLink size={13} /></a>, then copy the session ID from the token request URL and the complete Cookie request header from the browser network inspector. The studio never asks for your Suno password.</p>
        </IntegrationForm>
        <IntegrationForm service="too_lost" title="Too Lost" fields={[{ key: "access_token", label: "OAuth access token or API key", secret: true }, { key: "api_base_url", label: "API base URL", placeholder: "https://api.toolost.com" }, { key: "create_release_path", label: "Create release path", placeholder: "/v2/releases" }]}>
          <p>Register this site in the <a href="https://developer.toolost.com" target="_blank" rel="noreferrer">Too Lost developer portal <ExternalLink size={13} /></a>. Use its sandbox token first; switch to production only after a complete validation pass.</p>
        </IntegrationForm>
      </div>
      <aside className="security-note"><ShieldCheck /><div><h3>Deliberate by design</h3><p>Suno sync is low-volume. Audio is not copied during sync. Each MP3/WAV save and every distributor submission has its own review and confirmation step.</p></div><CheckCircle2 /></aside>
    </div>
  );
}
