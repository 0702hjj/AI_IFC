// SPDX-License-Identifier: Apache-2.0
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
  projectId?: string;
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
export function createChatSessionByProject(title: string, projectId: string) {
  return request<ChatSession>("/api/v1/chat/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, projectId }),
  });
}
export function listChatSessions() { return request<ChatSession[]>("/api/v1/chat/sessions"); }

/** 项目创建响应（A1：id=首模型兼容 ModelInfo + projectId 新字段）。 */
export interface CreateProjectResult {
  id: string;
  projectId?: string;
  title: string;
  kind?: string;
  status?: string;
}
export function createChatProject(title: string, kind: string = "ifc") {
  return request<CreateProjectResult>("/api/v1/chat/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, kind }),
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
export function answerChatQuestion(cid: string, interruptId: string, answer: string) {
  return request<{ accepted: boolean }>(`/api/v1/chat/sessions/${cid}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ interruptId, answer }),
  });
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
// web-ifc 查看器用：拉取原始 IFC 字节（非 envelope，鉴权头经 fetch headers）
export async function downloadIfcBytes(id: string): Promise<Uint8Array> {
  const headers = new Headers();
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const resp = await fetch(downloadUrl(id), { headers });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return new Uint8Array(await resp.arrayBuffer());
}
export const modelAssetUrl = (id: string, file: "model.xkt" | "metadata.json") => `/v1/models/${id}/${file}`;
// dxf 模型的实体级渲染载荷（Go 直挂只读，非 envelope）
export const renderJsonUrl = (id: string) => `/v1/models/${id}/render.json`;

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
// dxf 侧同构端点：XDATA key → 脚本调用点（cad edit-service 按 key 定位，query 透传）
export function locateScriptByKey(modelId: string, key: string) {
  return request<ScriptLocateResult>(
    `/api/v1/models/${modelId}/script/locate?key=${encodeURIComponent(key)}`
  );
}
