// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

import { describe, it, expect } from "vitest";
import { fitZoomPan, FIT_PADDING } from "./fit";

describe("fitZoomPan", () => {
  it("centers and scales square bounds with zero padding (height-limited)", () => {
    // flipped center = (5, -5)；zoom = min(200/10, 100/10) = 10
    expect(fitZoomPan({ min: [0, 0], max: [10, 10] }, 200, 100, 0)).toEqual({
      zoom: 10,
      panX: 50,
      panY: 100,
    });
  });

  it("applies padding to the available viewport", () => {
    // avail = 160x80 → zoom 8；pan 仍居中
    expect(fitZoomPan({ min: [0, 0], max: [10, 10] }, 200, 100, 0.1)).toEqual({
      zoom: 8,
      panX: 60,
      panY: 90,
    });
  });

  it("uses the default FIT_PADDING when padding is omitted", () => {
    const explicit = fitZoomPan({ min: [0, 0], max: [10, 10] }, 200, 100, FIT_PADDING);
    expect(fitZoomPan({ min: [0, 0], max: [10, 10] }, 200, 100)).toEqual(explicit);
  });

  it("is width-limited for wide bounds", () => {
    // zoom = min(200/100, 100/10) = 2；flipped center (50, -5)
    expect(fitZoomPan({ min: [0, 0], max: [100, 10] }, 200, 100, 0)).toEqual({
      zoom: 2,
      panX: 0,
      panY: 60,
    });
  });

  it("falls back to zoom 1 for degenerate point bounds", () => {
    expect(fitZoomPan({ min: [3, 4], max: [3, 4] }, 200, 100, 0)).toEqual({
      zoom: 1,
      panX: 97,
      panY: 54,
    });
  });

  it("fits by height for zero-width bounds", () => {
    expect(fitZoomPan({ min: [2, 0], max: [2, 10] }, 200, 100, 0)).toEqual({
      zoom: 10,
      panX: 80,
      panY: 100,
    });
  });
});
