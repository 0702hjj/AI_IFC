// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// ChatSidebar 消息流共享类型（主消息流 + 子 agent 边栏分组）。

export type ToolStatus = "running" | "completed" | "error";
export interface ToolInfo {
  name: string;
  title?: string;
  status: ToolStatus;
  input?: string;
  output?: string;
  error?: string;
}
export interface ChatMsg {
  id: string;
  role: "user" | "assistant" | "system";
  kind: "text" | "tool" | "reasoning" | "system";
  text?: string;
  tool?: ToolInfo;
}

// 子 agent 边栏分组：一个 subagentId 一组（persona 徽章 + 运行状态 + part 流）。
export interface SubagentPart {
  id: string;
  kind: "text" | "tool";
  text?: string;
  tool?: ToolInfo;
}
export interface SubagentGroup {
  id: string;
  persona: string;
  task?: string;
  status: "running" | "finished";
  parts: SubagentPart[];
}

export const WELCOME = "已绑定当前项目，告诉 AI 要修改什么、或从零建造什么吧。";
