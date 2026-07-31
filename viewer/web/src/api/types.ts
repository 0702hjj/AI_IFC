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
