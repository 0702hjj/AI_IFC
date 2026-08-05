// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

import { describe, it, expect, vi, beforeEach } from "vitest";
import { listModels, fetchModel, uploadModel, deleteModel, downloadUrl, listIssues, createIssue, updateIssue, deleteIssue, fetchEditVersions, postEditDiff, fetchDesign, stageDesign, designUndo, designRedo, discardDesign, regenerateDesign, saveDesign, fetchDesignVersions, postDesignDiff, rollbackDesign } from "./client";

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
    expect(url).toBe("/api/v1/models");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
  });
  it("downloadUrl format", () => {
    expect(downloadUrl("m_abc")).toBe("/api/v1/models/m_abc/download");
  });
  it("deleteModel uses DELETE", async () => {
    const spy = vi.fn(async () => new Response(JSON.stringify(envelope(null)), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    await deleteModel("m_1");
    expect((spy.mock.calls[0] as unknown as [string, RequestInit])[1].method).toBe("DELETE");
  });
  it("fetchModel gets a single model", async () => {
    const spy = vi.fn(async () => new Response(JSON.stringify(envelope({ id: "m_1", status: "converting" })), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    const m = await fetchModel("m_1");
    expect((spy.mock.calls[0] as unknown as [string])[0]).toBe("/api/v1/models/m_1");
    expect(m.status).toBe("converting");
  });
});

describe("edit api", () => {
  it("fetchEditVersions unwraps envelope", async () => {
    const spy = vi.fn(async () => new Response(JSON.stringify(envelope({
      versions: [{ version: "v1", createdAt: "2026-07-29T00:00:00Z" }],
      current: "v1",
    })), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    const res = await fetchEditVersions("m_1");
    expect((spy.mock.calls[0] as unknown as [string])[0]).toBe("/api/v1/models/m_1/edit/versions");
    expect(res.versions).toHaveLength(1);
    expect(res.versions[0].version).toBe("v1");
    expect(res.current).toBe("v1");
  });

  it("postEditDiff posts base/target and unwraps", async () => {
    const diff = {
      base: "v1", target: "current",
      added: ["g1"], removed: ["g2"],
      changed: [{ guid: "g3", changes: [{ field: "Name", old: "A", new: "B" }] }],
    };
    const spy = vi.fn(async () => new Response(JSON.stringify(envelope(diff)), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    const res = await postEditDiff("m_1", "v1", "current");
    const [url, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/v1/models/m_1/edit/diff");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ base: "v1", target: "current" });
    expect(res.added).toEqual(["g1"]);
    expect(res.changed[0].changes[0]).toEqual({ field: "Name", old: "A", new: "B" });
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
    expect(patchUrl).toContain("/api/v1/models/m_0123456789abcdef/issues/i_abcdef012345");
    const [, delInit] = spy.mock.calls[1] as unknown as [string, RequestInit];
    expect(delInit.method).toBe("DELETE");
  });

  it("fetchDesign gets design state", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(envelope({ modelId: "m_1", design: { meta: {} }, staged: 0, canUndo: false, canRedo: false, maxSteps: 10 })), { status: 200 })));
    const s = await fetchDesign("m_1");
    expect(s.modelId).toBe("m_1");
    expect(s.maxSteps).toBe(10);
  });
  it("stageDesign PUTs the design", async () => {
    const spy = vi.fn(async () => new Response(JSON.stringify(envelope({ modelId: "m_1", staged: 1, canUndo: true, canRedo: false })), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    await stageDesign("m_1", { meta: { name: "x" } });
    const [url, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/v1/models/m_1/design");
    expect(init.method).toBe("PUT");
  });
  it("undo/redo/discard/regenerate/save hit the right endpoints", async () => {
    const spy = vi.fn(async () => new Response(JSON.stringify(envelope({ modelId: "m_1" })), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    await designUndo("m_1");
    await designRedo("m_1");
    await discardDesign("m_1");
    await regenerateDesign("m_1");
    await saveDesign("m_1");
    await fetchDesignVersions("m_1");
    await rollbackDesign("m_1", "v1");
    await postDesignDiff("m_1", "v1", "v2");
    const methods = (spy.mock.calls as unknown as [string, RequestInit | undefined][]).map(([url, init]) => `${init?.method ?? "GET"} ${url}`);
    expect(methods).toContain("POST /api/v1/models/m_1/design/undo");
    expect(methods).toContain("POST /api/v1/models/m_1/design/redo");
    expect(methods).toContain("POST /api/v1/models/m_1/design/discard");
    expect(methods).toContain("POST /api/v1/models/m_1/design/regenerate");
    expect(methods).toContain("POST /api/v1/models/m_1/design/save");
    expect(methods).toContain("GET /api/v1/models/m_1/designs");
    expect(methods).toContain("POST /api/v1/models/m_1/design/rollback");
    expect(methods).toContain("POST /api/v1/models/m_1/design/diff");
  });
});

describe("design api envelope contract", () => {
  it("fetchDesign unwraps envelope data", async () => {
    const state = { modelId: "m_1", design: { meta: { name: "x" } }, staged: 0, canUndo: false, canRedo: false, maxSteps: 10 };
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(envelope(state)), { status: 200 })));
    const s = await fetchDesign("m_1");
    expect(s).toEqual(state);
  });

  it("stageDesign unwraps envelope data", async () => {
    const result = { modelId: "m_1", staged: 1, canUndo: true, canRedo: false };
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(envelope(result)), { status: 200 })));
    const r = await stageDesign("m_1", { meta: {} }, "n1");
    expect(r).toEqual(result);
  });

  it("saveDesign unwraps envelope data", async () => {
    const result = { modelId: "m_1", version: "v1", committed: 1 };
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(envelope(result)), { status: 200 })));
    const r = await saveDesign("m_1", "note");
    expect(r).toEqual(result);
  });

  it("postDesignDiff unwraps envelope data", async () => {
    const diff = { base: "v1", target: "v2", added: ["e1"], removed: [], changed: [] };
    const spy = vi.fn(async () => new Response(JSON.stringify(envelope(diff)), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    const r = await postDesignDiff("m_1", "v1", "v2");
    expect(JSON.parse((spy.mock.calls[0] as unknown as [string, RequestInit])[1].body as string)).toEqual({ base: "v1", target: "v2" });
    expect(r).toEqual(diff);
  });

  it("rejects when design endpoints return bare JSON without envelope (regression: P0-1)", async () => {
    const bare = () => new Response(JSON.stringify({ modelId: "m_1", design: {} }), { status: 200 });
    vi.stubGlobal("fetch", vi.fn(bare));
    await expect(fetchDesign("m_1")).rejects.toThrow();
    await expect(stageDesign("m_1", {})).rejects.toThrow();
    await expect(saveDesign("m_1")).rejects.toThrow();
    await expect(postDesignDiff("m_1", "v1", "v2")).rejects.toThrow();
  });

  it("rejects with server message on non-zero design envelope code", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ code: 40400, message: "design not found", data: null }), { status: 404 })));
    await expect(fetchDesign("m_1")).rejects.toThrow("design not found");
  });
});
