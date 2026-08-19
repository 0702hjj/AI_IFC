// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";

const mockCtx: { current: unknown } = { current: null };
vi.mock("./ViewerContext", () => ({ useViewer: () => mockCtx.current }));

const api = vi.hoisted(() => ({
  fetchOverrides: vi.fn(),
  locateScript: vi.fn(),
}));
vi.mock("@/api/client", () => api);

import { PropertyPanel } from "./PropertyPanel";
import { useViewerStore } from "./store";

afterEach(cleanup);

const metaObject = {
  id: "w1",
  name: "Wall A",
  type: "IfcWall",
  parent: "st",
  propertySets: [
    {
      id: "pset1",
      name: "Pset_WallCommon",
      type: "Pset",
      properties: [
        { name: "FireRating", value: "120 min", type: "1" },
        { name: "LoadBearing", value: true, type: "3" },
      ],
    },
    {
      id: "pset2",
      name: "Pset_Geometry",
      type: "Pset",
      properties: [{ name: "Height", value: 3200, type: "4" }],
    },
  ],
};

function setup() {
  mockCtx.current = { metaModel: { metaObjects: { w1: metaObject } } };
  useViewerStore.setState({
    selectedId: null, tool: "select", hiddenIds: [], isolateId: null, xray: false,
    overrides: {}, changesVersion: 0, pendingModelReload: false, scriptJump: null,
  });
  vi.clearAllMocks();
  api.fetchOverrides.mockResolvedValue({});
  api.locateScript.mockResolvedValue({ found: false });
}

async function selectAndRender() {
  useViewerStore.getState().setSelected("w1");
  render(<PropertyPanel modelId="m1" />);
  await waitFor(() => expect(screen.getByText("FireRating")).toBeTruthy());
}

describe("PropertyPanel read-only base", () => {
  beforeEach(setup);

  it("shows empty state when nothing is selected", () => {
    render(<PropertyPanel modelId="m1" />);
    expect(screen.getByText("点击构件查看属性")).toBeTruthy();
  });

  it("stays in empty state without a meta model even if selected", () => {
    mockCtx.current = null;
    useViewerStore.getState().setSelected("w1");
    render(<PropertyPanel modelId="m1" />);
    expect(screen.getByText("点击构件查看属性")).toBeTruthy();
  });

  it("renders meta psets read-only: values visible, no edit inputs or retired edit affordances", async () => {
    await selectAndRender();
    expect(screen.getByText("120 min")).toBeTruthy();
    fireEvent.click(screen.getByText("Pset_Geometry"));
    expect(screen.getByText("3200")).toBeTruthy();
    expect(document.querySelector(".editable-value")).toBeNull();
    expect(document.querySelector(".editable-input")).toBeNull();
    expect(screen.queryByRole("button", { name: "删除构件" })).toBeNull();
    expect(screen.queryByRole("button", { name: "提交" })).toBeNull();
    expect(screen.queryByText(/有未提交修改/)).toBeNull();
  });

  it("search filters read-only props", async () => {
    await selectAndRender();
    fireEvent.change(screen.getByPlaceholderText("搜索属性"), { target: { value: "fire" } });
    expect(screen.getByText("FireRating")).toBeTruthy();
    expect(screen.queryByText("LoadBearing")).toBeNull();
    expect(screen.queryByText("Height")).toBeNull();
  });

  it("historical overrides shadow displayed values read-only with a marker", async () => {
    api.fetchOverrides.mockResolvedValue({ w1: { FireRating: "90 min" } });
    await selectAndRender();
    await waitFor(() => expect(api.fetchOverrides).toHaveBeenCalledWith("m1"));
    const psetRow = screen.getByLabelText("复制 FireRating").closest("tr")!;
    expect(psetRow.querySelector(".property-value")!.textContent).toBe("90 min");
    expect(psetRow.classList.contains("overridden")).toBe(true);
  });

  it("copy button writes name: value to clipboard", async () => {
    const writeText = vi.fn(async () => {});
    Object.assign(navigator, { clipboard: { writeText } });
    await selectAndRender();
    const row = await screen.findByLabelText("复制 FireRating");
    fireEvent.click(row.closest("tr")!.querySelector("button.property-copy-btn")!);
    expect(writeText).toHaveBeenCalledWith("FireRating: 120 min");
  });
});

