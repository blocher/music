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

    await waitFor(() => expect(screen.getByText(/Music for the/)).toBeInTheDocument());
    expect(screen.getByText(/first records are being prepared/i)).toBeInTheDocument();
  });
});
