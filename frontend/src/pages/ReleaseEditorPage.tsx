import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, ChevronDown, ChevronUp, CircleAlert, CloudUpload, Download, ExternalLink, FileAudio, Image, Link2, ListMusic, Music2, RefreshCw, Save, ShieldCheck, Sparkles, Trash2 } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, patch, post } from "../api";
import { PlatformLinks } from "../components/PlatformLinks";
import { Waveform } from "../components/Waveform";
import type { Album, PlatformLink, TimedLyric, Track } from "../types";

type Paged<T> = { count: number; results: T[] };
type Tab = "metadata" | "tracks" | "lyrics" | "delivery" | "links";
type Validation = { valid: boolean; errors: Array<{ field: string; message: string }> };
type Submission = { id: number; status: string; validation_errors: Validation["errors"] };
type ConfirmAction = { title: string; body: string; action: () => Promise<void>; confirmLabel?: string; danger?: boolean };

const tabs: Array<{ id: Tab; label: string; icon: typeof Music2 }> = [
  { id: "metadata", label: "Metadata", icon: Music2 },
  { id: "tracks", label: "Tracks & audio", icon: ListMusic },
  { id: "lyrics", label: "Waveform & lyrics", icon: FileAudio },
  { id: "delivery", label: "Delivery", icon: CloudUpload },
  { id: "links", label: "Store links", icon: Link2 },
];

const seconds = (value: number) => `${Math.floor(value / 60)}:${Math.floor(value % 60).toString().padStart(2, "0")}`;

export function ReleaseEditorPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [album, setAlbum] = useState<Album | null>(null);
  const [allTracks, setAllTracks] = useState<Track[]>([]);
  const [tab, setTab] = useState<Tab>("metadata");
  const [message, setMessage] = useState("");
  const [confirming, setConfirming] = useState<ConfirmAction | null>(null);

  const load = useCallback(async () => {
    const [release, tracks] = await Promise.all([
      api<Album>(`/api/studio/albums/${id}/`),
      api<Paged<Track>>("/api/studio/tracks/"),
    ]);
    setAlbum(release); setAllTracks(tracks.results);
  }, [id]);
  useEffect(() => { void load(); }, [load]);
  if (!album) return <div className="loading-screen">Opening the album workspace…</div>;
  const canDelete = ["draft", "ready"].includes(album.status) && !album.too_lost_release_id && !album.latest_submission && !album.has_replacements;
  const requestDelete = () => setConfirming({
    title: `Delete “${album.title}”?`,
    body: "This permanently removes the album and its public page from Locher songs. The songs and any saved audio stay safely in your library. Albums sent to music stores must be taken down instead.",
    confirmLabel: "Delete album",
    danger: true,
    action: async () => {
      await api<void>(`/api/studio/albums/${album.id}/`, { method: "DELETE" });
      navigate("/studio", { replace: true });
    },
  });

  return (
    <div className="release-editor">
      <aside className="release-sidebar">
        <Link className="back-link" to="/studio"><ArrowLeft /> Back to releases</Link>
        <span className="eyebrow">Current release</span><h2>{album.title}</h2>
        <div className="sidebar-cover" style={{ backgroundImage: `url(${album.cover_url})` }} />
        <div className="record-facts vertical"><span>Album</span><span>{album.track_count} tracks</span><span>Version {album.version}</span></div>
        <nav>{tabs.map(({ id: tabId, label, icon: Icon }) => <button className={tab === tabId ? "active" : ""} key={tabId} onClick={() => setTab(tabId)}><Icon />{label}<ArrowRight /></button>)}</nav>
      </aside>
      <section className="release-workspace">
        {message && <div className="banner success"><CheckCircle2 />{message}<button onClick={() => setMessage("")}>×</button></div>}
        {tab === "metadata" && <MetadataPanel album={album} onSaved={(next) => { setAlbum(next); setMessage("Release metadata saved."); }} />}
        {tab === "tracks" && <TracksPanel album={album} reload={load} confirm={setConfirming} />}
        {tab === "lyrics" && <LyricsPanel album={album} reload={load} />}
        {tab === "delivery" && <DeliveryPanel album={album} allTracks={allTracks} reload={load} confirm={setConfirming} />}
        {tab === "links" && <LinksPanel album={album} reload={load} />}
      </section>
      <aside className="release-status">
        <span className="eyebrow">Too Lost readiness</span>
        <h3><span className={album.status === "live" ? "status-dot success" : "status-dot"} />{album.status}</h3>
        <p>{album.too_lost_release_id ? `Release ${album.too_lost_release_id}` : "Not yet submitted"}</p>
        <div className="fine-rule" />
        <span className="eyebrow">Public catalog</span>
        <strong>{album.public ? "Visible to listeners" : "Private draft"}</strong>
        <PlatformLinks links={album.platform_links} />
        {album.replaces_id && <div className="replacement-badge"><ShieldCheck />Replacement version<br /><small>Original stays live until this is accepted.</small></div>}
        <div className="album-danger-zone">
          <span className="eyebrow">Album controls</span>
          <button className="danger-button" disabled={!canDelete} onClick={requestDelete}><Trash2 />Delete album</button>
          <small>{canDelete ? "Removes this album, but keeps its songs and audio." : "Distributed albums and albums with release history cannot be deleted."}</small>
        </div>
      </aside>
      {confirming && <ConfirmOverlay {...confirming} close={() => setConfirming(null)} />}
    </div>
  );
}

