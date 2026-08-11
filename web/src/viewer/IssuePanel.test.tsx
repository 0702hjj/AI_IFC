// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor, act } from "@testing-library/react";

const mockCtx: { current: unknown } = { current: null };
vi.mock("./ViewerContext", () => ({ useViewer: () => mockCtx.current }));

const api = vi.hoisted(() => ({
  listIssues: vi.fn(),
  createIssue: vi.fn(),
  updateIssue: vi.fn(),
  deleteIssue: vi.fn(),
  fetchChanges: vi.fn(),
  issueAssetUrl: vi.fn(() => "/models/m/shot.png"),
}));
vi.mock("@/api/client", () => api);

import { IssuePanel } from "./IssuePanel";
import { useViewerStore } from "./store";

afterEach(cleanup);

const sample = {
  id: "i_abcdef012345", entityId: "w1", entityName: "Wall A", entityType: "IfcWall",
  title: "Door width incorrect", comment: "", status: "open",
  camera: { eye: [1, 2, 3], look: [0, 0, 0], up: [0, 0, 1] },
  screenshot: "", createdAt: "2026-07-28T00:00:00Z", updatedAt: "2026-07-28T00:00:00Z",
};

function setup() {
  mockCtx.current = {
    viewer: {
      camera: { eye: [1, 2, 3], look: [0, 0, 0], up: [0, 0, 1] },
      cameraFlight: { flyTo: vi.fn() },
      scene: { objects: { w1: {} } },
    },
    metaModel: { metaObjects: { w1: { id: "w1", name: "Wall A", type: "IfcWall" } } },
  };
  useViewerStore.setState({
    selectedId: null, tool: "select", hiddenIds: [], isolateId: null, xray: false,
    overrides: {}, changesVersion: 0,
  });
  vi.clearAllMocks();
  api.listIssues.mockResolvedValue([sample]);
  api.fetchChanges.mockResolvedValue([]);
  api.updateIssue.mockResolvedValue({ ...sample, status: "resolved" });
  api.deleteIssue.mockResolvedValue(null);
  api.createIssue.mockResolvedValue({ ...sample, id: "i_new000000001", title: "new" });
}

describe("IssuePanel", () => {
  beforeEach(setup);

  it("lists issues on mount", async () => {
    render(<IssuePanel modelId="m_0123456789abcdef" />);
    expect(await screen.findByText("Door width incorrect")).toBeTruthy();
    expect(screen.getByText("Wall A")).toBeTruthy();
  });

  it("create button disabled without selection", async () => {
    render(<IssuePanel modelId="m_0123456789abcdef" />);
    await screen.findByText("Door width incorrect");
    expect(screen.getByText("新建 Issue")).toHaveProperty("disabled", true);
  });

  it("creates issue with camera from viewer", async () => {
    useViewerStore.getState().setSelected("w1");
    render(<IssuePanel modelId="m_0123456789abcdef" />);
    await screen.findByText("Door width incorrect");
    fireEvent.click(screen.getByText("新建 Issue"));
    fireEvent.change(screen.getByPlaceholderText("标题"), { target: { value: "new" } });
    fireEvent.click(screen.getByText("提交"));
    await waitFor(() => expect(api.createIssue).toHaveBeenCalledOnce());
    const [, payload] = api.createIssue.mock.calls[0];
    expect(payload.title).toBe("new");
    expect(payload.entityId).toBe("w1");
    expect(payload.camera.eye).toEqual([1, 2, 3]);
  });

  it("status select patches issue", async () => {
    render(<IssuePanel modelId="m_0123456789abcdef" />);
    await screen.findByText("Door width incorrect");
    fireEvent.change(screen.getByLabelText("状态"), { target: { value: "resolved" } });
    await waitFor(() =>
      expect(api.updateIssue).toHaveBeenCalledWith(
        "m_0123456789abcdef", "i_abcdef012345", { status: "resolved" }
      )
    );
  });

  it("clicking issue flies camera and selects entity", async () => {
    render(<IssuePanel modelId="m_0123456789abcdef" />);
    fireEvent.click(await screen.findByText("Door width incorrect"));
    const ctx = mockCtx.current as { viewer: { cameraFlight: { flyTo: ReturnType<typeof vi.fn> } } };
    expect(ctx.viewer.cameraFlight.flyTo).toHaveBeenCalledWith({
      eye: [1, 2, 3], look: [0, 0, 0], up: [0, 0, 1],
    });
    expect(useViewerStore.getState().selectedId).toBe("w1");
  });

  it("delete removes issue after confirm", async () => {
    vi.stubGlobal("confirm", vi.fn(() => true));
    render(<IssuePanel modelId="m_0123456789abcdef" />);
    await screen.findByText("Door width incorrect");
    fireEvent.click(screen.getByLabelText("删除 Issue"));
    await waitFor(() => expect(api.deleteIssue).toHaveBeenCalledOnce());
    await waitFor(() => expect(screen.queryByText("Door width incorrect")).toBeNull());
    vi.unstubAllGlobals();
  });
});

describe("IssuePanel history tab", () => {
  beforeEach(setup);

  const entries = [
    {
      id: "c_new000000001", entityId: "w1", entityName: "Wall A", field: "Name",
      oldValue: "Wall A", newValue: "Wall B", author: "local-user",
      provenance: { source: "UI" }, createdAt: "2026-07-29T10:00:00Z",
    },
    {
      id: "c_old000000001", entityId: "w1", entityName: "Wall A", field: "FireRating",
      oldValue: "", newValue: "90 min", author: "local-user",
      provenance: { source: "UI" }, createdAt: "2026-07-29T09:00:00Z",
    },
  ];

  it("lists changes newest-first with field, old→new and author", async () => {
    api.fetchChanges.mockResolvedValue(entries);
    render(<IssuePanel modelId="m_0123456789abcdef" />);
    fireEvent.click(screen.getByText("修改历史"));
    await waitFor(() => expect(api.fetchChanges).toHaveBeenCalledWith("m_0123456789abcdef"));
    const items = await screen.findAllByTestId("change-item");
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toContain("Name");
    expect(items[0].textContent).toContain("Wall A → Wall B");
    expect(items[0].textContent).toContain("local-user");
    expect(items[1].textContent).toContain("FireRating");
  });

  it("does not fetch changes while on issues tab", async () => {
    render(<IssuePanel modelId="m_0123456789abcdef" />);
    await screen.findByText("Door width incorrect");
    expect(api.fetchChanges).not.toHaveBeenCalled();
  });

  it("refetches history when changesVersion bumps", async () => {
    api.fetchChanges.mockResolvedValue(entries);
    render(<IssuePanel modelId="m_0123456789abcdef" />);
    fireEvent.click(screen.getByText("修改历史"));
    await screen.findAllByTestId("change-item");
    api.fetchChanges.mockResolvedValue([entries[0]]);
    act(() => useViewerStore.getState().bumpChanges());
    await waitFor(() => expect(api.fetchChanges).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getAllByTestId("change-item")).toHaveLength(1));
  });
});
