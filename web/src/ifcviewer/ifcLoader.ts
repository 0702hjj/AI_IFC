// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// web-ifc 纯逻辑层：IfcAPI 装配 / 几何 / 空间树 / 属性提取。
// 本文件是移植单元——不依赖 React、router、@/api（web-ifc IfcAPI 经结构化
// 窄接口 IfcApiLike 注入），移植到其他前端时只需换 openIfcApi 的数据源。
// 提取模式对齐 web-ifc 官方 three.js 示例（IfcAPI.Init → OpenModel →
// StreamAllMeshes → GetGeometry → GetVertexArray/GetIndexArray）。

import { IfcAPI } from "web-ifc";

// web-ifc 类型子集（d.ts 中 Vector/IfcGeometry/FlatMesh/Properties 的窄化），
// 保持注入面可 fake（jsdom 无法执行 wasm）。
export interface IfcVector<T> extends Iterable<T> {
  get(index: number): T;
  size(): number;
}

export interface IfcGeometryLike {
  GetVertexData(): number;
  GetVertexDataSize(): number;
  GetIndexData(): number;
  GetIndexDataSize(): number;
}

export interface IfcPlacedGeometryLike {
  color: { x: number; y: number; z: number; w: number };
  geometryExpressID: number;
  flatTransformation: number[];
}

export interface IfcFlatMeshLike {
  expressID: number;
  geometries: IfcVector<IfcPlacedGeometryLike>;
}

export interface IfcSpatialNodeLike {
  expressID: number;
  type: string;
  children: unknown[];
}

export interface IfcApiLike {
  Init(customLocateFileHandler?: unknown, forceSingleThread?: boolean): Promise<void>;
  SetWasmPath(path: string, absolute?: boolean): void;
  OpenModel(data: Uint8Array): number;
  CloseModel(modelID: number): void;
  IsModelOpen(modelID: number): boolean;
  StreamAllMeshes(modelID: number, meshCallback: (mesh: IfcFlatMeshLike) => void): void;
  GetGeometry(modelID: number, geometryExpressID: number): IfcGeometryLike;
  GetVertexArray(ptr: number, size: number): Float32Array;
  GetIndexArray(ptr: number, size: number): Uint32Array;
  GetLine(modelID: number, expressID: number, flatten?: boolean): unknown;
  properties: {
    getSpatialStructure(modelID: number, includeProperties?: boolean): Promise<IfcSpatialNodeLike>;
    getPropertySets(modelID: number, elementID?: number, recursive?: boolean): Promise<unknown[]>;
  };
}

// --- 提取结果形状（three 挂载层的输入，序列化友好） ---

/** 单条 placed geometry：位置砍掉 w 分量、索引原样、携带放置矩阵。 */
export interface IfcMeshData {
  expressID: number;
  positions: Float32Array;
  indices: Uint32Array;
  color: { x: number; y: number; z: number; w: number };
  transform: number[];
}

export interface SpatialTreeNode {
  expressID: number;
  type: string;
  name: string;
  children: SpatialTreeNode[];
}

export interface PropertyRow {
  label: string;
  value: string;
}

// --- wasm 路径 ---

/** wasm 目录 URL：base 对齐 vite base（部署在子路径时自适应）。 */
export function wasmBaseUrl(base = import.meta.env.BASE_URL): string {
  return `${base.endsWith("/") ? base : `${base}/`}wasm/`;
}

export async function initIfcApi(api: IfcApiLike, base?: string): Promise<void> {
  api.SetWasmPath(wasmBaseUrl(base));
  await api.Init();
}

// --- 几何提取 ---

