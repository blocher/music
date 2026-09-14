import { useCallback, useEffect, useState } from "react";
import { ArrowRight, CheckCircle2, CircleAlert, CloudDownload, RefreshCw, Settings2 } from "lucide-react";
import { Link } from "react-router-dom";

import { api, post } from "../api";
import type { Album } from "../types";

type Paged<T> = { count: number; results: T[] };
type SyncRun = { id: number; status: string; albums_seen: number; tracks_seen: number; loose_tracks_excluded: number; created_at: string; error: string };
type Integration = { connected: boolean; last_error?: string; display_label?: string };
type DownloadBudget = { used: number; limit: number; remaining: number; period: string; resets_at: string };

export function StudioPage() {
  const [albums, setAlbums] = useState<Album[]>([]);
  const [runs, setRuns] = useState<SyncRun[]>([]);
  const [suno, setSuno] = useState<Integration | null>(null);
  const [tooLost, setTooLost] = useState<Integration | null>(null);
  const [budget, setBudget] = useState<DownloadBudget | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const [albumPage, syncRuns, sunoStatus, tooLostStatus, downloadBudget] = await Promise.all([
      api<Paged<Album>>("/api/studio/albums/"),
      api<SyncRun[]>("/api/studio/sync-runs/"),
      api<Integration>("/api/studio/integrations/suno/"),
      api<Integration>("/api/studio/integrations/too_lost/"),
      api<DownloadBudget>("/api/studio/download-budget/"),
    ]);
    setAlbums(albumPage.results);
    setRuns(syncRuns);
    setSuno(sunoStatus);
    setTooLost(tooLostStatus);
    setBudget(downloadBudget);
    setSyncing(syncRuns[0]?.status === "queued" || syncRuns[0]?.status === "running");
  }, []);

  useEffect(() => { void load().catch((reason) => setError(reason.message)); }, [load]);
  useEffect(() => {
    if (!syncing) return;
    const timer = window.setInterval(() => void load(), 3000);
    return () => window.clearInterval(timer);
  }, [syncing, load]);

  const startSync = async () => {
    setError("");
    setSyncing(true);
    try {
      const run = await post<SyncRun>("/api/studio/sync-runs/", {});
      setRuns((current) => [run, ...current.filter((item) => item.id !== run.id)]);
      await load();
    }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Sync failed."); setSyncing(false); }
  };
  const latest = runs[0];

  return (
    <div className="studio-page">
      <section className="studio-title-row">
        <div><span className="eyebrow">Family studio</span><h1>Songs in progress.</h1><p>Sync a playlist, tidy up the details, and share it when it’s ready.</p></div>
        <button className="primary-button" disabled={!suno?.connected || syncing} onClick={startSync}><RefreshCw className={syncing ? "spinning" : ""} />{syncing ? "Syncing Suno…" : "Sync from Suno"}</button>
      </section>
      {error && <div className="banner error"><CircleAlert />{error}</div>}
      {syncing && <div className="banner sync-banner" role="status" aria-live="polite"><RefreshCw className="spinning" /><span><strong>{latest?.status === "running" ? "Syncing your Suno playlists…" : "Suno sync queued…"}</strong><small>You can stay here; albums and song counts update automatically when the sync finishes.</small></span></div>}
      {!syncing && latest?.status === "failed" && <div className="banner error"><CircleAlert /><span><strong>Suno sync did not finish.</strong><small>{latest.error || "Check the saved Suno session and try again."}</small></span></div>}
      {!suno?.connected && <div className="banner"><Settings2 /><span>Connect Suno before the first sync. Passwords are never stored.</span><Link to="/studio/integrations">Open integrations <ArrowRight /></Link></div>}
      <section className="studio-metrics">
        <div><span className="eyebrow">Suno sync</span><strong>{latest?.status || "Not run"}</strong><small>{latest ? new Date(latest.created_at).toLocaleString() : "Connect to begin"}</small></div>
        <div><span className="eyebrow">Imported</span><strong>{latest?.albums_seen ?? 0} albums / {latest?.tracks_seen ?? 0} tracks</strong><small>Playlists become albums</small></div>
        <div><span className="eyebrow">Excluded</span><strong>{latest?.loose_tracks_excluded ?? 0} loose songs</strong><small>Never imported</small></div>
        <div><span className="eyebrow">Download allowance</span><strong>{budget ? `${budget.used} / ${budget.limit}` : "—"}</strong><small>{budget ? `${budget.remaining} songs remain this month` : "Every save requires confirmation"}</small></div>
      </section>
      <section className="release-list-section">
        <header><div><span className="eyebrow">Our albums</span><h2>{albums.length ? `${albums.length} albums` : "No synced playlists yet"}</h2></div><Link className="text-button" to="/studio/integrations">Integrations <ArrowRight /></Link></header>
        <div className="studio-album-grid">
          {albums.map((album) => (
            <Link className="studio-album-card" to={`/studio/releases/${album.id}`} key={album.id}>
              <div className="studio-cover" style={{ backgroundImage: `url(${album.cover_url})` }} />
              <div><span className="eyebrow">Version {album.version} / {album.status}</span><h3>{album.title}</h3><p>{album.track_count} tracks · {album.public ? "Public" : "Private"}</p></div>
              {album.status === "live" ? <CheckCircle2 className="success" /> : <ArrowRight />}
            </Link>
          ))}
        </div>
      </section>
      <aside className="integration-strip">
        <div>{suno?.connected ? <CheckCircle2 /> : <CircleAlert />}<span>Suno<strong>{suno?.connected ? "Connected" : "Needs connection"}</strong></span></div>
        <div>{tooLost?.connected ? <CheckCircle2 /> : <CircleAlert />}<span>Too Lost<strong>{tooLost?.connected ? "Connected" : "Needs credentials"}</strong></span></div>
        <div><CloudDownload /><span>Downloads<strong>Confirmation protected</strong></span></div>
      </aside>
    </div>
  );
}
