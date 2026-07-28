import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { PropertyPanel } from "./PropertyPanel";
import { useViewerStore } from "./store";

afterEach(cleanup);

beforeEach(() => {
  useViewerStore.setState({ selectedId: null, tool: "select" });
});

describe("PropertyPanel", () => {
  it("shows empty state when nothing is selected", () => {
    render(<PropertyPanel />);
    expect(screen.getByText("点击构件查看属性")).toBeTruthy();
  });

  it("stays in empty state without a meta model even if selected", () => {
    useViewerStore.getState().setSelected("wall-1");
    render(<PropertyPanel />);
    expect(screen.getByText("点击构件查看属性")).toBeTruthy();
  });
});
