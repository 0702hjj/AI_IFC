// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// ChatSidebar 测试共享 kit（W-0049 测试按场景域拆分后抽出）：
// MockEventSource / store mock / fetch mock / 渲染 helper / 全局 beforeEach。
// 各 *.test.tsx 顶部 import 本模块并调用 setupChatSidebarSuite()。
import { beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, act } from "@testing-library/react";
import type { ChatSession } from "@/api/client";
import { ChatSidebar } from "./ChatSidebar";

// --- 可手动派发事件的 MockEventSource（替代浏览器 SSE 连接） ---
export class MockEventSource {
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

export function emit(es: MockEventSource, type: string, data: unknown) {
  act(() => es.dispatch(type, data));
}

// --- store mock：chatOpen 常开，setChatOpen/flagPendingModelReload 可断言 ---
// 注：不能用 vi.hoisted（vitest 不允许导出 hoisted 变量）；factory 经嵌套箭头
// 惰性读取 storeState，mock 注册早于本模块体执行也无 TDZ 问题。
export const storeState = {
  chatOpen: true,
  setChatOpen: vi.fn(),
  flagPendingModelReload: vi.fn(),
  flagStagedPreview: vi.fn(),
};
vi.mock("@/viewer/store", () => ({
  useViewerStore: (sel: any) => sel(storeState),
}));

export const session: ChatSession = {
  chatSessionId: "c1",
  opencodeSessionId: "oc1",
  modelId: "m_1",
  title: "t",
  createdAt: "2026-08-06T00:00:00Z",
};

export const envelope = (data: unknown) => JSON.stringify({ code: 0, message: "ok", data });

// 走真实 client.ts request() 解包的 fetch mock：按 URL/方法路由 chat REST 端点
export function makeFetch(history: unknown = []) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    const u = String(url);
    if (u.endsWith("/messages") && init?.method === "POST")
      return new Response(envelope({ accepted: true }), { status: 200 });
    if (u.endsWith("/messages")) return new Response(envelope(history), { status: 200 });
    if (u.endsWith("/abort")) return new Response(envelope({ aborted: true }), { status: 200 });
    return new Response(JSON.stringify({ code: 40400, message: "not found", data: null }), { status: 404 });
  });
}

export function lastES(): MockEventSource {
  return MockEventSource.instances[MockEventSource.instances.length - 1];
}

// 渲染并等历史回填完成（空历史 → 欢迎语），再开始派 SSE 事件，避免与初始 fetch 竞态
export async function renderSidebar() {
  const view = render(<ChatSidebar session={session} />);
  await screen.findByText(/已绑定当前项目/);
  rerenderSidebarRef.current = view.rerender;
  return lastES();
}

// renderSidebar 暴露的 rerender（切会话用例：同实例换 session prop）
const rerenderSidebarRef: { current: ((ui: React.ReactElement) => void) | null } = { current: null };
export function rerenderSidebar(next: ChatSession) {
  rerenderSidebarRef.current?.(<ChatSidebar session={next} />);
}

// 每个 ChatSidebar 测试文件的公共装置：清 mock/实例、桩 EventSource/fetch/localStorage。
export function setupChatSidebarSuite() {
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
}
