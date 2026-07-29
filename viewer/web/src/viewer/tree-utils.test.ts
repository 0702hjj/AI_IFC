import { describe, it, expect } from "vitest";
import { buildTree, filterTree, typeCounts, type MetaObjectLite } from "./tree-utils";

const objects: MetaObjectLite[] = [
  { id: "p", name: "Project", type: "IfcProject", parent: null },
  { id: "s", name: "Site", type: "IfcSite", parent: "p" },
  { id: "b", name: "Building", type: "IfcBuilding", parent: "s" },
  { id: "st1", name: "L1", type: "IfcBuildingStorey", parent: "b" },
  { id: "w1", name: "Wall A", type: "IfcWall", parent: "st1" },
  { id: "w2", name: "Wall B", type: "IfcWall", parent: "st1" },
  { id: "d1", name: "Door A", type: "IfcDoor", parent: "st1" },
];

describe("buildTree", () => {
  it("assembles hierarchy from parent links", () => {
    const tree = buildTree(objects);
    expect(tree).toHaveLength(1);
    const storey = tree[0].children[0].children[0].children[0];
    expect(storey.id).toBe("st1");
    expect(storey.children.map((c) => c.id)).toEqual(["w1", "w2", "d1"]);
  });
});

describe("typeCounts", () => {
  it("counts by type, sorted desc", () => {
    const counts = typeCounts(objects);
    expect(counts[0]).toEqual(["IfcWall", 2]);
    expect(counts.find(([t]) => t === "IfcDoor")).toEqual(["IfcDoor", 1]);
  });
});

describe("filterTree", () => {
  const tree = buildTree(objects);

  it("matches by name, keeping ancestors", () => {
    const out = filterTree(tree, "door a", new Set());
    const storey = out[0].children[0].children[0].children[0];
    expect(storey.children.map((c) => c.id)).toEqual(["d1"]);
  });

  it("matches by type case-insensitively", () => {
    const out = filterTree(tree, "ifcwall", new Set());
    const storey = out[0].children[0].children[0].children[0];
    expect(storey.children.map((c) => c.id)).toEqual(["w1", "w2"]);
  });

  it("filters by allowed types, keeping ancestors", () => {
    const out = filterTree(tree, "", new Set(["IfcDoor"]));
    const storey = out[0].children[0].children[0].children[0];
    expect(storey.children.map((c) => c.id)).toEqual(["d1"]);
  });

  it("empty query and empty types returns full tree", () => {
    expect(filterTree(tree, "", new Set())).toEqual(tree);
  });

  it("no match returns empty", () => {
    expect(filterTree(tree, "nonexistent", new Set())).toEqual([]);
  });
});
