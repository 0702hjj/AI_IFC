# Golden 验证用例

## residence_1br.py

1BR 住宅平面（mm 制），演练 floor_plan_assembly.md 全组装不变式。

运行（从 skill 目录）:

```bash
.venv/bin/python scripts/dxf tests/golden/residence_1br.py -o ../../results/golden/residence_1br.dxf
.venv/bin/python -c "from archdxf.canon import canonicalize_dxf; canonicalize_dxf('../../results/golden/residence_1br.dxf')"
```

六项比对清单（渲染 PNG 逐项核）:

1. poché：墙体实心填充，开洞处断开
2. 门摆弧：90° 门扇 + 1/4 弧，四值 swing 方向正确
3. jamb：每个开洞两端封口
4. 标注链：开洞链角→jamb→jamb→角 + 总尺寸（front+left 恒有）
5. 房间名层级：大写+下划线+面积小字
6. 圆标：门窗编号文字在圆内

确定性：同输入重生成 + canon 后 `diff` 为空。
渲染注意：白底会使 color 7（白/黑自动色）实体不可见——用深色背景渲染审查。

## 商场回归

`results/mall/mall_l1_v2.py`(workspace 侧，与金样同例）:storefront 回译为开洞三元组的实战验证。
