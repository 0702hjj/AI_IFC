# 输出契约（design，被房间/细节设计规范 include）

## 每 zone 只写这些文件

处理每个 zone 时，工作区是 `missions/<zone>.<stage>/` 目录。只允许在**该目录内**
创建/修改以下文件：

| 阶段 | 文件 | 说明 |
|---|---|---|
| 声明段 | `rooms.json` | 房间 DSL 声明（schema 见 references/schemas/rooms.schema.json） |
| 建造段 | `floor.dxf` | 正式 DXF（从 confirmed skeleton.<floor>.dxf 复制起步，逐构件增量画） |
| 建造段 | `geom_check.json` | 机检报告（运行 `aidxfv3 check` 产出） |
| 建造段 | `shot.svg` | 工程图导出返图（`aidxfv3 svg` 产出） |

## 边界（违反即判失败修正）

- 工作范围限 `missions/<node>/` 目录；`skeleton.json` / `plan.json` 保持原样
- 疑难先经断点询问用户（`references/orchestrator/breakpoint.md`），或走 `infeasible` 申报
- 只写 DSL 声明（分区引用/墙 key/沿墙距离/关系）——坐标由 `aidxfv3 normalize` 计算
  （分层外推/差集/切割/墙解析/沿墙定位全机器）
- 工程图逐构件调用画法库产生，逐构件画
- 解析/声明不了的情况写入 `geom_check.json` 报告（带坐标）

## 完成记录（一行摘要）

每个 zone 完成时向用户/ledger 记录**一行摘要**，格式：

```
[node] <房间数> 个房间，<校验结论>，产物: <文件指针列表>
```

示例：`[tower_std.rooms] 6 个房间，geom_check PASS，产物: missions/tower_std.rooms/{rooms.json, floor.dxf, shot.svg}`
