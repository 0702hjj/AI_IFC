// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

import { describe, it, expect } from "vitest";
import {
  aciColor,
  resolveEntityColor,
  linetypeDash,
  flipBounds,
  arcToPathD,
  payloadToObjectSpecs,
  DEFAULT_MTEXT_HEIGHT,
  FALLBACK_COLOR,
} from "./geometry";
import type { LayerInfo, RenderPayload } from "./types";

const LAYERS: LayerInfo[] = [
  { name: "0", color: 7, linetype: "CONTINUOUS" },
  { name: "WALLS", color: 3, linetype: "CONTINUOUS" },
];

describe("aciColor", () => {
  it("maps standard ACI 1-6 to primary colors", () => {
    expect(aciColor(1)).toBe("#ff0000");
    expect(aciColor(2)).toBe("#ffff00");
    expect(aciColor(3)).toBe("#00ff00");
    expect(aciColor(4)).toBe("#00ffff");
    expect(aciColor(5)).toBe("#0000ff");
    expect(aciColor(6)).toBe("#ff00ff");
  });

  it("maps ACI 7 to black (light-canvas contrast) and 8/9 to greys", () => {
    expect(aciColor(7)).toBe("#000000");
    expect(aciColor(8)).toBe("#808080");
    expect(aciColor(9)).toBe("#c0c0c0");
  });

  it("falls back to grey for unknown indices (incl. BYLAYER/BYBLOCK sentinels)", () => {
    expect(aciColor(250)).toBe(FALLBACK_COLOR);
    expect(aciColor(256)).toBe(FALLBACK_COLOR);
    expect(aciColor(0)).toBe(FALLBACK_COLOR);
  });
});

describe("resolveEntityColor", () => {
  it("resolves BYLAYER (256) through the layer table", () => {
    expect(resolveEntityColor(256, "WALLS", LAYERS)).toBe("#00ff00");
  });

  it("falls back to ACI 7 when the layer is missing from the table", () => {
    expect(resolveEntityColor(256, "GHOST", LAYERS)).toBe("#000000");
  });

  it("uses the explicit entity color when not BYLAYER", () => {
    expect(resolveEntityColor(2, "WALLS", LAYERS)).toBe("#ffff00");
  });

  it("renders BYBLOCK (0) as grey (no block context in flat spec list)", () => {
    expect(resolveEntityColor(0, "WALLS", LAYERS)).toBe(FALLBACK_COLOR);
  });
});

describe("linetypeDash", () => {
  it("returns undefined for continuous-ish linetypes", () => {
    expect(linetypeDash("CONTINUOUS")).toBeUndefined();
    expect(linetypeDash("BYLAYER")).toBeUndefined();
    expect(linetypeDash("BYBLOCK")).toBeUndefined();
  });

  it("returns a dash pattern for other linetypes", () => {
    expect(linetypeDash("DASHED")).toEqual([6, 4]);
    expect(linetypeDash("hidden")).toEqual([6, 4]);
  });
});

describe("flipBounds", () => {
  it("negates y and swaps min/max rows", () => {
    expect(flipBounds({ min: [1, 2], max: [5, 9] })).toEqual({
      min: [1, -9],
      max: [5, -2],
    });
  });
});

