// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// IfcLiteViewer 组件测试：three/web-ifc wasm 在 jsdom 均不可执行。策略：
// - "./ifcScene"（three 挂载层）整体 mock；
// - "./ifcLoader" 仅替换浏览器绑定的 openIfcApi，load* 纯函数用真实现跑
//   fake IfcAPI（编排链路拿真实提取逻辑覆盖）；
// - "@/api/client" 只 mock downloadIfcBytes。
// 测试价值：加载编排（下载→init→load→装配→清理）、树/属性面板渲染、
// 拾取/树点击的选中联动（store.setSelected + 场景 setSelection）。

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act, cleanup, render, screen, fireEvent, waitFor, within } from "@testing-library/react";

// three 挂载层 fake：IfcLiteViewer 不直接 import three，mock 后测试进程不加载真 three
const mountLayer = vi.hoisted(() => {
  const handles: {
    addMesh: ReturnType<typeof vi.fn>;
    fitToBoundingBox: ReturnType<typeof vi.fn>;
    setSelection: ReturnType<typeof vi.fn>;
    dispose: ReturnType<typeof vi.fn>;
    pick: ReturnType<typeof vi.fn>;
  }[] = [];
  return {
    handles,
    pickResult: null as number | null,
    mountIfcScene: vi.fn(() => {
      const handle = {
        addMesh: vi.fn(),
        fitToBoundingBox: vi.fn(),
        setSelection: vi.fn(),
        dispose: vi.fn(),
        pick: vi.fn(() => mountLayer.pickResult),
      };
      handles.push(handle);
      return handle;
    }),
  };
});
vi.mock("./ifcScene", () => mountLayer);

// web-ifc 真模块不需要（openIfcApi 被替换）
vi.mock("web-ifc", () => ({ IfcAPI: class {} }));

// fake IfcAPI：形状对齐 ifcLoader.IfcApiLike
const fakeApi = vi.hoisted(() => {
  function vec<T>(items: T[]) {
    return {
      get: (i: number) => items[i],
      size: () => items.length,
      [Symbol.iterator]: function* () {
        yield* items;
      },
    };
  }
  const state = {
    wasmPaths: [] as string[],
    openedWith: [] as Uint8Array[],
    closed: [] as number[],
    modelID: 7,
  };
  const api = {
    Init: vi.fn(async () => {}),
    SetWasmPath: (p: string) => state.wasmPaths.push(p),
    OpenModel: (d: Uint8Array) => {
      state.openedWith.push(d);
      return state.modelID;
    },
    CloseModel: (id: number) => state.closed.push(id),
    IsModelOpen: () => true,
    StreamAllMeshes: (_id: number, cb: (m: unknown) => void) => {
      cb({
        expressID: 11,
        geometries: vec([
          {
            color: { x: 0.5, y: 0.5, z: 0.5, w: 1 },
            geometryExpressID: 21,
            flatTransformation: new Array(16).fill(0),
          },
        ]),
      });
    },
    GetGeometry: () => ({
      GetVertexData: () => 1,
      GetVertexDataSize: () => 48,
      GetIndexData: () => 2,
      GetIndexDataSize: () => 12,
    }),
    GetVertexArray: () => new Float32Array([0, 0, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1]),
    GetIndexArray: () => new Uint32Array([0, 1, 2]),
    GetLine: (_id: number, eid: number) =>
      eid === 11
        ? { Name: { value: "基本墙" }, Tag: { value: "W-1" }, GlobalId: { value: "0abc$W" } }
        : undefined,
    properties: {
      getSpatialStructure: vi.fn(async () => ({
        expressID: 1,
        type: "IFCPROJECT",
        children: [{ expressID: 2, type: "IFCBUILDINGSTOREY", children: [] }],
      })),
      getPropertySets: vi.fn(async () => []),
    },
  };
  return { api, state };
});

// ifcLoader 部分替换：openIfcApi 返回 fake api 包装
vi.mock("./ifcLoader", async (importOriginal) => {
  const orig = await importOriginal<typeof import("./ifcLoader")>();
  return {
    ...orig,
    openIfcApi: vi.fn(async (data: Uint8Array) => {
      fakeApi.state.openedWith.push(data);
      return {
        api: fakeApi.api,
        modelID: fakeApi.state.modelID,
        close: () => fakeApi.state.closed.push(fakeApi.state.modelID),
      };
    }),
  };
});

