"""flowops —— 流程操作（无几何/画图逻辑，纯编排与装配）。

- validate:   DSL 声明 schema 校验（质量防线 L1/L2 工具）
- preprocess: S0 总装（含 packs 类型包加载，调 floorgeom.derive）
- pack:       mission 渲染（zone 包切片 + 骨架段 + feedback 注入）
- orchestrate: 状态编排（补缺 mission / 按产物推进 / 恢复对账——只记状态不派发）
- sync:       同步桥（哈希比对 → 回读再生 → audit 语义事件 → 更新声明）
"""

__all__ = ["validate", "preprocess", "pack", "orchestrate", "sync"]