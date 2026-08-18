// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

// fabric 假实现：jsdom 无 canvas 运行时。照 ViewerContext.test.tsx 的 xeokit mock
// 模式，假 Canvas 记录 add/viewportTransform，事件经 fire() 可编程触发。
const fabricFake = vi.hoisted(() => {
  type Handler = (e: unknown) => void;
  class FakeFabricObject {
    data: Record<string, unknown> | undefined;
    visible = true;
    selectable = true;
    evented = true;
    type = "object";
    options: Record<string, unknown>;
    constructor(options: Record<string, unknown> = {}) {
      this.options = options;
      Object.assign(this, options);
    }
  }
  class FakeLine extends FakeFabricObject {
    type = "line";
    points: number[];
    constructor(points: number[], options: Record<string, unknown>) {
      super(options);
      this.points = points;
    }
  }
  class FakeCircle extends FakeFabricObject {
    type = "circle";
  }
  class FakePath extends FakeFabricObject {
    type = "path";
    d: string;
    constructor(d: string, options: Record<string, unknown>) {
      super(options);
      this.d = d;
    }
  }
  class FakeFabricText extends FakeFabricObject {
    type = "text";
    text: string;
    constructor(text: string, options: Record<string, unknown>) {
      super(options);
      this.text = text;
    }
  }
  class FakeGroup extends FakeFabricObject {
    type = "group";
    objects: FakeFabricObject[];
    constructor(objects: FakeFabricObject[], options: Record<string, unknown> = {}) {
      super(options);
      this.objects = objects;
    }
  }
  class FakeCanvas {
    static instances: FakeCanvas[] = [];
    handlers = new Map<string, Handler[]>();
    objects: FakeFabricObject[] = [];
    viewportTransform: number[] = [1, 0, 0, 1, 0, 0];
    renderCount = 0;
    disposed = false;
    el: unknown;
    options: Record<string, unknown>;
    dims = { width: 800, height: 600 };
    setDimensionsCalls: { width: number; height: number }[] = [];
    constructor(el: unknown, options: Record<string, unknown>) {
      this.el = el;
      this.options = options;
      // 模仿真 fabric：构造时把 canvasEl 移入自建 .canvas-container，
      // 之后 parentElement 读到的不再是 .dxf-canvas-wrap。
      if (el instanceof HTMLCanvasElement && el.parentElement) {
        const container = document.createElement("div");
        container.className = "canvas-container";
        el.parentElement.insertBefore(container, el);
        container.appendChild(el);
      }
      FakeCanvas.instances.push(this);
    }
    add(...objs: FakeFabricObject[]) {
      this.objects.push(...objs);
    }
    getObjects() {
      return this.objects;
    }
    setViewportTransform(vpt: number[]) {
      this.viewportTransform = vpt;
    }
    setDimensions(dims: { width: number; height: number }) {
      this.dims = dims;
      this.setDimensionsCalls.push(dims);
    }
    getWidth() {
      return this.dims.width;
    }
    getHeight() {
      return this.dims.height;
    }
    requestRenderAll() {
      this.renderCount += 1;
    }
    on(event: string, cb: Handler) {
      const arr = this.handlers.get(event) ?? [];
      arr.push(cb);
      this.handlers.set(event, arr);
      return () => {
        this.handlers.set(
          event,
          (this.handlers.get(event) ?? []).filter((h) => h !== cb)
        );
      };
    }
    fire(event: string, payload: unknown) {
      for (const cb of this.handlers.get(event) ?? []) cb(payload);
    }
    dispose() {
      this.disposed = true;
    }
  }
  return { FakeCanvas, FakeFabricObject, FakeLine, FakeCircle, FakePath, FakeFabricText, FakeGroup };
});

vi.mock("fabric", () => ({
  Canvas: fabricFake.FakeCanvas,
  Line: fabricFake.FakeLine,
  Circle: fabricFake.FakeCircle,
  Path: fabricFake.FakePath,
  FabricText: fabricFake.FakeFabricText,
  Group: fabricFake.FakeGroup,
}));

// 定位脚本链路只 mock locateScriptByKey（dxf 按 key 定位），其余 client 导出保留
// 原样（useDxfRender 用 renderJsonUrl 直挂 fetch）。
const api = vi.hoisted(() => ({ locateScriptByKey: vi.fn() }));
vi.mock("@/api/client", async (importOriginal) => {
  const orig = await importOriginal<typeof import("@/api/client")>();
  return { ...orig, locateScriptByKey: api.locateScriptByKey };
});

