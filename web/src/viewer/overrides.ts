// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

import type { EntityFields } from "@/api/types";

export const EDITABLE_FIELDS = [
  "Name",
  "Description",
  "Classification",
  "FireRating",
  "Comments",
] as const;
export type EditableField = (typeof EDITABLE_FIELDS)[number];

export interface DisplayProp {
  name: string;
  value: unknown;
  type?: string;
}

export interface DisplayPset {
  id: string;
  name: string;
  properties?: DisplayProp[];
}

export interface DisplayMeta {
  id: string;
  name: string;
  type: string;
  propertySets?: DisplayPset[];
}

export interface EffectiveEntity {
  id: string;
  name: string;
  type: string;
  propertySets: DisplayPset[];
  fields: Record<EditableField, string>;
}

const editable = new Set<string>(EDITABLE_FIELDS);

export function applyOverrides(meta: DisplayMeta, ov: EntityFields = {}): EffectiveEntity {
  const propertySets = (meta.propertySets ?? []).map((pset) => ({
    ...pset,
    properties: (pset.properties ?? []).map((p) =>
      editable.has(p.name) && ov[p.name] !== undefined ? { ...p, value: ov[p.name] } : p
    ),
  }));

  const fields = {} as Record<EditableField, string>;
  for (const f of EDITABLE_FIELDS) {
    if (ov[f] !== undefined) {
      fields[f] = ov[f];
      continue;
    }
    if (f === "Name") {
      fields[f] = meta.name ?? "";
      continue;
    }
    let value = "";
    for (const pset of meta.propertySets ?? []) {
      const hit = (pset.properties ?? []).find((p) => p.name === f);
      if (hit) {
        value = hit.value == null ? "" : String(hit.value);
        break;
      }
    }
    fields[f] = value;
  }

  return { id: meta.id, name: ov.Name ?? meta.name, type: meta.type, propertySets, fields };
}
