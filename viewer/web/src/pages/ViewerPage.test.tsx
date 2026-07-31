// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render, act } from "@testing-library/react";
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

const api = vi.hoisted(() => ({ fetchModel: vi.fn() }));
vi.mock("@/api/client", () => api);

import ViewerPage from "./ViewerPage";

const model = (status: string) => ({
  id: "m_1",
  name: "m",
  size: 1,
  status,
  createdAt: "2026-07-29T00:00:00Z",
  error: "",
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
