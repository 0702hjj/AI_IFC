// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor, act } from "@testing-library/react";
import { useViewerStore } from "./store";

const api = vi.hoisted(() => ({
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

import { DesignPanel } from "./DesignPanel";

const scriptText = 'PARAMS = {\n    "wall_t": 0.2,\n}\n';
const scriptState = {
  modelId: "m_1",
  script: scriptText,
  staged: 2,
  canUndo: true,
  canRedo: false,
  maxSteps: 10,
};
const params = {
  wall_t: 0.2,
  name: "demo",
  flat: true,
  axis: [0, 0],
  frame: { storeys: 2 },
};
const versions = {
  modelId: "m_1",
  scripts: [
    { version: "v1", createdAt: "t1", note: "" },
    { version: "v2", createdAt: "t2", note: "n2" },
  ],
  versions: [{ version: "v1", createdAt: "t1" }],
};
const stagingDiff = {
  from: 1,
  to: 2,
  text_diff: "--- step1\n+++ step2\n-wall_t = 0.2\n+wall_t = 0.3\n",
  params_changes: [{ key: "wall_t", action: "modified", old: 0.2, new: 0.3 }],
  stats: { added: 1, removed: 1 },
};
const bigDiff = {
  base: "v1",
  target: "v2",
  engine: "script",
  text_diff: "@@ v1 -> v2 @@\n",
  params_changes: [{ key: "name", action: "modified", old: "a", new: "b" }],
  stats: { added: 1, removed: 0 },
};

function setup(opts?: {
  state?: unknown;
  params?: unknown;
  versions?: unknown;
  scriptError?: Error;
  paramsError?: Error;
}) {
  vi.clearAllMocks();
  useViewerStore.setState({ pendingModelReload: false, scriptJump: null });
  if (opts?.scriptError) api.fetchScript.mockRejectedValue(opts.scriptError);
  else api.fetchScript.mockResolvedValue(opts?.state ?? scriptState);
  if (opts?.paramsError) api.fetchScriptParams.mockRejectedValue(opts.paramsError);
  else api.fetchScriptParams.mockResolvedValue({ modelId: "m_1", params: opts?.params ?? params });
  api.fetchScriptVersions.mockResolvedValue(opts?.versions ?? versions);
  api.stageScriptParams.mockResolvedValue({ modelId: "m_1", staged: 3, canUndo: true, canRedo: false });
  api.stageScript.mockResolvedValue({ modelId: "m_1", staged: 3, canUndo: true, canRedo: false });
  api.scriptUndo.mockResolvedValue({ modelId: "m_1", script: scriptText, canRedo: true });
  api.scriptRedo.mockResolvedValue({ modelId: "m_1", script: scriptText, canUndo: true });
  api.discardScript.mockResolvedValue({ modelId: "m_1", discarded: 2, script: scriptText });
  api.runScript.mockResolvedValue({ modelId: "m_1", ok: true });
  api.saveScript.mockResolvedValue({ modelId: "m_1", version: "v3", staged: 0 });
  api.postScriptDiff.mockResolvedValue(bigDiff);
  api.fetchStagingDiff.mockResolvedValue(stagingDiff);
}

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
  setup();
});
afterEach(cleanup);

describe("DesignPanel PARAMS 表单", () => {
  it("renders PARAMS fields by value type (number/string/boolean/json/nested)", async () => {
    render(<DesignPanel modelId="m_1" />);
    expect(await screen.findByText("暂存 2/10")).toBeTruthy();
    const num = screen.getByLabelText("wall_t") as HTMLInputElement;
    expect(num.value).toBe("0.2");
    const str = screen.getByLabelText("name") as HTMLInputElement;
    expect(str.value).toBe("demo");
    const bool = screen.getByLabelText("flat") as HTMLInputElement;
    expect(bool.type).toBe("checkbox");
    expect(bool.checked).toBe(true);
    const arr = screen.getByLabelText("axis") as HTMLTextAreaElement;
    expect(arr.tagName).toBe("TEXTAREA");
    expect(arr.value).toBe("[0,0]");
    // nested object flattened to a dotted path
    expect((screen.getByLabelText("frame.storeys") as HTMLInputElement).value).toBe("2");
  });

  it("暂存修改 posts merged params via PUT params mode", async () => {
    render(<DesignPanel modelId="m_1" />);
    const num = (await screen.findByLabelText("wall_t")) as HTMLInputElement;
    fireEvent.change(num, { target: { value: "0.35" } });
    fireEvent.click(screen.getByText("暂存修改"));
    await waitFor(() =>
      expect(api.stageScriptParams).toHaveBeenCalledWith("m_1", {
        ...params,
        wall_t: 0.35,
      })
    );
  });

  it("toggling a boolean checkbox flips the submitted value", async () => {
    render(<DesignPanel modelId="m_1" />);
    fireEvent.click(await screen.findByLabelText("flat"));
    fireEvent.click(screen.getByText("暂存修改"));
    await waitFor(() =>
      expect(api.stageScriptParams).toHaveBeenCalledWith("m_1", { ...params, flat: false })
    );
  });

  it("rejects an unparsable number draft and shows an error", async () => {
    render(<DesignPanel modelId="m_1" />);
    fireEvent.change(await screen.findByLabelText("wall_t"), { target: { value: "abc" } });
    fireEvent.click(screen.getByText("暂存修改"));
    expect(await screen.findByText(/不是有效数字/)).toBeTruthy();
    expect(api.stageScriptParams).not.toHaveBeenCalled();
  });
});

describe("DesignPanel staging 状态机", () => {
  it("undo/redo disabled state follows canUndo/canRedo", async () => {
    setup({ state: { ...scriptState, canUndo: false, canRedo: true } });
    render(<DesignPanel modelId="m_1" />);
    await screen.findByText("暂存 2/10");
    expect((screen.getByText("撤销") as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByText("重做") as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByText("重做"));
    await waitFor(() => expect(api.scriptRedo).toHaveBeenCalledWith("m_1"));
  });

  it("撤销 calls scriptUndo", async () => {
    render(<DesignPanel modelId="m_1" />);
    await screen.findByText("暂存 2/10");
    fireEvent.click(screen.getByText("撤销"));
    await waitFor(() => expect(api.scriptUndo).toHaveBeenCalledWith("m_1"));
  });

  it("放弃暂存 calls discardScript", async () => {
    render(<DesignPanel modelId="m_1" />);
    await screen.findByText("暂存 2/10");
    fireEvent.click(screen.getByText("放弃暂存"));
    await waitFor(() => expect(api.discardScript).toHaveBeenCalledWith("m_1"));
  });

  it("保存大版本 disabled with no staged steps; enabled saves + flags 3D reload", async () => {
    setup({ state: { ...scriptState, staged: 0 } });
    render(<DesignPanel modelId="m_1" />);
    await screen.findByText("暂存 0/10");
    expect((screen.getByText("保存大版本") as HTMLButtonElement).disabled).toBe(true);

    cleanup();
    setup({ state: scriptState });
    render(<DesignPanel modelId="m_1" />);
    await screen.findByText("暂存 2/10");
    fireEvent.click(screen.getByText("保存大版本"));
    await waitFor(() => expect(api.saveScript).toHaveBeenCalledWith("m_1"));
    await waitFor(() => expect(useViewerStore.getState().pendingModelReload).toBe(true));
  });

  it("试跑 calls runScript and flags 3D reload", async () => {
    render(<DesignPanel modelId="m_1" />);
    await screen.findByText("暂存 2/10");
    fireEvent.click(screen.getByText("试跑"));
    await waitFor(() => expect(api.runScript).toHaveBeenCalledWith("m_1"));
    await waitFor(() => expect(useViewerStore.getState().pendingModelReload).toBe(true));
  });
});

describe("DesignPanel 脚本编辑器", () => {
  it("drills down into a line-numbered editor and stages the edited script", async () => {
    render(<DesignPanel modelId="m_1" />);
    await screen.findByText("暂存 2/10");
    fireEvent.click(screen.getByText("脚本编辑器"));
    const ta = (await screen.findByLabelText("脚本编辑器文本")) as HTMLTextAreaElement;
    expect(ta.value).toBe(scriptText);
    expect(screen.getByTestId("script-gutter").textContent).toContain("1");
    fireEvent.change(ta, { target: { value: "PARAMS = {}\n" } });
    fireEvent.click(screen.getByText("暂存脚本"));
    await waitFor(() =>
      expect(api.stageScript).toHaveBeenCalledWith("m_1", "PARAMS = {}\n")
    );
  });

  it("form edits reflect script staging after refresh (同一 staging 源)", async () => {
    render(<DesignPanel modelId="m_1" />);
    await screen.findByText("暂存 2/10");
    fireEvent.click(screen.getByText("脚本编辑器"));
    const ta = (await screen.findByLabelText("脚本编辑器文本")) as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: "PARAMS = {}\n" } });
    fireEvent.click(screen.getByText("暂存脚本"));
    await waitFor(() => expect(api.stageScript).toHaveBeenCalled());
    // refresh re-pulls params so the form stays in sync with the staged script
    await waitFor(() => expect(api.fetchScriptParams.mock.calls.length).toBeGreaterThan(1));
  });
});

