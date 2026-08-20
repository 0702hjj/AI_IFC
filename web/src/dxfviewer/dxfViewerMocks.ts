// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// DxfViewer 测试共享 mock 对象（W-0049 拆分抽出）：
// 独立成无 vi.mock 的纯模块，保证 vi.mock factory 惰性执行时这些绑定已初始化
// （vi.hoisted 的变量不允许导出，故 fabricFake/api 以普通导出住在本模块）。

// fabric 假实现：jsdom 无 canvas 运行时。照 ViewerContext.test.tsx 的 xeokit mock
// 模式，假 Canvas 记录 add/viewportTransform，事件经 fire() 可编程触发。
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

export const fabricFake = { FakeCanvas, FakeFabricObject, FakeLine, FakeCircle, FakePath, FakeFabricText, FakeGroup };

// 定位脚本链路只 mock locateScriptByKey（dxf 按 key 定位），其余 client 导出保留
// 原样（useDxfRender 用 renderJsonUrl 直挂 fetch）。
import { vi } from "vitest";
export const api = { locateScriptByKey: vi.fn() };
