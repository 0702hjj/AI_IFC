# residence 类型包 v2(住宅)

> v2(2026-08-06):四份数据(房间属性表/规则实例/预锁集/目标权重表)+ 粒度覆盖,
> 与 `residence.rules.json` **同源双写**——漂移由 `layout.packs.check_drift` 机械拦截
> (决策⑥)。规则名一律来自 `../predicate_vocabulary.md`(V3 扁平规则名);下表规则实例保留
> 历史参数模板签名(供 pack-drift 双写校验),plan 侧书写 requirements 用扁平规则名 + subject 单独给。
> T0 通用设计标准全包继承(只可收紧):`_template.md`。

- 粒度覆盖:栅格 **250mm**(决策②住宅值)
- 适用范围:多层/高层单元式住宅,直角轮廓;曲线立面走人工编辑+同步桥(决策⑦)

## 房间属性表(数据一)

| 房间 | privacy | needs_exterior | wet | hub | prelocked |
|---|---|---|---|---|---|
| living | public | ✓(采光面) | | ✓(客厅枢纽,RPLAN★) | |
| bedroom | private | ✓ | | | |
| kitchen | shared | | ✓ | | |
| bathroom | private | | ✓ | | |
| corridor | public | | | | |
| balcony | shared | ✓ | | | |
| stair | public | | | | ✓ |
| shaft | public | | ✓ | | ✓ |
| core | public | | | | ✓ |

## 规则实例集(数据二,与 rules.json 同源)

| 规范化规则 | 人读 | 来源 |
|---|---|---|
| `hub_connect(hub=living;members=bathroom.*,bedroom.*,kitchen)[must]` | 客厅枢纽:卧室/厨房/卫生间都连起居厅 | U-B2 |
| `not_through(a=*;b=@private)[must]` | 穿套禁忌:进任何房间不穿越私密房间 | U-B2 |
| `faces(dir=s;room=bedroom.*)[must]` | 卧室朝南 | U-C5 |
| `faces(dir=s;room=living)[prefer]` | 客厅宜南 | U-C5 |
| `near(a=bathroom.*;b=shaft)[prefer]` | 卫生间贴管井 | U-C3 |
| `near(a=kitchen;b=@wet)[prefer]` | 湿区聚拢 | U-C3 |
| `no_opening(a=bathroom.*;b=kitchen)[must]` | 卫生间门不可开向厨房 | U-C1 |
| `far(a=bedroom.*;b=stair)[prefer]` | 卧室远离楼梯(噪声) | U-C4 |
| `align_vertical(room=shaft)[must]` | 管井跨层对齐 | U-D2 |
| `align_vertical(room=stair)[must]` | 楼梯跨层对齐 | U-D2 |

## 预锁定集(数据三)

- stair + shaft:多层对齐,各层预锁格坐标一致(align_vertical 的编译目标)
- core:塔楼核心筒贯穿裙房落位时整体预锁(vertical_relations.core_continuous)

## 目标权重表(数据四)

枢纽居中 1.0 / 朝南房间 1.0 / 采光面利用 0.6 / 湿区聚拢 0.8 /
走廊总长 0.4 / 展示面 0.0 / 矩形度 0.3 —— 解的形态:客厅居中+南排卧室。

## 采纳日志

| 日期 | 规则 | 状态 | 依据 |
|---|---|---|---|
| 2026-08-06 | 全部 v2 初版 | ADOPT | architecture §3 + buildV2 六项决策 |
