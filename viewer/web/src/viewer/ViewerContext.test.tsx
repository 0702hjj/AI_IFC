// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

import { describe, it, expect, afterEach, vi } from "vitest";
import { cleanup, render, waitFor } from "@testing-library/react";

const IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];

vi.mock("@xeokit/xeokit-sdk", () => ({
  Viewer: class {
    camera = { eye: [0, 0, 1], look: [0, 0, 0], up: [0, 1, 0], viewMatrix: IDENTITY, projMatrix: IDENTITY };
    cameraFlight = { flyTo: vi.fn() };
    cameraControl = { on: vi.fn(() => ({})), off: vi.fn() };
    scene = {
      objects: {},
      selectedObjectIds: [],
      canvas: { canvas: { offsetWidth: 800, offsetHeight: 600 } },
      on: vi.fn(() => ({})),
      off: vi.fn(),
    };
    metaScene = { metaModels: {} };
    destroy() {}
  },
  NavCubePlugin: class {},
  XKTLoaderPlugin: class {
    load() {
      return {
        id: "model",
        on: (event: string, cb: () => void) => {
          if (event === "loaded") setTimeout(cb, 0);
        },
      };
    }
  },
}));

vi.mock("@/api/client", () => ({
  modelAssetUrl: (id: string, file: string) => `/models/${id}/${file}`,
}));

import { ViewerProvider } from "./ViewerContext";
import { useViewerStore } from "./store";

afterEach(cleanup);

describe("ViewerProvider", () => {
  it("renders the issue pins layer inside the canvas wrap", async () => {
    useViewerStore.setState({ issues: [], selectedIssueId: null });
    const { container } = render(<ViewerProvider modelId="m_1" />);
    await waitFor(() =>
      expect(container.querySelector(".issue-pins-layer")).toBeTruthy()
    );
    const wrap = container.querySelector(".viewer-canvas-wrap");
    expect(wrap).toBeTruthy();
    expect(wrap!.querySelector(":scope > .issue-pins-layer")).toBeTruthy();
  });
});
