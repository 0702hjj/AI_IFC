
### 1. Web 显示 IFC 的主流技术方案汇总

按照“几何渲染方式”**与**“运行位置”的不同，主流方案可以划分为以下 3 大类：

| 方案分类 | 代表技术栈 | 架构工作原理 | 优点 | 缺点 |
| --- | --- | --- | --- | --- |
| **A. 纯前端直接解析** *(Client-side WASM)* | **That Open Engine** *(原 IFC.js)* | 在浏览器端利用 WebAssembly 直接解析 `.ifc` 文本并生成 WebGL 网格。 | 极度轻量、**无需部署后端**算力，即传即看。 | 大文件（>50MB）极易卡死或导致浏览器 OOM 内存溢出。 |
| **B. 云端/服务端异步离线转码** *(Server-side Pipeline)* | **glTF / glB + Three.js** 或 **xeokit (.xkt)** | 在服务端将 IFC 离散化为轻量化 3D 格式（glTF/xeokit），前端仅加载轻量网格。 | **加载极快（秒开）**，能支撑 GB 级大模型，不吃用户设备配置。 | 依赖服务端转码流水线，首次上传需要数秒到数分钟排队。 |
| **C. 商业 PaaS 云引擎** *(Cloud API)* | **Autodesk APS (Forge)** / **BIMFACE** | 调用商业平台 API 上传并转码，直接嵌入厂商提供的 Web 控件。 | 解析成功率与容错率极高，功能丰富（截面、碰撞、标注）。 | **收费高昂**，数据敏感型项目无法闭环部署在私有云。 |

---

### 2. 适配 IfcOpenShell 的推荐路线

业务前置了 **IfcOpenShell (Python)** 节点（通常由 Agent 生成 IFC 文件），**强烈推荐采取“B 类：服务端轻量化转码（glTF/glB）+ 前端渲染”路线**。

这是目前与 IfcOpenShell 最契合、开发维护成本最低且性能最优的组合：

#### 最佳搭配方案：`IfcConvert` + `glTF (glb)` + `Three.js` (或 `xeokit`)

##### 架构流程：

1. **Agent Python 脚本：** 用 `ifcopenshell` 在内存中生成 `.ifc` 文件。
2. **服务端转码（零额外代码）：** 脚本生成完 IFC 后，直接调用系统内置的 **`IfcConvert`**（IfcOpenShell 官方提供的 C++ 极速命令行工具）：
```bash
IfcConvert input.ifc output.glb --center-model

```


*`IfcConvert` 可以直接将 `.ifc` 几何推演为极其轻量的三维网格二进制文件 `.glb`。*
3. **抽取空间树与属性（数据）：** 同步运行 Python 的 `ifcopenshell` 提取项目的构件树（`Spatial Hierarchy`）和属性（`Pset`），导出为一个轻量的 `metadata.json` 文件。
4. **前端 Web 渲染：** 前端通过 **Three.js** 仅需 2 行代码加载 `.glb`（毫秒级呈现），左侧挂载基于 `metadata.json` 渲染的构件树。

---

### 3. 为什么这是适配 IfcOpenShell 的“完美方案”？

1. **同源生态无缝集成：** `IfcConvert` 是 IfcOpenShell 项目组原生维护的 C++ 工具，对 IfcOpenShell 生成的实体对象兼容性达到 100%。
2. **生成速度极快：** Agent 生成的简单/中等建筑（墙、板、门窗），`IfcConvert` 在服务端转码成 `.glb` 只需要 **100毫秒 ~ 2秒** 即可完成。
3. **Web 端体验极佳：** 前端加载 `.glb` 的速度比加载原始 `.ifc` 快数十倍，完全做到**网页打开即显示**，无需用户在浏览器端等待漫长的解析过程。
