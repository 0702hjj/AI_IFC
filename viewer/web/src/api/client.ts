import type { ModelInfo } from "./types";

interface Envelope<T> { code: number; message: string; data: T }

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, init);
  const env: Envelope<T> = await resp.json();
  if (!resp.ok || env.code !== 0) throw new Error(env.message || `HTTP ${resp.status}`);
  return env.data;
}

export function listModels() { return request<ModelInfo[]>("/api/models"); }
export function uploadModel(file: File) {
  const fd = new FormData();
  fd.append("file", file);
  return request<ModelInfo>("/api/models", { method: "POST", body: fd });
}
export function retryModel(id: string) { return request<ModelInfo>(`/api/models/${id}/retry`, { method: "POST" }); }
export function deleteModel(id: string) { return request<null>(`/api/models/${id}`, { method: "DELETE" }); }
export const downloadUrl = (id: string) => `/api/models/${id}/download`;
export const modelAssetUrl = (id: string, file: "model.xkt" | "metadata.json") => `/models/${id}/${file}`;
