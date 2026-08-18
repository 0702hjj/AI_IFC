# single_family 类型标准（美式独栋 Single Family Detached）

> 对应美国典型独栋住宅（如 Bishop-Overland-08 floorplan.dxf）。
> 与 residence（中国商品房）**区分定位**：商品房是标准层多户（core+corridor+units），
> 独栋是**单栋单户**——无 core、无公共走廊，车库是独立特征区。

## 1. 类型词表（本类型特有的 block/role）

| block/role | 含义 | 必填 | 案例来源 |
|---|---|---|---|
| `living` | 公共起居（GREAT ROOM + DINING + KITCHEN 开放带） | ✅ | floorplan |
| `bedroom` | 卧室/主卧套房（MASTER + W.I.C.） | ✅ | floorplan |
| `garage` | 车库（独立区，2-car 典型） | ❌（有车库则必填） | floorplan |
| `outdoor` | 露台/门廊（DECK / COVERED PORCH） | ❌ | floorplan |
| `entry` | 入口（ENTRY + 门廊） | ❌ | floorplan |
| `utility` | 辅助（UTIL / WH 洗衣设备） | ❌ | floorplan |

**独栋没有 core / corridor / units / balcony**（那些是商品房标准层词表）——不要混用。

## 2. 分区规则（实测，floorplan.dxf）

```
美式独栋 = 主屋 + 车库 两个大块（实测坐标判定）:
  主屋（西-东 四区）:
    公共起居带（东）: DINING + KITCHEN（开放布局无隔墙，GREAT ROOM 居中偏东）
    私密带（西）:     MASTER + HALL + W.I.C.（主卧套房，远离入口）
    入口（西）:       ENTRY + COVERED PORCH（西侧门廊入口）
  车库（南）:         2-car 独立区，GARAGE + WH（热水器贴车库）
  户外延伸:           DECK（东 2.5m×4.4m）+ COVERED PORCH（西 2.2m×1.3m）
```

- 采光优先给公共起居（DINING/KITCHEN 靠东）；
- 私密卧室（MASTER）远离入口动线，靠西；
- 车库靠主屋南侧，独立成区不占主屋采光面；
- 设备（WH）贴车库/厨房（管线短）。

## 3. 默认值（有出处，不凭空）

| 参数 | 默认 | 出处 |
|---|---|---|
| 车库门宽 | 16'（4877mm，2-car） | floorplan A-GARAGE-DOOR 192" |
| 尺度量级 | 独栋总占地 15~25m × 10~15m（含车库）；主屋 17.7m × 7.8m | floorplan 总占地 20.2m × 14.3m |
| 窗户数 | 采光房 1~3 窗（外窗多门少） | floorplan 145 窗 / 11 门弧 |
| 结构层 | 有基础 S-FOOTER / 地梁墙 STEM-WALL / 板 S-SLAB | floorplan 结构层齐全 |

## 4. 规则（对 R-01~R-09 的独栋解释）

| 规则 | 独栋含义 |
|---|---|
| R-01（锚点） | 独栋无 core → 锚点是车库/入口门位（非核心筒） |
| R-03（面积） | 区域面积按实测——开放起居带（GREAT+DINING+KITCHEN）常 30~50㎡ |
| R-06（对齐） | 车库与主屋共享墙对齐（车库门在共享墙上是开口） |
| R-07（连通） | 每房间至少 1 门；主屋→车库、HALL→各房 |
| R-08（采光） | 公共起居采光面优先（东/北）；MASTER 也有窗（独立采光） |

## 5. 反例（混用禁区）

- 给独栋写 `core` → SchemaError（独栋词表无 core，R-01 锚点语义错）；
- 写 `corridor` 走廊 → 独栋无公共走廊（HALL 是室内短廊，不是 corridor block）；
- 把 `units` 当户 → 独栋是单户，`units` 是商品房标准层概念；
- 车库当普通房间（无车库门/无独立区）→ 漏车库 = 类型特征丢失。
