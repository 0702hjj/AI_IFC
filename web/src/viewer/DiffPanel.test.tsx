// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";

const mockCtx: { current: unknown } = { current: null };
vi.mock("./ViewerContext", () => ({ useViewer: () => mockCtx.current }));

const api = vi.hoisted(() => ({
  fetchEditVersions: vi.fn(),
  postEditDiff: vi.fn(),
  fetchScriptVersions: vi.fn(),
  postScriptDiff: vi.fn(),
}));
vi.mock("@/api/client", () => api);

import { DiffPanel, DIFF_COLORS } from "./DiffPanel";
import { useViewerStore } from "./store";

afterEach(cleanup);

const versions = {
  versions: [
    { version: "v1", createdAt: "2026-07-28T00:00:00Z" },
    { version: "v2", createdAt: "2026-07-29T00:00:00Z" },
  ],
  current: "v2",
};

const diff = {
  base: "v1",
  target: "current",
  added: ["g_add"],
  removed: ["g_del"],
  changed: [
    { guid: "g_chg", changes: [{ field: "Name", old: "Wall A", new: "Wall B" }] },
  ],
};

function setup(opts?: { versions?: unknown; diff?: unknown }) {
  const objects: Record<string, { colorize: [number, number, number] | null }> = {
    g_add: { colorize: null },
    g_chg: { colorize: null },
  };
  mockCtx.current = {
    viewer: {
      cameraFlight: { flyTo: vi.fn() },
      scene: { objects },
    },
    metaModel: null,
  };
  useViewerStore.setState({
    selectedId: null,
    diffOpen: true,
  });
  vi.clearAllMocks();
  api.fetchEditVersions.mockResolvedValue(
    opts && "versions" in opts ? opts.versions : versions
  );
  api.postEditDiff.mockResolvedValue(
    opts && "diff" in opts ? opts.diff : diff
  );
  api.fetchScriptVersions.mockResolvedValue({
    modelId: "m_1",
    scripts: [
      { version: "v1", createdAt: "t1", note: "" },
      { version: "v2", createdAt: "t2", note: "" },
    ],
    versions: [],
  });
  api.postScriptDiff.mockResolvedValue({
    base: "v1",
    target: "v2",
    engine: "script",
    text_diff: "--- v1\n+++ v2\n-old\n+new\n",
    params_changes: [{ key: "wall_t", action: "modified", old: 0.2, new: 0.3 }],
    stats: { added: 1, removed: 1 },
  });
  return { objects };
}

describe("DiffPanel", () => {
  beforeEach(() => {
    setup();
  });

  it("renders nothing when closed", () => {
    useViewerStore.setState({ diffOpen: false });
    const { container } = render(<DiffPanel modelId="m_1" />);
    expect(container.firstChild).toBeNull();
  });

  it("fetches versions and fills base/target selects, target includes current", async () => {
    render(<DiffPanel modelId="m_1" />);
    await waitFor(() =>
      expect(api.fetchEditVersions).toHaveBeenCalledWith("m_1")
    );
    const base = (await screen.findByLabelText("base 版本")) as HTMLSelectElement;
    const target = screen.getByLabelText("target 版本") as HTMLSelectElement;
    expect([...base.options].map((o) => o.value)).toEqual(["v1", "v2"]);
    expect([...target.options].map((o) => o.value)).toEqual(["current", "v1", "v2"]);
    expect(target.value).toBe("current");
  });

  it("shows empty hint when no versions exist", async () => {
    api.fetchEditVersions.mockResolvedValue({ versions: [], current: null });
    render(<DiffPanel modelId="m_1" />);
    expect(await screen.findByText("暂无版本可对比")).toBeTruthy();
    expect(screen.queryByLabelText("base 版本")).toBeNull();
  });

  it("compare posts diff and colorizes added green / changed yellow, removed only listed", async () => {
    const { objects } = setup();
    render(<DiffPanel modelId="m_1" />);
    await screen.findByLabelText("base 版本");
    fireEvent.click(screen.getByText("对比"));
    await waitFor(() =>
      expect(api.postEditDiff).toHaveBeenCalledWith("m_1", "v1", "current")
    );
    await screen.findByText("g_add");
    expect(objects.g_add.colorize).toEqual(DIFF_COLORS.added);
    expect(objects.g_chg.colorize).toEqual(DIFF_COLORS.changed);
    expect(objects.g_del).toBeUndefined();
    expect(screen.getByText("g_del")).toBeTruthy();
    expect(screen.getByText("Wall A → Wall B")).toBeTruthy();
  });

  it("counts guids missing from the scene", async () => {
    setup({
      diff: { ...diff, added: ["g_add", "g_ghost"] },
    });
    render(<DiffPanel modelId="m_1" />);
    await screen.findByLabelText("base 版本");
    fireEvent.click(screen.getByText("对比"));
    expect(
      await screen.findByText("1 个构件在当前模型中不存在，已跳过着色")
    ).toBeTruthy();
  });

  it("clear resets colorize and empties the result", async () => {
    const { objects } = setup();
    render(<DiffPanel modelId="m_1" />);
    await screen.findByLabelText("base 版本");
    fireEvent.click(screen.getByText("对比"));
    await screen.findByText("g_add");
    fireEvent.click(screen.getByText("清除"));
    expect(objects.g_add.colorize).toBeNull();
    expect(objects.g_chg.colorize).toBeNull();
    expect(screen.queryByText("g_add")).toBeNull();
    expect(screen.queryByText("g_del")).toBeNull();
  });

  it("clicking a changed entry flies to and selects the entity", async () => {
    const { objects } = setup();
    render(<DiffPanel modelId="m_1" />);
    await screen.findByLabelText("base 版本");
    fireEvent.click(screen.getByText("对比"));
    fireEvent.click(await screen.findByText("g_chg"));
    const ctx = mockCtx.current as {
      viewer: { cameraFlight: { flyTo: ReturnType<typeof vi.fn> } };
    };
    expect(ctx.viewer.cameraFlight.flyTo).toHaveBeenCalledWith(objects.g_chg);
    expect(useViewerStore.getState().selectedId).toBe("g_chg");
  });
});

