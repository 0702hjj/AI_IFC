// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

import { describe, it, expect } from "vitest";
import { flattenParams, draftOf, parseDraft, applyDrafts, pathKey } from "./scriptEdit";

describe("scriptEdit.flattenParams", () => {
  it("classifies number / string / boolean leaves", () => {
    const fields = flattenParams({ wall_t: 0.2, name: "demo", flat: true });
    const byKey = Object.fromEntries(fields.map((f) => [pathKey(f.path), f]));
    expect(byKey["wall_t"].type).toBe("number");
    expect(byKey["name"].type).toBe("string");
    expect(byKey["flat"].type).toBe("boolean");
  });

  it("recurses into nested plain objects with dotted paths", () => {
    const fields = flattenParams({ frame: { storeys: 2, bay: { w: 6 } } });
    expect(fields.map((f) => pathKey(f.path))).toEqual([
      "frame.storeys",
      "frame.bay.w",
    ]);
  });

  it("degrades arrays and other values to json fields", () => {
    const fields = flattenParams({ axis: [0, 0], nothing: null });
    expect(fields.every((f) => f.type === "json")).toBe(true);
  });

  it("keeps insertion order (stable form layout)", () => {
    const fields = flattenParams({ b: 1, a: 2, c: 3 });
    expect(fields.map((f) => f.name)).toEqual(["b", "a", "c"]);
  });
});

describe("scriptEdit.draftOf / parseDraft", () => {
  it("draftOf stringifies scalars and JSON-encodes json fields", () => {
    expect(draftOf({ path: ["t"], name: "t", type: "number", value: 0.2 })).toBe("0.2");
    expect(draftOf({ path: ["s"], name: "s", type: "string", value: "abc" })).toBe("abc");
    expect(draftOf({ path: ["a"], name: "a", type: "json", value: [1, 2] })).toBe("[1,2]");
    expect(draftOf({ path: ["n"], name: "n", type: "json", value: null })).toBe("null");
  });

  it("parseDraft parses per type", () => {
    expect(parseDraft("number", " 3.5 ")).toBe(3.5);
    expect(parseDraft("string", " hi ")).toBe("hi");
    expect(parseDraft("json", '{"x": 1}')).toEqual({ x: 1 });
  });

  it("parseDraft rejects invalid number / json", () => {
    expect(() => parseDraft("number", "abc")).toThrow();
    expect(() => parseDraft("json", "{oops")).toThrow();
  });
});

describe("scriptEdit.applyDrafts", () => {
  const params = { wall_t: 0.2, frame: { storeys: 2 }, axis: [0, 0], flag: false };

  it("applies edited drafts into a deep-cloned params object", () => {
    const fields = flattenParams(params);
    const drafts: Record<string, string> = {};
    for (const f of fields) drafts[pathKey(f.path)] = draftOf(f);
    drafts["wall_t"] = "0.3";
    drafts["frame.storeys"] = "5";
    const next = applyDrafts(params, fields, drafts);
    expect(next).toEqual({ wall_t: 0.3, frame: { storeys: 5 }, axis: [0, 0], flag: false });
    expect(params.wall_t).toBe(0.2); // untouched
    expect(params.frame.storeys).toBe(2);
  });

  it("keeps boolean fields from their value, not the draft string", () => {
    const fields = flattenParams(params);
    const next = applyDrafts(params, fields, {});
    expect(next.flag).toBe(false);
  });

  it("throws on the first unparsable draft", () => {
    const fields = flattenParams(params);
    expect(() => applyDrafts(params, fields, { wall_t: "not-a-number" })).toThrow();
  });
});
