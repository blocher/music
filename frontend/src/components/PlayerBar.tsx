import { Download, Pause, Play, Volume2 } from "lucide-react";

import { usePlayer } from "../player";
import { Waveform } from "./Waveform";

const formatTime = (value: number) => {
  if (!Number.isFinite(value)) return "0:00";
  const minutes = Math.floor(value / 60);
  const seconds = Math.floor(value % 60);
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
};

export function PlayerBar() {
  const player = usePlayer();
  if (!player.track || !player.album) return null;
  const progress = player.duration ? player.currentTime / player.duration : 0;
  return (
    <aside className="player-bar" aria-label="Now playing">
      <div className="player-art" style={{ backgroundImage: `url(${player.album.cover_url})` }} />
      <div className="player-title">
        <strong>{player.track.title}</strong>
        <span>{player.album.title} — Benjamin Locher</span>
      </div>
      <button className="round-control" onClick={player.toggle} aria-label={player.playing ? "Pause" : "Play"}>
        {player.playing ? <Pause /> : <Play />}
      </button>
      <span className="player-time">{formatTime(player.currentTime)}</span>
      <Waveform progress={progress} onSeek={(ratio) => player.seek(ratio * player.duration)} />
      <span className="player-time">{formatTime(player.duration)}</span>
      <Volume2 className="player-volume" />
      {player.track.mp3_download_url && (
        <a className="icon-button" href={player.track.mp3_download_url} download aria-label="Download MP3"><Download /></a>
      )}
    </aside>
  );
}
