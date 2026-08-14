// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render, act, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";

const mounts = vi.hoisted(() => ({ count: 0 }));
vi.mock("@/viewer/ViewerContext", async () => {
  const React = await import("react");
  return {
    ViewerProvider: ({ children }: { children?: ReactNode }) => {
      React.useEffect(() => {
        mounts.count += 1;
      }, []);
      return <div data-testid="viewer-provider">{children}</div>;
    },
  };
});
vi.mock("@/viewer/Toolbar", () => ({ Toolbar: () => null }));
vi.mock("@/viewer/ModelTreePanel", () => ({ ModelTreePanel: () => null }));
vi.mock("@/viewer/PropertyPanel", () => ({ PropertyPanel: () => null }));
vi.mock("@/viewer/IssuePanel", () => ({ IssuePanel: () => null }));
vi.mock("@/viewer/DiffPanel", () => ({ DiffPanel: () => null }));
vi.mock("@/viewer/DesignPanel", () => ({ DesignPanel: () => null }));
vi.mock("@/viewer/ChatSidebar", () => ({ ChatSidebar: () => null }));
vi.mock("@/dxfviewer/DxfViewer", () => ({
  default: ({ modelId }: { modelId: string }) => <div data-testid="dxf-viewer">{modelId}</div>,
}));

const api = vi.hoisted(() => ({
  fetchModel: vi.fn(),
  createChatSession: vi.fn(() => new Promise(() => {})), // 永不 resolve：本测试不关心 chat
  listChatSessions: vi.fn(() => Promise.resolve([])),
}));
vi.mock("@/api/client", () => api);

import ViewerPage from "./ViewerPage";

const model = (status: string, kind?: string) => ({
  id: "m_1",
  name: "m",
  size: 1,
  status,
  createdAt: "2026-07-29T00:00:00Z",
  error: "",
  ...(kind !== undefined ? { kind } : {}),
});

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/view/m_1"]}>
      <Routes>
        <Route path="/view/:id" element={<ViewerPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("ViewerPage auto reload", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mounts.count = 0;
    vi.clearAllMocks();
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("polls while converting and reloads the viewer once ready", async () => {
    api.fetchModel
      .mockResolvedValueOnce(model("converting"))
      .mockResolvedValue(model("ready"));
    renderPage();
    await act(async () => {});
    expect(mounts.count).toBe(1);
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });
    expect(api.fetchModel).toHaveBeenCalledTimes(2);
    expect(mounts.count).toBe(2);
    await act(async () => {
      vi.advanceTimersByTime(4000);
    });
    expect(mounts.count).toBe(2);
  });

  it("does not reload while status stays ready", async () => {
    api.fetchModel.mockResolvedValue(model("ready"));
    renderPage();
    await act(async () => {});
    await act(async () => {
      vi.advanceTimersByTime(6000);
    });
    expect(mounts.count).toBe(1);
  });

  it("reloads again after an external re-conversion", async () => {
    api.fetchModel
      .mockResolvedValueOnce(model("ready"))
      .mockResolvedValueOnce(model("converting"))
      .mockResolvedValue(model("ready"));
    renderPage();
    await act(async () => {});
    expect(mounts.count).toBe(1);
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });
    expect(mounts.count).toBe(1);
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });
    expect(mounts.count).toBe(2);
  });
});

describe("ViewerPage kind routing", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mounts.count = 0;
    vi.clearAllMocks();
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("routes kind=dxf models to the DXF canvas viewer (no XKT provider)", async () => {
    api.fetchModel.mockResolvedValue(model("ready", "dxf"));
    renderPage();
    await act(async () => {});
    expect(screen.queryByTestId("dxf-viewer")).toBeTruthy();
    expect(screen.queryByTestId("viewer-provider")).toBeNull();
    expect(mounts.count).toBe(0);
  });

  it("routes kind-less models to the XKT viewer (legacy default ifc)", async () => {
    api.fetchModel.mockResolvedValue(model("ready"));
    renderPage();
    await act(async () => {});
    expect(screen.queryByTestId("viewer-provider")).toBeTruthy();
    expect(screen.queryByTestId("dxf-viewer")).toBeNull();
  });

  it("routes kind=ifc models to the XKT viewer", async () => {
    api.fetchModel.mockResolvedValue(model("ready", "ifc"));
    renderPage();
    await act(async () => {});
    expect(screen.queryByTestId("viewer-provider")).toBeTruthy();
    expect(screen.queryByTestId("dxf-viewer")).toBeNull();
  });
});
