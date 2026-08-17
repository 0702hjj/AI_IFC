// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
import type { ChatSession } from "@/api/client";
import { ChatSidebar } from "./ChatSidebar";

// --- 可手动派发事件的 MockEventSource（替代浏览器 SSE 连接） ---
class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  closed = false;
  private listeners = new Map<string, ((e: Event) => void)[]>();
  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }
  addEventListener(type: string, cb: (e: Event) => void) {
    const arr = this.listeners.get(type) ?? [];
    arr.push(cb);
    this.listeners.set(type, arr);
  }
  removeEventListener(type: string, cb: (e: Event) => void) {
    this.listeners.set(type, (this.listeners.get(type) ?? []).filter((f) => f !== cb));
  }
  close() {
    this.closed = true;
  }
  dispatch(type: string, data: unknown) {
    const ev = new MessageEvent(type, { data: typeof data === "string" ? data : JSON.stringify(data) });
    for (const cb of this.listeners.get(type) ?? []) cb(ev);
  }
}

function emit(es: MockEventSource, type: string, data: unknown) {
  act(() => es.dispatch(type, data));
}

// --- store mock：chatOpen 常开，setChatOpen/flagPendingModelReload 可断言 ---
const storeState = vi.hoisted(() => ({
  chatOpen: true,
  setChatOpen: vi.fn(),
  flagPendingModelReload: vi.fn(),
}));
vi.mock("@/viewer/store", () => ({
  useViewerStore: (sel: any) => sel(storeState),
}));

const session: ChatSession = {
  chatSessionId: "c1",
  opencodeSessionId: "oc1",
  modelId: "m_1",
  title: "t",
  createdAt: "2026-08-06T00:00:00Z",
};

const envelope = (data: unknown) => JSON.stringify({ code: 0, message: "ok", data });

// 走真实 client.ts request() 解包的 fetch mock：按 URL/方法路由 chat REST 端点
function makeFetch(history: unknown = []) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    const u = String(url);
    if (u.endsWith("/messages") && init?.method === "POST")
      return new Response(envelope({ accepted: true }), { status: 200 });
    if (u.endsWith("/messages")) return new Response(envelope(history), { status: 200 });
    if (u.endsWith("/abort")) return new Response(envelope({ aborted: true }), { status: 200 });
    return new Response(JSON.stringify({ code: 40400, message: "not found", data: null }), { status: 404 });
  });
}

function lastES(): MockEventSource {
  return MockEventSource.instances[MockEventSource.instances.length - 1];
}

// 渲染并等历史回填完成（空历史 → 欢迎语），再开始派 SSE 事件，避免与初始 fetch 竞态
async function renderSidebar() {
  const view = render(<ChatSidebar session={session} />);
  await screen.findByText(/已绑定当前项目/);
  rerenderSidebarRef.current = view.rerender;
  return lastES();
}

// renderSidebar 暴露的 rerender（切会话用例：同实例换 session prop）
const rerenderSidebarRef: { current: ((ui: React.ReactElement) => void) | null } = { current: null };
function rerenderSidebar(next: ChatSession) {
  rerenderSidebarRef.current?.(<ChatSidebar session={next} />);
}

beforeEach(() => {
  vi.clearAllMocks();
  cleanup();
  MockEventSource.instances = [];
  storeState.chatOpen = true;
  vi.stubGlobal("EventSource", MockEventSource);
  vi.stubGlobal("fetch", makeFetch());
  const store: Record<string, string> = {};
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store[k] ?? null,
    setItem: (k: string, v: string) => { store[k] = String(v); },
    removeItem: (k: string) => { delete store[k]; },
    clear: () => { for (const k of Object.keys(store)) delete store[k]; },
  });
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => vi.unstubAllGlobals());

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

