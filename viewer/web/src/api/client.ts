// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

import type { ModelInfo, Issue, NewIssue, OverridesMap, ChangeEntry, EditVersionsResponse, DiffResponse, ScriptState, ScriptStageResult, ScriptSaveResult, ScriptParamsResponse, ScriptVersionsResponse, ScriptDiffResponse, ScriptRunResult, ScriptLocateResult } from "./types";
import { getToken, notifyUnauthorized, waitForToken } from "./auth";

interface Envelope<T> { code: number; message: string; data: T }

async function request<T>(url: string, init?: RequestInit, retried = false): Promise<T> {
  const headers = new Headers(init?.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const resp = await fetch(url, { ...init, headers });
  if (resp.status === 401) {
    notifyUnauthorized();
    if (!retried) {
      await waitForToken();
      return request<T>(url, init, true);
    }
  }
  const env: Envelope<T> = await resp.json();
  if (!resp.ok || env.code !== 0) throw new Error(env.message || `HTTP ${resp.status}`);
  return env.data;
}

export function listModels() { return request<ModelInfo[]>("/api/v1/models"); }
export function fetchModel(id: string) { return request<ModelInfo>(`/api/v1/models/${id}`); }

// --- chat 模块（demo） ---
export interface ChatSession {
  chatSessionId: string;
  opencodeSessionId: string;
  modelId: string;
  title: string;
  createdAt: string;
}
export function createChatSession(title: string, modelId: string | null) {
  return request<ChatSession>("/api/v1/chat/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, modelId: modelId ?? "" }),
  });
}
export function listChatSessions() { return request<ChatSession[]>("/api/v1/chat/sessions"); }
export function createChatProject(title: string) {
  return request<ModelInfo>("/api/v1/chat/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
}
export function postChatMessage(cid: string, text: string) {
  return request<{ accepted: boolean }>(`/api/v1/chat/sessions/${cid}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}
export interface ChatPart {
  id?: string;
  type: string; // text | reasoning | tool
  text?: string;
  tool?: string;
  state?: { status?: string; title?: string; input?: unknown; output?: string; error?: string };
}
export interface ChatHistoryMsg {
  info: { id: string; role: string };
  parts: ChatPart[];
}
export function fetchChatMessages(cid: string) {
  return request<ChatHistoryMsg[]>(`/api/v1/chat/sessions/${cid}/messages`);
}
export function abortChatSession(cid: string) {
  return request<{ aborted: boolean }>(`/api/v1/chat/sessions/${cid}/abort`, { method: "POST" });
}
// EventSource 不支持自定义头：token 经 query 传递（server 侧仅 events 路径放行 ?token= 回退）
export const chatEventsUrl = (cid: string) => {
  const base = `/api/v1/chat/sessions/${cid}/events`;
  const token = getToken();
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
};
export function uploadModel(file: File) {
  const fd = new FormData();
  fd.append("file", file);
  return request<ModelInfo>("/api/v1/models", { method: "POST", body: fd });
}
export function retryModel(id: string) { return request<ModelInfo>(`/api/v1/models/${id}/retry`, { method: "POST" }); }
export function deleteModel(id: string) { return request<null>(`/api/v1/models/${id}`, { method: "DELETE" }); }
export const downloadUrl = (id: string) => `/api/v1/models/${id}/download`;
export const modelAssetUrl = (id: string, file: "model.xkt" | "metadata.json") => `/v1/models/${id}/${file}`;

export function listIssues(modelId: string) {
  return request<Issue[]>(`/api/v1/models/${modelId}/issues`);
}
export function createIssue(modelId: string, issue: NewIssue, screenshot: Blob | null) {
  const fd = new FormData();
  fd.append("issue", JSON.stringify(issue));
  if (screenshot) fd.append("screenshot", screenshot, "screenshot.png");
  return request<Issue>(`/api/v1/models/${modelId}/issues`, { method: "POST", body: fd });
}
export function updateIssue(
  modelId: string,
  issueId: string,
  patch: Partial<Pick<Issue, "title" | "comment" | "status">>
) {
  return request<Issue>(`/api/v1/models/${modelId}/issues/${issueId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}
export function deleteIssue(modelId: string, issueId: string) {
  return request<null>(`/api/v1/models/${modelId}/issues/${issueId}`, { method: "DELETE" });
}
export const issueAssetUrl = (modelId: string, issue: Issue) => `/v1/models/${modelId}/${issue.screenshot}`;

export function fetchOverrides(modelId: string) {
  return request<OverridesMap>(`/api/v1/models/${modelId}/overrides`);
}
export function fetchChanges(modelId: string) {
  return request<ChangeEntry[]>(`/api/v1/models/${modelId}/changes`);
}

export function fetchEditVersions(modelId: string) {
  return request<EditVersionsResponse>(`/api/v1/models/${modelId}/edit/versions`);
}
export function postEditDiff(modelId: string, base: string, target: string) {
  return request<DiffResponse>(`/api/v1/models/${modelId}/edit/diff`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ base, target }),
  });
}

// --- script-as-source 编辑（WPS 式暂存 + 大版本 + 脚本 diff，W-0013） ---

export function fetchScript(modelId: string) {
  return request<ScriptState>(`/api/v1/models/${modelId}/script`);
}
export function fetchScriptParams(modelId: string) {
  return request<ScriptParamsResponse>(`/api/v1/models/${modelId}/script/params`);
}
export function stageScript(modelId: string, script: string, note = "") {
  return request<ScriptStageResult>(`/api/v1/models/${modelId}/script`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ script, note }),
  });
}
export function stageScriptParams(modelId: string, params: Record<string, unknown>, note = "") {
  return request<ScriptStageResult>(`/api/v1/models/${modelId}/script`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ params, note }),
  });
}
export function scriptUndo(modelId: string) {
  return request<{ modelId: string; script: string; canRedo: boolean }>(
    `/api/v1/models/${modelId}/script/undo`, { method: "POST" });
}
export function scriptRedo(modelId: string) {
  return request<{ modelId: string; script: string; canUndo: boolean }>(
    `/api/v1/models/${modelId}/script/redo`, { method: "POST" });
}
export function discardScript(modelId: string) {
  return request<{ modelId: string; discarded: number; script: string }>(
    `/api/v1/models/${modelId}/script/discard`, { method: "POST" });
}
export function runScript(modelId: string) {
  return request<ScriptRunResult>(`/api/v1/models/${modelId}/script/run`, { method: "POST" });
}
export function saveScript(modelId: string, note = "") {
  return request<ScriptSaveResult>(`/api/v1/models/${modelId}/script/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note }),
  });
}
export function rollbackScript(modelId: string, version: string) {
  return request<{ modelId: string; version: string; script: string }>(
    `/api/v1/models/${modelId}/script/rollback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ version }),
    });
}
export function fetchScriptVersions(modelId: string) {
  return request<ScriptVersionsResponse>(`/api/v1/models/${modelId}/scripts`);
}
export function postScriptDiff(modelId: string, base: string, target: string) {
  return request<ScriptDiffResponse>(`/api/v1/models/${modelId}/script/diff`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ base, target }),
  });
}
export function fetchStagingDiff(modelId: string, from?: number, to?: number) {
  const qs = from != null && to != null ? `?from=${from}&to=${to}` : "";
  return request<ScriptDiffResponse>(`/api/v1/models/${modelId}/script/staging/diff${qs}`);
}
export function locateScript(modelId: string, guid: string) {
  return request<ScriptLocateResult>(
    `/api/v1/models/${modelId}/script/locate?guid=${encodeURIComponent(guid)}`
  );
}
