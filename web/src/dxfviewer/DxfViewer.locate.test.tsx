// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// 定位脚本（选中 key → locate → requestScriptJump → DesignPanel 跳行，对齐
// PropertyPanel 的 IFC guid 链路；dxf 侧端点按 key 定位，server 代理已就绪）。
// import 顺序：kit（mock 注册）必须先于被测模块。
import { describe, it, expect, beforeEach } from "vitest";
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import {
  makePayload,
  renderViewer,
  setupDxfViewerSuite,
} from "./dxfViewerTestKit";
import { api } from "./dxfViewerMocks";
import { useViewerStore } from "@/viewer/store";

setupDxfViewerSuite();

describe("DxfViewer 定位脚本", () => {
  beforeEach(() => {
    api.locateScriptByKey.mockReset();
  });

  async function selectKey(key: string) {
    const { canvas } = await renderViewer(makePayload());
    const obj = canvas.getObjects().find((o) => o.data?.["key"] === key)!;
    act(() => canvas.fire("selection:created", { selected: [obj] }));
    return canvas;
  }

  it("选中面板点定位脚本：按 key locate 命中 → requestScriptJump 入 store", async () => {
    api.locateScriptByKey.mockResolvedValue({
      found: true, key: "k1", line: 7, col: 2, snippet: "s", origin: "literal", params_keys: [],
    });
    await selectKey("k1");
    const panel = screen.getByTestId("dxf-selected-panel");
    const btn = within(panel).getByRole("button", { name: "定位脚本" });
    await act(async () => {
      fireEvent.click(btn);
    });
    expect(api.locateScriptByKey).toHaveBeenCalledWith("m_x", "k1");
    await waitFor(() => expect(useViewerStore.getState().scriptJump?.line).toBe(7));
    expect(useViewerStore.getState().scriptJump?.origin).toBe("literal");
    expect(await within(panel).findByText(/已定位到脚本第 7 行/)).toBeTruthy();
  });

  it("origin=params 命中透传 paramsKeys（PARAMS 表单聚焦键）", async () => {
    api.locateScriptByKey.mockResolvedValue({
      found: true, key: "k1", line: 3, col: 0, snippet: "s", origin: "params", params_keys: ["wall_t"],
    });
    await selectKey("k1");
    const btn = within(screen.getByTestId("dxf-selected-panel")).getByRole("button", { name: "定位脚本" });
    await act(async () => {
      fireEvent.click(btn);
    });
    await waitFor(() => expect(useViewerStore.getState().scriptJump?.line).toBe(3));
    expect(useViewerStore.getState().scriptJump?.paramsKeys).toEqual(["wall_t"]);
  });

  it("locate miss → 非阻断提示，不发 scriptJump", async () => {
    api.locateScriptByKey.mockResolvedValue({ found: false, key: "k1" });
    await selectKey("k1");
    const btn = within(screen.getByTestId("dxf-selected-panel")).getByRole("button", { name: "定位脚本" });
    await act(async () => {
      fireEvent.click(btn);
    });
    expect(await screen.findByText(/没有脚本调用点/)).toBeTruthy();
    expect(useViewerStore.getState().scriptJump).toBeNull();
  });

  it("locate stale（staging 与 map 分叉）→ 过期提示，不发 scriptJump", async () => {
    api.locateScriptByKey.mockResolvedValue({ found: false, key: "k1", stale: true });
    await selectKey("k1");
    const btn = within(screen.getByTestId("dxf-selected-panel")).getByRole("button", { name: "定位脚本" });
    await act(async () => {
      fireEvent.click(btn);
    });
    expect(await screen.findByText(/已过期/)).toBeTruthy();
    expect(useViewerStore.getState().scriptJump).toBeNull();
  });

  it("locate 请求失败 → 降级提示，不抛错", async () => {
    api.locateScriptByKey.mockRejectedValue(new Error("HTTP 500"));
    await selectKey("k1");
    const btn = within(screen.getByTestId("dxf-selected-panel")).getByRole("button", { name: "定位脚本" });
    await act(async () => {
      fireEvent.click(btn);
    });
    expect(await screen.findByText(/脚本定位不可用/)).toBeTruthy();
    expect(useViewerStore.getState().scriptJump).toBeNull();
  });

  it("无 key 的选中（块内子实体）不渲染定位按钮", async () => {
    const { canvas } = await renderViewer(makePayload());
    const blockChild = canvas.getObjects().find((o) => o.data?.["block"] === "DOOR")!;
    act(() => canvas.fire("selection:created", { selected: [blockChild] }));
    const panel = screen.getByTestId("dxf-selected-panel");
    expect(within(panel).queryByRole("button", { name: "定位脚本" })).toBeNull();
  });
});
