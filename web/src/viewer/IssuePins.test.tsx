// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render, screen, fireEvent, act } from "@testing-library/react";
import type { Issue } from "@/api/types";

const mockCtx: { current: unknown } = { current: null };
vi.mock("./ViewerContext", () => ({ useViewer: () => mockCtx.current }));

import { IssuePins } from "./IssuePins";
import { useViewerStore } from "./store";

afterEach(cleanup);

const IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];

const issue: Issue = {
  id: "i_abcdef012345",
  entityId: "w1",
  entityName: "Wall A",
  entityType: "IfcWall",
  title: "Door width incorrect",
  comment: "",
  status: "open",
  camera: { eye: [1, 2, 3], look: [0, 0, 0], up: [0, 0, 1] },
  screenshot: "",
  createdAt: "2026-07-28T00:00:00Z",
  updatedAt: "2026-07-28T00:00:00Z",
};

function makeCtx(objects: Record<string, unknown>) {
  const tickHandlers = new Set<() => void>();
  const ctx = {
    viewer: {
      camera: { viewMatrix: IDENTITY, projMatrix: IDENTITY },
      cameraFlight: { flyTo: vi.fn() },
      scene: {
        objects,
        canvas: { canvas: { offsetWidth: 800, offsetHeight: 600 } },
        on: vi.fn((event: string, cb: () => void) => {
          if (event === "tick") tickHandlers.add(cb);
          return cb;
        }),
        off: vi.fn((sub: () => void) => tickHandlers.delete(sub)),
      },
    },
    metaModel: null,
  };
  return {
    ctx,
    tick: () => act(() => tickHandlers.forEach((cb) => cb())),
  };
}

function setup(objects: Record<string, unknown>, issues: Issue[] = [issue]) {
  useViewerStore.setState({
    issues,
    selectedIssueId: null,
    selectedId: null,
  });
  const made = makeCtx(objects);
  mockCtx.current = made.ctx;
  return made;
}

describe("IssuePins", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing without a viewer context", () => {
    mockCtx.current = null;
    useViewerStore.setState({ issues: [issue] });
    const { container } = render(<IssuePins />);
    expect(container.querySelector(".issue-pins-layer")).toBeNull();
  });

  it("renders a status-colored pin at the projected aabb center", () => {
    setup({ w1: { visible: true, aabb: [-1, -1, -1, 1, 1, 1] } });
    render(<IssuePins />);
    const pin = screen.getByRole("button", { name: "Issue: Door width incorrect" });
    expect(pin.className).toContain("issue-status-open");
    expect(pin.style.left).toBe("400px");
    expect(pin.style.top).toBe("300px");
  });

  it("skips issues without entityId", () => {
    setup({ w1: { visible: true, aabb: [-1, -1, -1, 1, 1, 1] } }, [
      { ...issue, entityId: "" },
    ]);
    render(<IssuePins />);
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("hides the pin when the entity has no scene object", () => {
    setup({});
    render(<IssuePins />);
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("hides the pin when the entity is invisible", () => {
    setup({ w1: { visible: false, aabb: [-1, -1, -1, 1, 1, 1] } });
    render(<IssuePins />);
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("hides the pin when projected off-canvas", () => {
    setup({ w1: { visible: true, aabb: [10, 10, 10, 12, 12, 12] } });
    render(<IssuePins />);
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("updates pin positions on scene tick", () => {
    const objects: Record<string, unknown> = {
      w1: { visible: true, aabb: [10, 10, 10, 12, 12, 12] },
    };
    const { tick } = setup(objects);
    render(<IssuePins />);
    expect(screen.queryByRole("button")).toBeNull();
    objects.w1 = { visible: true, aabb: [-1, -1, -1, 1, 1, 1] };
    tick();
    expect(screen.getByRole("button").style.left).toBe("400px");
  });

  it("clicking a pin flies the camera and selects entity and issue", () => {
    const made = setup({ w1: { visible: true, aabb: [-1, -1, -1, 1, 1, 1] } });
    render(<IssuePins />);
    fireEvent.click(screen.getByRole("button", { name: "Issue: Door width incorrect" }));
    expect(made.ctx.viewer.cameraFlight.flyTo).toHaveBeenCalledWith({
      eye: [1, 2, 3],
      look: [0, 0, 0],
      up: [0, 0, 1],
    });
    expect(useViewerStore.getState().selectedId).toBe("w1");
    expect(useViewerStore.getState().selectedIssueId).toBe(issue.id);
    expect(screen.getByRole("button").className).toContain("active");
  });

  it("unsubscribes from tick on unmount", () => {
    const made = setup({ w1: { visible: true, aabb: [-1, -1, -1, 1, 1, 1] } });
    const { unmount } = render(<IssuePins />);
    unmount();
    expect(made.ctx.viewer.scene.off).toHaveBeenCalled();
  });
});
