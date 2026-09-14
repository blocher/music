import { useEffect, useState } from "react";

import { api } from "../api";
import { PlatformLinks } from "../components/PlatformLinks";
import type { Artist } from "../types";

export function AboutPage() {
  const [artist, setArtist] = useState<Artist | null>(null);
  useEffect(() => { void api<Artist>("/api/public/artist/").then(setArtist); }, []);
  if (!artist) return <div className="loading-screen">Finding the family notes…</div>;
  return (
    <article className="about-page">
      <div className="about-portrait" style={{ backgroundImage: `url(${artist.portrait_url || "/images/locher-family-band.webp"})` }} />
      <div className="about-copy">
        <span className="eyebrow">About the songs</span>
        <h1>{artist.name}</h1>
        <p className="lead">Songs for the kitchen, the car, and wherever we wind up.</p>
        <div className="prose">{artist.bio || "Locher songs are little family experiments: ideas from ordinary days, made into music with a lot of curiosity and a little help from AI. Pick one, turn it up, and join in."}</div>
        <PlatformLinks links={artist.platform_links} />
      </div>
    </article>
  );
}
