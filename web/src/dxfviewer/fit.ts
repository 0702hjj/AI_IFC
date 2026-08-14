// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// fit-bounds：由 payload bounds 计算初始 viewport（zoom/pan）。
// 坐标模型：canvasPoint = flippedWorld * zoom + pan（Y 翻转经 flipBounds）。

import { flipBounds } from "./geometry";
import type { Bounds } from "./types";

/** FIT 常量：视口四边各留 5% 边距。 */
export const FIT_PADDING = 0.05;

export interface FitResult {
  zoom: number;
  panX: number;
  panY: number;
}

export function fitZoomPan(
  bounds: Bounds,
  canvasW: number,
  canvasH: number,
  padding: number = FIT_PADDING
): FitResult {
  const w = bounds.max[0] - bounds.min[0];
  const h = bounds.max[1] - bounds.min[1];
  const availW = canvasW * (1 - 2 * padding);
  const availH = canvasH * (1 - 2 * padding);
  const zx = w > 0 ? availW / w : Infinity;
  const zy = h > 0 ? availH / h : Infinity;
  const zoom = Math.min(zx, zy);
  const flipped = flipBounds(bounds);
  const cx = (flipped.min[0] + flipped.max[0]) / 2;
  const cy = (flipped.min[1] + flipped.max[1]) / 2;
  const z = Number.isFinite(zoom) ? zoom : 1;
  return {
    zoom: z,
    panX: canvasW / 2 - cx * z,
    panY: canvasH / 2 - cy * z,
  };
}
