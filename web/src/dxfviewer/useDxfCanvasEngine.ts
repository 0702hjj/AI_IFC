// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// fabric.Canvas 生命周期 hook（DXF 只读查看器）：挂载/销毁、尺寸适配
// （setDimensions + ResizeObserver re-fit）、wheel zoom、drag pan、hover、
// 选中回调。组织模式参考 gaia_web useCanvasEngine：canvasEl 驱动 effect、
// 回调经 ref 保鲜、事件 disposer 统一回收。

import { useCallback, useEffect, useRef, useState } from "react";
import { Canvas } from "fabric";
import type { FabricObject } from "fabric";
import { fitZoomPan } from "./fit";
import type { Bounds } from "./types";

/** wheel 缩放基准：zoom *= WHEEL_ZOOM_BASE ** deltaY（向下滚放大）。 */
export const WHEEL_ZOOM_BASE = 0.999;
export const DXF_ZOOM_MIN = 0.01;
export const DXF_ZOOM_MAX = 1000;
/** 父容器尺寸读不到（jsdom / 布局未就绪）时的画布兜底尺寸。 */
export const CANVAS_FALLBACK_W = 800;
export const CANVAS_FALLBACK_H = 600;

export interface DxfSelectionInfo {
  key: string | null;
  entityType: string | null;
  layer: string | null;
  block?: string;
}

export interface DxfHoverInfo {
  key: string | null;
  layer: string | null;
  block?: string;
}

export interface UseDxfCanvasEngineOptions {
  canvasEl: HTMLCanvasElement | null;
  onObjectSelected?: (info: DxfSelectionInfo | null) => void;
  onHover?: (info: DxfHoverInfo | null) => void;
}

export interface UseDxfCanvasEngineReturn {
  canvas: Canvas | null;
  isReady: boolean;
  /** 应用 fit 并记录 bounds；容器尺寸变化时引擎按记录的 bounds 自动 re-fit。 */
  fitTo: (bounds: Bounds) => void;
}

interface ObjData {
  key?: string | null;
  entityType?: string;
  layer?: string;
  block?: string;
}

interface WheelLike {
  deltaY: number;
  offsetX?: number;
  offsetY?: number;
  preventDefault(): void;
  stopPropagation(): void;
}

interface PointerLike {
  clientX?: number;
  clientY?: number;
}

type Vpt = [number, number, number, number, number, number];

function clampZoom(z: number): number {
  return Math.min(DXF_ZOOM_MAX, Math.max(DXF_ZOOM_MIN, z));
}

// fabric 7 类型不含自定义 data 字段；运行时挂载照常，读取统一走此 helper。
type WithData = { data?: ObjData };

function dataOf(obj: FabricObject | undefined | null): ObjData {
  return (obj as WithData | undefined | null)?.data ?? {};
}

function resolveSelection(
  obj: FabricObject | undefined,
  subTargets: FabricObject[]
): DxfSelectionInfo | null {
  if (!obj) return null;
  const data = dataOf(obj);
  if (data.key != null || data.entityType !== undefined) {
    return {
      key: data.key ?? null,
      entityType: data.entityType ?? null,
      layer: data.layer ?? null,
      block: data.block,
    };
  }
  // Group 合并路径：选中落在图层 Group 上，优先解析指针下的子实体 key。
  const child = subTargets.find((t) => dataOf(t).key != null) ?? subTargets[0];
  if (child) {
    const cd = dataOf(child);
    return {
      key: cd.key ?? null,
      entityType: cd.entityType ?? null,
      layer: cd.layer ?? data.layer ?? null,
      block: cd.block,
    };
  }
  // 兜底：图层级选中，只展示图层。
  return { key: null, entityType: "group", layer: data.layer ?? null };
}