describe("DesignPanel diff 视图", () => {
  it("小版本 diff: 相邻暂存步 diff + PARAMS 变化摘要，可折叠", async () => {
    render(<DesignPanel modelId="m_1" />);
    await screen.findByText("暂存 2/10");
    fireEvent.click(screen.getByText("暂存改动"));
    await waitFor(() => expect(api.fetchStagingDiff).toHaveBeenCalledWith("m_1"));
    expect((await screen.findByTestId("staging-diff-text")).textContent).toContain("+wall_t = 0.3");
    expect(screen.getByText(/wall_t: 0.2 → 0.3/)).toBeTruthy();
    fireEvent.click(screen.getByText("收起"));
    expect(screen.queryByTestId("staging-diff-text")).toBeNull();
  });

  it("小版本 diff 按钮在暂存步不足时禁用", async () => {
    setup({ state: { ...scriptState, staged: 1 } });
    render(<DesignPanel modelId="m_1" />);
    await screen.findByText("暂存 1/10");
    expect((screen.getByText("暂存改动") as HTMLButtonElement).disabled).toBe(true);
  });

  it("大版本 diff: 两个脚本版本对比 + params 摘要", async () => {
    render(<DesignPanel modelId="m_1" />);
    await screen.findByText("大版本对比");
    fireEvent.click(screen.getByTestId("diff-compare"));
    await waitFor(() => expect(api.postScriptDiff).toHaveBeenCalledWith("m_1", "v1", "v2"));
    expect((await screen.findByTestId("big-diff-text")).textContent).toContain("@@ v1 -> v2 @@");
    expect(screen.getByText(/name: "a" → "b"/)).toBeTruthy();
  });
});

