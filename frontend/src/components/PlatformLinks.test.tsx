import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlatformLinks } from "./PlatformLinks";

describe("PlatformLinks", () => {
  it("renders distributor links with recognizable platform names", () => {
    render(
      <PlatformLinks
        links={[
          { id: 1, platform: "spotify", url: "https://open.spotify.com/album/1", external_id: "1" },
          { id: 2, platform: "apple_music", url: "https://music.apple.com/album/1", external_id: "1" },
        ]}
      />,
    );

    expect(screen.getByRole("link", { name: /Spotify/ })).toHaveAttribute("href", "https://open.spotify.com/album/1");
    expect(screen.getByRole("link", { name: /Apple Music/ })).toHaveAttribute("href", "https://music.apple.com/album/1");
  });
});
