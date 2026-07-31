// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";

const mockCtx: { current: unknown } = { current: null };
vi.mock("./ViewerContext", () => ({ useViewer: () => mockCtx.current }));

const api = vi.hoisted(() => ({
  fetchOverrides: vi.fn(),
  saveEntityProperties: vi.fn(),
}));
vi.mock("@/api/client", () => api);

import { PropertyPanel } from "./PropertyPanel";
import { useViewerStore } from "./store";

afterEach(cleanup);

const metaObject = {
  id: "w1",
  name: "Wall A",
  type: "IfcWall",
  parent: "st",
  propertySets: [
    {
      id: "pset1",
      name: "Pset_WallCommon",
      type: "Pset",
      properties: [
        { name: "FireRating", value: "120 min", type: "1" },
        { name: "LoadBearing", value: true, type: "3" },
      ],
    },
    {
      id: "pset2",
      name: "Pset_Geometry",
      type: "Pset",
      properties: [{ name: "Height", value: 3200, type: "4" }],
    },
  ],
};

function setup() {
  mockCtx.current = { metaModel: { metaObjects: { w1: metaObject } } };
  useViewerStore.setState({
    selectedId: null, tool: "select", hiddenIds: [], isolateId: null, xray: false,
    overrides: {}, changesVersion: 0,
  });
  vi.clearAllMocks();
  api.fetchOverrides.mockResolvedValue({});
}

describe("PropertyPanel", () => {
  beforeEach(setup);

  it("shows empty state when nothing is selected", () => {
    render(<PropertyPanel modelId="m1" />);
    expect(screen.getByText("点击构件查看属性")).toBeTruthy();
  });

  it("stays in empty state without a meta model even if selected", () => {
    mockCtx.current = null;
    useViewerStore.getState().setSelected("w1");
    render(<PropertyPanel modelId="m1" />);
    expect(screen.getByText("点击构件查看属性")).toBeTruthy();
  });

  it("search filters properties by name or value", () => {
    useViewerStore.getState().setSelected("w1");
    render(<PropertyPanel modelId="m1" />);
    fireEvent.change(screen.getByPlaceholderText("搜索属性"), {
      target: { value: "fire" },
    });
    expect(screen.getAllByText("FireRating").length).toBeGreaterThan(0);
    expect(screen.queryByText("LoadBearing")).toBeNull();
  });

  it("second pset collapsed by default, expands on click", () => {
    useViewerStore.getState().setSelected("w1");
    render(<PropertyPanel modelId="m1" />);
    expect(screen.queryByText("Height")).toBeNull();
    fireEvent.click(screen.getByText("Pset_Geometry"));
    expect(screen.getByText("Height")).toBeTruthy();
  });

  it("copy button writes name: value to clipboard", async () => {
    const writeText = vi.fn(async () => {});
    Object.assign(navigator, { clipboard: { writeText } });
    useViewerStore.getState().setSelected("w1");
    render(<PropertyPanel modelId="m1" />);
    const row = screen.getByLabelText("复制 FireRating").closest("tr")!;
    fireEvent.click(row.querySelector("button.property-copy-btn")!);
    expect(writeText).toHaveBeenCalledWith("FireRating: 120 min");
  });
});

describe("PropertyPanel editing", () => {
  beforeEach(setup);

  it("loads overrides on mount and shadows overridden pset values with a marker", async () => {
    api.fetchOverrides.mockResolvedValue({ w1: { FireRating: "90 min" } });
    useViewerStore.getState().setSelected("w1");
    render(<PropertyPanel modelId="m1" />);
    await waitFor(() => expect(api.fetchOverrides).toHaveBeenCalledWith("m1"));
    const psetRow = screen.getByLabelText("复制 FireRating").closest("tr")!;
    expect(psetRow.querySelector(".property-value")!.textContent).toBe("90 min");
    const editRow = screen.getByTestId("editable-FireRating");
    expect(editRow.classList.contains("overridden")).toBe(true);
    expect(editRow.textContent).toContain("90 min");
  });

  it("editable section lists whitelist fields with effective values", () => {
    useViewerStore.getState().setSelected("w1");
    render(<PropertyPanel modelId="m1" />);
    expect(screen.getByTestId("editable-Name").textContent).toContain("Wall A");
    expect(screen.getByTestId("editable-FireRating").textContent).toContain("120 min");
    expect(screen.getByTestId("editable-Comments").classList.contains("overridden")).toBe(false);
  });

  it("click value, edit, Enter saves and updates store overrides", async () => {
    api.saveEntityProperties.mockResolvedValue({ Name: "Wall B" });
    useViewerStore.getState().setSelected("w1");
    render(<PropertyPanel modelId="m1" />);
    fireEvent.click(screen.getByTestId("editable-Name").querySelector(".editable-value")!);
    const input = screen.getByDisplayValue("Wall A");
    fireEvent.change(input, { target: { value: "Wall B" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() =>
      expect(api.saveEntityProperties).toHaveBeenCalledWith("m1", "w1", { Name: "Wall B" }, "Wall A")
    );
    await waitFor(() =>
      expect(useViewerStore.getState().overrides).toEqual({ w1: { Name: "Wall B" } })
    );
    expect(useViewerStore.getState().changesVersion).toBe(1);
    expect(screen.getByTestId("editable-Name").classList.contains("overridden")).toBe(true);
  });

  it("Esc cancels editing without saving", () => {
    useViewerStore.getState().setSelected("w1");
    render(<PropertyPanel modelId="m1" />);
    fireEvent.click(screen.getByTestId("editable-Name").querySelector(".editable-value")!);
    const input = screen.getByDisplayValue("Wall A");
    fireEvent.change(input, { target: { value: "Wall B" } });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(api.saveEntityProperties).not.toHaveBeenCalled();
    expect(screen.queryByDisplayValue("Wall B")).toBeNull();
  });

  it("blur saves the draft", async () => {
    api.saveEntityProperties.mockResolvedValue({ Comments: "note" });
    useViewerStore.getState().setSelected("w1");
    render(<PropertyPanel modelId="m1" />);
    fireEvent.click(screen.getByTestId("editable-Comments").querySelector(".editable-value")!);
    const input = screen.getByLabelText("编辑 Comments");
    fireEvent.change(input, { target: { value: "note" } });
    fireEvent.blur(input);
    await waitFor(() =>
      expect(api.saveEntityProperties).toHaveBeenCalledWith("m1", "w1", { Comments: "note" }, "Wall A")
    );
  });

  it("shows error when save fails and keeps editing", async () => {
    api.saveEntityProperties.mockRejectedValue(new Error("field not in whitelist"));
    useViewerStore.getState().setSelected("w1");
    render(<PropertyPanel modelId="m1" />);
    fireEvent.click(screen.getByTestId("editable-Name").querySelector(".editable-value")!);
    const input = screen.getByDisplayValue("Wall A");
    fireEvent.change(input, { target: { value: "X" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(await screen.findByText("field not in whitelist")).toBeTruthy();
  });
});