function ConfirmOverlay({ title, body, action, close, confirmLabel = "Confirm", danger = false }: ConfirmAction & { close: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const run = async () => {
    setBusy(true); setError("");
    try { await action(); close(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "The action could not be completed."); setBusy(false); }
  };
  return <div className="modal-backdrop"><section className="confirm-modal"><span className="eyebrow">Confirm action</span><h2>{title}</h2><p>{body}</p>{error && <div className="banner error"><CircleAlert />{error}</div>}<div className="form-actions"><button className="secondary-button" onClick={close}>Go back</button><button className={danger ? "danger-button" : "primary-button"} disabled={busy} onClick={() => void run()}>{busy ? "Working…" : confirmLabel}</button></div></section></div>;
}

function MetadataPanel({ album, onSaved }: { album: Album; onSaved: (album: Album) => void }) {
  const [form, setForm] = useState(album);
  const [cover, setCover] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [aiStyle, setAiStyle] = useState("");
  const [aiPrompt, setAiPrompt] = useState("");
  const [aiSource, setAiSource] = useState<File | null>(null);
  const [aiBusy, setAiBusy] = useState("");
  const [aiMessage, setAiMessage] = useState("");
  const save = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true);
    let next = await patch<Album>(`/api/studio/albums/${album.id}/`, {
      title: form.title, slug: form.slug, description: form.description, release_date: form.release_date || null,
      catalog_number: form.catalog_number, upc: form.upc, label_name: form.label_name,
      copyright_line: form.copyright_line, production_line: form.production_line, public: form.public,
    });
    if (cover) {
      const data = new FormData(); data.append("cover", cover);
      next = await api<Album>(`/api/studio/albums/${album.id}/`, { method: "PATCH", body: data });
    }
    setBusy(false); onSaved(next);
  };
  const field = (key: keyof Album, value: string | boolean | null) => setForm({ ...form, [key]: value });
  const writeDescription = async () => {
    setAiBusy("description"); setAiMessage("");
    try {
      const result = await post<{ description: string }>(`/api/studio/albums/${album.id}/generate_description/`, { style: aiStyle, existing_description: form.description });
      field("description", result.description); setAiMessage("Draft added below. Review it, then save metadata.");
    } catch (reason) { setAiMessage(reason instanceof Error ? reason.message : "Could not write a description."); }
    finally { setAiBusy(""); }
  };
  const makeCover = async () => {
    setAiBusy("cover"); setAiMessage("");
    try {
      const data = new FormData(); data.append("prompt", aiPrompt); if (aiSource) data.append("source_image", aiSource);
      const next = await api<Album>(`/api/studio/albums/${album.id}/generate_cover/`, { method: "POST", body: data });
      setForm({ ...form, cover_url: next.cover_url }); onSaved(next); setAiMessage("New album cover generated and saved.");
    } catch (reason) { setAiMessage(reason instanceof Error ? reason.message : "Could not generate artwork."); }
    finally { setAiBusy(""); }
  };
  return <form className="editor-panel metadata-panel" onSubmit={save}>
    <header><div><span className="eyebrow">Release metadata</span><h1>{form.title}</h1><p>“Sync new” preserves your edits. “Refresh all” deliberately replaces Suno-owned metadata.</p></div><button className="primary-button" disabled={busy}><Save />{busy ? "Saving…" : "Save metadata"}</button></header>
    <div className="form-grid">
      <label className="wide">Album title<input value={form.title} onChange={(event) => field("title", event.target.value)} /></label>
      <label>URL slug<input value={form.slug} onChange={(event) => field("slug", event.target.value)} /></label>
      <label>Release date<input type="date" value={form.release_date || ""} onChange={(event) => field("release_date", event.target.value)} /></label>
      <label className="wide">Description<textarea rows={6} value={form.description} onChange={(event) => field("description", event.target.value)} /></label>
      <div className="ai-tool wide"><Sparkles /><div><strong>Help me describe this album</strong><p>Uses the songs’ lyrics, your notes, and the current description. Nothing is final until you save.</p><input value={aiStyle} onChange={(event) => setAiStyle(event.target.value)} placeholder="Style or details to emphasize (optional)" /></div><button type="button" className="secondary-button" disabled={Boolean(aiBusy)} onClick={() => void writeDescription()}>{aiBusy === "description" ? "Writing…" : "Draft description"}</button></div>
      <label>Catalog number<input value={form.catalog_number} onChange={(event) => field("catalog_number", event.target.value)} /></label>
      <label>UPC<input value={form.upc || ""} onChange={(event) => field("upc", event.target.value)} /></label>
      <label>Label<input value={form.label_name || ""} onChange={(event) => field("label_name", event.target.value)} /></label>
      <label>Copyright line<input value={form.copyright_line || ""} onChange={(event) => field("copyright_line", event.target.value)} /></label>
      <label className="wide file-field"><Image /><span>Final cover art<small>Square, high resolution. Replaces the Suno preview for publishing.</small></span><input type="file" accept="image/*" onChange={(event) => setCover(event.target.files?.[0] || null)} /></label>
      <div className="ai-cover-tool wide"><div className="ai-cover-preview" style={{ backgroundImage: `url(${form.cover_url})` }} /><div><span className="eyebrow">AI cover studio</span><textarea rows={3} value={aiPrompt} onChange={(event) => setAiPrompt(event.target.value)} placeholder="A joyful paper-cutout backyard concert with handmade instruments…" /><label className="source-upload">Optional source image<input type="file" accept="image/*" onChange={(event) => setAiSource(event.target.files?.[0] || null)} /></label></div><button type="button" className="secondary-button" disabled={Boolean(aiBusy)} onClick={() => void makeCover()}>{aiBusy === "cover" ? "Making art…" : "Generate cover"}</button></div>
      {aiMessage && <p className="form-message wide">{aiMessage}</p>}
      <label className="toggle wide"><input type="checkbox" checked={form.public} onChange={(event) => field("public", event.target.checked)} /><span>Show this album in the public catalog</span></label>
    </div>
  </form>;
}

