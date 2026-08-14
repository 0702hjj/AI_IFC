// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// render.json → fabric 对象装载：fetch → payloadToObjectSpecs（Task 2 纯函数，
// Y 翻转已在规格层完成）→ 实例化入 canvas → fit。图层开关与合并阈值在此。

import { useCallback, useEffect, useState } from "react";
import { Circle, FabricText, Group, Line, Path } from "fabric";
import type { Canvas, FabricObject } from "fabric";
import { renderJsonUrl } from "@/api/client";
import { payloadToObjectSpecs } from "./geometry";
import type { FabricObjectSpec } from "./geometry";
import type { Bounds, LayerInfo, RenderPayload } from "./types";

/** 实体数超过阈值按图层合并 Group：数千独立对象的选中/渲染路径会明显退化。 */
export const GROUP_MERGE_THRESHOLD = 2000;

export interface DxfRenderState {
  payload: RenderPayload | null;
  layers: LayerInfo[];
  hiddenLayers: string[];
  unsupportedCount: number;
  error: string | null;
  toggleLayer: (name: string) => void;
}

interface LineProps {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

// fabric 7 类型不含自定义 data 字段；运行时挂载照常，读写统一走此类型。
type WithData = { data?: { key?: string | null; entityType?: string; layer?: string; block?: string } };

function specToObject(spec: FabricObjectSpec): FabricObject {
  // 只读：禁移动/控制点；key=null（块子实体）不可选中，保留 hover 事件。
  const common: Record<string, unknown> = {
    selectable: spec.key != null,
    evented: true,
    hasControls: false,
    lockMovementX: true,
    lockMovementY: true,
    hoverCursor: spec.key != null ? "pointer" : "default",
  };
  let obj: FabricObject;
  switch (spec.kind) {
    case "line": {
      const { x1, y1, x2, y2, ...rest } = spec.props as unknown as LineProps &
        Record<string, unknown>;
      obj = new Line([x1, y1, x2, y2], { ...rest, ...common });
      break;
    }
    case "circle":
      obj = new Circle({ ...spec.props, ...common });
      break;
    case "path": {
      const { d, ...rest } = spec.props as { d: string } & Record<string, unknown>;
      obj = new Path(d, { ...rest, ...common });
      break;
    }
    case "text": {
      const { text, ...rest } = spec.props as { text: string } & Record<string, unknown>;
      obj = new FabricText(text, { ...rest, ...common });
      break;
    }
  }
  (obj as FabricObject & WithData).data = {
    key: spec.key,
    entityType: spec.kind,
    layer: spec.layer,
    ...(spec.block !== undefined ? { block: spec.block } : {}),
  };
  return obj;
}

function mergeIntoLayerGroups(objects: FabricObject[]): Group[] {
  const byLayer = new Map<string, FabricObject[]>();
  for (const obj of objects) {
    const layer = dataOfLayer(obj);
    const arr = byLayer.get(layer) ?? [];
    arr.push(obj);
    byLayer.set(layer, arr);
  }
  return [...byLayer.entries()].map(([layer, objs]) => {
    for (const o of objs) o.selectable = false;
    const group = new Group(objs, { selectable: true });
    (group as Group & WithData).data = { layer };
    return group;
  });
}

function dataOfLayer(obj: FabricObject): string {
  return (obj as FabricObject & WithData).data?.layer ?? "";
}

export function useDxfRender(
  modelId: string,
  canvas: Canvas | null,
  fitTo: (bounds: Bounds) => void
): DxfRenderState {
  const [payload, setPayload] = useState<RenderPayload | null>(null);
  const [hiddenLayers, setHiddenLayers] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!canvas) return;
    let cancelled = false;
    setError(null);
    // render.json 是 Go 直挂只读端点（非 envelope），直接 fetch。
    fetch(renderJsonUrl(modelId))
      .then((resp) => {
        if (!resp.ok) throw new Error(`render.json 加载失败（HTTP ${resp.status}）`);
        return resp.json() as Promise<RenderPayload>;
      })
      .then((data) => {
        if (cancelled) return;
        setPayload(data);
        const objects = payloadToObjectSpecs(data).map(specToObject);
        if (objects.length > GROUP_MERGE_THRESHOLD) {
          canvas.add(...mergeIntoLayerGroups(objects));
        } else if (objects.length > 0) {
          canvas.add(...objects);
        }
        if (data.bounds) fitTo(data.bounds);
        canvas.requestRenderAll();
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [modelId, canvas, fitTo]);

  const toggleLayer = useCallback(
    (name: string) => {
      setHiddenLayers((prev) => {
        const hide = !prev.includes(name);
        if (canvas) {
          for (const obj of canvas.getObjects()) {
            if (dataOfLayer(obj) === name) obj.visible = !hide;
          }
          canvas.requestRenderAll();
        }
        return hide ? [...prev, name] : prev.filter((x) => x !== name);
      });
    },
    [canvas]
  );

  return {
    payload,
    layers: payload?.layers ?? [],
    hiddenLayers,
    unsupportedCount: payload?.unsupported.length ?? 0,
    error,
    toggleLayer,
  };
}