export function useDxfCanvasEngine(
  options: UseDxfCanvasEngineOptions
): UseDxfCanvasEngineReturn {
  const { canvasEl } = options;

  const onObjectSelectedRef = useRef(options.onObjectSelected);
  const onHoverRef = useRef(options.onHover);
  // React 19：回调 ref 保鲜放进 effect，不在 render 期赋值。
  useEffect(() => {
    onObjectSelectedRef.current = options.onObjectSelected;
    onHoverRef.current = options.onHover;
  });

  const canvasRef = useRef<Canvas | null>(null);
  const fitBoundsRef = useRef<Bounds | null>(null);
  const [canvas, setCanvas] = useState<Canvas | null>(null);

  const fitTo = useCallback((bounds: Bounds) => {
    fitBoundsRef.current = bounds;
    const c = canvasRef.current;
    if (!c) return;
    const fit = fitZoomPan(bounds, c.getWidth(), c.getHeight());
    c.setViewportTransform([fit.zoom, 0, 0, fit.zoom, fit.panX, fit.panY]);
  }, []);

  useEffect(() => {
    if (!canvasEl) return;

    const c = new Canvas(canvasEl, {
      selection: false, // 只读查看器：禁橡皮筋多选，保留点选
      preserveObjectStacking: true,
    });

    // 尺寸适配：fabric 默认 300x150，必须显式同步父容器尺寸。
    const wrapEl = canvasEl.parentElement;
    const measure = () => ({
      width: wrapEl?.clientWidth || CANVAS_FALLBACK_W,
      height: wrapEl?.clientHeight || CANVAS_FALLBACK_H,
    });
    c.setDimensions(measure());

    let resizeObserver: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined" && wrapEl) {
      const wrap = wrapEl;
      resizeObserver = new ResizeObserver(() => {
        c.setDimensions(measure());
        const bounds = fitBoundsRef.current;
        if (bounds) {
          const fit = fitZoomPan(bounds, c.getWidth(), c.getHeight());
          c.setViewportTransform([fit.zoom, 0, 0, fit.zoom, fit.panX, fit.panY]);
        }
        c.requestRenderAll();
      });
      resizeObserver.observe(wrap);
    }

    let dragging = false;
    let lastX = 0;
    let lastY = 0;
    let lastSubTargets: FabricObject[] = [];

    const offWheel = c.on("mouse:wheel", (opt) => {
      const e = opt.e as unknown as WheelLike;
      e.preventDefault();
      e.stopPropagation();
      const vpt = c.viewportTransform.slice() as Vpt;
      const zoom = clampZoom(vpt[0] * Math.pow(WHEEL_ZOOM_BASE, e.deltaY));
      const scale = zoom / vpt[0];
      const px = e.offsetX ?? 0;
      const py = e.offsetY ?? 0;
      vpt[4] = px - (px - vpt[4]) * scale;
      vpt[5] = py - (py - vpt[5]) * scale;
      vpt[0] = zoom;
      vpt[3] = zoom;
      c.setViewportTransform(vpt);
    });
    const offDown = c.on("mouse:down", (opt) => {
      const e = opt.e as unknown as PointerLike;
      dragging = true;
      lastX = e.clientX ?? 0;
      lastY = e.clientY ?? 0;
      lastSubTargets = opt.subTargets ?? [];
    });
    const offMove = c.on("mouse:move", (opt) => {
      const e = opt.e as unknown as PointerLike;
      if (dragging) {
        const vpt = c.viewportTransform.slice() as Vpt;
        vpt[4] += (e.clientX ?? 0) - lastX;
        vpt[5] += (e.clientY ?? 0) - lastY;
        lastX = e.clientX ?? 0;
        lastY = e.clientY ?? 0;
        c.setViewportTransform(vpt);
        return;
      }
      const target = opt.target;
      if (!target) {
        onHoverRef.current?.(null);
        return;
      }
      const d = dataOf(target);
      onHoverRef.current?.({ key: d.key ?? null, layer: d.layer ?? null, block: d.block });
    });
    const offUp = c.on("mouse:up", () => {
      dragging = false;
      lastSubTargets = [];
    });
    const offSelectionCreated = c.on("selection:created", (e) => {
      onObjectSelectedRef.current?.(resolveSelection(e.selected?.[0], lastSubTargets));
    });
    const offSelectionUpdated = c.on("selection:updated", (e) => {
      onObjectSelectedRef.current?.(resolveSelection(e.selected?.[0], lastSubTargets));
    });
    const offSelectionCleared = c.on("selection:cleared", () => {
      onObjectSelectedRef.current?.(null);
    });

    canvasRef.current = c;
    setCanvas(c);

    return () => {
      resizeObserver?.disconnect();
      offWheel();
      offDown();
      offMove();
      offUp();
      offSelectionCreated();
      offSelectionUpdated();
      offSelectionCleared();
      c.dispose();
      canvasRef.current = null;
      fitBoundsRef.current = null;
      setCanvas(null);
    };
  }, [canvasEl]);

  return { canvas, isReady: canvas != null, fitTo };
}
