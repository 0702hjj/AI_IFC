// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

export interface PinPosition {
  x: number;
  y: number;
}

export function aabbCenter(aabb: number[]): [number, number, number] {
  return [
    (aabb[0] + aabb[3]) / 2,
    (aabb[1] + aabb[4]) / 2,
    (aabb[2] + aabb[5]) / 2,
  ];
}

function mulMat4v4(m: number[], v: [number, number, number, number]) {
  return [
    m[0] * v[0] + m[4] * v[1] + m[8] * v[2] + m[12] * v[3],
    m[1] * v[0] + m[5] * v[1] + m[9] * v[2] + m[13] * v[3],
    m[2] * v[0] + m[6] * v[1] + m[10] * v[2] + m[14] * v[3],
    m[3] * v[0] + m[7] * v[1] + m[11] * v[2] + m[15] * v[3],
  ];
}

export function projectToCanvas(
  worldPos: number[],
  viewMatrix: number[],
  projMatrix: number[],
  canvasWidth: number,
  canvasHeight: number
): PinPosition | null {
  const view = mulMat4v4(viewMatrix, [worldPos[0], worldPos[1], worldPos[2], 1]);
  const clip = mulMat4v4(projMatrix, view as [number, number, number, number]);
  const w = clip[3];
  if (w <= 0) return null;
  const nx = clip[0] / w;
  const ny = clip[1] / w;
  const nz = clip[2] / w;
  if (nx < -1 || nx > 1 || ny < -1 || ny > 1 || nz < -1 || nz > 1) return null;
  return {
    x: ((1 + nx) / 2) * canvasWidth,
    y: ((1 - ny) / 2) * canvasHeight,
  };
}
