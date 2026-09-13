import { ExternalLink } from "lucide-react";

import type { PlatformLink } from "../types";

const labels: Record<string, string> = {
  spotify: "Spotify",
  apple_music: "Apple Music",
  amazon_music: "Amazon Music",
  youtube_music: "YouTube Music",
  tidal: "Tidal",
  deezer: "Deezer",
  pandora: "Pandora",
  soundcloud: "SoundCloud",
  other: "Listen",
};

export function PlatformLinks({ links, compact = false }: { links: PlatformLink[]; compact?: boolean }) {
  if (!links.length) return null;
  return (
    <div className={compact ? "platform-links compact" : "platform-links"}>
      {links.map((link) => (
        <a key={link.id} href={link.url} target="_blank" rel="noreferrer">
          {labels[link.platform] ?? link.platform} <ExternalLink size={compact ? 12 : 15} />
        </a>
      ))}
    </div>
  );
}
