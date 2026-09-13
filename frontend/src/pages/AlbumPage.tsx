import { useEffect, useMemo, useState } from "react";
import { Download, Pause, Play } from "lucide-react";
import { useParams } from "react-router-dom";

import { api } from "../api";
import { PlatformLinks } from "../components/PlatformLinks";
import { usePlayer } from "../player";
import type { Album, Track } from "../types";

const duration = (value: string | null) => {
  const total = Number(value || 0);
  return `${Math.floor(total / 60)}:${Math.floor(total % 60).toString().padStart(2, "0")}`;
};

export function AlbumPage() {
  const { slug } = useParams();
  const [album, setAlbum] = useState<Album | null>(null);
  const [selected, setSelected] = useState<Track | null>(null);
  const player = usePlayer();
  useEffect(() => { void api<Album>(`/api/public/albums/${slug}/`).then((data) => { setAlbum(data); setSelected(data.album_tracks?.[0]?.track ?? null); }); }, [slug]);
  const currentCue = useMemo(() => selected?.timed_lyrics.find((cue, index, cues) => {
    const next = cues[index + 1];
    return player.currentTime * 1000 >= cue.start_ms && (!next || player.currentTime * 1000 < next.start_ms);
  }), [selected, player.currentTime]);
  if (!album) return <div className="loading-screen">Opening the record…</div>;

  return (
    <article className="album-page">
      <section className="album-story">
        <img className="album-cover-large" src={album.cover_url} alt={`${album.title} cover`} />
        <div>
          <span className="eyebrow">Release story</span>
          <h1>{album.title}</h1>
          <p className="album-description">{album.description}</p>
          <div className="record-facts"><span>{album.track_count} tracks</span><span>{album.release_date}</span><span>{album.catalog_number}</span></div>
          <PlatformLinks links={album.platform_links} />
        </div>
      </section>
      <section className="track-section">
        <header><span className="eyebrow">Tracks</span><h2>Listen & read</h2></header>
        <div className="track-list">
          {album.album_tracks?.map(({ track, position }) => {
            const isPlaying = player.playing && player.track?.id === track.id;
            return (
              <div className={selected?.id === track.id ? "track-row selected" : "track-row"} key={track.id} onClick={() => setSelected(track)}>
                <span className="track-number">{position.toString().padStart(2, "0")}</span>
                <button className="round-control small" disabled={!track.stream_url} onClick={(event) => { event.stopPropagation(); if (isPlaying) player.toggle(); else player.play(track, album); }}>
                  {isPlaying ? <Pause /> : <Play />}
                </button>
                <div className="track-name"><strong>{track.title}</strong><span>{track.description}</span></div>
                <span>{duration(track.duration_seconds)}</span>
                {track.wav_download_url && <a className="icon-button" href={track.wav_download_url} download onClick={(event) => event.stopPropagation()}><Download /></a>}
                <PlatformLinks links={track.platform_links} compact />
              </div>
            );
          })}
        </div>
      </section>
      {selected && (selected.lyrics || selected.timed_lyrics.length > 0) && (
        <section className="lyric-listener">
          <div><span className="eyebrow">Lyrics / {selected.title}</span><h2>{currentCue?.text || selected.title}</h2></div>
          <div className="lyrics-body">
            {selected.timed_lyrics.length ? selected.timed_lyrics.map((cue) => (
              <p key={`${cue.start_ms}-${cue.text}`} className={cue === currentCue ? "active" : ""}>{cue.text}<time>{duration(String(cue.start_ms / 1000))}</time></p>
            )) : <div className="plain-lyrics">{selected.lyrics}</div>}
          </div>
        </section>
      )}
    </article>
  );
}
