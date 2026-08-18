# 规则名词表(rule vocabulary)——requirements 规则名唯一来源

> V3 版(2026-08-12)。requirements 是 plan.json 的语义字段(纯语义传递——下游 LLM 读设计意图,
> 无机器编译/对账)。本表只定义**扁平规则名**(V2 的带参数谓词模板已按"规则名=谓词语义+第二对象/方向"扁平化,
> subject 由 requirements.subject 单独给)。类型包(.rules.json)与 plan 实例都只许用本表规则名给实例,
> 不许发明新规则名;新规则名先进本表(带一句话语义 + 例 subject + 来源)再进包。
> strength 三档:`must`(硬要求)→ 下游必须满足;`prefer`(倾向)→ 优先满足;`avoid`(禁忌)→ 避免发生。

| # | 规则名 | 一句话 | 例 subject | 常用 strength |
|---|---|---|---|---|
| 1 | `hub_connect_corridor` | 环廊枢纽:成员房间连到走廊枢纽 | office | must |
| 2 | `hub_connect_living` | 客厅枢纽:卧室/厨房/卫生间都连起居厅 | bedroom / kitchen / bathroom | must |
| 3 | `near_core` | 贴核心筒(卫生间/湿区贴筒省管线) | toilet / bathroom | must / prefer |
| 4 | `near_shaft` | 贴管井(湿区贴井聚管线) | bathroom | prefer |
| 5 | `near_dining` | 贴餐厅(备餐动线) | kitchen | prefer |
| 6 | `wet_cluster` | 湿区聚拢(厨房/卫生间等 wet 房间互相靠近) | kitchen / toilet | prefer |
| 7 | `faces_south` | 朝南(采光/朝向;8 向方位均可,仅列出已用方向) | bedroom / living / open_office | must / prefer |
| 8 | `faces_north` | 朝北 | open_office / unit_C | prefer |
| 9 | `no_through_private` | 禁止穿套:进入 subject 不须穿越私密房间 | unit | must |
| 10 | `not_inside_office` | 疏散设施不被办公/商铺围合(贴公共区) | stair_evac | must |
| 11 | `vertical_aligned` | 跨层竖向对齐:核心筒/管井/楼梯各层几何一致 | core / stair / shaft | must |
| 12 | `vertical_connected` | 竖向贯通:挑空/中庭/管道井跨层连通 | atrium | must |
| 13 | `no_opening_kitchen` | 与厨房之间不得有门/开洞(卫生间不对厨房开门) | bathroom | must |
| 14 | `far_stair` | 远离楼梯(噪声隔离) | bedroom | prefer |

---

### `hub_connect_corridor`

- **语义**:office 类房间(办公/会议/卫生间)经走廊枢纽连通——环廊组织,不是各自独立出入。
- **例**:`{subject: office, rule: hub_connect_corridor, strength: must}`。
- **来源**:office 类型包 U-B2(实例 `hub_connect(hub=corridor)` 扁平化)。

### `hub_connect_living`

- **语义**:住宅以客厅为枢纽,卧室/厨房/卫生间都连起居厅(流线经客厅组织)。
- **例**:`{subject: kitchen, rule: hub_connect_living, strength: must}`。
- **来源**:residence 类型包 U-B2(实例 `hub_connect(hub=living)` 扁平化)。

### `near_core`

- **语义**:subject 贴核心筒布置(卫生间/湿区贴筒省管线,筒体吃暗区)。
- **例**:`{subject: toilet, rule: near_core, strength: must}`。
- **来源**:office 类型包 U-C3 + plan 实例。

### `near_shaft`

- **语义**:subject 贴管井(湿区贴井聚管线,减少水平穿管)。
- **例**:`{subject: bathroom, rule: near_shaft, strength: prefer}`。
- **来源**:residence 类型包 U-C3(实例 `near(a=bathroom.*, b=shaft)` 扁平化)。

### `near_dining`

