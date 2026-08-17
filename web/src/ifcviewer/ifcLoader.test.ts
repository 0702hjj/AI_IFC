// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// ifcLoader 纯逻辑层单测：web-ifc wasm 在 jsdom 不可执行，全部经 fake
// IfcApi（结构化窄接口 IfcApiLike）驱动——几何/树/属性提取与 wasm 路径
// 拼接是测试价值所在（官方 three.js 示例模式的提取逻辑）。

import { describe, it, expect, vi } from "vitest";
import {
  initIfcApi,
  loadIfcGeometry,
  loadSpatialTree,
  loadElementProps,
  wasmBaseUrl,
  type IfcApiLike,
  type IfcFlatMeshLike,
  type IfcGeometryLike,
  type IfcVector,
} from "./ifcLoader";

// --- fake 基件 ---

function vec<T>(items: T[]): IfcVector<T> {
  return {
    get: (i: number) => items[i],
    size: () => items.length,
    [Symbol.iterator]: function* () {
      for (const it of items) yield it;
    },
  };
}

function fakeGeometry(vertex: number[], index: number[]): IfcGeometryLike {
  const vertF32 = new Float32Array(vertex);
  const idxU32 = new Uint32Array(index);
  return {
    GetVertexData: () => 1,
    GetVertexDataSize: () => vertF32.byteLength,
    GetIndexData: () => 2,
    GetIndexDataSize: () => idxU32.byteLength,
  };
}

interface FakeApiOptions {
  openResult?: number;
  meshes?: IfcFlatMeshLike[];
  spatial?: { expressID: number; type: string; children: unknown[] };
  lines?: Record<number, unknown>;
  psets?: unknown[];
}

function fakeApi(opts: FakeApiOptions = {}): IfcApiLike & {
  calls: { setWasmPath: string[]; closed: number[]; lines: number[]; psetElements: number[] };
} {
  const calls = { setWasmPath: [] as string[], closed: [] as number[], lines: [] as number[], psetElements: [] as number[] };
  const vertexStore = new Map<number, Float32Array>([[1, new Float32Array([0, 0, 0, 1, 1, 0, 0, 1, 1, 1, 1, 1])]]);
  const indexStore = new Map<number, Uint32Array>([[2, new Uint32Array([0, 1, 2])]]);
  const geoms = new Map<number, IfcGeometryLike>();
  const api: IfcApiLike = {
    Init: vi.fn(async () => {}),
    SetWasmPath: (path: string) => {
      calls.setWasmPath.push(path);
    },
    OpenModel: () => opts.openResult ?? 7,
    CloseModel: (id: number) => {
      calls.closed.push(id);
    },
    IsModelOpen: () => true,
    StreamAllMeshes: (_id: number, cb: (m: IfcFlatMeshLike) => void) => {
      for (const m of opts.meshes ?? []) cb(m);
    },
    GetGeometry: (_id: number, geometryExpressID: number) => {
      const g = geoms.get(geometryExpressID);
      if (g) return g;
      const created = fakeGeometry([0, 0, 0, 1, 1, 0, 0, 1, 1, 1, 1, 1], [0, 1, 2]);
      geoms.set(geometryExpressID, created);
      return created;
    },
    GetVertexArray: (ptr: number) => vertexStore.get(ptr) ?? new Float32Array(0),
    GetIndexArray: (ptr: number) => indexStore.get(ptr) ?? new Uint32Array(0),
    GetLine: (_id: number, expressID: number) => {
      calls.lines.push(expressID);
      return opts.lines?.[expressID];
    },
    properties: {
      getSpatialStructure: vi.fn(async () => opts.spatial ?? { expressID: 1, type: "IFCPROJECT", children: [] }),
      getPropertySets: vi.fn(async (_id: number, elementID: number) => {
        calls.psetElements.push(elementID);
        return opts.psets ?? [];
      }),
    },
  };
  return Object.assign(api, { calls });
}

function placed(geometryExpressID: number, flatTransformation: number[]) {
  return {
    color: { x: 0.5, y: 0.5, z: 0.5, w: 1 },
    geometryExpressID,
    flatTransformation,
  };
}

// --- wasm 路径 ---

describe("wasmBaseUrl", () => {
  it("拼接指定 base 与 wasm/ 目录", () => {
    expect(wasmBaseUrl("/AI_IFC/")).toBe("/AI_IFC/wasm/");
  });

  it("默认 base 为 / 时得到 /wasm/", () => {
    expect(wasmBaseUrl("/")).toBe("/wasm/");
  });
});

describe("initIfcApi", () => {
  it("先 SetWasmPath 后 Init，路径含 base", async () => {
    const api = fakeApi();
    await initIfcApi(api, "/AI_IFC/");
    expect(api.calls.setWasmPath).toEqual(["/AI_IFC/wasm/"]);
  });

  it("base 缺省用 vite BASE_URL", async () => {
    const api = fakeApi();
    await initIfcApi(api);
    expect(api.calls.setWasmPath).toEqual([wasmBaseUrl()]);
  });
});

// --- 几何提取 ---

