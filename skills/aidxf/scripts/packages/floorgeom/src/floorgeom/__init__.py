"""floorgeom —— plan 平面几何内核（shapely 唯一依赖，零设计判断）。

四大件（各模块）：
- derive:   轮廓 → 派生几何事实（geo_cognition §1 全字段）
- normalize: DSL 声明 → 坐标几何（轴网 snap/索引解析/消重叠/SchemaError）
- check:    规则机检 R-01~R-09 + 轮廓级摄取校验
- reconcile: 声明房间图 vs 回读房间图对账（两侧统一 {rooms, adjacencies, doors}）
- room_graph: normalize 产物 → 统一房间图（polygon 推邻接，reconcile 输入）
- io:        canon/sha256/确定性写出
"""

__all__ = ["derive", "normalize", "check", "reconcile", "room_graph", "io"]