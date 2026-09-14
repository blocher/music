import { useEffect, useState } from "react";
import { ArrowRight, Play } from "lucide-react";
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

  if (loading) return <div className="loading-screen">Finding the songs…</div>;
  if (!albums.length) {
    return (
      <>
        <section className="family-hero">
          <div className="hero-copy">
            <span className="eyebrow">Songs for real life</span>
            <h1>Our family makes songs.</h1>
            <p className="hero-deck">Come have a listen. These are songs for the kitchen, the car, and everywhere else.</p>
          </div>
          <img className="family-hero-art" src="/images/locher-family-band.webp" alt="A cheerful illustrated portrait of the six-member Locher family making music together" />
        </section>
        <section className="empty-catalog">
          <span className="eyebrow">Almost ready</span>
          <h2>We’re getting the first songs ready.</h2>
          <p>Check back soon for something new to play.</p>
        </section>
      </>
    );
  }

  const [featured] = albums;
  const firstTrack = featured.album_tracks?.[0]?.track;
  return (
    <>
      <section className="family-hero">
        <div className="hero-copy">
          <span className="eyebrow">Songs for real life</span>
          <h1>Our family makes songs.</h1>
          <p className="hero-deck">Come have a listen. These are songs for the kitchen, the car, and everywhere else.</p>
          <p className="newest-album">Newest album: <Link to={`/records/${featured.slug}`}>{featured.title}</Link></p>
          <div className="hero-actions">
            {firstTrack?.stream_url && (
              <button className="primary-button" onClick={() => player.play(firstTrack, featured)}><Play /> Play our songs</button>
            )}
            <a className="secondary-button" href="#albums">Browse albums <ArrowRight /></a>
          </div>
        </div>
        <img className="family-hero-art" src="/images/locher-family-band.webp" alt="A cheerful illustrated portrait of the six-member Locher family making music together" />
      </section>
      <section className="catalog-grid-section" id="albums">
        <div className="section-heading"><span className="eyebrow">Pick a little soundtrack</span><h2>Albums for whatever today is doing.</h2></div>
        <div className="album-grid">
          {albums.map((album) => (
            <Link className="album-card" to={`/records/${album.slug}`} key={album.id}>
              <img src={album.cover_url} alt={`${album.title} cover`} />
              <span>{album.track_count} songs · {album.release_date?.slice(0, 4)}</span>
              <h3>{album.title}</h3>
              <p>{album.description}</p>
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}
