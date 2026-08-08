// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";

const mockCtx: { current: unknown } = { current: null };
vi.mock("./ViewerContext", () => ({ useViewer: () => mockCtx.current }));

const api = vi.hoisted(() => ({
  fetchOverrides: vi.fn(),
  fetchEditableSchema: vi.fn(),
  putEntityEdit: vi.fn(),
  deleteEntity: vi.fn(),
  fetchEditPending: vi.fn(),
  commitEdits: vi.fn(),
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

const schema = {
  guid: "w1",
  ifcType: "IfcWall",
  fields: [
    { name: "Name", kind: "string", value: "Wall A" },
    { name: "Description", kind: "string", value: "Desc" },
    {
      name: "PredefinedType",
      kind: "enum",
      value: null,
      enumValues: ["STANDARD", "PARTITIONING", "USERDEFINED", "NOTDEFINED"],
    },
  ],
  psets: [
    {
      name: "Pset_WallCommon",
      properties: [
        { name: "FireRating", kind: "string", value: "120 min" },
        { name: "LoadBearing", kind: "bool", value: true },
        { name: "ThermalTransmittance", kind: "float", value: 0.24 },
      ],
    },
  ],
};

function setup({ withSchema = true } = {}) {
  mockCtx.current = { metaModel: { metaObjects: { w1: metaObject } } };
  useViewerStore.setState({
    selectedId: null, tool: "select", hiddenIds: [], isolateId: null, xray: false,
    overrides: {}, changesVersion: 0, pendingModelReload: false,
  });
  vi.clearAllMocks();
  api.fetchOverrides.mockResolvedValue({});
  api.fetchEditPending.mockResolvedValue([]);
  if (withSchema) {
    api.fetchEditableSchema.mockResolvedValue(structuredClone(schema));
  } else {
    api.fetchEditableSchema.mockRejectedValue(new Error("edit service unreachable"));
  }
}

function selectAndRender() {
  useViewerStore.getState().setSelected("w1");
  render(<PropertyPanel modelId="m1" />);
  return waitFor(() => expect(api.fetchEditableSchema).toHaveBeenCalledWith("m1", "w1"));
}

describe("PropertyPanel base", () => {
  beforeEach(() => setup());

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

  it("fetches editable schema and pending count for the selection", async () => {
    await selectAndRender();
    await waitFor(() => expect(screen.getByTestId("field-Name")).toBeTruthy());
    expect(api.fetchEditPending).toHaveBeenCalledWith("m1");
  });
});

describe("PropertyPanel typed rendering", () => {
  beforeEach(() => setup());

  it("renders string fields as click-to-edit values", async () => {
    await selectAndRender();
    const row = await screen.findByTestId("field-Name");
    expect(row.textContent).toContain("Wall A");
    expect(row.querySelector(".editable-value")).toBeTruthy();
  });

  it("renders enum fields as a select with legal values when editing", async () => {
    await selectAndRender();
    const row = await screen.findByTestId("field-PredefinedType");
    fireEvent.click(row.querySelector(".editable-value")!);
    const select = row.querySelector("select")!;
    const options = Array.from(select.querySelectorAll("option")).map((o) => o.textContent);
    for (const v of ["STANDARD", "PARTITIONING", "USERDEFINED", "NOTDEFINED"]) {
      expect(options).toContain(v);
    }
  });

  it("renders bool pset props as checkboxes", async () => {
    await selectAndRender();
    const row = await screen.findByTestId("pset-Pset_WallCommon.LoadBearing");
    const checkbox = row.querySelector("input[type=checkbox]") as HTMLInputElement;
    expect(checkbox).toBeTruthy();
    expect(checkbox.checked).toBe(true);
  });

  it("renders numeric pset props with kind-typed values", async () => {
    await selectAndRender();
    const row = await screen.findByTestId("pset-Pset_WallCommon.ThermalTransmittance");
    expect(row.textContent).toContain("0.24");
  });

  it("search filters schema fields and pset props", async () => {
    await selectAndRender();
    await screen.findByTestId("field-Name");
    fireEvent.change(screen.getByPlaceholderText("搜索属性"), { target: { value: "fire" } });
    expect(screen.queryByTestId("field-Name")).toBeNull();
    expect(screen.queryByTestId("pset-Pset_WallCommon.FireRating")).toBeTruthy();
    expect(screen.queryByTestId("pset-Pset_WallCommon.LoadBearing")).toBeNull();
  });
});

describe("PropertyPanel true-edit flow", () => {
  beforeEach(() => setup());

  it("string field edit PUTs fields payload and shows pending banner", async () => {
    api.putEntityEdit.mockResolvedValue({ id: "e_1" });
    api.fetchEditPending.mockResolvedValue([{ id: "e_1" }]);
    await selectAndRender();
    const row = await screen.findByTestId("field-Name");
    fireEvent.click(row.querySelector(".editable-value")!);
    const input = screen.getByDisplayValue("Wall A");
    fireEvent.change(input, { target: { value: "Wall B" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() =>
      expect(api.putEntityEdit).toHaveBeenCalledWith("m1", "w1", {
        fields: { Name: "Wall B" },
        author: "local-user",
        provenance: { source: "UI" },
      })
    );
    expect(await screen.findByText(/有未提交修改/)).toBeTruthy();
    expect((await screen.findByTestId("field-Name")).textContent).toContain("Wall B");
  });

  it("enum select saves chosen value via PUT", async () => {
    api.putEntityEdit.mockResolvedValue({ id: "e_1" });
    await selectAndRender();
    const row = await screen.findByTestId("field-PredefinedType");
    fireEvent.click(row.querySelector(".editable-value")!);
    fireEvent.change(row.querySelector("select")!, { target: { value: "PARTITIONING" } });
    await waitFor(() =>
      expect(api.putEntityEdit).toHaveBeenCalledWith("m1", "w1", {
        fields: { PredefinedType: "PARTITIONING" },
        author: "local-user",
        provenance: { source: "UI" },
      })
    );
  });

  it("bool checkbox toggles via PUT with psets payload", async () => {
    api.putEntityEdit.mockResolvedValue({ id: "e_1" });
    await selectAndRender();
    const row = await screen.findByTestId("pset-Pset_WallCommon.LoadBearing");
    fireEvent.click(row.querySelector("input[type=checkbox]")!);
    await waitFor(() =>
      expect(api.putEntityEdit).toHaveBeenCalledWith("m1", "w1", {
        psets: { Pset_WallCommon: { LoadBearing: false } },
        author: "local-user",
        provenance: { source: "UI" },
      })
    );
  });

  it("pset string edit PUTs psets payload", async () => {
    api.putEntityEdit.mockResolvedValue({ id: "e_1" });
    await selectAndRender();
    const row = await screen.findByTestId("pset-Pset_WallCommon.FireRating");
    fireEvent.click(row.querySelector(".editable-value")!);
    const input = screen.getByDisplayValue("120 min");
    fireEvent.change(input, { target: { value: "90 min" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() =>
      expect(api.putEntityEdit).toHaveBeenCalledWith("m1", "w1", {
        psets: { Pset_WallCommon: { FireRating: "90 min" } },
        author: "local-user",
        provenance: { source: "UI" },
      })
    );
  });

  it("rejects invalid numeric input without calling PUT", async () => {
    await selectAndRender();
    const row = await screen.findByTestId("pset-Pset_WallCommon.ThermalTransmittance");
    fireEvent.click(row.querySelector(".editable-value")!);
    const input = screen.getByDisplayValue("0.24");
    fireEvent.change(input, { target: { value: "abc" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(api.putEntityEdit).not.toHaveBeenCalled();
    expect(await screen.findByText(/无效数字/)).toBeTruthy();
  });

  it("Esc cancels editing without saving", async () => {
    await selectAndRender();
    const row = await screen.findByTestId("field-Name");
    fireEvent.click(row.querySelector(".editable-value")!);
    const input = screen.getByDisplayValue("Wall A");
    fireEvent.change(input, { target: { value: "Wall B" } });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(api.putEntityEdit).not.toHaveBeenCalled();
  });

  it("shows error when PUT fails", async () => {
    api.putEntityEdit.mockRejectedValue(new Error("invalid enum value"));
    await selectAndRender();
    const row = await screen.findByTestId("field-Name");
    fireEvent.click(row.querySelector(".editable-value")!);
    const input = screen.getByDisplayValue("Wall A");
    fireEvent.change(input, { target: { value: "X" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(await screen.findByText("invalid enum value")).toBeTruthy();
  });

  it("existing pending changes show the banner on load", async () => {
    api.fetchEditPending.mockResolvedValue([{ id: "e_old" }]);
    await selectAndRender();
    expect(await screen.findByText(/有未提交修改/)).toBeTruthy();
  });

  it("commit button commits, clears banner and flags model reload", async () => {
    api.commitEdits.mockResolvedValue({ committed: 1 });
    api.fetchEditPending.mockResolvedValue([{ id: "e_old" }]);
    await selectAndRender();
    fireEvent.click(await screen.findByRole("button", { name: "提交" }));
    await waitFor(() => expect(api.commitEdits).toHaveBeenCalledWith("m1"));
    await waitFor(() =>
      expect(useViewerStore.getState().pendingModelReload).toBe(true)
    );
    expect(useViewerStore.getState().changesVersion).toBe(1);
    expect(screen.queryByText(/有未提交修改/)).toBeNull();
  });

  it("shows error when commit fails", async () => {
    api.commitEdits.mockRejectedValue(new Error("no pending changes"));
    api.fetchEditPending.mockResolvedValue([{ id: "e_old" }]);
    await selectAndRender();
    fireEvent.click(await screen.findByRole("button", { name: "提交" }));
    expect(await screen.findByText("no pending changes")).toBeTruthy();
  });
});

describe("PropertyPanel entity deletion", () => {
  beforeEach(() => setup());

  it("delete button asks for confirmation then DELETEs into pending", async () => {
    const confirmSpy = vi.fn(() => true);
    vi.stubGlobal("confirm", confirmSpy);
    api.deleteEntity.mockResolvedValue({ id: "e_del", action: "delete" });
    api.fetchEditPending.mockResolvedValue([{ id: "e_del" }]);
    await selectAndRender();
    fireEvent.click(await screen.findByRole("button", { name: "删除构件" }));
    expect(confirmSpy).toHaveBeenCalled();
    await waitFor(() =>
      expect(api.deleteEntity).toHaveBeenCalledWith("m1", "w1", {
        author: "local-user",
        provenance: { source: "UI" },
      })
    );
    expect(await screen.findByText(/已标记删除/)).toBeTruthy();
    expect(await screen.findByText(/有未提交修改/)).toBeTruthy();
    vi.unstubAllGlobals();
  });

  it("cancelled confirmation does not delete", async () => {
    vi.stubGlobal("confirm", vi.fn(() => false));
    await selectAndRender();
    fireEvent.click(await screen.findByRole("button", { name: "删除构件" }));
    expect(api.deleteEntity).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });
});

describe("PropertyPanel read-only fallback and overrides", () => {
  beforeEach(() => setup({ withSchema: false }));

  it("falls back to read-only meta psets when schema is unavailable", async () => {
    await selectAndRender();
    expect(await screen.findByText("编辑服务不可用，只读模式")).toBeTruthy();
    expect(screen.getByText("FireRating")).toBeTruthy();
    expect(screen.queryByTestId("field-Name")).toBeNull();
  });

  it("historical overrides shadow displayed values read-only with a marker", async () => {
    api.fetchOverrides.mockResolvedValue({ w1: { FireRating: "90 min" } });
    await selectAndRender();
    await waitFor(() => expect(api.fetchOverrides).toHaveBeenCalledWith("m1"));
    const psetRow = screen.getByLabelText("复制 FireRating").closest("tr")!;
    expect(psetRow.querySelector(".property-value")!.textContent).toBe("90 min");
    expect(psetRow.classList.contains("overridden")).toBe(true);
  });

  it("copy button writes name: value to clipboard in fallback mode", async () => {
    const writeText = vi.fn(async () => {});
    Object.assign(navigator, { clipboard: { writeText } });
    await selectAndRender();
    const row = await screen.findByLabelText("复制 FireRating");
    fireEvent.click(row.closest("tr")!.querySelector("button.property-copy-btn")!);
    expect(writeText).toHaveBeenCalledWith("FireRating: 120 min");
  });
});
