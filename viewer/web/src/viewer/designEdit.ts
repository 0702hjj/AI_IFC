// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

// designEdit: locate a design-JSON element by its stable `key` and apply edits.
// The IFC→design link comes from Pset_AIIFC.designKey (written by the build
// pipeline); editing a design element keeps its key, so cross-version diff
// alignment holds.

export type DesignElementKind = "wall" | "opening" | "slab" | "stair";

export interface DesignElement {
  key: string;
  kind: DesignElementKind;
  storey: string;
  index: number; // index within its kind's array
  data: Record<string, unknown>;
}

const KIND_FIELDS: Record<DesignElementKind, string> = {
  wall: "walls",
  opening: "openings",
  slab: "slabs",
  stair: "stairs",
};

// Param schema per kind: which fields are editable + their label/type.
export const DESIGN_PARAM_SCHEMA: Record<
  DesignElementKind,
  Array<{ field: string; label: string; type: "number" | "text" | "select"; options?: string[] }>
> = {
  wall: [
    { field: "t", label: "厚度 (m)", type: "number" },
    { field: "kind", label: "类型", type: "select", options: ["ext", "int"] },
  ],
  opening: [
    { field: "type", label: "类型", type: "select", options: ["window", "door"] },
    { field: "w", label: "宽度 (m)", type: "number" },
    { field: "h", label: "高度 (m)", type: "number" },
    { field: "sill", label: "窗台 (m)", type: "number" },
    { field: "along", label: "沿墙位置 (m)", type: "number" },
  ],
  slab: [
    { field: "t", label: "厚度 (m)", type: "number" },
    { field: "predef", label: "类型", type: "select", options: ["FLOOR", "ROOF", "LANDING"] },
  ],
  stair: [
    { field: "type", label: "类型", type: "text" },
    { field: "width", label: "宽度 (m)", type: "number" },
  ],
};

export function findElementByKey(design: Record<string, unknown>, key: string): DesignElement | null {
  const floors = (design.floors ?? {}) as Record<string, Record<string, unknown>>;
  for (const [storey, floor] of Object.entries(floors)) {
    for (const [kind, field] of Object.entries(KIND_FIELDS)) {
      const items = (floor[field] ?? []) as Array<Record<string, unknown>>;
      for (let i = 0; i < items.length; i++) {
        if (items[i].key === key) {
          return { key, kind: kind as DesignElementKind, storey, index: i, data: items[i] };
        }
      }
    }
  }
  return null;
}

export function updateElement(
  design: Record<string, unknown>,
  found: DesignElement,
  patch: Record<string, unknown>
): Record<string, unknown> {
  // Deep-clone the design, then patch the matched element in place.
  const next: Record<string, unknown> = JSON.parse(JSON.stringify(design));
  const floors = (next.floors ?? {}) as Record<string, Record<string, unknown>>;
  const floor = floors[found.storey] as Record<string, unknown>;
  const items = (floor[KIND_FIELDS[found.kind]] ?? []) as Array<Record<string, unknown>>;
  items[found.index] = { ...items[found.index], ...patch, key: found.key };
  floor[KIND_FIELDS[found.kind]] = items;
  return next;
}
