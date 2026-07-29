import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { VisibilityToolbar } from "./VisibilityToolbar";
import { useViewerStore } from "./store";

afterEach(cleanup);
beforeEach(() => {
  useViewerStore.setState({
    selectedId: null, tool: "select", hiddenIds: [], isolateId: null, xray: false,
  });
});

describe("VisibilityToolbar", () => {
  it("hide/isolate disabled without selection", () => {
    render(<VisibilityToolbar />);
    expect(screen.getByText("隐藏选中")).toHaveProperty("disabled", true);
    expect(screen.getByText("隔离")).toHaveProperty("disabled", true);
  });

  it("isolate toggles store isolateId", () => {
    useViewerStore.getState().setSelected("a");
    render(<VisibilityToolbar />);
    fireEvent.click(screen.getByText("隔离"));
    expect(useViewerStore.getState().isolateId).toBe("a");
    fireEvent.click(screen.getByText("隔离"));
    expect(useViewerStore.getState().isolateId).toBeNull();
  });

  it("xray toggles store", () => {
    render(<VisibilityToolbar />);
    fireEvent.click(screen.getByText("X-Ray"));
    expect(useViewerStore.getState().xray).toBe(true);
  });

  it("reset clears visibility state", () => {
    useViewerStore.getState().setXray(true);
    render(<VisibilityToolbar />);
    fireEvent.click(screen.getByText("重置可见性"));
    expect(useViewerStore.getState().xray).toBe(false);
  });
});
