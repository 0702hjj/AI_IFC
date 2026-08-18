"""dxfkit —— 图纸板块：画（逐构件）/预览（示意）/导出/回读。

- draw:     archdxf 画法工具箱封装，worker 逐构件调用（不是 JSON→DXF 渲染器）
- svg:      DXF → SVG 导出
- readback: DXF → 房间图（几何→语义翻译）
"""

__all__ = ["draw", "svg", "readback"]