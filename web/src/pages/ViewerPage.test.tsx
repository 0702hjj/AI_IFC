// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render, act, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";

const mounts = vi.hoisted(() => ({ count: 0, dxf: 0, ifcLite: 0 }));
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
vi.mock("@/viewer/DesignPanel", () => ({
  DesignPanel: ({ modelId }: { modelId: string }) => (
    <div data-testid="design-panel">{modelId}</div>
  ),
}));
vi.mock("@/viewer/ChatSidebar", () => ({ ChatSidebar: () => null }));
vi.mock("@/dxfviewer/DxfViewer", async () => {
  const React = await import("react");
  function MockDxfViewer({ modelId }: { modelId: string }) {
    React.useEffect(() => {
      mounts.dxf += 1;
    }, []);
    return <div data-testid="dxf-viewer">{modelId}</div>;
  }
  return { default: MockDxfViewer };
});
vi.mock("@/ifcviewer/IfcLiteViewer", async () => {
  const React = await import("react");
  function MockIfcLiteViewer({ modelId }: { modelId: string }) {
    React.useEffect(() => {
      mounts.ifcLite += 1;
    }, []);
    return <div data-testid="ifc-lite-viewer">{modelId}</div>;
  }
  return { default: MockIfcLiteViewer };
});

const api = vi.hoisted(() => ({
  fetchModel: vi.fn(),
  createChatSession: vi.fn(() => new Promise(() => {})), // 永不 resolve：本测试不关心 chat
  listChatSessions: vi.fn(() => Promise.resolve([])),
}));
vi.mock("@/api/client", () => api);

import ViewerPage from "./ViewerPage";
import { useViewerStore } from "@/viewer/store";

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

describe("ViewerPage engine switch (ifc)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mounts.count = 0;
    vi.clearAllMocks();
    localStorage.clear();
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    localStorage.clear();
  });

  it("defaults to the xeokit engine when viewerEngine is unset", async () => {
    api.fetchModel.mockResolvedValue(model("ready", "ifc"));
    renderPage();
    await act(async () => {});
    expect(screen.queryByTestId("viewer-provider")).toBeTruthy();
    expect(screen.queryByTestId("ifc-lite-viewer")).toBeNull();
  });

  it("falls back to xeokit when viewerEngine holds an invalid value", async () => {
    localStorage.setItem("viewerEngine", "garbage");
    api.fetchModel.mockResolvedValue(model("ready", "ifc"));
    renderPage();
    await act(async () => {});
    expect(screen.queryByTestId("viewer-provider")).toBeTruthy();
    expect(screen.queryByTestId("ifc-lite-viewer")).toBeNull();
  });

  it("renders the web-ifc viewer when viewerEngine=webifc", async () => {
    localStorage.setItem("viewerEngine", "webifc");
    api.fetchModel.mockResolvedValue(model("ready", "ifc"));
    renderPage();
    await act(async () => {});
    expect(screen.queryByTestId("ifc-lite-viewer")).toBeTruthy();
    expect(screen.queryByTestId("viewer-provider")).toBeNull();
    expect(screen.queryByTestId("dxf-viewer")).toBeNull();
  });

  it("switch button toggles the engine, persists it and remounts the viewer", async () => {
    api.fetchModel.mockResolvedValue(model("ready", "ifc"));
    renderPage();
    await act(async () => {});
    expect(screen.queryByTestId("viewer-provider")).toBeTruthy();

    const btn = screen.getByRole("button", { name: "web-ifc 引擎" });
    await act(async () => {
      btn.click();
    });
    expect(localStorage.getItem("viewerEngine")).toBe("webifc");
    expect(screen.queryByTestId("ifc-lite-viewer")).toBeTruthy();
    expect(screen.queryByTestId("viewer-provider")).toBeNull();

    // 再切回 xeokit
    const back = screen.getByRole("button", { name: "xeokit 引擎" });
    await act(async () => {
      back.click();
    });
    expect(localStorage.getItem("viewerEngine")).toBe("xeokit");
    expect(screen.queryByTestId("viewer-provider")).toBeTruthy();
    expect(screen.queryByTestId("ifc-lite-viewer")).toBeNull();
  });

  it("dxf models ignore the engine switch (dxf viewer always)", async () => {
    localStorage.setItem("viewerEngine", "webifc");
    api.fetchModel.mockResolvedValue(model("ready", "dxf"));
    renderPage();
    await act(async () => {});
    expect(screen.queryByTestId("dxf-viewer")).toBeTruthy();
    expect(screen.queryByTestId("ifc-lite-viewer")).toBeNull();
    expect(screen.queryByTestId("viewer-provider")).toBeNull();
  });
});

