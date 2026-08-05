// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { DesignPanel } from "./DesignPanel";

const designState = {
  modelId: "m_1",
  design: {
    meta: { name: "t" },
    frame: { storeys: { "1F": 0.0 } },
    floors: {
      "1F": {
        walls: [{ key: "1F:wall:0", axis: [[0, 0], [6, 0]], t: 0.2, kind: "ext" }],
        openings: [],
        slabs: [{ key: "1F:slab:0", t: 0.15 }],
      },
    },
  },
  staged: 2,
  canUndo: true,
  canRedo: false,
  maxSteps: 10,
};

const versions = {
  modelId: "m_1",
  designs: [
    { version: "v1", createdAt: "t" },
    { version: "v2", createdAt: "t" },
  ],
  versions: [{ version: "v1", createdAt: "t" }],
};

// mock the viewer context and store used by DesignPanel
vi.mock("@/viewer/ViewerContext", () => ({
  useViewer: () => ({
    metaModel: {
      metaObjects: { "g1": { propertySets: [{ name: "Pset_AIIFC", properties: [{ name: "designKey", value: "1F:wall:0" }] }] } },
    },
  }),
}));
vi.mock("@/viewer/store", () => ({
  useViewerStore: (sel: any) => sel({ selectedId: "g1" }),
}));
vi.mock("@/api/client", () => ({
  fetchDesign: vi.fn(async () => designState),
  fetchDesignVersions: vi.fn(async () => versions),
  stageDesign: vi.fn(async () => ({ modelId: "m_1", staged: 3, canUndo: true, canRedo: false })),
  designUndo: vi.fn(async () => ({ modelId: "m_1", design: designState.design, canRedo: true })),
  designRedo: vi.fn(async () => ({ modelId: "m_1", design: designState.design, canUndo: true })),
  discardDesign: vi.fn(async () => ({ modelId: "m_1", discarded: 2, design: designState.design })),
  regenerateDesign: vi.fn(async () => ({ ok: true, ifc: "x", walls: 1, openings: 0, slabs: 1 })),
  saveDesign: vi.fn(async () => ({ modelId: "m_1", version: "v3", staged: 0 })),
  postDesignDiff: vi.fn(async () => ({ base: "v1", target: "v2", engine: "design-json", changed: [], added: 0, removed: 0, modified: 0 })),
}));

beforeEach(() => { vi.clearAllMocks(); cleanup(); });

describe("DesignPanel", () => {
  it("renders the selected element's params", async () => {
    render(<DesignPanel modelId="m_1" />);
    expect(await screen.findByText("Design 编辑")).toBeTruthy();
    expect(await screen.findByText("暂存 2/10")).toBeTruthy();
    expect(await screen.findByText(/1F wall 1F:wall:0/)).toBeTruthy();
    // wall schema: 厚度 + 类型
    expect(await screen.findByText("厚度 (m)")).toBeTruthy();
    expect(await screen.findByText("类型")).toBeTruthy();
  });

  it("shows big-version diff controls when >1 version", async () => {
    render(<DesignPanel modelId="m_1" />);
    expect(await screen.findByText("大版本对比")).toBeTruthy();
    expect(screen.getAllByText("对比").length).toBeGreaterThan(0);
    expect(screen.getByTestId("diff-base")).toBeTruthy();
    expect(screen.getByTestId("diff-target")).toBeTruthy();
  });
});