const clientFake = vi.hoisted(() => ({
  downloadIfcBytes: vi.fn(),
  locateScript: vi.fn(),
}));
vi.mock("@/api/client", () => clientFake);

import IfcLiteViewer from "./IfcLiteViewer";
import { openIfcApi } from "./ifcLoader";
import { useViewerStore } from "@/viewer/store";

beforeEach(() => {
  clientFake.downloadIfcBytes.mockReset();
  clientFake.downloadIfcBytes.mockResolvedValue(new Uint8Array([1, 2, 3]));
  clientFake.locateScript.mockReset();
  clientFake.locateScript.mockResolvedValue({ found: false });
  mountLayer.mountIfcScene.mockClear();
  mountLayer.handles.length = 0;
  mountLayer.pickResult = null;
  fakeApi.state.openedWith = [];
  fakeApi.state.closed = [];
  useViewerStore.setState({ selectedId: null, scriptJump: null });
});

afterEach(() => {
  cleanup();
  useViewerStore.setState({ selectedId: null, scriptJump: null });
});

function renderViewer(modelId = "m_abcd0000abcd0001") {
  return render(<IfcLiteViewer modelId={modelId} />);
}

async function ready() {
  // 树渲染是异步链（下载→open→几何→树 setState），用 findBy 等出现而非立即断言
  await screen.findByTestId("ifc-tree");
  await screen.findByText("IFCBUILDINGSTOREY #2");
}

describe("IfcLiteViewer 加载编排", () => {
  it("下载 IFC 字节 → openIfcApi → 几何装配 → fit → 树渲染", async () => {
    renderViewer();
    await ready();
    expect(clientFake.downloadIfcBytes).toHaveBeenCalledWith("m_abcd0000abcd0001");
    expect(openIfcApi).toHaveBeenCalled();
    const handle = mountLayer.handles[0];
    expect(handle.addMesh).toHaveBeenCalledTimes(1);
    expect(handle.fitToBoundingBox).toHaveBeenCalledTimes(1);
    expect(screen.getByText("IFCBUILDINGSTOREY #2")).toBeTruthy();
  });

  it("卸载时关模型 + dispose 场景", async () => {
    const { unmount } = renderViewer();
    await ready();
    unmount();
    expect(fakeApi.state.closed).toEqual([fakeApi.state.modelID]);
    expect(mountLayer.handles[0].dispose).toHaveBeenCalled();
  });

  it("下载失败出错误横幅，不装配场景", async () => {
    clientFake.downloadIfcBytes.mockRejectedValue(new Error("network down"));
    renderViewer();
    expect(await screen.findByText(/模型加载失败/)).toBeTruthy();
    expect(mountLayer.mountIfcScene).not.toHaveBeenCalled();
  });
});

describe("IfcLiteViewer 选中联动", () => {
  it("画布点击拾取到构件 → store 选中 + 场景高亮 + 属性面板出标量行", async () => {
    renderViewer();
    await ready();
    mountLayer.pickResult = 11;
    await act(async () => {
      fireEvent.click(screen.getByTestId("ifc-canvas"));
    });
    expect(useViewerStore.getState().selectedId).toBe("11");
    expect(mountLayer.handles[0].setSelection).toHaveBeenCalledWith(11);
    expect(await screen.findByText("基本墙")).toBeTruthy();
    expect(screen.getByText("W-1")).toBeTruthy();
  });

  it("拾取落空 → 清选中（store + 场景 + 面板回空态）", async () => {
    renderViewer();
    await ready();
    mountLayer.pickResult = 11;
    await act(async () => {
      fireEvent.click(screen.getByTestId("ifc-canvas"));
    });
    expect(screen.queryByText("基本墙")).toBeTruthy();
    mountLayer.pickResult = null;
    await act(async () => {
      fireEvent.click(screen.getByTestId("ifc-canvas"));
    });
    expect(useViewerStore.getState().selectedId).toBeNull();
    expect(mountLayer.handles[0].setSelection).toHaveBeenCalledWith(null);
    expect(screen.queryByText("基本墙")).toBeNull();
  });

  it("树节点点击 → 选中该 expressID（无属性行时面板出空态）", async () => {
    renderViewer();
    await ready();
    await act(async () => {
      fireEvent.click(screen.getByText("IFCBUILDINGSTOREY #2"));
    });
    expect(useViewerStore.getState().selectedId).toBe("2");
    expect(mountLayer.handles[0].setSelection).toHaveBeenCalledWith(2);
    expect(await screen.findByText("该节点无属性")).toBeTruthy();
  });
});