function TracksPanel({ album, reload, confirm }: { album: Album; reload: () => Promise<void>; confirm: React.Dispatch<React.SetStateAction<ConfirmAction | null>> }) {
  const tracks = album.album_tracks || [];
  const [selectedId, setSelectedId] = useState(tracks[0]?.track.id || "");
  const selected = tracks.find(({ track }) => track.id === selectedId)?.track || tracks[0]?.track;
  const reorder = async (index: number, direction: -1 | 1) => {
    const next = [...tracks]; const target = index + direction;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    await post(`/api/studio/albums/${album.id}/reorder/`, { track_ids: next.map((item) => item.track.id) }); await reload();
  };
  const requestDownload = async (track: Track) => {
    const [request, budget] = await Promise.all([
      post<{ id: number }>("/api/studio/downloads/", { track: track.id, formats: ["mp3", "wav"] }),
      api<{ used: number; limit: number; remaining: number }>("/api/studio/download-budget/"),
    ]);
    confirm({
      title: `Save ${track.title}?`,
      body: `This will save the source MP3 and request Suno's WAV conversion. ${budget.remaining} of ${budget.limit} locally tracked song downloads remain this month. Nothing is downloaded until you confirm.`,
      action: async () => { await post(`/api/studio/downloads/${request.id}/confirm/`, {}); await reload(); },
    });
  };
  return <section className="editor-panel"><header><div><span className="eyebrow">Tracks & source audio</span><h1>{album.title}</h1><p>Put the songs in order and approve each quota-counted download before it starts.</p></div></header>
    <div className="admin-track-list">{tracks.map(({ track }, index) => <article key={track.id}>
      <span className="track-number">{(index + 1).toString().padStart(2, "0")}</span><button className="mini-cover" aria-label={`Edit ${track.title}`} style={{ backgroundImage: `url(${track.cover_url || album.cover_url})` }} onClick={() => setSelectedId(track.id)} />
      <div><h3>{track.title}</h3><p>{track.release_date && <>{track.release_date} · </>}{track.audio_status === "saved" ? "MP3 + WAV saved" : "Metadata synced; audio remains at Suno"}</p></div>
      <span>{seconds(Number(track.duration_seconds || 0))}</span><span className={`status-pill ${track.audio_status === "saved" ? "success" : ""}`}>{track.audio_status}</span>
      <div className="row-actions"><button onClick={() => setSelectedId(track.id)}>Edit</button><button onClick={() => void reorder(index, -1)} disabled={index === 0}><ChevronUp /></button><button onClick={() => void reorder(index, 1)} disabled={index === tracks.length - 1}><ChevronDown /></button>{track.audio_status !== "saved" && <button className="download-action" onClick={() => void requestDownload(track)}><Download /> Request audio</button>}</div>
    </article>)}</div>
    {selected && <TrackMetadataForm key={selected.id} track={selected} reload={reload} />}
  </section>;
}

