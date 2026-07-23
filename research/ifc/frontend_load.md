# IFC 模型 Web 端加载与显示 — 开源方案研究报告

日期:2026-07-22
研究问题:IFC 模型如何在浏览器端加载与显示?IfcOpenShell 生态内有无现成方案?
结论速览:**纯"显示"用 web-ifc / xeokit(轻、快);"显示 + 读写编辑"用 IfcOpenShell WASM(pyodide)方案(重但功能全)。**

---

## 1. 方案总览

| 方案 | 仓库 | 许可证 | 渲染 | 定位 | 读 IFC | 写/编辑 IFC |
|---|---|---|---|---|---|---|
| IfcOpenShell WASM (pyodide) | IfcOpenShell/IfcOpenShell `src/pyodide/` | LGPL-3.0 | three.js | 浏览器内跑完整 Python API | ✅ | ✅ 完整 authoring |
| web-ifc | ThatOpen/engine_web-ifc(994★) | MPL-2.0 | 自带/配 three.js | C++ 编译 WASM 的 IFC 读写内核 | ✅ | ✅(底层 API) |
| That Open Engine Components | ThatOpen/engine_components(684★) | MIT | three.js | web-ifc 之上的组件化 BIM 应用框架 | ✅(经 web-ifc) | 部分(导出片段/ DXF) |
| xeokit-sdk | xeokit/xeokit-sdk(916★) | **AGPL-3.0**(商用需授权) | 纯 WebGL(自研) | 大模型高性能查看器 | 经 XKT 预转换(或 web-ifc) | ❌(查看为主) |

辅助方案:`ifcconvert`(IfcOpenShell 自带)→ glTF/OBJ → three.js 通用加载器(服务端预转换路线)。

---

## 2. IfcOpenShell 自带 WASM 方案(源码内)

**位置**:已下载源码 `/CADapi/IfcOpenShell/IfcOpenShell-0.8.0/src/pyodide/demo-app/`
**在线 demo**:http://wasm.ifcopenshell.org

### 2.1 原理

- 用 Emscripten 将 Python 解释器 + IfcOpenShell C++ 核心整体编译为 WebAssembly;
  浏览器通过 Pyodide 加载 wasm 版 `ifcopenshell` wheel(demo 中为
  `ifcopenshell-0.8.3+...-emscripten_4_0_9_wasm32.whl`)。
- 前端用 three.js(importmap 引入 `three@0.141.0` + OrbitControls)渲染;
  Python 侧调用 `ifcopenshell.geom.settings()` 等生成网格,经 Pyodide proxy 对象传给 JS。

### 2.2 能力(来自 demo-app/README 与 index.html)

- 打开/保存本地 `.ifc` 文件(file input → `performDownload` 导出)
- **浏览器内直接建模**:工具栏含选择/画线/门/窗,底层调用与桌面端相同的
  `root.create_entity`、`geometry.add_wall_representation`、`geometry.add_window_representation`
- 三种 JS↔Python 互操作方式:Pyodide proxy 对象、`pyodide.runPython()`、PyScript 内联
- 依赖 numpy、shapely 等 wasm 包,任意纯 Python 模块均可用 → 校验、属性编辑、几何处理都能做

### 2.3 局限(README 明示)

- 加载与运行性能不佳(需下载 Python 解释器 + 单体 wheel,启动重)
- OCC 的 C++ 异常不继承 `std::exception`,在 WASM 下会导致内核错误难以捕获

### 2.4 适用判断

适合"网页端需要**读写/编辑** IFC、且想复用 Python API 全家桶"的场景;
不适合只做轻量查看的生产级前端。

---

## 3. web-ifc(That Open Company)

**仓库**:https://github.com/ThatOpen/engine_web-ifc (994★,276 fork,TS 72% + C++ 28%,最新 release 0.77 / 2026-03)
**文档**:https://thatopen.github.io/engine_web-ifc/docs · **demo**:https://thatopen.github.io/engine_web-ifc/demo · **npm**:`web-ifc`

### 3.1 原理

- IFC 解析/几何内核用 C++ 编写,Emscripten 编译为 WASM,浏览器/Node 均以近原生速度运行。
- 构建产物:`web-ifc.wasm`(浏览器)、`web-ifc-mt.wasm`(多线程,配 worker)、`web-ifc-node.wasm`、
  `web-ifc-api.js` 封装 + 完整 TypeScript 类型(含 IFC schema 类型)。

### 3.2 用法(README 示例)

```js
const WebIFC = require("web-ifc/web-ifc-api.js");
const ifcApi = new WebIFC.IfcAPI();
await ifcApi.Init();
let modelID = ifcApi.OpenModel(/* IFC 数据 string/UInt8Array */);
// 用 modelID 拉取几何与属性;完毕 CloseModel(modelID) 释放内存
```

### 3.3 特点

- 只提供**内核**(解析/几何/属性/写回),不带渲染;渲染自行接 three.js 或用上层组件库
- 支持 IFC 写入(SaveModel),可做属性级编辑
- 也可脱离 WASM 作为独立 C++ 库/可执行文件使用
- 有回归测试集(`tests/public` 公开模型库)

---

## 4. That Open Engine Components(web-ifc 上层框架)

