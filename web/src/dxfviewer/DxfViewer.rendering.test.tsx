// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// DxfViewer 实体渲染与画布尺寸场景。import 顺序：kit（mock 注册）必须先于被测模块。
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import {
  makePayload,
  renderViewer,
  setupDxfViewerSuite,
  stubFetch,
  stubResizeObserver,
} from "./dxfViewerTestKit";
import { fabricFake } from "./dxfViewerMocks";
import DxfViewer from "./DxfViewer";
import { fitZoomPan } from "./fit";
import { CANVAS_FALLBACK_H, CANVAS_FALLBACK_W } from "./useDxfCanvasEngine";

setupDxfViewerSuite();

describe("DxfViewer entity rendering", () => {
  it("instantiates one fabric object per drawable entity (INSERT produces none)", async () => {
    const { canvas } = await renderViewer(makePayload());
    const objs = canvas.getObjects();
    // LINE x2（含块展开子实体）、CIRCLE、ARC→Path、TEXT、MTEXT 各 1；INSERT 无独立几何
    expect(objs).toHaveLength(6);
    expect(objs.filter((o) => o instanceof fabricFake.FakeLine)).toHaveLength(2);
    expect(objs.filter((o) => o instanceof fabricFake.FakeCircle)).toHaveLength(1);
    expect(objs.filter((o) => o instanceof fabricFake.FakePath)).toHaveLength(1);
    expect(objs.filter((o) => o instanceof fabricFake.FakeFabricText)).toHaveLength(2);
  });

  it("attaches key/entityType/layer/block to obj.data; block children are not selectable", async () => {
    const { canvas } = await renderViewer(makePayload());
    const wallLine = canvas.getObjects().find((o) => o.data?.["key"] === "k1");
    expect(wallLine?.data).toEqual({ key: "k1", entityType: "line", layer: "WALL" });
    expect(wallLine?.selectable).toBe(true);
    const blockChild = canvas.getObjects().find((o) => o.data?.["block"] === "DOOR");
    expect(blockChild?.data?.["key"]).toBeNull();
    expect(blockChild?.data?.["entityType"]).toBe("line");
    expect(blockChild?.selectable).toBe(false);
  });

  it("applies fit viewport from payload bounds", async () => {
    const payload = makePayload();
    const { canvas } = await renderViewer(payload);
    const fit = fitZoomPan(payload.bounds!, 800, 600);
    expect(canvas.viewportTransform).toEqual([fit.zoom, 0, 0, fit.zoom, fit.panX, fit.panY]);
  });

  it("renders empty state for bounds-null payload without crashing", async () => {
    const payload = makePayload({ bounds: null, entities: [], unsupported: [] });
    stubFetch(payload);
    render(<DxfViewer modelId="m_x" />);
    const canvas = fabricFake.FakeCanvas.instances[0];
    await waitFor(() => expect(screen.getByText(/空图纸/)).toBeTruthy());
    expect(canvas.getObjects()).toHaveLength(0);
    expect(canvas.viewportTransform).toEqual([1, 0, 0, 1, 0, 0]);
  });

  it("surfaces unsupported entity count as a badge", async () => {
    const payload = makePayload({
      unsupported: [
        { type: "SPLINE", handle: "ff", coords: [] },
        { type: "HATCH", handle: "fe", coords: [] },
      ],
    });
    await renderViewer(payload);
    expect(screen.getByText("2 个不支持的实体")).toBeTruthy();
  });

  it("shows error banner when render.json fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("not found", { status: 404 }))
    );
    render(<DxfViewer modelId="m_x" />);
    await waitFor(() => expect(screen.getByText(/HTTP 404/)).toBeTruthy());
  });

  it("disposes the fabric canvas on unmount", async () => {
    const { canvas, unmount } = await renderViewer(makePayload());
    unmount();
    expect(canvas.disposed).toBe(true);
  });
});

describe("DxfViewer canvas sizing", () => {
  let wrapW = 1024;
  let wrapH = 640;
  let origW: PropertyDescriptor | undefined;
  let origH: PropertyDescriptor | undefined;

  beforeEach(() => {
    wrapW = 1024;
    wrapH = 640;
    origW = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientWidth");
    origH = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientHeight");
    // 只有 .dxf-canvas-wrap 报注入尺寸；其余元素（含 fabric 自建 container）报 0，
    // 这样 engine 若在 fabric 接管后才读 parentElement 就会暴露（读到 0 → 回落）。
    Object.defineProperty(HTMLElement.prototype, "clientWidth", {
      configurable: true,
      get(this: HTMLElement) {
        return this.classList?.contains("dxf-canvas-wrap") ? wrapW : 0;
      },
    });
    Object.defineProperty(HTMLElement.prototype, "clientHeight", {
      configurable: true,
      get(this: HTMLElement) {
        return this.classList?.contains("dxf-canvas-wrap") ? wrapH : 0;
      },
    });
  });
  afterEach(() => {
    if (origW) Object.defineProperty(HTMLElement.prototype, "clientWidth", origW);
    if (origH) Object.defineProperty(HTMLElement.prototype, "clientHeight", origH);
  });

  it("calls setDimensions with the wrap container size on mount", async () => {
    const { canvas } = await renderViewer(makePayload());
    expect(canvas.setDimensionsCalls.length).toBeGreaterThan(0);
    expect(canvas.dims).toEqual({ width: 1024, height: 640 });
  });

  it("fits using the wrap size rather than the fabric default 300x150", async () => {
    const payload = makePayload();
    const { canvas } = await renderViewer(payload);
    const fit = fitZoomPan(payload.bounds!, 1024, 640);
    expect(canvas.viewportTransform[0]!).toBeCloseTo(fit.zoom, 6);
  });

  it("falls back to default size when the wrap reports zero", async () => {
    wrapW = 0;
    wrapH = 0;
    const { canvas } = await renderViewer(makePayload());
    expect(canvas.dims).toEqual({ width: CANVAS_FALLBACK_W, height: CANVAS_FALLBACK_H });
  });

  it("re-dimensions and re-fits when the wrap resizes", async () => {
    const ro = stubResizeObserver();
    const payload = makePayload();
    const { canvas } = await renderViewer(payload);
    wrapW = 500;
    wrapH = 400;
    act(() => ro.fire());
    expect(canvas.dims).toEqual({ width: 500, height: 400 });
    const fit = fitZoomPan(payload.bounds!, 500, 400);
    expect(canvas.viewportTransform[0]!).toBeCloseTo(fit.zoom, 6);
    expect(canvas.viewportTransform[4]!).toBeCloseTo(fit.panX, 6);
    expect(canvas.viewportTransform[5]!).toBeCloseTo(fit.panY, 6);
  });

  it("disconnects the ResizeObserver on unmount", async () => {
    const ro = stubResizeObserver();
    const { unmount } = await renderViewer(makePayload());
    expect(ro.instances.length).toBeGreaterThan(0);
    unmount();
    expect(ro.instances.every((i) => i.disconnected)).toBe(true);
  });
});
