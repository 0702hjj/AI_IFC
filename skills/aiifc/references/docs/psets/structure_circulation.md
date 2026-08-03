# Pset — Structure & Circulation(结构与流线)

## IfcBeam (13 applicable: 12 PSET + 1 QTO)

**PSET (12):** Pset_BeamCommon, Pset_EnvironmentalImpactIndicators, Pset_EnvironmentalImpactValues, Pset_Condition, Pset_ManufacturerOccurrence, Pset_ManufacturerTypeInformation, Pset_ServiceLife, Pset_Warranty, Pset_ConcreteElementGeneral, Pset_PrecastConcreteElementFabrication, Pset_PrecastConcreteElementGeneral, Pset_ReinforcementBarPitchOfBeam

**QTO (1):** Qto_BeamBaseQuantities

**Pset_BeamCommon properties (9):**

FireRating, IsExternal, LoadBearing, Reference, Roll, Slope, Span, Status, ThermalTransmittance

> 屋架(halfspant)用 IfcBeam + Pset_BeamCommon(Span)。

---

## IfcColumn (13 applicable: 12 PSET + 1 QTO)

**PSET (12):** Pset_ColumnCommon, Pset_EnvironmentalImpactIndicators, Pset_EnvironmentalImpactValues, Pset_Condition, Pset_ManufacturerOccurrence, Pset_ManufacturerTypeInformation, Pset_ServiceLife, Pset_Warranty, Pset_ConcreteElementGeneral, Pset_PrecastConcreteElementFabrication, Pset_PrecastConcreteElementGeneral, Pset_ReinforcementBarPitchOfColumn

**QTO (1):** Qto_ColumnBaseQuantities

**Pset_ColumnCommon properties (8):**

FireRating, IsExternal, LoadBearing, Reference, Roll, Slope, Status, ThermalTransmittance

---

## IfcStairFlight (verified)

**Pset_StairFlightCommon properties (12):**

Headroom, NosingLength, **NumberOfRiser**(注意单数, 非 NumberOfRisers), NumberOfTreads, Reference, RiserHeight, Status, TreadLength, TreadLengthAtInnerSide, TreadLengthAtOffset, WaistThickness, WalkingLineOffset

> 数值属性(RiserHeight / TreadLength 等)用**项目单位 mm**(如 183 / 270)。

---

## IfcRailing (verified)

**Pset_RailingCommon properties (5):**

Diameter, Height, IsExternal, Reference, Status

> Diameter / Height 用项目单位 mm(如 50.0 / 1100.0)。
