export type PlatformLink = {
  id: number;
  platform: string;
  url: string;
  external_id: string;
};

export type Artist = {
  id: number;
  name: string;
  slug: string;
  bio: string;
  portrait_url: string;
  platform_links: PlatformLink[];
};

export type TimedLyric = {
  start_ms: number;
  end_ms: number | null;
  text: string;
  words?: Array<{ start_ms: number; end_ms: number; text: string }>;
};

export type Track = {
  id: string;
  suno_clip_id: string;
  title: string;
  slug: string;
  description: string;
  lyrics: string;
  timed_lyrics: TimedLyric[];
  cover_url: string;
  explicit: boolean;
  instrumental: boolean;
  duration_seconds: string | null;
  isrc: string;
  too_lost_track_id: string;
  source_image_url: string;
  audio_status: string;
  stream_url: string;
  mp3_download_url: string;
  wav_download_url: string;
  platform_links: PlatformLink[];
};

export type AlbumTrack = { id: number; position: number; track: Track };

export type Album = {
  id: string;
  title: string;
  slug: string;
  description: string;
  cover_url: string;
  source_cover_url: string;
  release_date: string | null;
  catalog_number: string;
  upc?: string;
  label_name?: string;
  copyright_line?: string;
  production_line?: string;
  status: string;
  public: boolean;
  version: number;
  artist: Artist;
  track_count: number;
  duration_seconds: string;
  platform_links: PlatformLink[];
  album_tracks?: AlbumTrack[];
  too_lost_release_id?: string;
  replaces_id?: string | null;
  latest_submission?: { id: number; kind: string; status: string; too_lost_id: string; error: string } | null;
};

export type Session = { authenticated: boolean; is_admin: boolean; name: string };
