import { describe, it, expect, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useVisibility } from "./useVisibility";
import { useViewerStore } from "./store";
import type { ViewerContextValue } from "./ViewerContext";

function fakeCtx() {
  const objects: Record<string, { visible: boolean; xrayed: boolean }> = {
    a: { visible: true, xrayed: false },
    b: { visible: true, xrayed: false },
  };
  const ctx = { viewer: { scene: { objects } } } as unknown as ViewerContextValue;
  return { ctx, objects };
}

beforeEach(() => {
  useViewerStore.setState({ hiddenIds: [], isolateId: null, xray: false });
});

describe("useVisibility", () => {
  it("hides objects in hiddenIds", () => {
    const { ctx, objects } = fakeCtx();
    useViewerStore.getState().toggleHidden("a");
    renderHook(() => useVisibility(ctx));
    expect(objects.a.visible).toBe(false);
    expect(objects.b.visible).toBe(true);
  });

  it("isolate shows only the isolated object", () => {
    const { ctx, objects } = fakeCtx();
    useViewerStore.getState().isolate("a");
    renderHook(() => useVisibility(ctx));
    expect(objects.a.visible).toBe(true);
    expect(objects.b.visible).toBe(false);
  });

  it("xray marks non-isolated objects xrayed", () => {
    const { ctx, objects } = fakeCtx();
    useViewerStore.getState().setXray(true);
    renderHook(() => useVisibility(ctx));
    expect(objects.a.xrayed).toBe(true);
    expect(objects.b.xrayed).toBe(true);
  });

  it("reset restores all", () => {
    const { ctx, objects } = fakeCtx();
    useViewerStore.getState().toggleHidden("a");
    const { rerender } = renderHook(() => useVisibility(ctx));
    useViewerStore.getState().resetVisibility();
    rerender();
    expect(objects.a.visible).toBe(true);
    expect(objects.a.xrayed).toBe(false);
  });
});
