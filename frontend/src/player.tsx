import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";

import type { Album, Track } from "./types";

type PlayerState = {
  track: Track | null;
  album: Album | null;
  playing: boolean;
  currentTime: number;
  duration: number;
  play: (track: Track, album: Album) => void;
  toggle: () => void;
  seek: (time: number) => void;
};

const PlayerContext = createContext<PlayerState | null>(null);

export function PlayerProvider({ children }: { children: ReactNode }) {
  const audio = useRef(new Audio());
  const [track, setTrack] = useState<Track | null>(null);
  const [album, setAlbum] = useState<Album | null>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  useEffect(() => {
    const element = audio.current;
    const update = () => {
      setCurrentTime(element.currentTime || 0);
      setDuration(element.duration || 0);
    };
    const stopped = () => setPlaying(false);
    element.addEventListener("timeupdate", update);
    element.addEventListener("durationchange", update);
    element.addEventListener("ended", stopped);
    return () => {
      element.pause();
      element.removeEventListener("timeupdate", update);
      element.removeEventListener("durationchange", update);
      element.removeEventListener("ended", stopped);
    };
  }, []);

  const play = (nextTrack: Track, nextAlbum: Album) => {
    if (!nextTrack.stream_url) return;
    if (track?.id !== nextTrack.id) {
      audio.current.src = nextTrack.stream_url;
      setTrack(nextTrack);
      setAlbum(nextAlbum);
    }
    void audio.current.play();
    setPlaying(true);
  };
  const toggle = () => {
    if (!track) return;
    const willPlay = audio.current.paused;
    if (willPlay) void audio.current.play();
    else audio.current.pause();
    setPlaying(willPlay);
  };
  const seek = (time: number) => {
    audio.current.currentTime = time;
    setCurrentTime(time);
  };

  return (
    <PlayerContext.Provider value={{ track, album, playing, currentTime, duration, play, toggle, seek }}>
      {children}
    </PlayerContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function usePlayer() {
  const context = useContext(PlayerContext);
  if (!context) throw new Error("Player context missing");
  return context;
}
