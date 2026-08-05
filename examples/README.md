# AI_IFC Examples

IFC 时代的示例脚本。从仓库根运行（需 `viewer/edit-service` 的 Python 环境，含 ifcopenshell）：

```bash
cd viewer/edit-service && uv run python ../../examples/<script>.py
```

- `build_two_storey.py` — 用 ifcopenshell 直写一栋两层小楼（墙/板/开洞），演示骨架优先建模流程；产物 `two_storey.ifc` 可上传到 viewer 查看。
- `smoke_test_minimal.py` — 最小冒烟：建单墙模型并自检，用于快速验证 ifcopenshell 环境可用。

历史 SimpleCADAPI 示例（齿轮/减速器/机器人等 01-20）已于 2026-08-05 随仓库清理移除，见 git 历史。