// 定位脚本（选中 → 属性行取 GlobalId → locate → requestScriptJump → DesignPanel 跳行，
// 对齐 PropertyPanel 的 xeokit 链路；webifc 侧 selectedId 是 expressID，guid 从属性行取）。
// miss/stale/请求失败降级为非阻断提示；无 GlobalId 的选中不渲染按钮。
describe("IfcLiteViewer 定位脚本", () => {
  async function pickWall() {
    renderViewer();
    await ready();
    mountLayer.pickResult = 11;
    await act(async () => {
      fireEvent.click(screen.getByTestId("ifc-canvas"));
    });
    // 等属性行（含 GlobalId）落地再点按钮
    await screen.findByText("0abc$W");
  }

  it("选中带 GlobalId 的构件 → 按 guid locate 命中 → scriptJump 入 store + 提示", async () => {
    clientFake.locateScript.mockResolvedValue({
      found: true, designKey: "wall-1", line: 12, col: 4, origin: "literal", params_keys: [],
    });
    await pickWall();
    const panel = screen.getByTestId("ifc-props");
    await act(async () => {
      fireEvent.click(within(panel).getByRole("button", { name: "定位脚本" }));
    });
    expect(clientFake.locateScript).toHaveBeenCalledWith("m_abcd0000abcd0001", "0abc$W");
    await waitFor(() =>
      expect(useViewerStore.getState().scriptJump).toMatchObject({ line: 12, origin: "literal" })
    );
    expect(await screen.findByText(/已定位到脚本第 12 行/)).toBeTruthy();
  });

  it("origin=params 命中透传 paramsKeys（snake_case 载荷 → camel store，PARAMS 表单聚焦键）", async () => {
    clientFake.locateScript.mockResolvedValue({
      found: true, designKey: "wall-1", line: 3, col: 0, origin: "params", params_keys: ["wall_t"],
    });
    await pickWall();
    const panel = screen.getByTestId("ifc-props");
    await act(async () => {
      fireEvent.click(within(panel).getByRole("button", { name: "定位脚本" }));
    });
    await waitFor(() => expect(useViewerStore.getState().scriptJump?.line).toBe(3));
    expect(useViewerStore.getState().scriptJump?.paramsKeys).toEqual(["wall_t"]);
  });

  it("locate miss → 非阻断提示，不发 scriptJump，属性仍可见", async () => {
    clientFake.locateScript.mockResolvedValue({ found: false });
    await pickWall();
    const panel = screen.getByTestId("ifc-props");
    await act(async () => {
      fireEvent.click(within(panel).getByRole("button", { name: "定位脚本" }));
    });
    expect(await screen.findByText(/没有脚本调用点/)).toBeTruthy();
    expect(useViewerStore.getState().scriptJump).toBeNull();
    expect(screen.getByText("基本墙")).toBeTruthy();
  });

  it("locate stale（staging 与 map 分叉）→ 过期提示，不发 scriptJump", async () => {
    clientFake.locateScript.mockResolvedValue({ found: false, stale: true });
    await pickWall();
    const panel = screen.getByTestId("ifc-props");
    await act(async () => {
      fireEvent.click(within(panel).getByRole("button", { name: "定位脚本" }));
    });
    expect(await screen.findByText(/已过期/)).toBeTruthy();
    expect(useViewerStore.getState().scriptJump).toBeNull();
  });

  it("locate 请求失败 → 降级提示，不抛错", async () => {
    clientFake.locateScript.mockRejectedValue(new Error("HTTP 500"));
    await pickWall();
    const panel = screen.getByTestId("ifc-props");
    await act(async () => {
      fireEvent.click(within(panel).getByRole("button", { name: "定位脚本" }));
    });
    expect(await screen.findByText(/脚本定位不可用/)).toBeTruthy();
    expect(useViewerStore.getState().scriptJump).toBeNull();
  });

  it("无 GlobalId 的选中（树节点 storey）不渲染定位按钮", async () => {
    renderViewer();
    await ready();
    await act(async () => {
      fireEvent.click(screen.getByText("IFCBUILDINGSTOREY #2"));
    });
    await screen.findByText("该节点无属性");
    const panel = screen.getByTestId("ifc-props");
    expect(within(panel).queryByRole("button", { name: "定位脚本" })).toBeNull();
  });
});
