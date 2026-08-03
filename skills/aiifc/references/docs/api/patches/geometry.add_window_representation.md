# Patch: geometry.add_window_representation

## Known Issue: multi-panel windows require explicit panel_properties (ifcopenshell 0.8.5)

When `partition_type` is multi-panel (DOUBLE_*/TRIPLE_*), `panel_properties` only generates **1** panel config by default. The usecase raises when indexing the 2nd/3rd panel from `DEFAULT_PANEL_SCHEMAS`:

```
IndexError: list index out of range
```

**Workaround: pass one empty dict per panel** (defaults auto-fill each panel):

```python
from ifcopenshell.api.geometry.add_window_representation import DEFAULT_PANEL_SCHEMAS
n = max(p for row in DEFAULT_PANEL_SCHEMAS[partition_type] for p in row) + 1
ifcopenshell.api.run("geometry.add_window_representation", model,
    context=body, overall_height=1500, overall_width=1500,   # project units, mm
    partition_type="DOUBLE_PANEL_VERTICAL",
    panel_properties=[{}] * n, unit_scale=us)
```

Ref: `AI_IFC/examples/seaside_villa2.py` (triple/double-panel windows).
