# Pset — Walls & Openings(墙与门窗)

## IfcWall (13 applicable: 12 PSET + 1 QTO)

**PSET (12):** Pset_WallCommon, Pset_EnvironmentalImpactIndicators, Pset_EnvironmentalImpactValues, Pset_Condition, Pset_ManufacturerOccurrence, Pset_ManufacturerTypeInformation, Pset_ServiceLife, Pset_Warranty, Pset_ConcreteElementGeneral, Pset_PrecastConcreteElementFabrication, Pset_PrecastConcreteElementGeneral, Pset_ReinforcementBarPitchOfWall

**QTO (1):** Qto_WallBaseQuantities

**Pset_WallCommon properties (11):**

| property | description |
|---|---|
| AcousticRating | Acoustic rating |
| Combustible | Combustible material flag (BOOLEAN) |
| Compartmentation | Fire compartment flag (BOOLEAN) |
| ExtendToStructure | Extends to structure above (BOOLEAN) |
| FireRating | Fire rating (LABEL) |
| IsExternal | External element flag (BOOLEAN) |
| LoadBearing | Load-bearing flag (BOOLEAN) |
| Reference | Reference identifier (IDENTIFIER) |
| Status | Element status (LABEL) |
| SurfaceSpreadOfFlame | Surface spread of flame rating (LABEL) |
| ThermalTransmittance | Thermal transmittance U-value (REAL) |

---

## IfcDoor (10 applicable: 9 PSET + 1 QTO)

**PSET (9):** Pset_DoorCommon, Pset_DoorWindowGlazingType, Pset_EnvironmentalImpactIndicators, Pset_EnvironmentalImpactValues, Pset_Condition, Pset_ManufacturerOccurrence, Pset_ManufacturerTypeInformation, Pset_ServiceLife, Pset_Warranty

**QTO (1):** Qto_DoorBaseQuantities

**Pset_DoorCommon properties (19):**

AcousticRating, DurabilityRating, FireExit, FireRating, GlazingAreaFraction, HandicapAccessible, HasDrive, HygrothermalRating, Infiltration, IsExternal, MechanicalLoadRating, Reference, SecurityRating, SelfClosing, SmokeStop, Status, ThermalTransmittance, WaterTightnessRating, WindLoadRating

---

## IfcWindow (9 applicable: 8 PSET + 1 QTO)

**PSET (8):** Pset_WindowCommon, Pset_EnvironmentalImpactIndicators, Pset_EnvironmentalImpactValues, Pset_Condition, Pset_ManufacturerOccurrence, Pset_ManufacturerTypeInformation, Pset_ServiceLife, Pset_Warranty

**QTO (1):** Qto_WindowBaseQuantities

**Pset_WindowCommon properties (17):**

AcousticRating, FireExit, FireRating, GlazingAreaFraction, HasDrive, HasSillExternal, HasSillInternal, Infiltration, IsExternal, MechanicalLoadRating, Reference, SecurityRating, SmokeStop, Status, ThermalTransmittance, WaterTightnessRating, WindLoadRating
