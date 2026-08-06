# 平面图组装参考（floor_plan_assembly)

> 用 archdxf 组装一张标准平面图的不变式。先读 `vocabulary.md` 取词、`archdxf_api.md` 取调用方式。
> 铁律：**设计决策（墙在哪、开什么洞）由你声明；构造执行（声明如何展开成实体）全走 archdxf，不手写几何**。
> **起步方式：复制 `references/scaffold_floor_plan.py`，只改 DECLARATION ZONE**——本文是它所固化的规范说明。

## 1. 声明格式

一切构造从声明出发。开洞永远以三元组声明：

```python
# (所属墙, 沿墙偏移 offset, 宽度) — 位置换算在写声明时完成,画图零换算
OPENINGS = {
    "front": [("door", 1000, 900, "in-left"), ("window", 4000, 1500, None)],
    "rear":  [("window", 2000, 1200, None)],
}
PARTITIONS = [  # (axis, offset, from, to, thickness, doors)
    ("x", 3000, 0, 8000, 100, [("door", 1500, 800, "in-right")]),
]
```

## 2. 组装顺序（不变式）

1. **文档**:ezdxf.new + 钉元数据（api §7 配方）→ `ensure_layers(doc, "floor")` → `ensure_dimstyle(doc, text_height=...)`
2. **frame 定义段**:`rect_wall_frames(W, D)`；每道隔墙 `partition_frame(...)`。**禁止出现逐墙手写朝向算式**
3. **外墙**：每面墙 wall_run（角部归属：front/rear 的 hatch_span 含角部，left/right 止于内角）→ jamb_pair → door_leaf/window_line
4. **隔墙**:wall_run(inner_span=span,hatch_span=span)→ 门洞 jamb+door_leaf → 自由端 end_cap
5. **房间标签**:room_label（面积 STATED，不计算）
6. **洁具**:draw_fixture（避开墙体，中心在轮廓内）
7. **引线**:add_leader（拥挤构件避让标注）
8. **探测器**:detector_symbol
9. **剖切线**:add_line + 两端 section_bubble（有剖面时）
10. **标注**:dim_chain 开洞链（有开洞的每面墙一道）→ add_dim 总尺寸（front+left 恒有，有开洞侧面加一道）
11. **指北针**（用户给了朝向才画）→ **图题** view_title

## 3. 几何校验清单（生成后自查/审查规则）

| 检查 | 规则 | 错误消息格式 |
|---|---|---|
| 开洞拟合 | `offset + 宽度 ≤ 墙长` | `openings[i]: 洞 spans offset+width 超 wall 长度` |
| 隔墙门拟合 | `door.at + width ≤ wall.to` 且 `≥ wall.from` | `partitions[i].doors[j]: 超墙段` |
| 字段互斥 | door 无 sill、window 无 swing | `openings[i]: door 不得设 sill` |
| 门窗顶高 | sill+height ≤ 墙高 | `openings[i]: 顶超墙高` |
| 轮廓内 | 房间标签/洁具/探测器中心在轮廓内 | `rooms[i]: 在轮廓外` |

语义判断（疏散宽度、净面积、适用性）**标 BY REVIEW，不进自动校验**。

## 4. 常见错误（审查时重点查）

- 逐墙手写 sin/cos 朝向算式 → 必须用 frame
- 先画整墙再用白块遮开洞 → 必须用 subtract_intervals 断口
- 门摆弧方向错（swing 四值没查表） → 查 vocabulary §2
- 角部填充重叠（两面墙都填角部） → hatch_span 归属唯一
- 隔墙插入外墙填充区 → 隔墙绘制范围钳制到外墙内面
- 标注文本用 ezdxf 默认小数 → 用 add_dim 的 unit 覆写
- HATCH 无填充 → 必须 `set_solid_fill()`(archdxf wall_run 已内置；自画填充时注意）
- 渲染审查白底 → color 7（白/黑自动色）实体不可见，用深色背景渲染
