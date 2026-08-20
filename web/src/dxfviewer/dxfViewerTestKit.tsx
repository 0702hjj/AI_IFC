// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// DxfViewer 测试共享 kit（W-0049 测试按场景域拆分后抽出）：
// fabric/client mock 注册 + 渲染 helper + 公共 beforeEach。
// 各 *.test.tsx 必须先 import 本模块（mock 先生效），再 import 被测模块。
import { beforeEach, afterEach, expect, vi } from "vitest";
import { cleanup, render, waitFor } from "@testing-library/react";
import { fabricFake, api } from "./dxfViewerMocks";

vi.mock("fabric", () => ({
  Canvas: fabricFake.FakeCanvas,
  Line: fabricFake.FakeLine,
  Circle: fabricFake.FakeCircle,
  Path: fabricFake.FakePath,
  FabricText: fabricFake.FakeFabricText,
  Group: fabricFake.FakeGroup,
}));

vi.mock("@/api/client", async (importOriginal) => {
  const orig = await importOriginal<typeof import("@/api/client")>();
  return { ...orig, locateScriptByKey: api.locateScriptByKey };
});

import DxfViewer from "./DxfViewer";
import { useViewerStore } from "@/viewer/store";
import type { LineEntity, RenderPayload } from "./types";

// 注意：含 vi.mock 的模块不能再导出 import 来的绑定（vitest hoist 转换后变
// undefined），fabricFake/api 请各测试文件直接 import "./dxfViewerMocks"。

export function makePayload(overrides: Partial<RenderPayload> = {}): RenderPayload {
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

export function stubFetch(payload: RenderPayload) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(payload), { status: 200 }))
  );
}

export async function renderViewer(payload: RenderPayload) {
  stubFetch(payload);
  const utils = render(<DxfViewer modelId="m_x" />);
  const canvas = fabricFake.FakeCanvas.instances[0];
  expect(canvas).toBeTruthy();
  await waitFor(() => expect(canvas.getObjects().length).toBeGreaterThan(0));
  return { canvas, ...utils };
}

export const wheelEvent = (deltaY: number) => ({
  e: { deltaY, offsetX: 400, offsetY: 300, preventDefault() {}, stopPropagation() {} },
});

export function manyLines(count: number): LineEntity[] {
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

export async function renderMergedViewer(entityCount: number) {
  const payload = makePayload({
    layers: [
      { name: "A", color: 1, linetype: "CONTINUOUS" },
      { name: "B", color: 2, linetype: "CONTINUOUS" },
    ],
    entities: manyLines(entityCount),
  });
  return renderViewer(payload);
}

// jsdom 无 ResizeObserver；可编程桩：fire() 手动触发回调。
export function stubResizeObserver() {
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

// 每个 DxfViewer 测试文件的公共装置：清 fabric 实例与 store 选中态。
export function setupDxfViewerSuite() {
  beforeEach(() => {
    fabricFake.FakeCanvas.instances.length = 0;
    useViewerStore.setState({ selectedId: null, scriptJump: null });
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });
}