describe("loadIfcGeometry", () => {
  it("提取 placed geometry：位置砍 4 分量→3，索引原样，保留变换矩阵", () => {
    const api = fakeApi({
      meshes: [
        {
          expressID: 11,
          geometries: vec([placed(21, [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 1, 2, 3, 1])]),
        },
      ],
    });
    const meshes = loadIfcGeometry(api, 7);
    expect(meshes).toHaveLength(1);
    // fake 顶点堆 12 floats = 3 顶点 × (x,y,z,w) → 砍 w 后 9
    expect(Array.from(meshes[0].positions)).toEqual([0, 0, 0, 1, 0, 0, 1, 1, 1]);
    expect(Array.from(meshes[0].indices)).toEqual([0, 1, 2]);
    expect(meshes[0].transform).toHaveLength(16);
    expect(meshes[0].expressID).toBe(11);
  });

  it("同一 element 的多个 placed geometry 拆成多条（各自变换）", () => {
    const api = fakeApi({
      meshes: [
        {
          expressID: 12,
          geometries: vec([
            placed(31, new Array(16).fill(0)),
            placed(32, new Array(16).fill(1)),
          ]),
        },
      ],
    });
    const meshes = loadIfcGeometry(api, 7);
    expect(meshes).toHaveLength(2);
    expect(meshes[0].transform[0]).toBe(0);
    expect(meshes[1].transform[0]).toBe(1);
  });
});

// --- 空间树 ---

describe("loadSpatialTree", () => {
  it("空间结构映射为带名字的树：Name 优先，缺省回退 类型#expressID", async () => {
    const api = fakeApi({
      spatial: {
        expressID: 1,
        type: "IFCPROJECT",
        children: [
          { expressID: 2, type: "IFCSITE", children: [] },
          { expressID: 3, type: "IFCBUILDING", children: [] },
        ],
      },
      lines: {
        1: { Name: { value: "示范项目" }, GlobalId: { value: "g1" } },
        3: { GlobalId: { value: "g3" } }, // 无 Name → 回退
      },
    });
    const tree = await loadSpatialTree(api, 7);
    expect(tree.name).toBe("示范项目");
    expect(tree.children[0].name).toBe("IFCSITE #2");
    expect(tree.children[1].name).toBe("IFCBUILDING #3");
  });

  it("根节点携带 expressID 供选中联动", async () => {
    const api = fakeApi();
    const tree = await loadSpatialTree(api, 7);
    expect(tree.expressID).toBe(1);
    expect(tree.type).toBe("IFCPROJECT");
  });

  it("children 缺省（空/未定义）时安全映射为空数组", async () => {
    const api = fakeApi({
      spatial: { expressID: 1, type: "IFCPROJECT", children: undefined as never },
    });
    const tree = await loadSpatialTree(api, 7);
    expect(tree.children).toEqual([]);
  });

  it("GetLine 未命中（undefined）时节点名回退 类型#expressID", async () => {
    const api = fakeApi({ spatial: { expressID: 9, type: "IFCWALL", children: [] } });
    const tree = await loadSpatialTree(api, 7);
    expect(tree.name).toBe("IFCWALL #9");
  });
});

// --- 属性提取 ---

describe("loadElementProps", () => {
  it("标量行字符串化 + 对象行跳过 + pset 展开为 组.名 行", async () => {
    const api = fakeApi({
      lines: {
        42: {
          GlobalId: { value: "0abc$W" },
          Name: { value: "基本墙" },
          ObjectType: { value: "Wall-Std" },
          Tag: { value: "W-1" },
          ObjectPlacement: { Value: "嵌套对象应跳过" },
        },
      },
      psets: [
        {
          Name: { value: "Pset_WallCommon" },
          HasProperties: [
            { Name: { value: "Length" }, NominalValue: { value: 3.2 } },
            { Name: { value: "Reference" }, NominalValue: { value: "Std" } },
          ],
        },
      ],
    });
    const rows = await loadElementProps(api, 7, 42);
    const map = Object.fromEntries(rows.map((r) => [r.label, r.value]));
    expect(map["GlobalId"]).toBe("0abc$W");
    expect(map["Name"]).toBe("基本墙");
    expect(map["ObjectType"]).toBe("Wall-Std");
    expect(map["Tag"]).toBe("W-1");
    expect(map["Pset_WallCommon.Length"]).toBe("3.2");
    expect(map["Pset_WallCommon.Reference"]).toBe("Std");
    // 嵌套对象行不出现
    expect(rows.find((r) => r.label === "ObjectPlacement")).toBeUndefined();
  });

  it("行序稳定：标量在前 pset 在后，同组保持声明顺序", async () => {
    const api = fakeApi({
      lines: { 42: { Name: { value: "a" }, Tag: { value: "t" } } },
      psets: [
        {
          Name: { value: "P1" },
          HasProperties: [{ Name: { value: "x" }, NominalValue: { value: 1 } }],
        },
        {
          Name: { value: "P2" },
          HasProperties: [{ Name: { value: "y" }, NominalValue: { value: 2 } }],
        },
      ],
    });
    const rows = await loadElementProps(api, 7, 42);
    expect(rows.map((r) => r.label)).toEqual(["Name", "Tag", "P1.x", "P2.y"]);
  });

  it("空 psets（无属性集）时只出标量行", async () => {
    const api = fakeApi({ lines: { 42: { Name: { value: "a" } } }, psets: [] });
    const rows = await loadElementProps(api, 7, 42);
    expect(rows).toHaveLength(1);
  });
});
