// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

import { describe, it, expect, afterEach, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const api = vi.hoisted(() => ({
  listModels: vi.fn(async () => [] as unknown[]),
  uploadModel: vi.fn(),
  deleteModel: vi.fn(),
  retryModel: vi.fn(),
  createChatProject: vi.fn(),
  fetchModel: vi.fn(),
  downloadUrl: (id: string) => `/api/v1/models/${id}/download`,
}));
vi.mock("@/api/client", () => api);

import LibraryPage from "./LibraryPage";

const model = (id: string, kind?: string) => ({
  id,
  name: id,
  size: 1,
  status: "ready",
  createdAt: "2026-08-13T00:00:00Z",
  error: "",
  ...(kind !== undefined ? { kind } : {}),
});

function renderPage() {
  return render(
    <MemoryRouter>
      <LibraryPage />
    </MemoryRouter>
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("LibraryPage kind badge", () => {
  it("shows DXF badge for kind=dxf models and IFC for kind-less models", async () => {
    api.listModels.mockResolvedValue([model("m_dxf", "dxf"), model("m_legacy")]);
    renderPage();
    await waitFor(() => expect(screen.getByText("DXF")).toBeTruthy());
    expect(screen.getByText("IFC")).toBeTruthy();
  });

  it("shows IFC badge for explicit kind=ifc models", async () => {
    api.listModels.mockResolvedValue([model("m_ifc", "ifc")]);
    renderPage();
    await waitFor(() => expect(screen.getByText("IFC")).toBeTruthy());
    expect(screen.queryByText("DXF")).toBeNull();
  });
});
