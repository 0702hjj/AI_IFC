// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { listModels, fetchModel, uploadModel, deleteModel, downloadUrl, renderJsonUrl, listIssues, createIssue, updateIssue, deleteIssue, fetchEditVersions, postEditDiff, fetchScript, fetchScriptParams, stageScript, stageScriptParams, scriptUndo, scriptRedo, discardScript, runScript, saveScript, rollbackScript, fetchScriptVersions, postScriptDiff, fetchStagingDiff, locateScript, createChatProject, chatEventsUrl } from "./client";
import { setToken, clearToken, onUnauthorized } from "./auth";

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
  it("renderJsonUrl format", () => {
    expect(renderJsonUrl("m_x")).toBe("/v1/models/m_x/render.json");
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

describe("script locate api", () => {
  it("locateScript GETs locate endpoint with guid query", async () => {
    const located = {
      found: true, designKey: "wall-1", line: 12, col: 4,
      snippet: "make_wall(key='wall-1')", origin: "params",
    };
    const spy = vi.fn(async () => new Response(JSON.stringify(envelope(located)), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    const res = await locateScript("m_1", "3abc DEF");
    expect((spy.mock.calls[0] as unknown as [string])[0]).toBe(
      "/api/v1/models/m_1/script/locate?guid=3abc%20DEF"
    );
    expect(res).toEqual(located);
  });

  it("locateScript miss returns found=false without throwing", async () => {
    vi.stubGlobal("fetch", vi.fn(async () =>
      new Response(JSON.stringify(envelope({ found: false })), { status: 200 })));
    const res = await locateScript("m_1", "g1");
    expect(res.found).toBe(false);
  });
});

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

  it("fetchScript gets script state", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(envelope({ modelId: "m_1", script: "PARAMS = {}", staged: 0, canUndo: false, canRedo: false, maxSteps: 10 })), { status: 200 })));
    const s = await fetchScript("m_1");
    expect(s.modelId).toBe("m_1");
    expect(s.maxSteps).toBe(10);
  });
  it("fetchScriptParams unwraps params", async () => {
    const spy = vi.fn(async () => new Response(JSON.stringify(envelope({ modelId: "m_1", params: { wall_t: 0.2 } })), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    const r = await fetchScriptParams("m_1");
    expect((spy.mock.calls[0] as unknown as [string])[0]).toBe("/api/v1/models/m_1/script/params");
    expect(r.params).toEqual({ wall_t: 0.2 });
  });
  it("stageScript PUTs a full script, stageScriptParams PUTs params only", async () => {
    const spy = vi.fn(async () => new Response(JSON.stringify(envelope({ modelId: "m_1", staged: 1, canUndo: true, canRedo: false })), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    await stageScript("m_1", "PARAMS = {}");
    await stageScriptParams("m_1", { wall_t: 0.3 });
    const [url1, init1] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url1).toBe("/api/v1/models/m_1/script");
    expect(init1.method).toBe("PUT");
    expect(JSON.parse(init1.body as string)).toEqual({ script: "PARAMS = {}", note: "" });
    const [, init2] = spy.mock.calls[1] as unknown as [string, RequestInit];
    expect(JSON.parse(init2.body as string)).toEqual({ params: { wall_t: 0.3 }, note: "" });
  });
  it("undo/redo/discard/run/save/rollback/versions/diff hit the right script endpoints", async () => {
    const spy = vi.fn(async () => new Response(JSON.stringify(envelope({ modelId: "m_1" })), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    await scriptUndo("m_1");
    await scriptRedo("m_1");
    await discardScript("m_1");
    await runScript("m_1");
    await saveScript("m_1");
    await rollbackScript("m_1", "v1");
    await fetchScriptVersions("m_1");
    await postScriptDiff("m_1", "v1", "v2");
    await fetchStagingDiff("m_1");
    const methods = (spy.mock.calls as unknown as [string, RequestInit | undefined][]).map(([url, init]) => `${init?.method ?? "GET"} ${url}`);
    expect(methods).toContain("POST /api/v1/models/m_1/script/undo");
    expect(methods).toContain("POST /api/v1/models/m_1/script/redo");
    expect(methods).toContain("POST /api/v1/models/m_1/script/discard");
    expect(methods).toContain("POST /api/v1/models/m_1/script/run");
    expect(methods).toContain("POST /api/v1/models/m_1/script/save");
    expect(methods).toContain("POST /api/v1/models/m_1/script/rollback");
    expect(methods).toContain("GET /api/v1/models/m_1/scripts");
    expect(methods).toContain("POST /api/v1/models/m_1/script/diff");
    expect(methods).toContain("GET /api/v1/models/m_1/script/staging/diff");
  });
  it("fetchStagingDiff passes from/to as query params", async () => {
    const spy = vi.fn(async () => new Response(JSON.stringify(envelope({ from: 1, to: 2 })), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    await fetchStagingDiff("m_1", 1, 2);
    expect((spy.mock.calls[0] as unknown as [string])[0]).toBe("/api/v1/models/m_1/script/staging/diff?from=1&to=2");
  });
  it("postScriptDiff posts base/target and unwraps", async () => {
    const diff = { base: "v1", target: "v2", engine: "script", text_diff: "@@", params_changes: [{ key: "wall_t", action: "modified", old: 0.2, new: 0.3 }], stats: { added: 1, removed: 1 } };
    const spy = vi.fn(async () => new Response(JSON.stringify(envelope(diff)), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    const r = await postScriptDiff("m_1", "v1", "v2");
    const [, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ base: "v1", target: "v2" });
    expect(r).toEqual(diff);
  });
});

describe("chat api", () => {
  it("createChatProject posts to /api/v1/chat/projects and unwraps ModelInfo", async () => {
    const model = { id: "m_0123456789abcdef", name: "p.ifc", size: 540, status: "converting", createdAt: "2026-08-05T00:00:00Z", error: "" };
    const spy = vi.fn(async () => new Response(JSON.stringify(envelope(model)), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    const m = await createChatProject("p");
    const [url, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/v1/chat/projects");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ title: "p" });
    expect(m).toEqual(model);
  });
});

describe("api token 注入（W-0010）", () => {
  afterEach(() => clearToken());

  it("localStorage 有 token 时注入 Authorization: Bearer 头", async () => {
    setToken("s3cret");
    const spy = vi.fn(async () => new Response(JSON.stringify(envelope([])), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    await listModels();
    const headers = new Headers((spy.mock.calls[0] as unknown as [string, RequestInit])[1].headers);
    expect(headers.get("Authorization")).toBe("Bearer s3cret");
  });

  it("无 token 时不注入 Authorization 头（零行为变化）", async () => {
    const spy = vi.fn(async () => new Response(JSON.stringify(envelope([])), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    await listModels();
    const headers = new Headers((spy.mock.calls[0] as unknown as [string, RequestInit])[1].headers);
    expect(headers.get("Authorization")).toBeNull();
  });

  it("401 触发 unauthorized 订阅，保存 token 后带新 token 重试原请求", async () => {
    const on401 = vi.fn();
    const off = onUnauthorized(on401);
    const spy = vi.fn(async (_url: string, init?: RequestInit) => {
      const auth = new Headers(init?.headers).get("Authorization");
      if (auth !== "Bearer s3cret") {
        return new Response(JSON.stringify({ code: 40100, message: "missing or invalid bearer token", data: null }), { status: 401 });
      }
      return new Response(JSON.stringify(envelope([{ id: "m_1" }])), { status: 200 });
    });
    vi.stubGlobal("fetch", spy);
    const pending = listModels();
    await vi.waitFor(() => expect(on401).toHaveBeenCalledTimes(1));
    setToken("s3cret");
    const models = await pending;
    expect(models).toEqual([{ id: "m_1" }]);
    expect(spy).toHaveBeenCalledTimes(2);
    off();
  });

  it("重试后仍 401 则抛出服务端错误信息（不无限重试）", async () => {
    const on401 = vi.fn();
    const off = onUnauthorized(on401);
    vi.stubGlobal("fetch", vi.fn(async () =>
      new Response(JSON.stringify({ code: 40100, message: "missing or invalid bearer token", data: null }), { status: 401 })));
    const pending = listModels();
    const assertion = expect(pending).rejects.toThrow("missing or invalid bearer token");
    await vi.waitFor(() => expect(on401).toHaveBeenCalledTimes(1));
    setToken("wrong");
    await assertion;
    // 挂起的 promise 已 settle，无额外重试
    expect(vi.mocked(fetch).mock.calls.length).toBe(2);
    off();
  });

  it("chatEventsUrl 有 token 时拼 ?token=（SSE EventSource 无法带自定义头）", () => {
    expect(chatEventsUrl("c1")).toBe("/api/v1/chat/sessions/c1/events");
    setToken("s3cret");
    expect(chatEventsUrl("c1")).toBe("/api/v1/chat/sessions/c1/events?token=s3cret");
  });

  it("chatEventsUrl 对 token 做 URL 编码", () => {
    setToken("a b+c=");
    expect(chatEventsUrl("c1")).toBe(`/api/v1/chat/sessions/c1/events?token=${encodeURIComponent("a b+c=")}`);
  });
});

describe("script api envelope contract", () => {
  it("fetchScript unwraps envelope data", async () => {
    const state = { modelId: "m_1", script: "PARAMS = {}", staged: 0, canUndo: false, canRedo: false, maxSteps: 10 };
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(envelope(state)), { status: 200 })));
    const s = await fetchScript("m_1");
    expect(s).toEqual(state);
  });

  it("stageScript unwraps envelope data", async () => {
    const result = { modelId: "m_1", staged: 1, canUndo: true, canRedo: false };
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(envelope(result)), { status: 200 })));
    const r = await stageScript("m_1", "PARAMS = {}", "n1");
    expect(r).toEqual(result);
  });

  it("saveScript unwraps envelope data", async () => {
    const result = { modelId: "m_1", version: "v1", staged: 0 };
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(envelope(result)), { status: 200 })));
    const r = await saveScript("m_1", "note");
    expect(r).toEqual(result);
  });

  it("rollbackScript posts the version", async () => {
    const spy = vi.fn(async () => new Response(JSON.stringify(envelope({ modelId: "m_1", version: "v1", script: "x" })), { status: 200 }));
    vi.stubGlobal("fetch", spy);
    await rollbackScript("m_1", "v1");
    expect(JSON.parse((spy.mock.calls[0] as unknown as [string, RequestInit])[1].body as string)).toEqual({ version: "v1" });
  });

  it("fetchScriptVersions unwraps script + ifc version lists", async () => {
    const res = { modelId: "m_1", scripts: [{ version: "v1", createdAt: "t", note: "" }], versions: [{ version: "v1", createdAt: "t" }] };
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(envelope(res)), { status: 200 })));
    const r = await fetchScriptVersions("m_1");
    expect(r).toEqual(res);
  });

  it("rejects when script endpoints return bare JSON without envelope (regression: P0-1)", async () => {
    const bare = () => new Response(JSON.stringify({ modelId: "m_1", script: "" }), { status: 200 });
    vi.stubGlobal("fetch", vi.fn(bare));
    await expect(fetchScript("m_1")).rejects.toThrow();
    await expect(stageScript("m_1", "x")).rejects.toThrow();
    await expect(saveScript("m_1")).rejects.toThrow();
    await expect(postScriptDiff("m_1", "v1", "v2")).rejects.toThrow();
  });

  it("rejects with server message on non-zero script envelope code (legacy model 404)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ code: 40400, message: "no script for model", data: null }), { status: 404 })));
    await expect(fetchScript("m_1")).rejects.toThrow("no script for model");
  });
});
