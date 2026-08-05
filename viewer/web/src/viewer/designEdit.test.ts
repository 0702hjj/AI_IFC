// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

import { describe, it, expect } from "vitest";
import { findElementByKey, updateElement, DESIGN_PARAM_SCHEMA } from "./designEdit";

const design = {
  meta: { name: "t" },
  frame: { storeys: { "1F": 0.0 } },
  floors: {
    "1F": {
      walls: [{ key: "1F:wall:0", axis: [[0, 0], [6, 0]], t: 0.2, kind: "ext" }],
      openings: [{ key: "1F:opening:0", wall: 0, w: 1.0, h: 2.0, type: "door" }],
      slabs: [{ key: "1F:slab:0", t: 0.15 }],
    },
  },
};

describe("designEdit", () => {
  it("finds an element by key across kinds", () => {
    const wall = findElementByKey(design, "1F:wall:0");
    expect(wall?.kind).toBe("wall");
    expect(wall?.storey).toBe("1F");
    expect(wall?.index).toBe(0);
    const opening = findElementByKey(design, "1F:opening:0");
    expect(opening?.kind).toBe("opening");
  });
  it("returns null for unknown key", () => {
    expect(findElementByKey(design, "9F:wall:9")).toBeNull();
  });
  it("updates the element and keeps its key", () => {
    const next = updateElement(design, { key: "1F:wall:0", kind: "wall", storey: "1F", index: 0, data: {} }, { t: 0.3, kind: "int" });
    const floors = next.floors as Record<string, any>;
    expect(floors["1F"].walls[0].t).toBe(0.3);
    expect(floors["1F"].walls[0].kind).toBe("int");
    expect(floors["1F"].walls[0].key).toBe("1F:wall:0");
    expect(floors["1F"].walls[0].axis).toEqual([[0, 0], [6, 0]]); // untouched fields preserved
    // original design not mutated
    expect((design.floors as any)["1F"].walls[0].t).toBe(0.2);
  });
  it("exposes a param schema per kind", () => {
    expect(DESIGN_PARAM_SCHEMA.wall.map((f) => f.field)).toContain("t");
    expect(DESIGN_PARAM_SCHEMA.opening.map((f) => f.field)).toEqual(
      expect.arrayContaining(["w", "h", "sill", "along", "type"])
    );
  });
});
