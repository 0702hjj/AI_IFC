// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// render.json payload v2 类型（与 services/cad/app/render.py 对齐）。
// 字段保持服务端的 snake_case 与 DXF 原始坐标系（Y 向上），不做归一化。

export interface Bounds {
  min: [number, number];
  max: [number, number];
}

export interface LayerInfo {
  name: string;
  color: number;
  linetype: string;
}

export interface UnsupportedEntity {
  type: string;
  handle: string;
  coords: number[];
}

interface EntityCommon {
  /** XDATA 稳定 key（与 ScriptMap 同源）；INSERT 展开子实体为 null。 */
  key: string | null;
  layer: string;
  /** ACI 颜色索引；256=BYLAYER，0=BYBLOCK。 */
  color: number;
  linetype: string;
  /** INSERT 展开子实体的块来源标记（块名）。 */
  block?: string;
}

export interface LineEntity extends EntityCommon {
  type: "LINE";
  start: [number, number];
  end: [number, number];
}

export interface CircleEntity extends EntityCommon {
  type: "CIRCLE";
  center: [number, number];
  radius: number;
}

export interface ArcEntity extends EntityCommon {
  type: "ARC";
  center: [number, number];
  radius: number;
  /** 原生 ARC：CCW，end < start 表跨 0°；bulge 展开段：end = start + 有向 sweep（未归一化，可负/超 360）。 */
  start_angle: number;
  end_angle: number;
}

export interface TextEntity extends EntityCommon {
  type: "TEXT";
  text: string;
  insert: [number, number];
  height: number;
}

export interface MTextEntity extends EntityCommon {
  type: "MTEXT";
  text: string;
  insert: [number, number];
}

export interface InsertEntity extends EntityCommon {
  type: "INSERT";
  name: string;
  insert: [number, number];
  rotation: number;
  scale: number;
}

export type RenderEntity =
  | LineEntity
  | CircleEntity
  | ArcEntity
  | TextEntity
  | MTextEntity
  | InsertEntity;

export interface RenderPayload {
  schemaVersion: number;
  bounds: Bounds | null;
  layers: LayerInfo[];
  entities: RenderEntity[];
  unsupported: UnsupportedEntity[];
}