function TrackMetadataForm({ track, reload }: { track: Track; reload: () => Promise<void> }) {
  const [form, setForm] = useState(track);
  const [cover, setCover] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [aiStyle, setAiStyle] = useState("");
  const [aiPrompt, setAiPrompt] = useState("");
  const [aiSource, setAiSource] = useState<File | null>(null);
  const [aiBusy, setAiBusy] = useState("");
  const [aiMessage, setAiMessage] = useState("");
  const field = (key: keyof Track, value: string | boolean) => setForm({ ...form, [key]: value });
  const save = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setSaved(false);
    await patch<Track>(`/api/studio/tracks/${track.id}/`, {
      title: form.title, slug: form.slug, description: form.description, release_date: form.release_date || null, lyrics: form.lyrics,
      explicit: form.explicit, instrumental: form.instrumental, isrc: form.isrc,
    });
    if (cover) {
      const data = new FormData(); data.append("cover", cover);
      await api<Track>(`/api/studio/tracks/${track.id}/`, { method: "PATCH", body: data });
    }
    await reload(); setBusy(false); setSaved(true);
  };
  const writeDescription = async () => {
    setAiBusy("description"); setAiMessage("");
    try {
      const result = await post<{ description: string }>(`/api/studio/tracks/${track.id}/generate_description/`, { style: aiStyle, existing_description: form.description, lyrics: form.lyrics });
      field("description", result.description); setAiMessage("Draft added. Review it, then save the song.");
    } catch (reason) { setAiMessage(reason instanceof Error ? reason.message : "Could not write a description."); }
    finally { setAiBusy(""); }
  };
  const makeCover = async () => {
    setAiBusy("cover"); setAiMessage("");
    try {
      const data = new FormData(); data.append("prompt", aiPrompt); if (aiSource) data.append("source_image", aiSource);
      const next = await api<Track>(`/api/studio/tracks/${track.id}/generate_cover/`, { method: "POST", body: data });
      setForm({ ...form, cover_url: next.cover_url }); await reload(); setAiMessage("New song artwork generated and saved.");
    } catch (reason) { setAiMessage(reason instanceof Error ? reason.message : "Could not generate artwork."); }
    finally { setAiBusy(""); }
  };
  return <form className="track-metadata-form" onSubmit={save}>
    <header><div><span className="eyebrow">Song metadata</span><h2>{form.title}</h2><p>These values are used for the public catalog and the Too Lost release snapshot.</p></div><button className="primary-button" disabled={busy}><Save />{busy ? "Saving…" : "Save song"}</button></header>
    {saved && <div className="banner success"><CheckCircle2 />Song metadata saved.</div>}
    <div className="form-grid">
      <label>Song title<input value={form.title} onChange={(event) => field("title", event.target.value)} /></label>
      <label>URL slug<input value={form.slug} onChange={(event) => field("slug", event.target.value)} /></label>
      <label>Release date<input type="date" value={form.release_date || ""} onChange={(event) => field("release_date", event.target.value)} /></label>
      <label className="wide">Description<textarea rows={3} value={form.description} onChange={(event) => field("description", event.target.value)} /></label>
      <div className="ai-tool wide"><Sparkles /><div><strong>Help me describe this song</strong><p>Uses the lyrics, your style notes, and what is already written.</p><input value={aiStyle} onChange={(event) => setAiStyle(event.target.value)} placeholder="Playful folk-pop, bedtime song, inside joke…" /></div><button type="button" className="secondary-button" disabled={Boolean(aiBusy)} onClick={() => void writeDescription()}>{aiBusy === "description" ? "Writing…" : "Draft description"}</button></div>
      <label>ISRC<input value={form.isrc} onChange={(event) => field("isrc", event.target.value)} placeholder="Assigned after first delivery" /></label>
      <label className="file-field"><Image /><span>Song artwork<small>Overrides the Suno image in the catalog.</small></span><input type="file" accept="image/*" onChange={(event) => setCover(event.target.files?.[0] || null)} /></label>
      <div className="ai-cover-tool wide"><div className="ai-cover-preview" style={{ backgroundImage: `url(${form.cover_url})` }} /><div><span className="eyebrow">AI song artwork</span><textarea rows={3} value={aiPrompt} onChange={(event) => setAiPrompt(event.target.value)} placeholder="Describe the scene, color, mood, and medium…" /><label className="source-upload">Optional source image<input type="file" accept="image/*" onChange={(event) => setAiSource(event.target.files?.[0] || null)} /></label></div><button type="button" className="secondary-button" disabled={Boolean(aiBusy)} onClick={() => void makeCover()}>{aiBusy === "cover" ? "Making art…" : "Generate artwork"}</button></div>
      {aiMessage && <p className="form-message wide">{aiMessage}</p>}
      <label className="wide">Plain lyrics<textarea rows={9} value={form.lyrics} onChange={(event) => field("lyrics", event.target.value)} /></label>
      <label className="toggle"><input type="checkbox" checked={form.explicit} onChange={(event) => field("explicit", event.target.checked)} /><span>Explicit content</span></label>
      <label className="toggle"><input type="checkbox" checked={form.instrumental} onChange={(event) => field("instrumental", event.target.checked)} /><span>Instrumental</span></label>
    </div>
  </form>;
}

