// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

// scriptEdit: turn a script's PARAMS dict into an editable form model.
//
// Leaf values are classified by JS type: number/string/boolean get native
// inputs; arrays, null and other non-plain values degrade to a JSON text
// field. Nested plain objects are flattened to dotted paths (one level of
// form rows, no tree UI — YAGNI).

export type ParamFieldType = "number" | "string" | "boolean" | "json";

export interface ParamField {
  path: string[];
  name: string; // pathKey(path)，兼作表单 label
  type: ParamFieldType;
  value: unknown;
}

export function pathKey(path: string[]): string {
  return path.join(".");
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function fieldType(v: unknown): ParamFieldType {
  if (typeof v === "number") return "number";
  if (typeof v === "boolean") return "boolean";
  if (typeof v === "string") return "string";
  return "json";
}

export function flattenParams(params: Record<string, unknown>): ParamField[] {
  const out: ParamField[] = [];
  const walk = (obj: Record<string, unknown>, prefix: string[]) => {
    for (const [k, v] of Object.entries(obj)) {
      if (isPlainObject(v)) walk(v, [...prefix, k]);
      else {
        const path = [...prefix, k];
        out.push({ path, name: pathKey(path), type: fieldType(v), value: v });
      }
    }
  };
  walk(params, []);
  return out;
}

export function draftOf(field: ParamField): string {
  if (field.type === "json") return JSON.stringify(field.value);
  return String(field.value);
}

export function parseDraft(type: ParamFieldType, raw: string): unknown {
  if (type === "number") {
    const n = Number(raw.trim());
    if (raw.trim() === "" || Number.isNaN(n)) throw new Error(`不是有效数字: ${raw}`);
    return n;
  }
  if (type === "boolean") return raw === "true";
  if (type === "json") return JSON.parse(raw);
  return raw.trim();
}

// applyDrafts: deep-clone params, then overwrite each field with its draft
// (falling back to the field's current value when no draft exists, e.g. an
// untouched boolean). Throws on the first unparsable draft.
export function applyDrafts(
  params: Record<string, unknown>,
  fields: ParamField[],
  drafts: Record<string, string>
): Record<string, unknown> {
  const next: Record<string, unknown> = JSON.parse(JSON.stringify(params));
  for (const f of fields) {
    const raw = drafts[f.name];
    let value: unknown;
    try {
      value = raw === undefined ? f.value : parseDraft(f.type, raw);
    } catch (e) {
      throw new Error(`${f.name}: ${(e as Error).message}`);
    }
    let node = next;
    for (const seg of f.path.slice(0, -1)) node = node[seg] as Record<string, unknown>;
    node[f.path[f.path.length - 1]] = value;
  }
  return next;
}
