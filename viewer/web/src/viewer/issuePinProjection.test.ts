// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

import { describe, it, expect } from "vitest";
import { aabbCenter, projectToCanvas } from "./issuePinProjection";

const IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];

// Perspective-like projection where clip w = -viewZ (camera looks down -Z).
const PERSPECTIVE = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, -1, -1, 0, 0, -0.2, 0];

describe("aabbCenter", () => {
  it("returns the midpoint of a min/max aabb", () => {
    expect(aabbCenter([0, 0, 0, 2, 4, 6])).toEqual([1, 2, 3]);
    expect(aabbCenter([-2, -4, -6, 2, 4, 6])).toEqual([0, 0, 0]);
  });
});

describe("projectToCanvas", () => {
  it("projects the world origin to the canvas center with identity matrices", () => {
    expect(projectToCanvas([0, 0, 0], IDENTITY, IDENTITY, 800, 600)).toEqual({
      x: 400,
      y: 300,
    });
  });

  it("maps NDC to canvas coordinates with y flipped", () => {
    expect(projectToCanvas([0.5, 0.5, 0], IDENTITY, IDENTITY, 800, 600)).toEqual({
      x: 600,
      y: 150,
    });
    expect(projectToCanvas([-1, -1, 0], IDENTITY, IDENTITY, 800, 600)).toEqual({
      x: 0,
      y: 600,
    });
  });

  it("returns null for points outside the frustum", () => {
    expect(projectToCanvas([2, 0, 0], IDENTITY, IDENTITY, 800, 600)).toBeNull();
    expect(projectToCanvas([0, -1.5, 0], IDENTITY, IDENTITY, 800, 600)).toBeNull();
    expect(projectToCanvas([0, 0, 3], IDENTITY, IDENTITY, 800, 600)).toBeNull();
  });

  it("returns null for points behind the camera", () => {
    expect(projectToCanvas([0, 0, 1], IDENTITY, PERSPECTIVE, 800, 600)).toBeNull();
  });

  it("projects points in front of the camera with perspective divide", () => {
    const pos = projectToCanvas([0, 0, -10], IDENTITY, PERSPECTIVE, 800, 600);
    expect(pos).not.toBeNull();
    expect(pos!.x).toBeCloseTo(400);
    expect(pos!.y).toBeCloseTo(300);
    const off = projectToCanvas([2.5, 0, -10], IDENTITY, PERSPECTIVE, 800, 600);
    expect(off).not.toBeNull();
    expect(off!.x).toBeCloseTo(500);
  });

  it("applies the view matrix before projecting", () => {
    const translate = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -0.5, 0, 0, 1];
    expect(projectToCanvas([0.5, 0, 0], translate, IDENTITY, 800, 600)).toEqual({
      x: 400,
      y: 300,
    });
  });
});
