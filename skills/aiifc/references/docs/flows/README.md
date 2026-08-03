# flows Index — Modeling Operations

Runnable modeling operations + pitfalls & fixes. Component-building recipes in `../design/`; modeling discipline in `../../MODELING_WORKFLOWS.md`.

> **结构原则**: 可累加的规律性内容(bug / 技巧 / 构建模板)分成**独立文件**,本 README 只留**索引(追踪轨迹)**——新增内容时往对应文件加,不在此堆。

---

## 1. End-to-End Flows(整体流程)

- [design_builder.py](design_builder.py) — **框定器**: design JSON → features.json(规范化 + 展开)
- [build_script_template.py](build_script_template.py) — **下游构建脚本模板**: features.json → IFC(每建筑复制此模板走 Pipeline)

## 2. 单步操作(构建积木)

下游构建脚本(build_script_template 或每建筑自建)用这些单步操作组装:
- [skeleton.py](skeleton.py) — 骨架(project / units / context / spatial tree)
- [wall.py](wall.py) — 墙(entity + geometry + placement + container)
- [slab_profile.py](slab_profile.py) — 板(任意轮廓拉伸)
- [opening_door.py](opening_door.py) — 开洞 + 门填充
- [type_material.py](type_material.py) — 类型 + 材质层
- [pset_qto.py](pset_qto.py) — 属性集 + 工程量
- [full_building.py](full_building.py) — 完整单层建筑构建脚本示例

## 3. Performance

- [performance.py](performance.py) — 大模型性能三招(type 级材质 / deferred container / os._exit)

## 4. Pitfalls & Fixes(流程 bug,可累加)

- [pitfalls.md](pitfalls.md) — 流程 bug 及解决方法(几何 G / 开洞 O / 镜像 M / 性能 P / 楼梯 S / 屋顶 R,可累加新坑)

## 5. Placement Tricks(放置技巧,可累加)

- [placement_tricks.md](placement_tricks.md) — 放置/开洞技巧(多轴旋转矩阵 / 开洞定位 / 居中墙 / 世界坐标)

## 6. Tools

- [style_color.py](style_color.py) — 染色(make_style / colorize)
- [tracker.py](tracker.py) — ModelStateTracker 增量状态追踪
- [design_review.py](design_review.py) — 设计质量 + 几何完整性审查
- [ifc_inspect.py](ifc_inspect.py) — 按需几何检查(design_review 报错 / 调整 / 外部修改回传)

---

## Related Documents

- `../../MODELING_WORKFLOWS.md` — 建模纪律(骨架/世界坐标/三层校验/Design JSON 框定)
- `../design/README.md` — 构件建造配方(楼梯/屋顶/窗户/女儿墙/阳台)
- `../api/README.md` — ifcopenshell.api usecase 索引