describe("ChatSidebar 发送与中止", () => {
  it("发送消息：乐观插入用户气泡并 POST 正确 URL/body", async () => {
    const spy = makeFetch();
    vi.stubGlobal("fetch", spy);
    render(<ChatSidebar session={session} />);
    fireEvent.change(screen.getByPlaceholderText("描述修改需求…"), { target: { value: "  加一面墙  " } });
    fireEvent.click(screen.getByText("发送"));
    expect(await screen.findByText("加一面墙")).toBeTruthy();
    const post = (spy.mock.calls as unknown as [string, RequestInit | undefined][])
      .find(([u, i]) => u.endsWith("/messages") && i?.method === "POST");
    expect(post).toBeTruthy();
    expect(post![0]).toBe("/api/v1/chat/sessions/c1/messages");
    expect(JSON.parse(post![1]!.body as string)).toEqual({ text: "加一面墙" });
    // busy：发送按钮切换为停止按钮
    expect(await screen.findByText("⏹ 停止")).toBeTruthy();
  });

  it("发送失败时显示错误系统消息并恢复可发送状态", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      const u = String(url);
      if (u.endsWith("/messages") && init?.method === "POST")
        return new Response(JSON.stringify({ code: 50200, message: "opencode 不可达", data: null }), { status: 502 });
      if (u.endsWith("/messages")) return new Response(envelope([]), { status: 200 });
      return new Response(envelope(null), { status: 200 });
    }));
    render(<ChatSidebar session={session} />);
    fireEvent.change(screen.getByPlaceholderText("描述修改需求…"), { target: { value: "hi" } });
    fireEvent.click(screen.getByText("发送"));
    expect(await screen.findByText("发送失败：opencode 不可达")).toBeTruthy();
    expect(await screen.findByText("发送")).toBeTruthy();
  });

  it("busy 时点击停止调用 abort 端点，session.idle 后恢复发送按钮", async () => {
    const spy = makeFetch();
    vi.stubGlobal("fetch", spy);
    const es = await renderSidebar();
    emit(es, "session.status", { status: { type: "busy" } });
    fireEvent.click(await screen.findByText("⏹ 停止"));
    await screen.findByText("⏹ 停止"); // busy 未清前仍是停止按钮
    const abort = (spy.mock.calls as unknown as [string, RequestInit | undefined][])
      .find(([u, i]) => u.endsWith("/abort") && i?.method === "POST");
    expect(abort).toBeTruthy();
    expect(abort![0]).toBe("/api/v1/chat/sessions/c1/abort");
    emit(lastES(), "session.idle", {});
    expect(await screen.findByText("发送")).toBeTruthy();
  });
});