- **语义**:subject 贴餐厅(备餐/就联动线)。
- **例**:`{subject: kitchen, rule: near_dining, strength: prefer}`。
- **来源**:plan 实例(滨河住宅楼)。

### `wet_cluster`

- **语义**:湿区(厨房/卫生间/@wet 属性房间)互相靠近聚拢——管线成簇、检修集中。
- **例**:`{subject: kitchen, rule: wet_cluster, strength: prefer}`。
- **来源**:residence/office 类型包 U-C3(实例 `near(a=…, b=@wet)` 扁平化)。

### `faces_south`

- **语义**:subject 朝南(采光/朝向;贴南向外轮廓)。方位词表 8 向
  {n,ne,e,se,s,sw,w,nw},已实例化的方向单独成名(`faces_south`/`faces_north`),
  新方向先进本表。
- **例**:`{subject: bedroom, rule: faces_south, strength: must}`。
- **来源**:residence 类型包 U-C5 + plan 实例。

### `faces_north`

- **语义**:subject 朝北。同 faces_south 纪律。
- **例**:`{subject: open_office, rule: faces_north, strength: prefer}`。
- **来源**:plan 实例(滨河城市综合办公楼)。

### `no_through_private`

- **语义**:进入 subject 不须穿越私密房间(穿套禁忌;房间直接向走廊/公共区开门)。
- **例**:`{subject: unit, rule: no_through_private, strength: must}`。
- **来源**:residence 类型包 U-B2(实例 `not_through(a=*, b=@private)` 扁平化)+ plan 实例。

### `not_inside_office`

- **语义**:疏散设施(stair_evac 等)不被办公/商铺围合——贴公共区,疏散路径独立。
- **例**:`{subject: stair_evac, rule: not_inside_office, strength: must}`。
- **来源**:office 类型包 U-B3(实例 `public_placement(not_inside=…)` 扁平化)+ plan 实例。

### `vertical_aligned`

- **语义**:subject(核心筒/管井/楼梯)跨层几何一致——结构/管井竖向贯通的机械保证。
- **例**:`{subject: core, rule: vertical_aligned, strength: must}`。
- **来源**:类型包 U-D2(`align_vertical` 扁平化)+ plan 实例。

### `vertical_connected`

- **语义**:subject 竖向贯通(挑空/中庭/管道井跨层连通),非逐层独立。
- **例**:`{subject: atrium, rule: vertical_connected, strength: must}`。
- **来源**:plan 实例(滨河城市综合办公楼)。

### `no_opening_kitchen`

- **语义**:subject 与厨房之间不得有门/开洞(卫生间门不可开向厨房)。
- **例**:`{subject: bathroom, rule: no_opening_kitchen, strength: must}`。
- **来源**:residence 类型包 U-C1(实例 `no_opening(a=bathroom.*, b=kitchen)` 扁平化)。

### `far_stair`

- **语义**:subject 远离楼梯(噪声隔离;不邻接且保持距离)。
- **例**:`{subject: bedroom, rule: far_stair, strength: prefer}`。
- **来源**:residence 类型包 U-C4(实例 `far(a=bedroom.*, b=stair)` 扁平化)。

---

## 与类型包的关系(同源纪律)

- **词表是规则名唯一来源**:类型包 .rules.json 的规则实例、plan.json 的 requirements,
  一律用本表规则名;新规则名先进本表(带一句话语义+例+来源)再进包。
- **历史参数模板**:类型包 .md/.rules.json 内部仍保留带参数签名(供 pack-drift 双写校验),
  但 plan 侧书写 requirements 时用扁平规则名(本表),subject 单独给——
  `{subject, rule: 本表名, strength}` 三元组即完整表达,不写参数括号。
- **下游消费**:requirements 落 plan.json 后由下游 cad 段 LLM 语义读取(设计意图),
  无机器编译/对账——本表只约束"词",不约束"机制"。
