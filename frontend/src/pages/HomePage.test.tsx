import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PlayerProvider } from "../player";
import { HomePage } from "./HomePage";

afterEach(() => vi.restoreAllMocks());

describe("HomePage", () => {
  it("shows an intentional empty state before the first public release", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => [] }));

    render(<MemoryRouter><PlayerProvider><HomePage /></PlayerProvider></MemoryRouter>);

    await waitFor(() => expect(screen.getByText(/Our family makes songs/)).toBeInTheDocument());
    expect(screen.getByText(/getting the first songs ready/i)).toBeInTheDocument();
  });
});
