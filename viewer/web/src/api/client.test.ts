import { describe, it, expect, vi, beforeEach } from "vitest";
import { listModels, uploadModel, deleteModel, downloadUrl } from "./client";

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
