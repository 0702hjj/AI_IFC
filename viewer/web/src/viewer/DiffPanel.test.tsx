// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";

const mockCtx: { current: unknown } = { current: null };
vi.mock("./ViewerContext", () => ({ useViewer: () => mockCtx.current }));

const api = vi.hoisted(() => ({
  fetchEditVersions: vi.fn(),
  postEditDiff: vi.fn(),
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