**仓库**:https://github.com/ThatOpen/engine_components (684★,MIT,最新 v3.4.0 / 2026-04)
**文档**:https://docs.thatopen.com/intro · **npm**:`@thatopen/components`、`@thatopen/components-front`

### 4.1 定位与能力

基于 three.js + web-ifc 的**组件化 BIM 应用框架**,前身即 IFC.js。开箱功能包括:

- IFC 加载(IfcLoader)、属性面板、空间结构树
- 剖切(clipping)、尺寸标注(dimensions)、测量
- 楼层平面导航(floorplan navigation)
- 后处理(postproduction 渲染效果)
- **DXF 导出**(与我们的 DXF 流水线可衔接)
- 分包:`components`(核心,浏览器/Node 通用)+ `components-front`(浏览器专属)

### 4.2 最小示例(README)

```ts
import * as OBC from "@thatopen/components";
const components = new OBC.Components();
const worlds = components.get(OBC.Worlds);
const world = worlds.create<OBC.SimpleScene, OBC.SimpleCamera, OBC.SimpleRenderer>();
world.scene = new OBC.SimpleScene(components);
world.renderer = new OBC.SimpleRenderer(components, container);
world.camera = new OBC.SimpleCamera(components);
components.init();
```

---

## 5. xeokit-sdk

**仓库**:https://github.com/xeokit/xeokit-sdk (916★,**AGPL-3.0**,最新 v2.6.112 / 2026-06)
**示例**:http://xeokit.github.io/xeokit-sdk/examples/

### 5.1 特点

- 纯 WebGL 自研渲染,主打**超大模型性能**与全双精度真实坐标(适合城市级/园区级)
- 加载路线:推荐**服务端预转换 IFC → XKT**(自有压缩格式)→ `XKTLoaderPlugin`;
  也支持 glTF / CityJSON / LAZ / OBJ 直接加载
- 插件体系:剖切、BCF 批注、测量、NavCube、树视图等

### 5.2 许可注意

AGPL-3.0:集成进项目即要求项目整体开源;闭源/商用需向 Creoox AG 购买商业授权。
相比之下 web-ifc(MPL-2.0)与 engine_components(MIT)宽松得多。

---

## 6. 备选路线:服务端预转换

不做浏览器内解析,而是在服务端用已下载的 IfcOpenShell:

```
IFC --(ifcconvert / ifcopenshell-python)--> glTF/OBJ --> three.js GLTFLoader
```

- 优点:前端零 BIM 依赖、加载最快、可用 Draco/meshopt 压缩
- 缺点:丢失语义交互(除非另传 JSON 属性表)、需转换服务
- 工具就在源码内:`src/ifcconvert/`(支持 OBJ/DAE/glTF/SVG 等输出)

---

## 7. 对比与选型建议

| 维度 | IfcOpenShell WASM | web-ifc + three.js | engine_components | xeokit | 服务端转 glTF |
|---|---|---|---|---|---|
| 前端体积/启动 | 很重(Python+wheel) | 中(WASM 内核) | 中 | 轻(XKT 很小) | 最轻 |
| 渲染功能 | 基础(three.js 自搭) | 自搭 | 组件齐全 | 插件齐全 | 自搭 |
| 大模型性能 | 弱 | 中(支持 mt) | 中 | **强** | 取决于压缩 |
| 读 IFC | ✅ | ✅ | ✅ | 需预转 XKT | 需预转 |
| **编辑/写 IFC** | ✅ **最强(全 Python API)** | ✅(底层) | 部分 | ❌ | ❌ |
| 许可证 | LGPL-3.0 | MPL-2.0 | MIT | AGPL-3.0(商用付费) | - |
| 学习成本 | 低(复用 Python 知识) | 中 | 中(组件概念) | 中 | 低 |

**建议**:

1. **网页端建模闭环**(与本项目 DXF→IFC 流水线配套演示/轻编辑):
   首选 **IfcOpenShell WASM**——前后端同一套 `ifcopenshell.api`,无需重复实现;接受其启动开销。
2. **生产级查看 + 交互**(剖切/属性/楼层导航/量测):
   **engine_components**(MIT、组件全、可导出 DXF)为首选;需要极致大模型性能再考虑 xeokit(注意 AGPL)。
3. **纯展示、追求秒开**:服务端 `ifcconvert` → glTF + three.js。

## 8. 与本项目流水线的衔接

```
DXF → cad-to-shapely → IfcOpenShell(Python) 生成 model.ifc
   ├─ 路线A:ifcconvert → glTF → three.js 静态展示
   ├─ 路线B:web-ifc / engine_components 直接加载 model.ifc(可交互)
   └─ 路线C:IfcOpenShell WASM(pyodide)浏览器内打开 model.ifc,
            继续用同一套 api 做二次编辑(画墙/插门窗)
```

## 9. 参考链接

- IfcOpenShell WASM demo:http://wasm.ifcopenshell.org(源码 `src/pyodide/demo-app/`)
- web-ifc:https://github.com/ThatOpen/engine_web-ifc
- engine_components:https://github.com/ThatOpen/engine_components · https://docs.thatopen.com/intro
- xeokit:https://github.com/xeokit/xeokit-sdk · https://xeokit.io
- ifcconvert:源码 `src/ifcconvert/`
