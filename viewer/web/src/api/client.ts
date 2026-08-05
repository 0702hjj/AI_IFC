// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

import type { ModelInfo, Issue, NewIssue, OverridesMap, EntityFields, ChangeEntry, EditVersionsResponse, DiffResponse, DesignState, DesignStageResult, DesignSaveResult, DesignVersionsResponse, DesignDiffResponse, RegenerateResult } from "./types";

interface Envelope<T> { code: number; message: string; data: T }

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, init);
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
export const chatEventsUrl = (cid: string) => `/api/v1/chat/sessions/${cid}/events`;
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
export function saveEntityProperties(
  modelId: string,
  entityId: string,
  fields: EntityFields,
  entityName: string
) {
  return request<EntityFields>(`/api/v1/models/${modelId}/entities/${entityId}/properties`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fields, entityName }),
  });
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

// --- design JSON 编辑（WPS 式暂存 + 大版本 + 语义 diff） ---

export function fetchDesign(modelId: string) {
  return request<DesignState>(`/api/v1/models/${modelId}/design`);
}
export function stageDesign(modelId: string, design: Record<string, unknown>, note = "") {
  return request<DesignStageResult>(`/api/v1/models/${modelId}/design`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ design, note }),
  });
}
export function designUndo(modelId: string) {
  return request<{ modelId: string; design: Record<string, unknown>; canRedo: boolean }>(
    `/api/v1/models/${modelId}/design/undo`, { method: "POST" });
}
export function designRedo(modelId: string) {
  return request<{ modelId: string; design: Record<string, unknown>; canUndo: boolean }>(
    `/api/v1/models/${modelId}/design/redo`, { method: "POST" });
}
export function discardDesign(modelId: string) {
  return request<{ modelId: string; discarded: number; design: Record<string, unknown> }>(
    `/api/v1/models/${modelId}/design/discard`, { method: "POST" });
}
export function regenerateDesign(modelId: string) {
  return request<RegenerateResult>(`/api/v1/models/${modelId}/design/regenerate`, { method: "POST" });
}
export function saveDesign(modelId: string, note = "") {
  return request<DesignSaveResult>(`/api/v1/models/${modelId}/design/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note }),
  });
}
export function fetchDesignVersions(modelId: string) {
  return request<DesignVersionsResponse>(`/api/v1/models/${modelId}/designs`);
}
export function postDesignDiff(modelId: string, base: string, target: string) {
  return request<DesignDiffResponse>(`/api/v1/models/${modelId}/design/diff`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ base, target }),
  });
}
export function rollbackDesign(modelId: string, version: string) {
  return request<{ modelId: string; version: string; design: Record<string, unknown> }>(
    `/api/v1/models/${modelId}/design/rollback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ version }),
    });
}