function LyricsPanel({ album, reload }: { album: Album; reload: () => Promise<void> }) {
  const tracks = album.album_tracks?.map((item) => item.track) || [];
  const [selectedId, setSelectedId] = useState(tracks[0]?.id || "");
  const selected = tracks.find((track) => track.id === selectedId) || tracks[0];
  const [cues, setCues] = useState<TimedLyric[]>(selected?.timed_lyrics || []);
  const [lrc, setLrc] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(Number(selected?.duration_seconds || 0));
  const audio = useRef<HTMLAudioElement | null>(null);
  useEffect(() => setCues(selected?.timed_lyrics || []), [selected]);
  useEffect(() => { setCurrentTime(0); setPlaying(false); setDuration(Number(selected?.duration_seconds || 0)); }, [selected]);
  if (!selected) return <section className="editor-panel"><p>No tracks yet.</p></section>;
  const updateCue = (index: number, update: Partial<TimedLyric>) => setCues(cues.map((cue, cueIndex) => cueIndex === index ? { ...cue, ...update } : cue));
  const save = async () => { await patch(`/api/studio/tracks/${selected.id}/`, { timed_lyrics: cues }); await reload(); };
  const importLrc = async () => { const next = await post<Track>(`/api/studio/tracks/${selected.id}/import_lrc/`, { lrc }); setCues(next.timed_lyrics); await reload(); };
  const sync = async (forceOpenAI = false) => {
    setBusy(true); setError("");
    try { const next = await post<Track>(`/api/studio/tracks/${selected.id}/sync_lyrics/`, { force_openai: forceOpenAI }); setCues(next.timed_lyrics); await reload(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not align lyrics."); }
    finally { setBusy(false); }
  };
  const togglePlayback = async () => {
    if (!audio.current) return;
    if (audio.current.paused) { await audio.current.play(); } else { audio.current.pause(); }
  };
  const seek = (ratio: number) => { if (audio.current && duration) audio.current.currentTime = ratio * duration; };
  const confidence = selected.lyrics_alignment_confidence ? `${Math.round(Number(selected.lyrics_alignment_confidence) * 100)}% match` : "Not scored";
  return <section className="editor-panel lyrics-panel"><header><div><span className="eyebrow">Waveform & lyric timing</span><h1>{selected.title}</h1><p>Use Suno timing when it is good, fall back to OpenAI when needed, then listen and refine each line.</p></div><div className="form-actions"><button className="secondary-button" disabled={busy} onClick={() => void sync(false)}><Sparkles />{busy ? "Aligning…" : "Auto-align lyrics"}</button><button className="secondary-button" disabled={busy || !selected.stream_url} onClick={() => void sync(true)}>Use OpenAI instead</button><button className="primary-button" onClick={() => void save()}><Save />Save timing</button></div></header>
    <div className="track-tabs">{tracks.map((track) => <button className={selected.id === track.id ? "active" : ""} key={track.id} onClick={() => setSelectedId(track.id)}>{track.title}</button>)}</div>
    <div className="alignment-status"><span className={`status-pill ${selected.lyrics_alignment_status === "ready" ? "success" : ""}`}>{selected.lyrics_alignment_status.replaceAll("_", " ")}</span><strong>{selected.lyrics_alignment_source ? `${selected.lyrics_alignment_source} timing` : "No alignment yet"}</strong><small>{confidence}</small><span className={`status-pill ${selected.musixmatch_delivery_status === "submitted" || selected.musixmatch_delivery_status === "ready" ? "success" : ""}`}>Musixmatch: {selected.musixmatch_delivery_status.replaceAll("_", " ")}</span></div>
    {error && <div className="banner error"><CircleAlert />{error}</div>}
    <audio ref={audio} src={selected.stream_url || undefined} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)} onLoadedMetadata={(event) => setDuration(event.currentTarget.duration)} />
    <div className="timing-wave"><button disabled={!selected.stream_url} onClick={() => void togglePlayback()}>{playing ? "❚❚" : "▶"}</button><span>{seconds(currentTime)}</span><Waveform progress={duration ? currentTime / duration : 0} onSeek={seek} /><span>{seconds(duration)}</span></div>
    <div className="lyric-editor-grid"><div className="cue-list">{cues.map((cue, index) => <div className="cue-row" key={`${index}-${cue.start_ms}`}><input aria-label="Start seconds" type="number" step="0.01" value={cue.start_ms / 1000} onChange={(event) => updateCue(index, { start_ms: Math.round(Number(event.target.value) * 1000) })} /><textarea value={cue.text} onChange={(event) => updateCue(index, { text: event.target.value })} /><button onClick={() => setCues(cues.filter((_, cueIndex) => cueIndex !== index))}>×</button></div>)}<button className="secondary-button" onClick={() => setCues([...cues, { start_ms: 0, end_ms: null, text: "", words: [] }])}>+ Add lyric line</button></div>
      <aside><span className="eyebrow">Import LRC</span><textarea rows={14} placeholder="[00:12.30]A narrower sky" value={lrc} onChange={(event) => setLrc(event.target.value)} /><button className="secondary-button" onClick={() => void importLrc()}>Parse & import</button><p>Imported lines remain fully editable. Existing timing is replaced only when you click import.</p></aside>
    </div>
  </section>;
}

