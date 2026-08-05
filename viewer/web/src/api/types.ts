// SPDX-License-Identifier: AGPL-3.0-only
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

// --- design JSON 编辑（WPS 式暂存 + 大版本） ---

export interface DesignState {
  modelId: string;
  design: Record<string, unknown>;
  staged: number;
  canUndo: boolean;
  canRedo: boolean;
  maxSteps: number;
}

export interface DesignStageResult {
  modelId: string;
  staged: number;
  canUndo: boolean;
  canRedo: boolean;
}

export interface DesignSaveResult {
  modelId: string;
  version: string;
  staged: number;
}

export interface DesignVersion {
  version: string;
  createdAt: string;
}

export interface DesignVersionsResponse {
  modelId: string;
  designs: DesignVersion[];
  versions: DesignVersion[];
}

export interface DesignChange {
  key: string;
  type?: string;
  human_label?: string;
  action?: "added" | "removed";
  changes?: Array<{ field: string; old: unknown; new: unknown }>;
}

export interface DesignDiffResponse {
  base: string;
  target: string;
  engine: string;
  changed: DesignChange[];
  added: number;
  removed: number;
  modified: number;
}

export interface RegenerateResult {
  ok: boolean;
  ifc: string;
  walls: number;
  openings: number;
  slabs: number;
}
