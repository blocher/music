import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StudioPage } from "./StudioPage";

afterEach(() => vi.restoreAllMocks());

const response = (payload: unknown) => ({ ok: true, status: 200, json: async () => payload });

describe("StudioPage", () => {
  it("keeps visible progress after a Suno sync is queued", async () => {
    let syncStarted = false;
    const currentRun = { id: 2, status: "queued", albums_seen: 0, tracks_seen: 0, loose_tracks_excluded: 0, created_at: "2026-09-14T03:00:00Z", error: "" };
    const oldRun = { ...currentRun, id: 1, status: "succeeded", created_at: "2026-09-13T03:00:00Z" };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, options?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/studio/sync-runs/") && options?.method === "POST") {
        syncStarted = true;
        return response(currentRun);
      }
      if (url.endsWith("/api/studio/sync-runs/")) return response(syncStarted ? [currentRun, oldRun] : [oldRun]);
      if (url.endsWith("/api/studio/albums/")) return response({ count: 0, results: [] });
      if (url.includes("/api/studio/integrations/")) return response({ connected: true });
      if (url.endsWith("/api/studio/download-budget/")) return response({ used: 0, limit: 20, remaining: 20, period: "2026-09", resets_at: "" });
      throw new Error(`Unexpected request: ${url}`);
    }));

    render(<MemoryRouter><StudioPage /></MemoryRouter>);
    const button = await screen.findByRole("button", { name: /sync from suno/i });

    fireEvent.click(button);

    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/Suno sync queued/i));
    expect(screen.getByRole("button", { name: /Syncing Suno/i })).toBeDisabled();
  });
});
