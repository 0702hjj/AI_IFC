# Patch: geometry.add_railing_representation

## Known Issue: Missing default params trigger AttributeError (ifcopenshell 0.8.5)

Omitting any default-valued parameter (`support_spacing` / `railing_diameter` / `clear_width` / `height`) causes:

```
AttributeError: 'Usecase' object has no attribute 'settings'
```

Root cause: the module-level wrapper calls `usecase.convert_si_to_unit(...)` to compute defaults before `Usecase.settings` is injected.

**Workaround: pass all optional parameters explicitly** (project units, mm):

```python
ifcopenshell.api.run("geometry.add_railing_representation", model,
    context=body, railing_path=np.array([[0, 0, 1100], [12000, 0, 1100]]),  # mm
    height=1100, support_spacing=1000, railing_diameter=50, clear_width=40,
    unit_scale=ifcopenshell.util.unit.calculate_unit_scale(model))
```

Ref: `AI_IFC/examples/seaside_villa.py` (balcony GUARDRAIL railing).