describe("arcToPathD", () => {
  it("emits a quarter arc 0→90 (CCW → SVG sweep-flag 1, large-arc 0), Y flipped", () => {
    expect(arcToPathD(0, 0, 10, 0, 90)).toBe("M 10 0 A 10 10 0 0 1 0 -10");
  });

  it("handles the cross-0° case 270→45 as a 135° CCW sweep", () => {
    expect(arcToPathD(0, 0, 10, 270, 45)).toBe(
      "M 0 10 A 10 10 0 0 1 7.071068 -7.071068"
    );
  });

  it("sets large-arc=1 for a 180° half circle", () => {
    expect(arcToPathD(0, 0, 5, 0, 180)).toBe("M 5 0 A 5 5 0 1 1 -5 0");
  });

  it("sets large-arc=1 for sweeps over 180°", () => {
    // end 270° → Y-up (0,-10) → canvas (0,10)
    expect(arcToPathD(0, 0, 10, 0, 270)).toBe("M 10 0 A 10 10 0 1 1 0 10");
  });

  it("honours negative (CW bulge) sweeps when end_angle is unnormalized negative", () => {
    // bulge 段：start 90 + sweep -120 → end -30；Y 翻转后 CW → sweep-flag 0
    expect(arcToPathD(0, 0, 10, 90, -30)).toBe("M 0 -10 A 10 10 0 0 0 8.660254 5");
  });

  it("splits a full circle (end_angle ≥ 360, bulge convention) into two arcs", () => {
    expect(arcToPathD(0, 0, 10, 0, 360)).toBe(
      "M 10 0 A 10 10 0 1 1 -10 0 A 10 10 0 1 1 10 0"
    );
  });

  it("flips a non-origin center into canvas coordinates", () => {
    expect(arcToPathD(5, 5, 2, 0, 90)).toBe("M 7 -5 A 2 2 0 0 1 5 -7");
  });

  it("treats INSERT-rotated native ARC angles (start shifted below 0) as CCW", () => {
    // 原生 ARC {10,50} + rotation -60 → payload {-50,-10}；真值 CCW 40°
    // start -50 ≡ 310：canvas start point = pointAt(310°), end = pointAt(350°)
    expect(arcToPathD(0, 0, 10, -50, -10)).toBe(
      "M 6.427876 7.660444 A 10 10 0 0 1 9.848078 1.736482"
    );
  });

  it("treats INSERT-rotated bulge CW angles (start shifted above 360) as CW", () => {
    // bulge CW 段 start=300 sweep=-120 + rotation +90 → payload {390,270}；真值 CW 120°
    // 平移后 {30,-90}：sweep=-120 → sweep-flag 0
    expect(arcToPathD(0, 0, 10, 390, 270)).toBe(
      "M 8.660254 -5 A 10 10 0 0 0 0 10"
    );
  });

  it("emits a degenerate move-only path for zero sweep", () => {
    expect(arcToPathD(0, 0, 10, 45, 45)).toBe("M 7.071068 -7.071068");
  });
});

function payloadWith(entities: RenderPayload["entities"]): RenderPayload {
  return {
    schemaVersion: 2,
    bounds: null,
    layers: LAYERS,
    entities,
    unsupported: [],
  };
}

