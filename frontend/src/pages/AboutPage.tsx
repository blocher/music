import { useEffect, useState } from "react";

import { api } from "../api";
import { PlatformLinks } from "../components/PlatformLinks";
import type { Artist } from "../types";

export function AboutPage() {
  const [artist, setArtist] = useState<Artist | null>(null);
  useEffect(() => { void api<Artist>("/api/public/artist/").then(setArtist); }, []);
  if (!artist) return <div className="loading-screen">Opening the artist notes…</div>;
  return (
    <article className="about-page">
      <div className="about-portrait" style={{ backgroundImage: artist.portrait_url ? `url(${artist.portrait_url})` : undefined }} />
      <div className="about-copy">
        <span className="eyebrow">Artist notes</span>
        <h1>{artist.name}</h1>
        <p className="lead">Independent music made with machines, patience, and human intention.</p>
        <div className="prose">{artist.bio || "Benjamin Locher makes records for attentive listening: songs shaped by atmosphere, memory, technology, and the small human decisions that give a generated sound a life of its own."}</div>
        <PlatformLinks links={artist.platform_links} />
      </div>
    </article>
  );
}
