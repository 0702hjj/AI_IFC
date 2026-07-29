import { describe, it, expect } from "vitest";
import { applyOverrides } from "./overrides";

const meta = {
  id: "w1",
  name: "Wall A",
  type: "IfcWall",
  propertySets: [
    {
      id: "p1",
      name: "Pset_WallCommon",
      properties: [
        { name: "FireRating", value: "120 min" },
        { name: "LoadBearing", value: true },
      ],
    },
    {
      id: "p2",
      name: "Base",
      properties: [{ name: "Description", value: "exterior" }],
    },
  ],
};

describe("applyOverrides", () => {
  it("returns original values when there are no overrides", () => {
    const eff = applyOverrides(meta, {});
    expect(eff.name).toBe("Wall A");
    expect(eff.propertySets[0].properties?.[0].value).toBe("120 min");
    expect(eff.fields).toEqual({
      Name: "Wall A",
      Description: "exterior",
      Classification: "",
      FireRating: "120 min",
      Comments: "",
    });
  });

  it("Name override shadows entity name and fields", () => {
    const eff = applyOverrides(meta, { Name: "Wall B" });
    expect(eff.name).toBe("Wall B");
    expect(eff.fields.Name).toBe("Wall B");
  });

  it("pset field override shadows the displayed pset value", () => {
    const eff = applyOverrides(meta, { FireRating: "90 min" });
    const pset = eff.propertySets[0];
    expect(pset.properties?.[0]).toEqual({ name: "FireRating", value: "90 min" });
    expect(pset.properties?.[1]).toEqual({ name: "LoadBearing", value: true });
    expect(eff.fields.FireRating).toBe("90 min");
  });

  it("override for a field absent from psets still appears in fields", () => {
    const eff = applyOverrides(meta, { Comments: "check later" });
    expect(eff.fields.Comments).toBe("check later");
    expect(eff.fields.Classification).toBe("");
  });

  it("does not mutate the input meta object", () => {
    applyOverrides(meta, { FireRating: "90 min", Name: "X" });
    expect(meta.name).toBe("Wall A");
    expect(meta.propertySets[0].properties?.[0].value).toBe("120 min");
  });

  it("defaults overrides parameter to empty", () => {
    expect(applyOverrides(meta).fields.FireRating).toBe("120 min");
  });
});