describe("ChatSidebar SSE 流式渲染", () => {
  it("text part 建行后多条 delta 按序累加渲染", async () => {
    const es = await renderSidebar();
    emit(es, "message.updated", { info: { id: "m1", role: "assistant" } });
    emit(es, "message.part.updated", { part: { id: "p1", type: "text", messageID: "m1", text: "" } });
    emit(es, "message.part.delta", { messageID: "m1", partID: "p1", field: "text", delta: "你好，" });
    emit(es, "message.part.delta", { messageID: "m1", partID: "p1", field: "text", delta: "世界" });
    emit(es, "message.part.delta", { messageID: "m1", partID: "p1", field: "text", delta: "！" });
    expect(await screen.findByText("你好，世界！")).toBeTruthy();
  });

  it("delta 先于 part.updated 到达（乱序）时被丢弃，后续 delta 正常累加", async () => {
    const es = await renderSidebar();
    emit(es, "message.updated", { info: { id: "m1", role: "assistant" } });
    emit(es, "message.part.delta", { messageID: "m1", partID: "p1", field: "text", delta: "前半" });
    emit(es, "message.part.updated", { part: { id: "p1", type: "text", messageID: "m1", text: "" } });
    emit(es, "message.part.delta", { messageID: "m1", partID: "p1", field: "text", delta: "后半" });
    expect(await screen.findByText("后半")).toBeTruthy();
    expect(screen.queryByText(/前半/)).toBeNull();
  });

  it("reasoning part 渲染为可折叠思考链，点击展开可见增量文本", async () => {
    const es = await renderSidebar();
    emit(es, "message.part.updated", { part: { id: "r1", type: "reasoning", messageID: "m1", text: "" } });
    emit(es, "message.part.delta", { messageID: "m1", partID: "r1", field: "text", delta: "推演中…" });
    fireEvent.click(await screen.findByText("💭 思考过程"));
    expect(await screen.findByText("推演中…")).toBeTruthy();
  });

  it("tool part 渲染工具卡片并随事件更新状态，点击展开 output", async () => {
    const es = await renderSidebar();
    emit(es, "message.part.updated", {
      part: { id: "t1", type: "tool", tool: "bash", messageID: "m1", state: { status: "running", title: "运行测试" } },
    });
    expect(await screen.findByText("运行测试")).toBeTruthy();
    expect(screen.getByText("⟳")).toBeTruthy();
    emit(es, "message.part.updated", {
      part: {
        id: "t1", type: "tool", tool: "bash", messageID: "m1",
        state: { status: "completed", title: "运行测试", input: { cmd: "npm test" }, output: "114 passed" },
      },
    });
    expect(await screen.findByText("✓")).toBeTruthy();
    fireEvent.click(screen.getByText("运行测试"));
    expect(await screen.findByText("114 passed")).toBeTruthy();
    expect(await screen.findByText(/npm test/)).toBeTruthy();
  });

  it("message.part.removed 移除对应消息行", async () => {
    const es = await renderSidebar();
    emit(es, "message.part.updated", { part: { id: "p1", type: "text", messageID: "m1", text: "进行中的话" } });
    expect(await screen.findByText("进行中的话")).toBeTruthy();
    emit(es, "message.part.removed", { part: { id: "p1" } });
    expect(screen.queryByText("进行中的话")).toBeNull();
  });

  it("session.error 对象错误安全提取为红色系统消息", async () => {
    const es = await renderSidebar();
    emit(es, "session.error", { error: { message: "model boom" } });
    expect(await screen.findByText("❌ model boom")).toBeTruthy();
  });

  it("viewer.committed 提示落盘成功并标记待刷新", async () => {
    const es = await renderSidebar();
    emit(es, "viewer.committed", { version: "v3" });
    expect(await screen.findByText("✅ 修改已落盘（版本 v3），模型转换中…")).toBeTruthy();
    expect(storeState.flagPendingModelReload).toHaveBeenCalled();
  });

  it("viewer.notify_failed 提示落盘失败原因", async () => {
    const es = await renderSidebar();
    emit(es, "viewer.notify_failed", { step: "commit", reason: "磁盘满" });
    expect(await screen.findByText("⚠️ 落盘失败（commit）：磁盘满")).toBeTruthy();
  });

  it("session.status busy 显示打字指示，idle 后消失", async () => {
    const es = await renderSidebar();
    emit(es, "session.status", { status: { type: "busy" } });
    expect(await screen.findByText("AI 正在工作…")).toBeTruthy();
    emit(lastES(), "session.idle", {});
    expect(screen.queryByText("AI 正在工作…")).toBeNull();
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

describe("ChatSidebar EventSource 容错（W-0007）", () => {
  it("非法 JSON 帧被跳过，流不中断，后续正常帧仍渲染", async () => {
    const es = await renderSidebar();
    emit(es, "message.part.updated", "not-json{{{");
    emit(es, "message.updated", { info: { id: "m1", role: "assistant" } });
    emit(es, "message.part.updated", { part: { id: "p1", type: "text", messageID: "m1", text: "正常帧" } });
    expect(await screen.findByText("正常帧")).toBeTruthy();
  });

  it("error 事件显示连接中断提示，open 后恢复，重连后事件续传", async () => {
    const es = await renderSidebar();
    emit(es, "error", {});
    expect(await screen.findByText(/连接中断/)).toBeTruthy();
    emit(es, "open", {});
    expect(screen.queryByText(/连接中断/)).toBeNull();
    // 重连（EventSource 原生带 Last-Event-ID，服务端补发）后事件正常续传
    emit(es, "message.updated", { info: { id: "m1", role: "assistant" } });
    emit(es, "message.part.updated", { part: { id: "p1", type: "text", messageID: "m1", text: "重连后的回复" } });
    expect(await screen.findByText("重连后的回复")).toBeTruthy();
  });
});

describe("ChatSidebar 子 agent 边栏（subagent 面板）", () => {
  it("subagent.status started 后子 part 事件进入右侧边栏分组，不进主消息流", async () => {
    const es = await renderSidebar();
    emit(es, "session.status", { status: { type: "busy" } });
    emit(es, "message.updated", { info: { id: "m1", role: "assistant" } });
    // 主会话普通帧
    emit(es, "message.part.updated", { part: { id: "p-main", type: "text", messageID: "m1", text: "" } });
    emit(es, "message.part.delta", { messageID: "m1", partID: "p-main", field: "text", delta: "主回复" });
    // 子 agent 启动
    emit(es, "subagent.status", {
      subagentId: "sa_1_1", parentSessionId: "s_1", persona: "ifc-agent", status: "started", task: "建一堵墙",
    });
    // 子 text part（带 subagentId 字段）
    emit(es, "message.part.updated", {
      part: { id: "sp_sa_1_1_1_1_text", type: "text", messageID: "sub_sa_1_1_msg_1_1", text: "" },
      subagentId: "sa_1_1",
    });
    emit(es, "message.part.delta", {
      sessionID: "s_1", messageID: "sub_sa_1_1_msg_1_1", partID: "sp_sa_1_1_1_1_text", field: "text", delta: "子的文本",
      subagentId: "sa_1_1",
    });
    // 子 tool 卡片
    emit(es, "message.part.updated", {
      part: {
        id: "sp_sa_1_1_1_1_tool_cc-1", type: "tool", tool: "get_script",
        messageID: "sub_sa_1_1_msg_1_1",
        state: { status: "running", title: "get_script", input: "{}" },
      },
      subagentId: "sa_1_1",
    });

    // 边栏出现：分组标题（persona 徽章 + 状态）
    expect(await screen.findByText(/ifc-agent/)).toBeTruthy();
    // 子文本进边栏
    expect(await screen.findByText("子的文本")).toBeTruthy();
    // 子工具卡进边栏
    expect(await screen.findByText("get_script")).toBeTruthy();
    // 主消息流不受污染：子的文本不在主流出现（主流只有 主回复 + 欢迎语）
    expect(screen.getAllByText("子的文本")).toHaveLength(1);
    // 主流照常渲染
    expect(screen.getByText("主回复")).toBeTruthy();
  });

  it("subagent.status finished 后边栏组状态更新为完成", async () => {
    const es = await renderSidebar();
    emit(es, "subagent.status", {
      subagentId: "sa_1_1", parentSessionId: "s_1", persona: "cad-agent", status: "started", task: "画平面",
    });
    emit(es, "message.part.updated", {
      part: { id: "sp_x", type: "text", messageID: "sub_x", text: "" },
      subagentId: "sa_1_1",
    });
    emit(es, "message.part.delta", {
      messageID: "sub_x", partID: "sp_x", field: "text", delta: "子的输出", subagentId: "sa_1_1",
    });
    expect(await screen.findByText("子的输出")).toBeTruthy();
    emit(es, "subagent.status", {
      subagentId: "sa_1_1", parentSessionId: "s_1", persona: "cad-agent", status: "finished", task: "画平面",
    });
    // 完成后组头显示完成标记（✓）
    expect(await screen.findByText("✓")).toBeTruthy();
  });

  it("两个 subagentId 分组独立渲染，互不混淆", async () => {
    const es = await renderSidebar();
    emit(es, "subagent.status", {
      subagentId: "sa_1_1", parentSessionId: "s_1", persona: "ifc-agent", status: "started", task: "a",
    });
    emit(es, "subagent.status", {
      subagentId: "sa_1_2", parentSessionId: "s_1", persona: "cad-agent", status: "started", task: "b",
    });
    emit(es, "message.part.updated", {
      part: { id: "sp1", type: "text", messageID: "sub1", text: "IFC 子输出" },
      subagentId: "sa_1_1",
    });
    emit(es, "message.part.updated", {
      part: { id: "sp2", type: "text", messageID: "sub2", text: "CAD 子输出" },
      subagentId: "sa_1_2",
    });
    expect(await screen.findByText("IFC 子输出")).toBeTruthy();
    expect(await screen.findByText("CAD 子输出")).toBeTruthy();
    // 两个 persona 徽章各出现一次
    expect(screen.getAllByText(/ifc-agent/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/cad-agent/).length).toBeGreaterThanOrEqual(1);
  });

  it("主会话同名事件（无 subagentId 字段）不进边栏——旧形状不变", async () => {
    const es = await renderSidebar();
    emit(es, "message.updated", { info: { id: "m1", role: "assistant" } });
    emit(es, "message.part.updated", { part: { id: "p1", type: "text", messageID: "m1", text: "纯主回复" } });
    expect(await screen.findByText("纯主回复")).toBeTruthy();
    // 边栏不应被创建（无 subagent 组头）
    expect(screen.queryByText(/子 Agent/)).toBeNull();
  });

  it("切会话（session prop 变化）后子 agent 边栏清空，不残留上一会话分组", async () => {
    const es = await renderSidebar();
    emit(es, "subagent.status", {
      subagentId: "sa_1_1", parentSessionId: "s_1", persona: "ifc-agent", status: "started", task: "旧会话任务",
    });
    emit(es, "message.part.updated", {
      part: { id: "sp_old", type: "text", messageID: "sub_old", text: "旧会话子输出" },
      subagentId: "sa_1_1",
    });
    expect(await screen.findByText("旧会话子输出")).toBeTruthy();

    // 同组件实例换 session prop（不卸载重挂，模拟同页切模型场景）
    const session2: ChatSession = { ...session, chatSessionId: "c2", opencodeSessionId: "oc2" };
    rerenderSidebar(session2);
    // 新会话的欢迎语出现（历史已回填）
    await screen.findByText(/已绑定当前项目/);
    // 旧会话的子 agent 分组已清空
    expect(screen.queryByText(/ifc-agent/)).toBeNull();
    expect(screen.queryByText("旧会话子输出")).toBeNull();
  });
});
