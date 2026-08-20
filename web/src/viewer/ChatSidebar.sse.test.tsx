// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// ChatSidebar SSE 流式渲染（含 W-0007 EventSource 容错）场景。
import { describe, it, expect } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import {
  emit,
  lastES,
  renderSidebar,
  setupChatSidebarSuite,
  storeState,
} from "./chatSidebarTestKit";

setupChatSidebarSuite();

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

  it("viewer.staged 事件写入 stagedPreview（modelId/kind 透传）", async () => {
    const es = await renderSidebar();
    emit(es, "viewer.staged", { modelId: "m_0123456789abcdef", kind: "dxf" });
    expect(storeState.flagStagedPreview).toHaveBeenCalledWith({
      modelId: "m_0123456789abcdef",
      kind: "dxf",
    });
  });

  it("viewer.staged 非法载荷（缺 modelId / 未知 kind / 非 JSON）被忽略", async () => {
    const es = await renderSidebar();
    emit(es, "viewer.staged", { kind: "dxf" });
    emit(es, "viewer.staged", { modelId: "m_1", kind: "pdf" });
    emit(es, "viewer.staged", "not-json{{{");
    expect(storeState.flagStagedPreview).not.toHaveBeenCalled();
  });

  it("session.status busy 显示打字指示，idle 后消失", async () => {
    const es = await renderSidebar();
    emit(es, "session.status", { status: { type: "busy" } });
    expect(await screen.findByText("AI 正在工作…")).toBeTruthy();
    emit(lastES(), "session.idle", {});
    expect(screen.queryByText("AI 正在工作…")).toBeNull();
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
