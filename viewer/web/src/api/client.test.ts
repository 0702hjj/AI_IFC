import { describe, it, expect, vi, beforeEach } from "vitest";
import { listModels, uploadModel, deleteModel, downloadUrl, listIssues, createIssue, updateIssue, deleteIssue } from "./client";

const envelope = (data: unknown) => ({ code: 0, message: "ok", data });

beforeEach(() => vi.restoreAllMocks());

describe("api client", () => {
  it("listModels unwraps envelope", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(envelope([{ id: "m_1" }])), { status: 200 })));
    const models = await listModels();
    expect(models).toEqual([{ id: "m_1" }]);
  });
  it("throws on non-zero code", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ code: 40001, message: "bad type", data: null }), { status: 400 })));
    await expect(listModels()).rejects.toThrow("bad type");
  });
  it("uploadModel posts multipart FormData", async () => {
    const spy = vi.fn(async () => new Response(JSON.stringify(envelope({ id: "m_2" })), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    const file = new File(["x"], "a.ifc");
    await uploadModel(file);
    const [url, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/models");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
  });
  it("downloadUrl format", () => {
    expect(downloadUrl("m_abc")).toBe("/api/models/m_abc/download");
  });
  it("deleteModel uses DELETE", async () => {
    const spy = vi.fn(async () => new Response(JSON.stringify(envelope(null)), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    await deleteModel("m_1");
    expect((spy.mock.calls[0] as unknown as [string, RequestInit])[1].method).toBe("DELETE");
  });
});

const sampleIssue = {
  id: "i_abcdef012345", entityId: "e1", entityName: "Wall", entityType: "IfcWall",
  title: "t", comment: "", status: "open",
  camera: { eye: [1, 2, 3], look: [0, 0, 0], up: [0, 0, 1] },
  screenshot: "", createdAt: "2026-07-28T00:00:00Z", updatedAt: "2026-07-28T00:00:00Z",
};

describe("issue api", () => {
  it("listIssues unwraps envelope", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(envelope([sampleIssue])), { status: 200 })));
    const issues = await listIssues("m_0123456789abcdef");
    expect(issues).toHaveLength(1);
    expect(issues[0].id).toBe("i_abcdef012345");
  });

  it("createIssue posts multipart with issue json and screenshot", async () => {
    const spy = vi.fn(async (_url: string, init?: RequestInit) => {
      const fd = init?.body as FormData;
      expect(JSON.parse(fd.get("issue") as string).title).toBe("t");
      expect(fd.get("screenshot")).toBeTruthy();
      return new Response(JSON.stringify(envelope(sampleIssue)), { status: 200 });
    });
    vi.stubGlobal("fetch", spy);
    await createIssue("m_0123456789abcdef", {
      entityId: "e1", entityName: "Wall", entityType: "IfcWall", title: "t", comment: "",
      camera: { eye: [1, 2, 3], look: [0, 0, 0], up: [0, 0, 1] },
    }, new Blob(["x"], { type: "image/png" }));
    expect(spy).toHaveBeenCalledOnce();
  });

  it("updateIssue patches status, deleteIssue deletes", async () => {
    const spy = vi.fn(async () => new Response(JSON.stringify(envelope(sampleIssue)), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    await updateIssue("m_0123456789abcdef", "i_abcdef012345", { status: "resolved" });
    await deleteIssue("m_0123456789abcdef", "i_abcdef012345");
    expect(spy).toHaveBeenCalledTimes(2);
    const [patchUrl, patchInit] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(patchInit.method).toBe("PATCH");
    expect(patchUrl).toContain("/api/models/m_0123456789abcdef/issues/i_abcdef012345");
    const [, delInit] = spy.mock.calls[1] as unknown as [string, RequestInit];
    expect(delInit.method).toBe("DELETE");
  });
});
