// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// DxfViewer 交互（缩放/平移/选中/悬停/图层开关）与成组合并路径场景。
// import 顺序：kit（mock 注册）必须先于被测模块。
import { describe, it, expect } from "vitest";
import { act, fireEvent, screen, within } from "@testing-library/react";
import {
  makePayload,
  renderMergedViewer,
  renderViewer,
  setupDxfViewerSuite,
  wheelEvent,
} from "./dxfViewerTestKit";
import { fabricFake } from "./dxfViewerMocks";
import { GROUP_MERGE_THRESHOLD } from "./useDxfRender";
import { DXF_ZOOM_MIN } from "./useDxfCanvasEngine";
import { useViewerStore } from "@/viewer/store";

setupDxfViewerSuite();

describe("DxfViewer interactions", () => {
  it("clamps wheel zoom at the minimum", async () => {
    const { canvas } = await renderViewer(makePayload());
    for (let i = 0; i < 50; i++) {
      act(() => canvas.fire("mouse:wheel", wheelEvent(1000)));
    }
    expect(canvas.viewportTransform[0]!).toBeGreaterThanOrEqual(DXF_ZOOM_MIN);
  });

  it("zooms on wheel events around the pointer", async () => {
    const { canvas } = await renderViewer(makePayload());
    const z0 = canvas.viewportTransform[0]!;
    act(() => canvas.fire("mouse:wheel", wheelEvent(100)));
    const z1 = canvas.viewportTransform[0]!;
    expect(z1).toBeLessThan(z0);
    act(() => canvas.fire("mouse:wheel", wheelEvent(-100)));
    expect(canvas.viewportTransform[0]!).toBeGreaterThan(z1);
  });

  it("pans on mouse drag", async () => {
    const { canvas } = await renderViewer(makePayload());
    const [px0, py0] = [canvas.viewportTransform[4]!, canvas.viewportTransform[5]!];
    act(() => canvas.fire("mouse:down", { e: { clientX: 100, clientY: 100 }, target: null }));
    act(() => canvas.fire("mouse:move", { e: { clientX: 120, clientY: 90 }, target: null }));
    act(() => canvas.fire("mouse:up", { e: { clientX: 120, clientY: 90 } }));
    expect(canvas.viewportTransform[4]!).toBeCloseTo(px0 + 20, 6);
    expect(canvas.viewportTransform[5]!).toBeCloseTo(py0 - 10, 6);
  });

  it("writes selected key to the viewer store and shows the property panel", async () => {
    const { canvas } = await renderViewer(makePayload());
    const wallLine = canvas.getObjects().find((o) => o.data?.["key"] === "k1")!;
    act(() => canvas.fire("selection:created", { selected: [wallLine] }));
    expect(useViewerStore.getState().selectedId).toBe("k1");
    const panel = screen.getByTestId("dxf-selected-panel");
    expect(within(panel).getByText("k1")).toBeTruthy();
    expect(within(panel).getByText("line")).toBeTruthy();
    expect(within(panel).getByText("WALL")).toBeTruthy();
  });

  it("clears the store selection on selection:cleared", async () => {
    const { canvas } = await renderViewer(makePayload());
    const wallLine = canvas.getObjects().find((o) => o.data?.["key"] === "k1")!;
    act(() => canvas.fire("selection:created", { selected: [wallLine] }));
    act(() => canvas.fire("selection:cleared", {}));
    expect(useViewerStore.getState().selectedId).toBeNull();
    expect(screen.queryByTestId("dxf-selected-panel")).toBeNull();
  });

  it("shows hover tooltip with block name for block children", async () => {
    const { canvas } = await renderViewer(makePayload());
    const blockChild = canvas.getObjects().find((o) => o.data?.["block"] === "DOOR")!;
    act(() => canvas.fire("mouse:move", { target: blockChild, e: { clientX: 5, clientY: 5 } }));
    expect(screen.getByText(/块 DOOR/)).toBeTruthy();
    act(() => canvas.fire("mouse:move", { target: null, e: { clientX: 6, clientY: 6 } }));
    expect(screen.queryByText(/块 DOOR/)).toBeNull();
  });

  it("toggles layer visibility from the layer sidebar", async () => {
    const { canvas } = await renderViewer(makePayload());
    const rendersBefore = canvas.renderCount;
    fireEvent.click(screen.getByLabelText("WALL"));
    const wallLine = canvas.getObjects().find(
      (o) => o.data?.["layer"] === "WALL" && o.data?.["entityType"] === "line"
    )!;
    const otherCircle = canvas.getObjects().find((o) => o.data?.["entityType"] === "circle")!;
    expect(wallLine.visible).toBe(false);
    expect(otherCircle.visible).toBe(true);
    expect(canvas.renderCount).toBeGreaterThan(rendersBefore);
    fireEvent.click(screen.getByLabelText("WALL"));
    expect(wallLine.visible).toBe(true);
  });
});