import DxfViewer from "./DxfViewer";
import { fitZoomPan } from "./fit";
import { GROUP_MERGE_THRESHOLD } from "./useDxfRender";
import { CANVAS_FALLBACK_H, CANVAS_FALLBACK_W, DXF_ZOOM_MIN } from "./useDxfCanvasEngine";
import { useViewerStore } from "@/viewer/store";
import type { LineEntity, RenderPayload } from "./types";

function makePayload(overrides: Partial<RenderPayload> = {}): RenderPayload {
  return {
    schemaVersion: 2,
    bounds: { min: [0, 0], max: [10, 10] },
    layers: [
      { name: "0", color: 7, linetype: "CONTINUOUS" },
      { name: "WALL", color: 1, linetype: "CONTINUOUS" },
    ],
    entities: [
      { type: "LINE", key: "k1", layer: "WALL", color: 256, linetype: "CONTINUOUS", start: [0, 0], end: [10, 0] },
      { type: "CIRCLE", key: "k2", layer: "0", color: 1, linetype: "CONTINUOUS", center: [5, 5], radius: 2 },
      { type: "ARC", key: "k3", layer: "0", color: 1, linetype: "DASHED", center: [5, 5], radius: 3, start_angle: 0, end_angle: 90 },
      { type: "TEXT", key: "k4", layer: "WALL", color: 7, linetype: "CONTINUOUS", text: "hi", insert: [1, 1], height: 0.5 },
      { type: "MTEXT", key: "k5", layer: "0", color: 7, linetype: "CONTINUOUS", text: "multi", insert: [2, 2] },
      { type: "LINE", key: null, layer: "0", color: 0, linetype: "BYLAYER", block: "DOOR", start: [0, 0], end: [1, 1] },
      { type: "INSERT", key: "k6", layer: "0", color: 256, linetype: "BYLAYER", name: "DOOR", insert: [3, 3], rotation: 0, scale: 1 },
    ],
    unsupported: [],
    ...overrides,
  };
}

function stubFetch(payload: RenderPayload) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(payload), { status: 200 }))
  );
}

async function renderViewer(payload: RenderPayload) {
  stubFetch(payload);
  const utils = render(<DxfViewer modelId="m_x" />);
  const canvas = fabricFake.FakeCanvas.instances[0];
  expect(canvas).toBeTruthy();
  await waitFor(() => expect(canvas.getObjects().length).toBeGreaterThan(0));
  return { canvas, ...utils };
}

const wheelEvent = (deltaY: number) => ({
  e: { deltaY, offsetX: 400, offsetY: 300, preventDefault() {}, stopPropagation() {} },
});

function manyLines(count: number): LineEntity[] {
  return Array.from({ length: count }, (_, i) => ({
    type: "LINE" as const,
    key: `g${i}`,
    layer: i % 2 === 0 ? "A" : "B",
    color: 7,
    linetype: "CONTINUOUS",
    start: [i, 0] as [number, number],
    end: [i, 1] as [number, number],
  }));
}

async function renderMergedViewer(entityCount: number) {
  const payload = makePayload({
    layers: [
      { name: "A", color: 1, linetype: "CONTINUOUS" },
      { name: "B", color: 2, linetype: "CONTINUOUS" },
    ],
    entities: manyLines(entityCount),
  });
  return renderViewer(payload);
}

beforeEach(() => {
  fabricFake.FakeCanvas.instances.length = 0;
  useViewerStore.setState({ selectedId: null, scriptJump: null });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

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

// jsdom 无 ResizeObserver；可编程桩：fire() 手动触发回调。
function stubResizeObserver() {
  const instances: { cb: ResizeObserverCallback; observed: unknown[]; disconnected: boolean }[] = [];
  class FakeResizeObserver {
    cb: ResizeObserverCallback;
    observed: unknown[] = [];
    disconnected = false;
    constructor(cb: ResizeObserverCallback) {
      this.cb = cb;
      instances.push(this as never);
    }
    observe(el: unknown) {
      this.observed.push(el);
    }
    unobserve() {}
    disconnect() {
      this.disconnected = true;
    }
  }
  vi.stubGlobal("ResizeObserver", FakeResizeObserver);
  return {
    instances,
    fire: () => instances.forEach((i) => i.cb([] as never, {} as never)),
  };
}

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

// 定位脚本（选中 key → locate → requestScriptJump → DesignPanel 跳行，对齐
// PropertyPanel 的 IFC guid 链路；dxf 侧端点按 key 定位，server 代理已就绪）。
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
      found: true, key: "k1", line: 7, col: 2, snippet: "s", origin: "literal", paramsKeys: [],
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
      found: true, key: "k1", line: 3, col: 0, snippet: "s", origin: "params", paramsKeys: ["wall_t"],
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