describe("DesignPanel script jump（定位脚本）", () => {
  it("store scriptJump switches to the editor and selects the located line", async () => {
    render(<DesignPanel modelId="m_1" />);
    await screen.findByText("暂存 2/10");
    act(() => useViewerStore.getState().requestScriptJump({ line: 2, origin: "params" }));
    const ta = (await screen.findByLabelText("脚本编辑器文本")) as HTMLTextAreaElement;
    // scriptText 第 2 行 '    "wall_t": 0.2,' 起始于偏移 11（'PARAMS = {\n' 长度）
    await waitFor(() => expect(ta.selectionStart).toBe(11));
    expect(ta.selectionEnd).toBe(11 + '    "wall_t": 0.2,'.length);
    expect(useViewerStore.getState().scriptJump).toBeNull();
  });

  it("clamps an out-of-range line to the script end", async () => {
    render(<DesignPanel modelId="m_1" />);
    await screen.findByText("暂存 2/10");
    act(() => useViewerStore.getState().requestScriptJump({ line: 999 }));
    const ta = (await screen.findByLabelText("脚本编辑器文本")) as HTMLTextAreaElement;
    await waitFor(() => expect(ta.selectionStart).toBeGreaterThan(0));
    // 超界收敛到末行（trailing \n 产生的空行）：偏移 = 11 + 18 + 1 + 1 + 1 = 32
    expect(ta.selectionStart).toBe(32);
  });

  it("origin=params + paramsKeys switches to the PARAMS form and highlights the key", async () => {
    render(<DesignPanel modelId="m_1" />);
    await screen.findByText("暂存 2/10");
    act(() =>
      useViewerStore.getState().requestScriptJump({
        line: 2,
        origin: "params",
        paramsKeys: ["wall_t"],
      })
    );
    await waitFor(() => {
      const label = screen.getByText("wall_t").closest("label");
      expect(label?.className).toContain("design-field-focused");
    });
    // 停留在 PARAMS 表单，不切编辑器
    expect(screen.queryByLabelText("脚本编辑器文本")).toBeNull();
    expect(useViewerStore.getState().scriptJump).toBeNull();
  });

  it("嵌套 paramsKeys 前缀匹配聚焦（wall.t 由 wall 命中）+ scrollIntoView", async () => {
    const scroll = Element.prototype.scrollIntoView as unknown as ReturnType<typeof vi.fn>;
    render(<DesignPanel modelId="m_1" />);
    await screen.findByText("暂存 2/10");
    act(() =>
      useViewerStore.getState().requestScriptJump({
        line: 2,
        origin: "params",
        paramsKeys: ["frame"],
      })
    );
    // 高亮 + 滚动都落到扁平字段 frame.storeys（W-0022 逃逸补丁：直接查 fieldRefs["frame"]
    // 落空——表单字段名是扁平 dotted path）
    await waitFor(() => {
      const label = screen.getByText("frame.storeys").closest("label");
      expect(label?.className).toContain("design-field-focused");
    });
    await waitFor(() => expect(scroll).toHaveBeenCalled());
  });

  it("手动切模式（form→editor→form）清空 focusKeys，不再聚焦", async () => {
    render(<DesignPanel modelId="m_1" />);
    await screen.findByText("暂存 2/10");
    act(() =>
      useViewerStore.getState().requestScriptJump({
        line: 2,
        origin: "params",
        paramsKeys: ["wall_t"],
      })
    );
    await waitFor(() => {
      expect(screen.getByText("wall_t").closest("label")?.className).toContain("design-field-focused");
    });
    fireEvent.click(screen.getByText("脚本编辑器"));
    fireEvent.click(screen.getByText("参数表单"));
    expect(screen.getByText("wall_t").closest("label")?.className).not.toContain("design-field-focused");
  });

  it("重复同键 jump（nonce 递增）仍触发聚焦", async () => {
    const scroll = Element.prototype.scrollIntoView as unknown as ReturnType<typeof vi.fn>;
    render(<DesignPanel modelId="m_1" />);
    await screen.findByText("暂存 2/10");
    act(() =>
      useViewerStore.getState().requestScriptJump({
        line: 2,
        origin: "params",
        paramsKeys: ["wall_t"],
      })
    );
    await waitFor(() => expect(scroll).toHaveBeenCalledTimes(1));
    act(() =>
      useViewerStore.getState().requestScriptJump({
        line: 2,
        origin: "params",
        paramsKeys: ["wall_t"],
      })
    );
    await waitFor(() => expect(scroll).toHaveBeenCalledTimes(2));
  });
});

describe("DesignPanel 降级态", () => {
  it("老模型（无脚本 404）显示降级提示，不渲染表单", async () => {
    setup({ scriptError: new Error("no script for model") });
    render(<DesignPanel modelId="m_1" />);
    expect(await screen.findByText("该模型无构建脚本")).toBeTruthy();
    expect(screen.queryByText("暂存修改")).toBeNull();
  });

  it("PARAMS 解析失败时保留脚本编辑器入口", async () => {
    setup({ paramsError: new Error("PARAMS block not found") });
    render(<DesignPanel modelId="m_1" />);
    expect(await screen.findByText(/PARAMS 解析失败/)).toBeTruthy();
    fireEvent.click(screen.getByText("脚本编辑器"));
    expect((await screen.findByLabelText("脚本编辑器文本")) as HTMLTextAreaElement).toBeTruthy();
  });
});