describe("DxfViewer group merge path", () => {
  it("merges per-layer into Groups above the threshold", async () => {
    const { canvas } = await renderMergedViewer(GROUP_MERGE_THRESHOLD + 1);
    const groups = canvas.getObjects();
    expect(groups).toHaveLength(2);
    for (const g of groups) {
      expect(g).toBeInstanceOf(fabricFake.FakeGroup);
      expect(["A", "B"]).toContain(g.data?.["layer"]);
    }
    const total = groups.reduce(
      (n, g) => n + (g as InstanceType<typeof fabricFake.FakeGroup>).objects.length,
      0
    );
    expect(total).toBe(GROUP_MERGE_THRESHOLD + 1);
    for (const g of groups as InstanceType<typeof fabricFake.FakeGroup>[]) {
      for (const child of g.objects) expect(child.selectable).toBe(false);
    }
  });

  it("does not merge at exactly the threshold", async () => {
    const { canvas } = await renderMergedViewer(GROUP_MERGE_THRESHOLD);
    expect(canvas.getObjects()).toHaveLength(GROUP_MERGE_THRESHOLD);
    expect(canvas.getObjects()[0]).not.toBeInstanceOf(fabricFake.FakeGroup);
  });

  it("resolves the child key under the pointer when a layer group is selected", async () => {
    const { canvas } = await renderMergedViewer(GROUP_MERGE_THRESHOLD + 1);
    const group = canvas.getObjects()[0] as InstanceType<typeof fabricFake.FakeGroup>;
    const child = group.objects.find((o) => o.data?.["key"] != null)!;
    act(() => canvas.fire("mouse:down", { e: { clientX: 0, clientY: 0 }, target: group, subTargets: [child] }));
    act(() => canvas.fire("selection:created", { selected: [group] }));
    act(() => canvas.fire("mouse:up", { e: { clientX: 0, clientY: 0 } }));
    expect(useViewerStore.getState().selectedId).toBe(child.data!["key"]);
  });

  it("falls back to layer-level selection when no child target is available", async () => {
    const { canvas } = await renderMergedViewer(GROUP_MERGE_THRESHOLD + 1);
    const group = canvas.getObjects()[0] as InstanceType<typeof fabricFake.FakeGroup>;
    act(() => canvas.fire("mouse:down", { e: { clientX: 0, clientY: 0 }, target: group }));
    act(() => canvas.fire("selection:created", { selected: [group] }));
    act(() => canvas.fire("mouse:up", { e: { clientX: 0, clientY: 0 } }));
    expect(useViewerStore.getState().selectedId).toBeNull();
    const panel = screen.getByTestId("dxf-selected-panel");
    expect(within(panel).getByText(group.data!["layer"] as string)).toBeTruthy();
  });

  it("clears subTargets on mouse:up so a stale child is not resolved later", async () => {
    const { canvas } = await renderMergedViewer(GROUP_MERGE_THRESHOLD + 1);
    const group = canvas.getObjects()[0] as InstanceType<typeof fabricFake.FakeGroup>;
    const child = group.objects.find((o) => o.data?.["key"] != null)!;
    act(() => canvas.fire("mouse:down", { e: { clientX: 0, clientY: 0 }, target: group, subTargets: [child] }));
    act(() => canvas.fire("mouse:up", { e: { clientX: 0, clientY: 0 } }));
    act(() => canvas.fire("selection:created", { selected: [group] }));
    expect(useViewerStore.getState().selectedId).toBeNull();
    const panel = screen.getByTestId("dxf-selected-panel");
    expect(within(panel).getByText(group.data!["layer"] as string)).toBeTruthy();
  });
});