describe("DiffPanel 脚本 diff tab", () => {
  beforeEach(() => {
    setup();
  });

  it("script tab lists script versions and defaults base/target to the last two", async () => {
    render(<DiffPanel modelId="m_1" />);
    fireEvent.click(screen.getByText("脚本 diff"));
    await waitFor(() => expect(api.fetchScriptVersions).toHaveBeenCalledWith("m_1"));
    const base = (await screen.findByLabelText("脚本 base 版本")) as HTMLSelectElement;
    const target = screen.getByLabelText("脚本 target 版本") as HTMLSelectElement;
    expect(base.value).toBe("v1");
    expect(target.value).toBe("v2");
  });

  it("compares two script versions and renders pre text + params summary", async () => {
    render(<DiffPanel modelId="m_1" />);
    fireEvent.click(screen.getByText("脚本 diff"));
    await screen.findByLabelText("脚本 base 版本");
    fireEvent.click(screen.getByText("对比"));
    await waitFor(() => expect(api.postScriptDiff).toHaveBeenCalledWith("m_1", "v1", "v2"));
    expect((await screen.findByTestId("script-diff-text")).textContent).toContain("+new");
    expect(screen.getByText(/wall_t: 0.2 → 0.3/)).toBeTruthy();
    expect(screen.getByText(/\+1 -1/)).toBeTruthy();
  });

  it("script diff does not colorize the 3D scene", async () => {
    const { objects } = setup();
    render(<DiffPanel modelId="m_1" />);
    fireEvent.click(screen.getByText("脚本 diff"));
    await screen.findByLabelText("脚本 base 版本");
    fireEvent.click(screen.getByText("对比"));
    await screen.findByTestId("script-diff-text");
    expect(objects.g_add.colorize).toBeNull();
    expect(objects.g_chg.colorize).toBeNull();
  });

  it("shows an empty hint for legacy models without script versions", async () => {
    api.fetchScriptVersions.mockResolvedValue({ modelId: "m_1", scripts: [], versions: [] });
    render(<DiffPanel modelId="m_1" />);
    fireEvent.click(screen.getByText("脚本 diff"));
    expect(await screen.findByText("无脚本版本可对比")).toBeTruthy();
  });

  it("switching tabs keeps the IFC diff result intact", async () => {
    render(<DiffPanel modelId="m_1" />);
    await screen.findByLabelText("base 版本");
    fireEvent.click(screen.getByText("对比"));
    await screen.findByText("g_add");
    fireEvent.click(screen.getByText("脚本 diff"));
    await screen.findByLabelText("脚本 base 版本");
    fireEvent.click(screen.getByText("语义 diff"));
    expect(screen.getByText("g_add")).toBeTruthy();
  });
});
