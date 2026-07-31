// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

import type { ModelInfo, Issue, NewIssue, OverridesMap, EntityFields, ChangeEntry, EditVersionsResponse, DiffResponse } from "./types";

interface Envelope<T> { code: number; message: string; data: T }

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, init);
  const env: Envelope<T> = await resp.json();
  if (!resp.ok || env.code !== 0) throw new Error(env.message || `HTTP ${resp.status}`);
  return env.data;
}

export function listModels() { return request<ModelInfo[]>("/api/models"); }
export function fetchModel(id: string) { return request<ModelInfo>(`/api/models/${id}`); }
export function uploadModel(file: File) {
  const fd = new FormData();
  fd.append("file", file);
  return request<ModelInfo>("/api/models", { method: "POST", body: fd });
}
export function retryModel(id: string) { return request<ModelInfo>(`/api/models/${id}/retry`, { method: "POST" }); }
export function deleteModel(id: string) { return request<null>(`/api/models/${id}`, { method: "DELETE" }); }
export const downloadUrl = (id: string) => `/api/models/${id}/download`;
export const modelAssetUrl = (id: string, file: "model.xkt" | "metadata.json") => `/models/${id}/${file}`;

export function listIssues(modelId: string) {
  return request<Issue[]>(`/api/models/${modelId}/issues`);
}
export function createIssue(modelId: string, issue: NewIssue, screenshot: Blob | null) {
  const fd = new FormData();
  fd.append("issue", JSON.stringify(issue));
  if (screenshot) fd.append("screenshot", screenshot, "screenshot.png");
  return request<Issue>(`/api/models/${modelId}/issues`, { method: "POST", body: fd });
}
export function updateIssue(
  modelId: string,
  issueId: string,
  patch: Partial<Pick<Issue, "title" | "comment" | "status">>
) {
  return request<Issue>(`/api/models/${modelId}/issues/${issueId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}
export function deleteIssue(modelId: string, issueId: string) {
  return request<null>(`/api/models/${modelId}/issues/${issueId}`, { method: "DELETE" });
}
export const issueAssetUrl = (modelId: string, issue: Issue) => `/models/${modelId}/${issue.screenshot}`;

export function fetchOverrides(modelId: string) {
  return request<OverridesMap>(`/api/models/${modelId}/overrides`);
}
export function saveEntityProperties(
  modelId: string,
  entityId: string,
  fields: EntityFields,
  entityName: string
) {
  return request<EntityFields>(`/api/models/${modelId}/entities/${entityId}/properties`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fields, entityName }),
  });
}
export function fetchChanges(modelId: string) {
  return request<ChangeEntry[]>(`/api/models/${modelId}/changes`);
}

export function fetchEditVersions(modelId: string) {
  return request<EditVersionsResponse>(`/api/models/${modelId}/edit/versions`);
}
export function postEditDiff(modelId: string, base: string, target: string) {
  return request<DiffResponse>(`/api/models/${modelId}/edit/diff`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ base, target }),
  });
}
