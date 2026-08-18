// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// dxf / webifc 分支挂真实 DesignPanel 的集成测试（staging 交互 + scriptJump 联动）。
// DesignPanel 纯 REST+store 无 viewer context 依赖——这两个分支无需 ViewerProvider。

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render, act, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";

vi.mock("@/viewer/ViewerContext", () => ({
  ViewerProvider: ({ children }: { children?: ReactNode }) => (
    <div data-testid="viewer-provider">{children}</div>
  ),
}));
vi.mock("@/viewer/Toolbar", () => ({ Toolbar: () => null }));
vi.mock("@/viewer/ModelTreePanel", () => ({ ModelTreePanel: () => null }));
vi.mock("@/viewer/PropertyPanel", () => ({ PropertyPanel: () => null }));
vi.mock("@/viewer/IssuePanel", () => ({ IssuePanel: () => null }));
vi.mock("@/viewer/DiffPanel", () => ({ DiffPanel: () => null }));
vi.mock("@/viewer/ChatSidebar", () => ({ ChatSidebar: () => null }));
vi.mock("@/dxfviewer/DxfViewer", () => ({
  default: ({ modelId }: { modelId: string }) => <div data-testid="dxf-viewer">{modelId}</div>,
}));
vi.mock("@/ifcviewer/IfcLiteViewer", () => ({
  default: ({ modelId }: { modelId: string }) => <div data-testid="ifc-lite-viewer">{modelId}</div>,
}));

const api = vi.hoisted(() => ({
  fetchModel: vi.fn(),
  createChatSession: vi.fn(() => new Promise(() => {})), // 永不 resolve：本测试不关心 chat
  fetchScript: vi.fn(),
  fetchScriptParams: vi.fn(),
  fetchScriptVersions: vi.fn(),
  stageScript: vi.fn(),
  stageScriptParams: vi.fn(),
  scriptUndo: vi.fn(),
  scriptRedo: vi.fn(),
  discardScript: vi.fn(),
  runScript: vi.fn(),
  saveScript: vi.fn(),
  postScriptDiff: vi.fn(),
  fetchStagingDiff: vi.fn(),
}));
vi.mock("@/api/client", () => api);

import ViewerPage from "./ViewerPage";
import { useViewerStore } from "@/viewer/store";

const scriptText = 'PARAMS = {\n    "wall_t": 0.2,\n}\n';
const scriptState = {
  modelId: "m_1",
  script: scriptText,
  staged: 2,
  canUndo: true,
  canRedo: false,
  maxSteps: 10,
};

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

function setupScriptApi() {
  api.fetchScript.mockResolvedValue(scriptState);
  api.fetchScriptParams.mockResolvedValue({ modelId: "m_1", params: { wall_t: 0.2 } });
  api.fetchScriptVersions.mockResolvedValue({ modelId: "m_1", scripts: [], versions: [] });
  api.stageScriptParams.mockResolvedValue({ modelId: "m_1", staged: 3, canUndo: true, canRedo: false });
  api.stageScript.mockResolvedValue({ modelId: "m_1", staged: 3, canUndo: true, canRedo: false });
}

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
  vi.clearAllMocks();
  localStorage.clear();
  useViewerStore.setState({ stagedPreview: null, pendingModelReload: false, scriptJump: null });
  setupScriptApi();
});
afterEach(() => {
  cleanup();
  localStorage.clear();
  useViewerStore.setState({ stagedPreview: null, pendingModelReload: false, scriptJump: null });
});

describe("ViewerPage dxf 分支 DesignPanel 集成", () => {
  it("DesignPanel 加载脚本状态并完成 staging 交互（暂存修改 → PUT params）", async () => {
    api.fetchModel.mockResolvedValue(model("ready", "dxf"));
    renderPage();
    expect(await screen.findByTestId("dxf-viewer")).toBeTruthy();
    expect(await screen.findByText("暂存 2/10")).toBeTruthy();

    const num = (await screen.findByLabelText("wall_t")) as HTMLInputElement;
    expect(num.value).toBe("0.2");
    fireEvent.change(num, { target: { value: "0.35" } });
    fireEvent.click(screen.getByText("暂存修改"));
    await waitFor(() => expect(api.stageScriptParams).toHaveBeenCalledWith("m_1", { wall_t: 0.35 }));
  });

  it("scriptJump 联动：store 写入后 DesignPanel 切脚本编辑器并载入脚本", async () => {
    api.fetchModel.mockResolvedValue(model("ready", "dxf"));
    renderPage();
    expect(await screen.findByText("暂存 2/10")).toBeTruthy();
    act(() => {
      useViewerStore.getState().requestScriptJump({ line: 2, origin: "literal" });
    });
    const editor = (await screen.findByLabelText("脚本编辑器文本")) as HTMLTextAreaElement;
    expect(editor.value).toBe(scriptText);
    // 消费后清零，允许后续跳转
    expect(useViewerStore.getState().scriptJump).toBeNull();
  });
});

describe("ViewerPage webifc 分支 DesignPanel 集成", () => {
  it("webifc 引擎下 DesignPanel 渲染并加载脚本状态（ifc edit-service 同一套 REST）", async () => {
    localStorage.setItem("viewerEngine", "webifc");
    api.fetchModel.mockResolvedValue(model("ready", "ifc"));
    renderPage();
    expect(await screen.findByTestId("ifc-lite-viewer")).toBeTruthy();
    expect(await screen.findByText("暂存 2/10")).toBeTruthy();
    expect(api.fetchScript).toHaveBeenCalledWith("m_1");
  });
});
