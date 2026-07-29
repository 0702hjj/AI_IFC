import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";

const mockCtx: { current: unknown } = { current: null };
vi.mock("./ViewerContext", () => ({ useViewer: () => mockCtx.current }));

const api = vi.hoisted(() => ({
  listIssues: vi.fn(),
  createIssue: vi.fn(),
  updateIssue: vi.fn(),
  deleteIssue: vi.fn(),
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
  });
  api.listIssues.mockResolvedValue([sample]);
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
