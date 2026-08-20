// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// ChatSidebar 历史回填与连接（含 W-0006 历史/SSE 竞态）场景。
// 注意 import 顺序：kit（内含 store 的 vi.mock）必须先于 ./ChatSidebar 求值，
// 否则真实 store 会被抢先加载进模块缓存。
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import {
  emit,
  envelope,
  lastES,
  makeFetch,
  session,
  setupChatSidebarSuite,
  storeState,
} from "./chatSidebarTestKit";
import { ChatSidebar } from "./ChatSidebar";

setupChatSidebarSuite();

describe("ChatSidebar 历史与连接", () => {
  it("挂载时按会话 ID 建立 EventSource 连接", () => {
    render(<ChatSidebar session={session} />);
    expect(lastES().url).toBe("/api/v1/chat/sessions/c1/events");
  });

  it("空历史时显示欢迎语", async () => {
    render(<ChatSidebar session={session} />);
    expect(await screen.findByText(/已绑定当前项目/)).toBeTruthy();
  });

  it("历史拉取失败时回退到欢迎语", async () => {
    vi.stubGlobal("fetch", vi.fn(async () =>
      new Response(JSON.stringify({ code: 50000, message: "boom", data: null }), { status: 500 })));
    render(<ChatSidebar session={session} />);
    expect(await screen.findByText(/已绑定当前项目/)).toBeTruthy();
  });

  it("回填历史消息：text/reasoning/tool 三种 part 都渲染", async () => {
    const history = [
      { info: { id: "m1", role: "user" }, parts: [{ id: "p1", type: "text", text: "帮我加一扇窗" }] },
      {
        info: { id: "m2", role: "assistant" },
        parts: [
          { id: "p2", type: "reasoning", text: "先想布局" },
          { id: "p3", type: "text", text: "好的，马上处理" },
          { id: "p4", type: "tool", tool: "read", state: { status: "completed", title: "读取文件", output: "file-content" } },
        ],
      },
    ];
    vi.stubGlobal("fetch", makeFetch(history));
    render(<ChatSidebar session={session} />);
    expect(await screen.findByText("帮我加一扇窗")).toBeTruthy();
    expect(await screen.findByText("好的，马上处理")).toBeTruthy();
    expect(await screen.findByText("💭 思考过程")).toBeTruthy();
    expect(await screen.findByText("读取文件")).toBeTruthy();
  });

  it("点击收起按钮调用 setChatOpen(false)", async () => {
    render(<ChatSidebar session={session} />);
    fireEvent.click(await screen.findByTitle("收起"));
    expect(storeState.setChatOpen).toHaveBeenCalledWith(false);
  });
});

describe("ChatSidebar 历史/SSE 竞态（W-0006）", () => {
  // 可手动控制 resolve 时机的历史 fetch：构造「SSE 先到、历史后到」时序
  function deferredHistoryFetch(history: unknown) {
    let resolveHistory!: (r: Response) => void;
    const historyPromise = new Promise<Response>((res) => { resolveHistory = res; });
    const spy = vi.fn(async (url: string, init?: RequestInit) => {
      const u = String(url);
      if (u.endsWith("/messages") && init?.method === "POST")
        return new Response(envelope({ accepted: true }), { status: 200 });
      if (u.endsWith("/messages")) return historyPromise;
      return new Response(envelope(null), { status: 200 });
    });
    return { spy, resolve: () => resolveHistory(new Response(envelope(history), { status: 200 })) };
  }

  it("SSE 增量先于历史返回到达时，两条消息都保留（历史在前、SSE 在后）", async () => {
    const { spy, resolve } = deferredHistoryFetch([
      { info: { id: "m0", role: "user" }, parts: [{ id: "p0", type: "text", text: "历史消息" }] },
    ]);
    vi.stubGlobal("fetch", spy);
    render(<ChatSidebar session={session} />);
    const es = lastES();
    emit(es, "message.updated", { info: { id: "m1", role: "assistant" } });
    emit(es, "message.part.updated", { part: { id: "p1", type: "text", messageID: "m1", text: "实时回复" } });
    expect(await screen.findByText("实时回复")).toBeTruthy();
    await act(async () => { resolve(); });
    expect(await screen.findByText("历史消息")).toBeTruthy();
    expect(screen.getByText("实时回复")).toBeTruthy();
  });

  it("历史与 SSE 含相同 part id 时去重，只保留一条", async () => {
    const { spy, resolve } = deferredHistoryFetch([
      { info: { id: "m1", role: "assistant" }, parts: [{ id: "p1", type: "text", text: "历史版" }] },
    ]);
    vi.stubGlobal("fetch", spy);
    render(<ChatSidebar session={session} />);
    const es = lastES();
    emit(es, "message.updated", { info: { id: "m1", role: "assistant" } });
    emit(es, "message.part.updated", { part: { id: "p1", type: "text", messageID: "m1", text: "实时版" } });
    expect(await screen.findByText("实时版")).toBeTruthy();
    await act(async () => { resolve(); });
    await act(async () => {});
    expect(screen.queryByText("历史版")).toBeNull();
    expect(screen.getAllByText("实时版")).toHaveLength(1);
  });

  it("历史拉取失败时，已到达的 SSE 消息不被欢迎语覆盖", async () => {
    let rejectHistory!: (e: unknown) => void;
    const historyPromise = new Promise<Response>((_, rej) => { rejectHistory = rej; });
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (String(url).endsWith("/messages")) return historyPromise;
      return new Response(envelope(null), { status: 200 });
    }));
    render(<ChatSidebar session={session} />);
    const es = lastES();
    emit(es, "message.updated", { info: { id: "m1", role: "assistant" } });
    emit(es, "message.part.updated", { part: { id: "p1", type: "text", messageID: "m1", text: "实时回复" } });
    expect(await screen.findByText("实时回复")).toBeTruthy();
    await act(async () => { rejectHistory(new Error("network down")); });
    await act(async () => {});
    expect(screen.getByText("实时回复")).toBeTruthy();
    expect(screen.queryByText(/已绑定当前项目/)).toBeNull();
  });
});