describe("ViewerPage staged preview (viewer.staged 中途刷新)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mounts.count = 0;
    mounts.dxf = 0;
    mounts.ifcLite = 0;
    vi.clearAllMocks();
    localStorage.clear();
    useViewerStore.setState({ stagedPreview: null, pendingModelReload: false });
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    localStorage.clear();
    useViewerStore.setState({ stagedPreview: null, pendingModelReload: false });
  });

  // 模拟 ChatSidebar 收到 viewer.staged 后写入 store
  const staged = (modelId: string, kind: "ifc" | "dxf") =>
    act(() => {
      useViewerStore.getState().flagStagedPreview({ modelId, kind });
    });

  it("kind=dxf：直接重载 DXF 画布，连续多次事件每次都生效（nonce）", async () => {
    api.fetchModel.mockResolvedValue(model("ready", "dxf"));
    renderPage();
    await act(async () => {});
    expect(mounts.dxf).toBe(1);
    staged("m_1", "dxf");
    await act(async () => {});
    expect(mounts.dxf).toBe(2);
    staged("m_1", "dxf");
    await act(async () => {});
    expect(mounts.dxf).toBe(3);
    expect(screen.queryByText(/AI 中间结果/)).toBeNull();
  });

  it("kind=ifc 且引擎 webifc：自动重挂 IfcLiteViewer，不出角标", async () => {
    localStorage.setItem("viewerEngine", "webifc");
    api.fetchModel.mockResolvedValue(model("ready", "ifc"));
    renderPage();
    await act(async () => {});
    expect(mounts.ifcLite).toBe(1);
    staged("m_1", "ifc");
    await act(async () => {});
    expect(mounts.ifcLite).toBe(2);
    expect(screen.queryByText(/AI 中间结果/)).toBeNull();
  });

  it("kind=ifc 且引擎 xeokit：不自动重载，出角标点击后才重载", async () => {
    api.fetchModel.mockResolvedValue(model("ready", "ifc"));
    renderPage();
    await act(async () => {});
    expect(mounts.count).toBe(1);
    staged("m_1", "ifc");
    await act(async () => {});
    expect(mounts.count).toBe(1); // 重转 XKT 慢且闪烁，不自动重载
    const btn = screen.getByText("AI 中间结果 · 点击预览");
    await act(async () => {
      btn.click();
    });
    expect(mounts.count).toBe(2);
    expect(screen.queryByText("AI 中间结果 · 点击预览")).toBeNull();
  });

  it("其他 modelId 的 staged 事件被忽略（不刷新、不出角标）", async () => {
    api.fetchModel.mockResolvedValue(model("ready", "dxf"));
    renderPage();
    await act(async () => {});
    expect(mounts.dxf).toBe(1);
    staged("m_other", "dxf");
    await act(async () => {});
    expect(mounts.dxf).toBe(1);
    expect(screen.queryByText(/AI 中间结果/)).toBeNull();
  });
});

describe("ViewerPage DesignPanel 挂载（dxf/webifc 分支）", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mounts.count = 0;
    mounts.dxf = 0;
    mounts.ifcLite = 0;
    vi.clearAllMocks();
    localStorage.clear();
    useViewerStore.setState({ stagedPreview: null, pendingModelReload: false });
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    localStorage.clear();
    useViewerStore.setState({ stagedPreview: null, pendingModelReload: false });
  });

  it("kind=dxf：DxfViewer 与 DesignPanel 并列挂载（无 ViewerProvider）", async () => {
    api.fetchModel.mockResolvedValue(model("ready", "dxf"));
    renderPage();
    await act(async () => {});
    expect(screen.queryByTestId("dxf-viewer")).toBeTruthy();
    expect(screen.queryByTestId("viewer-provider")).toBeNull();
    const panel = screen.getByTestId("design-panel");
    expect(panel.textContent).toBe("m_1");
  });

  it("webifc 引擎：IfcLiteViewer 与 DesignPanel 并列挂载", async () => {
    localStorage.setItem("viewerEngine", "webifc");
    api.fetchModel.mockResolvedValue(model("ready", "ifc"));
    renderPage();
    await act(async () => {});
    expect(screen.queryByTestId("ifc-lite-viewer")).toBeTruthy();
    expect(screen.queryByTestId("viewer-provider")).toBeNull();
    expect(screen.getByTestId("design-panel").textContent).toBe("m_1");
  });

  it("xeokit 分支不回归：DesignPanel 仍在 ViewerProvider 内", async () => {
    api.fetchModel.mockResolvedValue(model("ready", "ifc"));
    renderPage();
    await act(async () => {});
    const provider = screen.getByTestId("viewer-provider");
    expect(provider.querySelector('[data-testid="design-panel"]')).toBeTruthy();
  });

  it("dxf staged 中途刷新重挂 DxfViewer 后 DesignPanel 保持挂载", async () => {
    api.fetchModel.mockResolvedValue(model("ready", "dxf"));
    renderPage();
    await act(async () => {});
    expect(mounts.dxf).toBe(1);
    act(() => {
      useViewerStore.getState().flagStagedPreview({ modelId: "m_1", kind: "dxf" });
    });
    await act(async () => {});
    expect(mounts.dxf).toBe(2);
    expect(screen.getByTestId("design-panel")).toBeTruthy();
  });
});
