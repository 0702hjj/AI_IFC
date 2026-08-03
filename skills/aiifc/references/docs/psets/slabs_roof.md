# Pset — Slabs & Roof(板与屋顶覆盖)

## IfcSlab (14 applicable: 13 PSET + 1 QTO)

**PSET (13):** Pset_SlabCommon, Pset_PrecastSlab, Pset_EnvironmentalImpactIndicators, Pset_EnvironmentalImpactValues, Pset_Condition, Pset_ManufacturerOccurrence, Pset_ManufacturerTypeInformation, Pset_ServiceLife, Pset_Warranty, Pset_ConcreteElementGeneral, Pset_PrecastConcreteElementFabrication, Pset_PrecastConcreteElementGeneral, Pset_ReinforcementBarPitchOfSlab

**QTO (1):** Qto_SlabBaseQuantities

**Pset_SlabCommon properties (11):**

AcousticRating, Combustible, Compartmentation, FireRating, IsExternal, LoadBearing, **PitchAngle**(坡屋顶板坡度角), Reference, Status, SurfaceSpreadOfFlame, ThermalTransmittance

---

## IfcRoof (verified)

**Pset_RoofCommon properties (7):**

AcousticRating, FireRating, IsExternal, LoadBearing, Reference, Status, ThermalTransmittance

---

## IfcCovering (9 applicable: 8 PSET + 1 QTO) — 覆盖层(屋面瓦/金属/保温/吊顶)

**PSET (8):** Pset_CoveringCommon, Pset_EnvironmentalImpactIndicators, Pset_EnvironmentalImpactValues, Pset_Condition, Pset_ManufacturerOccurrence, Pset_ManufacturerTypeInformation, Pset_ServiceLife, Pset_Warranty

**QTO (1):** Qto_CoveringBaseQuantities

**Pset_CoveringCommon properties (11):**

AcousticRating, Combustible, Finish, FireRating, FlammabilityRating, FragilityRating, IsExternal, Reference, Status, SurfaceSpreadOfFlame, ThermalTransmittance

> 屋面覆盖(design/roof_pitched, Castle 逆向): dakpan 瓦 / zinkwerk 金属 / waterslag 滴水 → PredefinedType=**ROOFING**; 保温 dakisolatie → PredefinedType=**INSULATION**。挂 `Pset_CoveringCommon`,覆盖在 IfcSlab(ROOF) 结构板上(**不用 IfcRoof**)。

---

## IfcChimney (verified)

**Pset_ChimneyCommon properties (7):**

FireRating, IsExternal, LoadBearing, NumberOfDrafts, Reference, Status, ThermalTransmittance
