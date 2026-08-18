# 谓词词表(predicate vocabulary)——类型包规则实例的唯一词汇来源

> 词表通用且固定,类型包(.md)只允许给**实例**。新谓词先进本表(带编译+对账规则)再进包。
> 参数支持三种引用:具体房间类型(`living`)、模式(`bedroom.*` 同基类全部)、
> 属性引用(`@private`/`@wet`/`@hub` 等,按 room_attrs 解析)、`*` 通配。
> 强度三档(plan_contract §1.4):`must`→硬约束+对账机械 FAIL;`prefer`→评分项;
> `avoid`→惩罚项。

| # | 谓词 | 一句话 |
|---|---|---|
| 1 | `hub_connect` | 枢纽连通:成员房间连到枢纽 |
| 2 | `public_placement` | 公共可达:房间贴公共区、不被私密围合 |
| 3 | `not_through` | 禁止穿套:进入 a 不须穿越 b |
| 4 | `no_opening` | a、b 之间不得有门/开洞 |
| 5 | `near` | 邻近:a 与 b 共享边界(must)/质心靠近(prefer) |
| 6 | `far` | 远离:a 与 b 不邻接且质心距达标 |
| 7 | `faces` | 朝向:房间贴指定方位外轮廓 |
| 8 | `at_end` | 尽端:a 位于 b 主轴尽端 |
| 9 | `inside` | 包含:a 被 b 围合(中庭/管井内嵌) |
| 10 | `align_vertical` | 竖向对齐:跨层同类预锁格坐标一致 |

---

### `hub_connect(hub, members)`

- **语义**:每个 member 与 hub 共享边界,或经门链 ≤2 跳连通(HouseGAN++ 门边
  证据 + RPLAN "living room first" 观察)。
- **CP-SAT 编译**:must → 每个 member 实例至少一格与 hub 实例邻接(硬);
  prefer → 未直连 member 数进惩罚。
- **A 层对账(R9)**:气泡图/门图上以 hub 为根 BFS,所有 member 可达且跳数 ≤2,
  否则点名缺失 member。

### `public_placement(room, not_inside)`

- **语义**:room 有边界贴 public 类型区,且其所有门邻都不是 not_inside
  类型(疏散设施不被办公/商铺围合)。
- **CP-SAT 编译**:must → room 实例至少一格邻接 public 类型格,且不邻接
  not_inside 类型格(硬)。
- **A 层对账(R10)**:检查 room 节点的邻接类型多重集:含 public 且与
  not_inside 无公共边界,否则点名。

### `not_through(a, b)`

- **语义**:进入 a 不须穿越 b(U-B2 泛化;b 常为 `@private`)。
- **CP-SAT 编译**:must → b 类房间的门边只允许通向 hub/public 类型(近似硬约束);
  精确判定留对账。
- **A 层对账(R5)**:门图上对每个 a 实例做"不经 b 类节点"的 public 可达性
  遍历,不可达即穿套,点名 a 与穿套节点。

### `no_opening(a, b)`

- **语义**:a、b 之间不得有门边或开敞连通(U-C1 卫生间-厨房)。
- **CP-SAT 编译**:must → a、b 实例间禁门边,且邻接边界长度 = 0 进硬约束
  (允许贴邻但不开洞时,退化为"无边"检查)。
- **A 层对账(R6)**:边表查 (a,b,door/open) 存在性,存在即 FAIL 点名。

### `near(a, b)`

- **语义**:邻近。must=a、b 共享边界;prefer=质心尽量近(湿区贴管井)。
- **CP-SAT 编译**:must → 实例对至少一格邻接(硬);prefer → 质心距离进惩罚。
- **A 层对账(R7a)**:must 检查公共边界长度 >0;prefer 记录质心距离供审计。

### `far(a, b)`

- **语义**:远离(U-C4 卧室离楼梯):不邻接且质心距 ≥ 类型包阈值。
- **CP-SAT 编译**:must → 无邻接格(硬)+质心距下限(硬);prefer → 距离进评分。
- **A 层对账(R7b)**:无公共边界且质心距达标,否则点名。

### `faces(room, dir)`

- **语义**:房间贴 dir 方位 ±45° 扇区的外轮廓(采光/朝向)。dir ∈ 8 向
  {n,ne,e,se,s,sw,w,nw}(Tell2Design 词表);plan 侧 `faces_south` =
  `faces(dir=s)` 的别名。
- **CP-SAT 编译**:must → 房间实例至少一格落在该方位外边界带(硬);
  prefer → 贴边长度进评分。
- **A 层对账(R7c)**:layout.json 房间多边形顶点方位检验,0 顶点入扇区即 FAIL。

### `at_end(a, of)`

- **语义**:a 位于 of(线性空间,如 arcade/步行街)主轴的尽端(主力店锚定)。
- **CP-SAT 编译**:must → a 格心沿 of 主轴投影 ∈ 两端 20% 分位(硬)。
- **A 层对账(R8)**:质心投影分位复算,不达即点名。

### `inside(a, b)`

- **语义**:a 被 b 围合(Tell2Design inclusion:中庭/管井内嵌)。
- **CP-SAT 编译**:a 通常预锁;must → b 实例环绕 a 预锁格四向均有格(硬)。
- **A 层对账(R8b)**:a 多边形外边界与 b 的共享率 ≥ 阈值(默认 0.8)。

### `align_vertical(room)`

- **语义**:跨层竖向对齐:同名/同类 room(核心筒/管井/楼梯)各层预锁格
  坐标一致——竖向对齐的机械保证。
- **CP-SAT 编译**:多层联合求解时同坐标固定(硬,不参与分配)。
- **A 层对账(R11)**:跨层 layout.json 同类型房间多边形质心偏差 ≤ 1 栅格、
  IoU ≥ 0.8,否则点名层号。