export function loadIfcGeometry(api: IfcApiLike, modelID: number): IfcMeshData[] {
  const meshes: IfcMeshData[] = [];
  api.StreamAllMeshes(modelID, (flat) => {
    for (const placed of flat.geometries) {
      const geom = api.GetGeometry(modelID, placed.geometryExpressID);
      // web-ifc 顶点为 (x,y,z,w) 4 分量交错，three BufferGeometry 用 3 分量
      const verts = api.GetVertexArray(geom.GetVertexData(), geom.GetVertexDataSize());
      const indices = api.GetIndexArray(geom.GetIndexData(), geom.GetIndexDataSize());
      const positions = new Float32Array(Math.floor(verts.length / 4) * 3);
      for (let i = 0, o = 0; i < verts.length; i += 4, o += 3) {
        positions[o] = verts[i];
        positions[o + 1] = verts[i + 1];
        positions[o + 2] = verts[i + 2];
      }
      meshes.push({
        expressID: flat.expressID,
        positions,
        indices: new Uint32Array(indices),
        color: placed.color,
        transform: placed.flatTransformation,
      });
    }
  });
  return meshes;
}

// --- 空间树 ---

interface IfcValueField {
  value?: unknown;
}

/** IFC 行字段的 value 展开（IfcLabel/IfcText/IfcIdentifier 均 { value } 形状）。 */
function fieldText(row: Record<string, unknown>, key: string): string | null {
  const v = row[key];
  if (v == null || typeof v !== "object") return null;
  const inner = (v as IfcValueField).value;
  if (inner == null) return null;
  return String(inner);
}

function toTreeNode(api: IfcApiLike, modelID: number, node: IfcSpatialNodeLike): SpatialTreeNode {
  const line = api.GetLine(modelID, node.expressID);
  const name =
    (line != null && typeof line === "object"
      ? fieldText(line as Record<string, unknown>, "Name")
      : null) ?? `${node.type} #${node.expressID}`;
  return {
    expressID: node.expressID,
    type: node.type,
    name,
    children: (node.children ?? []).map((c) =>
      toTreeNode(api, modelID, c as IfcSpatialNodeLike)
    ),
  };
}

export async function loadSpatialTree(
  api: IfcApiLike,
  modelID: number
): Promise<SpatialTreeNode> {
  const root = await api.properties.getSpatialStructure(modelID, false);
  return toTreeNode(api, modelID, root);
}

// --- 属性提取 ---

/** 标量行：行对象的字段值为 { value } 包装或原始标量（flatten=false 时嵌套对象跳过）。 */
function scalarRow(label: string, v: unknown): PropertyRow | null {
  if (v == null) return null;
  if (typeof v === "object") {
    const inner = (v as IfcValueField).value;
    if (inner == null || typeof inner === "object") return null;
    return { label, value: String(inner) };
  }
  return { label, value: String(v) };
}

export async function loadElementProps(
  api: IfcApiLike,
  modelID: number,
  expressID: number
): Promise<PropertyRow[]> {
  const line = api.GetLine(modelID, expressID);
  const rows: PropertyRow[] = [];
  if (line != null && typeof line === "object") {
    for (const [key, v] of Object.entries(line as Record<string, unknown>)) {
      const row = scalarRow(key, v);
      if (row) rows.push(row);
    }
  }
  const psets = await api.properties.getPropertySets(modelID, expressID, false);
  for (const ps of psets) {
    if (ps == null || typeof ps !== "object") continue;
    const pset = ps as Record<string, unknown>;
    const psetName = fieldText(pset, "Name") ?? "Pset";
    const hasProps = pset.HasProperties;
    if (!Array.isArray(hasProps)) continue;
    for (const p of hasProps) {
      if (p == null || typeof p !== "object") continue;
      const prop = p as Record<string, unknown>;
      const name = fieldText(prop, "Name");
      if (name == null) continue;
      const row = scalarRow(`${psetName}.${name}`, prop.NominalValue);
      if (row) rows.push(row);
    }
  }
  return rows;
}

// --- 模型打开（浏览器绑定点，移植时替换数据源） ---

export interface OpenedIfcModel {
  api: IfcApiLike;
  modelID: number;
  close: () => void;
}

export async function openIfcApi(data: Uint8Array): Promise<OpenedIfcModel> {
  const api = new IfcAPI() as unknown as IfcApiLike;
  await initIfcApi(api);
  const modelID = api.OpenModel(data);
  if (modelID < 0) throw new Error("web-ifc OpenModel 失败");
  return {
    api,
    modelID,
    close: () => {
      if (api.IsModelOpen(modelID)) api.CloseModel(modelID);
    },
  };
}
