// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// ChatSidebar 子 agent 边栏（subagent 面板）场景。
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import type { ChatSession } from "@/api/client";
import {
  emit,
  renderSidebar,
  rerenderSidebar,
  session,
  setupChatSidebarSuite,
} from "./chatSidebarTestKit";

setupChatSidebarSuite();

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
