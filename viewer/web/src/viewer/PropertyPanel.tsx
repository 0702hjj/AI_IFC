// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

import { useEffect, useState } from "react";
import type { MetaObject } from "@xeokit/xeokit-sdk";
import { saveEntityProperties } from "@/api/client";
import { useViewer } from "./ViewerContext";
import { useViewerStore } from "./store";
import { applyOverrides, EDITABLE_FIELDS, type EditableField } from "./overrides";
import "./PropertyPanel.css";

export function PropertyPanel({ modelId }: { modelId: string }) {
  const ctx = useViewer();
  const selectedId = useViewerStore((s) => s.selectedId);
  const overrides = useViewerStore((s) => s.overrides);
  const loadOverrides = useViewerStore((s) => s.loadOverrides);
  const setEntityOverrides = useViewerStore((s) => s.setEntityOverrides);
  const bumpChanges = useViewerStore((s) => s.bumpChanges);

  const [query, setQuery] = useState("");
  const [toggled, setToggled] = useState<Record<string, boolean>>({});
  const [editing, setEditing] = useState<EditableField | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadOverrides(modelId).catch(() => {});
  }, [modelId, loadOverrides]);

  useEffect(() => {
    setToggled({});
    setQuery("");
    setEditing(null);
    setError(null);
  }, [selectedId]);

  const metaModel = ctx?.metaModel ?? null;
  const metaObjects = metaModel
    ? (metaModel.metaObjects as unknown as Record<string, MetaObject>)
    : null;
  const metaObject =
    selectedId && metaObjects ? (metaObjects[selectedId] ?? null) : null;

  const entity = metaObject
    ? applyOverrides(
        metaObject as unknown as Parameters<typeof applyOverrides>[0],
        (selectedId && overrides[selectedId]) || {}
      )
    : null;

  const psets = entity?.propertySets ?? [];
  const q = query.trim().toLowerCase();
  const searching = q !== "";

  const propMatches = (p: { name: string; value: unknown }) =>
    p.name.toLowerCase().includes(q) ||
    (p.value != null && String(p.value).toLowerCase().includes(q));

  const isOpen = (id: string, index: number) =>
    searching || (id in toggled ? toggled[id] : index === 0);

  const startEdit = (field: EditableField) => {
    if (!entity) return;
    setEditing(field);
    setDraft(entity.fields[field]);
    setError(null);
  };

  const cancelEdit = () => {
    setEditing(null);
    setError(null);
  };

  const save = (field: EditableField) => {
    if (!entity || !selectedId || editing !== field) return;
    const value = draft;
    setEditing(null);
    if (value === entity.fields[field]) return;
    saveEntityProperties(modelId, selectedId, { [field]: value }, entity.name)
      .then((effective) => {
        setEntityOverrides(selectedId, effective ?? {});
        bumpChanges();
        setError(null);
      })
      .catch((e: Error) => {
        setError(e.message);
        setEditing(field);
      });
  };

  return (
    <aside className="property-panel">
      <h2>属性</h2>
      {!entity && <p className="property-empty">点击构件查看属性</p>}
      {entity && (
        <div className="property-body">
          <input
            className="property-search"
            type="search"
            placeholder="搜索属性"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <dl className="property-summary">
            <dt>名称</dt>
            <dd>{entity.name || "（未命名）"}</dd>
            <dt>类型</dt>
            <dd>{entity.type}</dd>
          </dl>
          <section className="property-set editable-section">
            <h3 className="property-set-title">可编辑属性</h3>
            {error && <p className="editable-error">{error}</p>}
            <table>
              <tbody>
                {EDITABLE_FIELDS.map((field) => {
                  const overridden =
                    (selectedId && overrides[selectedId]?.[field]) !== undefined;
                  return (
                    <tr
                      key={field}
                      data-testid={`editable-${field}`}
                      className={overridden ? "overridden" : ""}
                    >
                      <td className="property-name">
                        {overridden && <span className="override-dot" title="已修改" />}
                        {field}
                      </td>
                      <td className="property-value">
                        {editing === field ? (
                          <input
                            className="editable-input"
                            aria-label={`编辑 ${field}`}
                            value={draft}
                            autoFocus
                            onChange={(e) => setDraft(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") save(field);
                              if (e.key === "Escape") cancelEdit();
                            }}
                            onBlur={() => save(field)}
                          />
                        ) : (
                          <span
                            className="editable-value"
                            title="点击编辑"
                            onClick={() => startEdit(field)}
                          >
                            {entity.fields[field] || "（空）"}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>
          {psets.map((pset, index) => {
            const props = (pset.properties ?? []).filter(
              (p) => !searching || propMatches(p) || pset.name.toLowerCase().includes(q)
            );
            if (searching && props.length === 0) return null;
            return (
              <section key={pset.id} className="property-set">
                <h3
                  className="property-set-title"
                  onClick={() =>
                    setToggled((prev) => ({
                      ...prev,
                      [pset.id]: !isOpen(pset.id, index),
                    }))
                  }
                >
                  {isOpen(pset.id, index) ? "▾ " : "▸ "}
                  <span>{pset.name}</span>
                </h3>
                {isOpen(pset.id, index) && (
                  <table>
                    <tbody>
                      {props.map((prop, i) => (
                        <tr key={`${prop.name}-${i}`}>
                          <td className="property-name">{prop.name}</td>
                          <td className="property-value">
                            {prop.value == null ? "" : String(prop.value)}
                          </td>
                          <td className="property-copy">
                            <button
                              type="button"
                              className="property-copy-btn"
                              aria-label={`复制 ${prop.name}`}
                              onClick={() =>
                                navigator.clipboard.writeText(
                                  `${prop.name}: ${prop.value == null ? "" : String(prop.value)}`
                                )
                              }
                            >
                              复制
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </section>
            );
          })}
        </div>
      )}
    </aside>
  );
}