function DeliveryPanel({ album, allTracks, reload, confirm }: { album: Album; allTracks: Track[]; reload: () => Promise<void>; confirm: React.Dispatch<React.SetStateAction<ConfirmAction | null>> }) {
  const [validation, setValidation] = useState<Validation | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [lyricsMessage, setLyricsMessage] = useState("");
  const existingIds = new Set(album.album_tracks?.map((item) => item.track.id));
  const available = allTracks.filter((track) => !existingIds.has(track.id));
  const check = async () => setValidation(await api<Validation>(`/api/studio/albums/${album.id}/validate/`));
  const submit = () => confirm({ title: `Publish ${album.title} through Too Lost?`, body: "This creates a real distributor submission from the immutable metadata snapshot shown here. After submission, the studio also prepares every synced lyric package and sends it automatically when Musixmatch partner access is configured.", action: async () => { await post<Submission>("/api/studio/submissions/", { album: album.id, kind: album.replaces_id ? "replacement" : "new" }); await reload(); } });
  const replace = () => confirm({ title: "Create a safe replacement?", body: "The new version will reuse every existing track record and ISRC, append the selected songs, and leave the current release live. Takedown should happen only after the replacement is accepted.", action: async () => { await post(`/api/studio/albums/${album.id}/replacement/`, { new_track_ids: selected }); await reload(); } });
  const takeDown = () => confirm({ title: `Take down ${album.title}?`, body: "This asks Too Lost to remove the old release. The studio will refuse unless a replacement version is already live, so listeners keep a valid release while stores process the change.", action: async () => { await post(`/api/studio/albums/${album.id}/takedown/`, {}); await reload(); } });
  const refresh = async () => { if (album.latest_submission) { await post(`/api/studio/submissions/${album.latest_submission.id}/refresh/`, {}); await reload(); } };
  const deliverLyrics = async () => {
    const result = await post<Record<string, number>>(`/api/studio/albums/${album.id}/deliver_lyrics/`, {});
    setLyricsMessage(`${result.submitted || 0} sent · ${result.needs_partner_access || 0} ready for Musixmatch Pro · ${result.not_ready || 0} need lyrics`);
    await reload();
  };
  const lyricTracks = album.album_tracks?.map((item) => item.track).filter((track) => !track.instrumental) || [];
  const lyricsReady = lyricTracks.filter((track) => track.lyrics && track.timed_lyrics.length).length;
  return <section className="editor-panel delivery-panel"><header><div><span className="eyebrow">Distribution</span><h1>Ready to share?</h1><p>Validate first. Submission and replacement are separate, confirmed operations.</p></div></header>
    <div className="delivery-grid"><article><ShieldCheck /><span className="eyebrow">Too Lost readiness</span><h2>{validation ? (validation.valid ? "Ready" : "Needs attention") : "Not checked"}</h2>{validation?.errors.map((error) => <p className="validation-error" key={error.field}><CircleAlert />{error.message}</p>)}{album.latest_submission && <p>Latest submission: <strong>{album.latest_submission.status}</strong>{album.latest_submission.error ? ` · ${album.latest_submission.error}` : ""}</p>}<div className="form-actions"><button className="secondary-button" onClick={() => void check()}>Run validation</button>{album.latest_submission?.too_lost_id && <button className="secondary-button" onClick={() => void refresh()}><RefreshCw />Refresh status</button>}<button className="primary-button" disabled={!validation?.valid} onClick={submit}>Publish through Too Lost <ArrowRight /></button></div></article>
      <article><Music2 /><span className="eyebrow">Synced lyrics</span><h2>{lyricsReady} of {lyricTracks.length} songs ready.</h2><p>Suno timing is used first and OpenAI fills the gaps. Partner-enabled Musixmatch delivery runs automatically after publishing.</p>{lyricTracks.map((track) => <div className="lyrics-delivery-row" key={track.id}><span>{track.title}</span><small>{track.musixmatch_delivery_status.replaceAll("_", " ")}</small></div>)}{lyricsMessage && <p className="form-message">{lyricsMessage}</p>}<div className="form-actions"><button className="secondary-button" onClick={() => void deliverLyrics()}>Prepare / send now</button><a className="secondary-button" href="https://pro.musixmatch.com" target="_blank" rel="noreferrer">Open Musixmatch Pro <ExternalLink /></a></div></article>
      <article><Sparkles /><span className="eyebrow">Safe album replacement</span><h2>Add songs without losing IDs.</h2><p>Create version {album.version + 1} with every existing track plus the selected new tracks. The old album remains untouched.</p><div className="replacement-tracks">{available.length ? available.map((track) => <label key={track.id}><input type="checkbox" checked={selected.includes(track.id)} onChange={(event) => setSelected(event.target.checked ? [...selected, track.id] : selected.filter((id) => id !== track.id))} />{track.title}<small>{track.isrc || "New ISRC needed"}</small></label>) : <p>No additional synced tracks are available.</p>}</div><div className="form-actions"><button className="secondary-button" disabled={!selected.length} onClick={replace}>Create replacement version</button>{album.status === "live" && <button className="danger-button" onClick={takeDown}>Take down old version</button>}</div></article>
    </div>
  </section>;
}