describe("payloadToObjectSpecs", () => {
  it("returns an empty array for empty entities", () => {
    expect(payloadToObjectSpecs(payloadWith([]))).toEqual([]);
  });

  it("converts LINE with flipped y and resolved stroke", () => {
    const specs = payloadToObjectSpecs(
      payloadWith([
        {
          key: "k1",
          type: "LINE",
          start: [1, 2],
          end: [3, 4],
          layer: "0",
          color: 1,
          linetype: "CONTINUOUS",
        },
      ])
    );
    expect(specs).toEqual([
      {
        kind: "line",
        layer: "0",
        key: "k1",
        props: { x1: 1, y1: -2, x2: 3, y2: -4, stroke: "#ff0000" },
      },
    ]);
  });

  it("converts CIRCLE to bounding-box left/top with radius preserved", () => {
    const specs = payloadToObjectSpecs(
      payloadWith([
        {
          key: "k2",
          type: "CIRCLE",
          center: [10, 20],
          radius: 5,
          layer: "WALLS",
          color: 256,
          linetype: "CONTINUOUS",
        },
      ])
    );
    expect(specs).toEqual([
      {
        kind: "circle",
        layer: "WALLS",
        key: "k2",
        props: {
          left: 5,
          top: -25,
          radius: 5,
          stroke: "#00ff00",
          fill: null,
        },
      },
    ]);
  });

  it("converts ARC to a path spec using arcToPathD", () => {
    const specs = payloadToObjectSpecs(
      payloadWith([
        {
          key: "k3",
          type: "ARC",
          center: [0, 0],
          radius: 10,
          start_angle: 270,
          end_angle: 45,
          layer: "0",
          color: 7,
          linetype: "CONTINUOUS",
        },
      ])
    );
    expect(specs).toHaveLength(1);
    expect(specs[0].kind).toBe("path");
    expect(specs[0].props.d).toBe(arcToPathD(0, 0, 10, 270, 45));
    expect(specs[0].props.stroke).toBe("#000000");
  });

  it("converts TEXT with height as fontSize and top anchored above the flipped insert", () => {
    const specs = payloadToObjectSpecs(
      payloadWith([
        {
          key: "k4",
          type: "TEXT",
          text: "Hello",
          insert: [1, 2],
          height: 3,
          layer: "0",
          color: 5,
          linetype: "CONTINUOUS",
        },
      ])
    );
    expect(specs).toEqual([
      {
        kind: "text",
        layer: "0",
        key: "k4",
        props: { left: 1, top: -5, text: "Hello", fontSize: 3, fill: "#0000ff" },
      },
    ]);
  });

  it("converts MTEXT with the default font size", () => {
    const specs = payloadToObjectSpecs(
      payloadWith([
        {
          key: "k5",
          type: "MTEXT",
          text: "Multi",
          insert: [0, 0],
          layer: "0",
          color: 1,
          linetype: "CONTINUOUS",
        },
      ])
    );
    expect(specs).toHaveLength(1);
    expect(specs[0].kind).toBe("text");
    expect(specs[0].props.fontSize).toBe(DEFAULT_MTEXT_HEIGHT);
    expect(specs[0].props.text).toBe("Multi");
  });

  it("skips INSERT entries (geometry lives in expanded children)", () => {
    const specs = payloadToObjectSpecs(
      payloadWith([
        {
          key: "k6",
          type: "INSERT",
          name: "CHAIR",
          insert: [1, 1],
          rotation: 0,
          scale: 1,
          layer: "0",
          color: 256,
          linetype: "BYLAYER",
        },
      ])
    );
    expect(specs).toEqual([]);
  });

  it("carries the block marker and null key through for expanded children", () => {
    const specs = payloadToObjectSpecs(
      payloadWith([
        {
          key: null,
          block: "CHAIR",
          type: "LINE",
          start: [0, 0],
          end: [1, 0],
          layer: "0",
          color: 256,
          linetype: "BYLAYER",
        },
      ])
    );
    expect(specs).toHaveLength(1);
    expect(specs[0].key).toBeNull();
    expect(specs[0].block).toBe("CHAIR");
  });

  it("adds strokeDashArray for non-continuous linetypes", () => {
    const specs = payloadToObjectSpecs(
      payloadWith([
        {
          key: "k7",
          type: "LINE",
          start: [0, 0],
          end: [1, 1],
          layer: "0",
          color: 1,
          linetype: "DASHED",
        },
      ])
    );
    expect(specs[0].props.strokeDashArray).toEqual([6, 4]);
  });

  it("keeps canvas-space coverage of line endpoints consistent with flipped payload bounds", () => {
    const payload = payloadWith([
      {
        key: "k8",
        type: "LINE",
        start: [-2, 3],
        end: [4, 7],
        layer: "0",
        color: 1,
        linetype: "CONTINUOUS",
      },
      {
        key: "k9",
        type: "LINE",
        start: [0, -5],
        end: [1, 1],
        layer: "0",
        color: 1,
        linetype: "CONTINUOUS",
      },
    ]);
    payload.bounds = { min: [-2, -5], max: [4, 7] };
    const specs = payloadToObjectSpecs(payload);
    const xs = specs.flatMap((s) => [s.props.x1, s.props.x2] as number[]);
    const ys = specs.flatMap((s) => [s.props.y1, s.props.y2] as number[]);
    const flipped = flipBounds(payload.bounds);
    expect([Math.min(...xs), Math.min(...ys)]).toEqual(flipped.min);
    expect([Math.max(...xs), Math.max(...ys)]).toEqual(flipped.max);
  });
});
