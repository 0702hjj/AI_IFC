# Spatial: Atrium with Skylight

Central vertical void bringing light deep into the building.

## Parameters

| Parameter | Range | Default | Note |
|---|---|---|---|
| Atrium size | 10–40m × 8–30m | 20×12 | Proportional to building |
| Atrium floors | All or upper 2/3 | All | Full height preferred |
| Skylight type | Flat / pyramidal / barrel | Flat glass | Simplest |
| Railing | Per floor perimeter | — | GUARDRAIL 1.1m |

## Technical Mapping

- `profile.add_arbitrary_profile_with_voids` for floor slabs
- `IfcPlate` for skylight
- `IfcRailing` for perimeter

## Variations

- Rectangular atrium
- Elliptical atrium (24-gon approximation)
- Stepped atrium (narrower at top)
