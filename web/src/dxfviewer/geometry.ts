// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// payload → fabric 对象规格的纯函数层。规格是纯数据（不 import fabric），
// 组件层（Task 3）才实例化。DXF Y 向上 → canvas Y 向下的翻转统一在此完成。

import type { Bounds, LayerInfo, RenderPayload } from "./types";

/** MTEXT 不带 height 字段，用 DXF 标准默认字高。 */
export const DEFAULT_MTEXT_HEIGHT = 0.2;
export const FALLBACK_COLOR = "#808080";

export interface FabricObjectSpec {
  kind: "line" | "circle" | "path" | "text";
  layer: string;
  key: string | null;
  /** INSERT 展开子实体的块来源（块名）。 */
  block?: string;
  props: Record<string, unknown>;
}

// ACI 常用色表；7 在浅色画布上按黑渲染（对比度惯例）。其余索引回落灰色。
const ACI_COLORS: Record<number, string> = {
  1: "#ff0000",
  2: "#ffff00",
  3: "#00ff00",
  4: "#00ffff",
  5: "#0000ff",
  6: "#ff00ff",
  7: "#000000",
  8: "#808080",
  9: "#c0c0c0",
};

export function aciColor(aci: number): string {
  return ACI_COLORS[aci] ?? FALLBACK_COLOR;
}

export function resolveEntityColor(
  color: number,
  layer: string,
  layers: LayerInfo[]
): string {
  if (color === 256) {
    const info = layers.find((l) => l.name === layer);
    return aciColor(info ? info.color : 7);
  }
  if (color === 0) return FALLBACK_COLOR;
  return aciColor(color);
}

export function linetypeDash(linetype: string): number[] | undefined {
  const name = linetype.toUpperCase();
  if (name === "CONTINUOUS" || name === "BYLAYER" || name === "BYBLOCK") {
    return undefined;
  }
  return [6, 4];
}

export function flipBounds(bounds: Bounds): Bounds {
  return {
    min: [bounds.min[0], -bounds.max[1]],
    max: [bounds.max[0], -bounds.min[1]],
  };
}

const EPS = 1e-9;
const DEG = Math.PI / 180;

function r6(n: number): number {
  const v = Math.round(n * 1e6) / 1e6;
  return v === 0 ? 0 : v;
}

function normalizeDeg(a: number): number {
  const v = a % 360;
  return v < 0 ? v + 360 : v;
}

// 角度制约定（对齐 render.py）：原生 ARC 恒 CCW，end < start 表跨 0°；
// bulge 展开段 end = start + 有向 sweep（未归一化），end < 0 或 ≥ 360 时按有向
// sweep 解读。end ∈ [0,360) 且 < start 的歧义情形按原生跨零（CCW）处理。
function arcSweep(startDeg: number, endDeg: number): number {
  const start = normalizeDeg(startDeg);
  let sweep: number;
  if (endDeg < 0 || endDeg >= 360) {
    sweep = endDeg - start;
  } else if (endDeg < start) {
    sweep = endDeg - start + 360;
  } else {
    sweep = endDeg - start;
  }
  if (sweep > 360) return 360;
  if (sweep < -360) return -360;
  return sweep;
}

function pointAt(cx: number, cy: number, r: number, angleDeg: number): string {
  const x = r6(cx + r * Math.cos(angleDeg * DEG));
  const y = r6(-(cy + r * Math.sin(angleDeg * DEG)));
  return `${x} ${y}`;
}

export function arcToPathD(
  cx: number,
  cy: number,
  r: number,
  startDeg: number,
  endDeg: number
): string {
  const start = normalizeDeg(startDeg);
  const sweep = arcSweep(startDeg, endDeg);
  const radius = r6(r);
  const startPt = pointAt(cx, cy, r, start);
  if (Math.abs(sweep) < EPS) return `M ${startPt}`;
  // Y 翻转：Y-up 的 CCW（sweep>0）在 canvas 变 CW，即 SVG sweep-flag=1。
  const sweepFlag = sweep > 0 ? 1 : 0;
  if (Math.abs(sweep) >= 360 - EPS) {
    const midPt = pointAt(cx, cy, r, start + sweep / 2);
    const endPt = pointAt(cx, cy, r, start + sweep);
    return `M ${startPt} A ${radius} ${radius} 0 1 ${sweepFlag} ${midPt} A ${radius} ${radius} 0 1 ${sweepFlag} ${endPt}`;
  }
  const largeArc = Math.abs(sweep) >= 180 ? 1 : 0;
  const endPt = pointAt(cx, cy, r, start + sweep);
  return `M ${startPt} A ${radius} ${radius} 0 ${largeArc} ${sweepFlag} ${endPt}`;
}

export function payloadToObjectSpecs(payload: RenderPayload): FabricObjectSpec[] {
  const specs: FabricObjectSpec[] = [];
  for (const entity of payload.entities) {
    const base = {
      layer: entity.layer,
      key: entity.key,
      ...(entity.block !== undefined ? { block: entity.block } : {}),
    };
    const stroke = resolveEntityColor(entity.color, entity.layer, payload.layers);
    const dash = linetypeDash(entity.linetype);
    const dashProps = dash !== undefined ? { strokeDashArray: dash } : {};
    switch (entity.type) {
      case "LINE":
        specs.push({
          ...base,
          kind: "line",
          props: {
            x1: r6(entity.start[0]),
            y1: r6(-entity.start[1]),
            x2: r6(entity.end[0]),
            y2: r6(-entity.end[1]),
            stroke,
            ...dashProps,
          },
        });
        break;
      case "CIRCLE":
        specs.push({
          ...base,
          kind: "circle",
          props: {
            left: r6(entity.center[0] - entity.radius),
            top: r6(-entity.center[1] - entity.radius),
            radius: r6(entity.radius),
            stroke,
            fill: null,
            ...dashProps,
          },
        });
        break;
      case "ARC":
        specs.push({
          ...base,
          kind: "path",
          props: {
            d: arcToPathD(
              entity.center[0],
              entity.center[1],
              entity.radius,
              entity.start_angle,
              entity.end_angle
            ),
            stroke,
            fill: null,
            ...dashProps,
          },
        });
        break;
      case "TEXT":
        specs.push({
          ...base,
          kind: "text",
          props: {
            left: r6(entity.insert[0]),
            top: r6(-entity.insert[1] - entity.height),
            text: entity.text,
            fontSize: r6(entity.height),
            fill: stroke,
          },
        });
        break;
      case "MTEXT":
        specs.push({
          ...base,
          kind: "text",
          props: {
            left: r6(entity.insert[0]),
            top: r6(-entity.insert[1] - DEFAULT_MTEXT_HEIGHT),
            text: entity.text,
            fontSize: DEFAULT_MTEXT_HEIGHT,
            fill: stroke,
          },
        });
        break;
      case "INSERT":
        // INSERT 本体无独立几何：已展开的子实体各自成条目（block 标记），
        // 未展开（非等比 scale）者由 unsupported 计数明面化。
        break;
    }
  }
  return specs;
}