function LinksPanel({ album, reload }: { album: Album; reload: () => Promise<void> }) {
  const [platform, setPlatform] = useState("spotify"); const [url, setUrl] = useState(""); const [target, setTarget] = useState("album"); const [trackId, setTrackId] = useState(album.album_tracks?.[0]?.track.id || "");
  const links = useMemo(() => target === "artist" ? album.artist.platform_links : target === "album" ? album.platform_links : album.album_tracks?.find((item) => item.track.id === trackId)?.track.platform_links || [], [album, target, trackId]);
  const save = async (event: FormEvent) => { event.preventDefault(); await post<PlatformLink>("/api/studio/platform-links/", { platform, url, external_id: "", object_type: target, object_id: target === "artist" ? album.artist.id : target === "album" ? album.id : trackId }); setUrl(""); await reload(); };
  return <section className="editor-panel"><header><div><span className="eyebrow">Store destinations</span><h1>Find the songs elsewhere.</h1><p>Add the artist, album, and song URLs returned after delivery.</p></div></header>
    <div className="links-editor"><form onSubmit={save}><label>Link belongs to<select value={target} onChange={(event) => setTarget(event.target.value)}><option value="artist">Benjamin Locher</option><option value="album">This album</option><option value="track">A track</option></select></label>{target === "track" && <label>Track<select value={trackId} onChange={(event) => setTrackId(event.target.value)}>{album.album_tracks?.map((item) => <option value={item.track.id} key={item.track.id}>{item.track.title}</option>)}</select></label>}<label>Platform<select value={platform} onChange={(event) => setPlatform(event.target.value)}>{["spotify","apple_music","amazon_music","youtube_music","tidal","deezer","pandora","soundcloud","other"].map((value) => <option value={value} key={value}>{value.replace("_", " ")}</option>)}</select></label><label>Public URL<input type="url" required value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://…" /></label><button className="primary-button"><Link2 />Save store link</button></form><aside><span className="eyebrow">Published destinations</span>{links.length ? links.map((link) => <a href={link.url} target="_blank" rel="noreferrer" key={link.id}>{link.platform.replace("_", " ")}<ExternalLink /></a>) : <p>Links will appear here and on the public release page.</p>}</aside></div>
  </section>;
}
