// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// ChatSidebar SSE 事件的纯函数解析/格式化工具（无 React 依赖，便于单测与复用）。
import type { ToolStatus } from "./chatStreamTypes";

export function mapStatus(s?: string): ToolStatus {
  if (s === "completed") return "completed";
  if (s === "error" || s === "failed") return "error";
  return "running";
}

// 把任意 input（object/string）格式化为可展示文本。
export function fmtInput(input: unknown): string | undefined {
  if (input == null || input === "") return undefined;
  if (typeof input === "string") return input;
  try {
    return JSON.stringify(input, null, 2);
  } catch {
    return String(input);
  }
}

// 安全提取 session.error 的错误文本（opencode 的 error 字段可能是对象/字符串/嵌套，统一兜底防 [object Object]）。
export function extractErrText(d: any): string {
  const err = d?.error ?? d?.properties?.error;
  if (typeof err === "string") return err;
  if (err && typeof err === "object") return err.message || err.error || err.name || JSON.stringify(err).slice(0, 300);
  if (typeof d?.message === "string") return d.message;
  return JSON.stringify(d).slice(0, 300);
}

// 安全解析 SSE 帧：非法 JSON 跳过（返回 undefined），不中断事件流。
export function parseEventData(e: Event): any | undefined {
  try {
    return JSON.parse((e as MessageEvent).data);
  } catch {
    return undefined;
  }
}
