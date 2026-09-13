import { useEffect, useState } from "react";
import { ArrowRight, Download, Play } from "lucide-react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { usePlayer } from "../player";
import type { Album } from "../types";

export function HomePage() {
  const [albums, setAlbums] = useState<Album[]>([]);
  const [loading, setLoading] = useState(true);
  const player = usePlayer();
  useEffect(() => {
    void api<Album[]>("/api/public/albums/")
      .then(async (items) => {
        if (!items.length) return items;
        const featured = await api<Album>(`/api/public/albums/${items[0].slug}/`);
        return [featured, ...items.slice(1)];
      })
      .then(setAlbums)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading-screen">Gathering the records…</div>;
  if (!albums.length) {
    return (
      <section className="empty-catalog">
        <span className="eyebrow">Benjamin Locher / collected works</span>
        <h1>Music for the<br />space between.</h1>
        <p>The first records are being prepared for listening.</p>
        <div className="fine-rule" />
        <small>Independent sounds · AI-assisted · Human intention</small>
      </section>
    );
  }

  const [featured, ...others] = albums;
  const firstTrack = featured.album_tracks?.[0]?.track;
  return (
    <>
      <section className="record-hero">
        <Link className="cover-frame" to={`/records/${featured.slug}`}>
          <img src={featured.cover_url} alt={`${featured.title} cover`} />
          <span className="cover-catalog">{featured.catalog_number || "NEW RECORD"}</span>
        </Link>
        <div className="hero-copy">
          <span className="eyebrow">New album — {featured.catalog_number || "independent release"}</span>
          <h1>{featured.title}</h1>
          <p className="hero-deck">{featured.description || "A new collection of songs by Benjamin Locher."}</p>
          <div className="hero-actions">
            {firstTrack?.stream_url && (
              <button className="primary-button" onClick={() => player.play(firstTrack, featured)}><Play /> Play the album</button>
            )}
            {firstTrack?.wav_download_url && <a className="text-button" href={firstTrack.wav_download_url} download><Download /> Download WAV</a>}
          </div>
          <div className="record-facts">
            <span>{featured.track_count} tracks</span><span>{featured.release_date?.slice(0, 4)}</span><span>Benjamin Locher</span>
          </div>
          <Link className="story-link" to={`/records/${featured.slug}`}>Enter the record <ArrowRight /></Link>
        </div>
      </section>
      {others.length > 0 && (
        <section className="catalog-grid-section">
          <div className="section-heading"><span className="eyebrow">Earlier works</span><h2>Records for slower listening.</h2></div>
          <div className="album-grid">
            {others.map((album) => (
              <Link className="album-card" to={`/records/${album.slug}`} key={album.id}>
                <img src={album.cover_url} alt="" />
                <span>{album.release_date?.slice(0, 4)}</span>
                <h3>{album.title}</h3>
                <p>{album.description}</p>
              </Link>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
