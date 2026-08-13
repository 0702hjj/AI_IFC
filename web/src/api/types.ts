// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

export interface ModelInfo {
  id: string;
  name: string;
  size: number;
  status: "converting" | "ready" | "failed";
  createdAt: string;
  error: string;
}

export interface IssueCamera {
  eye: [number, number, number];
  look: [number, number, number];
  up: [number, number, number];
}

export type IssueStatus = "open" | "checking" | "resolved";

export interface Issue {
  id: string;
  entityId: string;
  entityName: string;
  entityType: string;
  title: string;
  comment: string;
  status: IssueStatus;
  camera: IssueCamera;
  screenshot: string;
  createdAt: string;
  updatedAt: string;
}

export interface NewIssue {
  entityId: string;
  entityName: string;
  entityType: string;
  title: string;
  comment: string;
  camera: IssueCamera;
}

export type EntityFields = Record<string, string>;
export type OverridesMap = Record<string, EntityFields>;

export interface ChangeEntry {
  id: string;
  entityId: string;
  entityName: string;
  field: string;
  oldValue: string;
  newValue: string;
  author: string;
  provenance: { source: string };
  operation?: "update" | "migrate";
  diff?: unknown;
  createdAt: string;
}

export interface EditVersion {
  version: string;
  createdAt: string;
}

export interface EditVersionsResponse {
  versions: EditVersion[];
  current: string | null;
}

export interface DiffFieldChange {
  field: string;
  old: string;
  new: string;
}

export interface DiffChangedEntity {
  guid: string;
  changes: DiffFieldChange[];
}

export interface DiffResponse {
  base: string;
  target: string;
  added: string[];
  removed: string[];
  changed: DiffChangedEntity[];
}

// --- script-as-source 编辑（WPS 式暂存 + 大版本，W-0013） ---

export interface ScriptState {
  modelId: string;
  script: string;
  staged: number;
  canUndo: boolean;
  canRedo: boolean;
  maxSteps: number;
}

export interface ScriptStageResult {
  modelId: string;
  staged: number;
  canUndo: boolean;
  canRedo: boolean;
}

export interface ScriptSaveResult {
  modelId: string;
  version: string;
  staged: number;
}

export interface ScriptParamsResponse {
  modelId: string;
  params: Record<string, unknown>;
}

export interface ScriptVersion {
  version: string;
  createdAt: string;
  note?: string;
}

export interface ScriptVersionsResponse {
  modelId: string;
  scripts: ScriptVersion[];
  versions: EditVersion[];
}

export interface ScriptParamChange {
  key: string;
  action: "added" | "removed" | "modified";
  old?: unknown;
  new?: unknown;
}

export interface ScriptDiffResponse {
  base?: string;
  target?: string;
  from?: number;
  to?: number;
  engine?: string;
  text_diff: string;
  params_changes: ScriptParamChange[];
  stats: { added: number; removed: number };
}

export interface ScriptRunResult {
  modelId: string;
  ok: boolean;
}

// guid → 脚本调用点（script-as-source 统一编辑：改模型 = 改脚本，L1 直改已 410 退役）
export type ScriptLocateOrigin = "literal" | "params" | "traced";

export interface ScriptLocateResult {
  found: boolean;
  designKey?: string;
  line?: number;
  col?: number;
  snippet?: string;
  origin?: ScriptLocateOrigin;
  // origin=params 时：该构件引用的 PARAMS 键（PARAMS 表单聚焦目标；literal/traced 为空）
  paramsKeys?: string[];
  // staging 与 ScriptMap 分叉（有未运行的脚本修改）→ true：行号不可信，不跳行
  stale?: boolean;
}