describe("PropertyPanel 定位脚本", () => {
  beforeEach(setup);

  it("locate hit jumps the script editor via the store and shows a notice", async () => {
    api.locateScript.mockResolvedValue({
      found: true, designKey: "wall-1", line: 12, col: 4,
      snippet: "make_wall(key='wall-1')", origin: "params",
    });
    await selectAndRender();
    fireEvent.click(screen.getByRole("button", { name: "定位脚本" }));
    await waitFor(() => expect(api.locateScript).toHaveBeenCalledWith("m1", "w1"));
    await waitFor(() =>
      expect(useViewerStore.getState().scriptJump).toMatchObject({ line: 12, origin: "params" })
    );
    expect(await screen.findByText(/已定位到脚本第 12 行/)).toBeTruthy();
  });

  it("locate hit passes paramsKeys through for params-origin entities", async () => {
    api.locateScript.mockResolvedValue({
      found: true, designKey: "wall-1", line: 12, col: 4,
      snippet: "create_entity(..., key=params['key'])", origin: "params",
      // 服务端真实载荷是 snake_case（map entry ** 原样铺开，Go 代理零转换透传）
      params_keys: ["key"],
    });
    await selectAndRender();
    fireEvent.click(screen.getByRole("button", { name: "定位脚本" }));
    await waitFor(() =>
      expect(useViewerStore.getState().scriptJump).toMatchObject({
        line: 12, origin: "params", paramsKeys: ["key"],
      })
    );
  });

  it("locate miss shows a non-blocking read-only hint and does not jump", async () => {
    api.locateScript.mockResolvedValue({ found: false });
    await selectAndRender();
    fireEvent.click(screen.getByRole("button", { name: "定位脚本" }));
    expect(await screen.findByText(/没有脚本调用点/)).toBeTruthy();
    expect(useViewerStore.getState().scriptJump).toBeNull();
    // 非阻断：属性仍然可见
    expect(screen.getByText("FireRating")).toBeTruthy();
  });

  it("locate stale shows a run-first hint and does not jump", async () => {
    api.locateScript.mockResolvedValue({ found: false, designKey: "wall-1", stale: true });
    await selectAndRender();
    fireEvent.click(screen.getByRole("button", { name: "定位脚本" }));
    expect(await screen.findByText(/未运行的修改/)).toBeTruthy();
    expect(useViewerStore.getState().scriptJump).toBeNull();
    expect(screen.getByText("FireRating")).toBeTruthy();
  });

  it("origin=traced jumps but guides to manual script editing (no auto-edit affordance)", async () => {
    api.locateScript.mockResolvedValue({
      found: true, designKey: "wall-1", line: 7, col: 0,
      snippet: "make_wall(key=k)", origin: "traced",
    });
    await selectAndRender();
    fireEvent.click(screen.getByRole("button", { name: "定位脚本" }));
    await waitFor(() =>
      expect(useViewerStore.getState().scriptJump).toMatchObject({ line: 7, origin: "traced" })
    );
    expect(await screen.findByText(/手动修改/)).toBeTruthy();
  });

  it("locate request failure degrades to a read-only hint without breaking selection", async () => {
    api.locateScript.mockRejectedValue(new Error("element not found"));
    await selectAndRender();
    fireEvent.click(screen.getByRole("button", { name: "定位脚本" }));
    expect(await screen.findByText(/定位不可用/)).toBeTruthy();
    expect(useViewerStore.getState().scriptJump).toBeNull();
    expect(screen.getByText("FireRating")).toBeTruthy();
  });

  it("switching selection clears the locate notice", async () => {
    api.locateScript.mockResolvedValue({ found: false });
    await selectAndRender();
    fireEvent.click(screen.getByRole("button", { name: "定位脚本" }));
    expect(await screen.findByText(/没有脚本调用点/)).toBeTruthy();
    useViewerStore.getState().setSelected(null);
    await waitFor(() => expect(screen.queryByText(/没有脚本调用点/)).toBeNull());
  });
});
