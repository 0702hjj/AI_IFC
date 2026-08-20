// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// ChatSidebar 发送与中止（乐观插入 / 失败恢复 / abort）场景。
// import 顺序同 history 测试：kit 先于 ./ChatSidebar（store mock 先生效）。
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import {
  emit,
  envelope,
  lastES,
  makeFetch,
  renderSidebar,
  session,
  setupChatSidebarSuite,
} from "./chatSidebarTestKit";
import { ChatSidebar } from "./ChatSidebar";

setupChatSidebarSuite();

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
