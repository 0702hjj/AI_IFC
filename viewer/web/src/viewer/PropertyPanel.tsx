// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

import { useEffect, useState } from "react";
import type { MetaObject } from "@xeokit/xeokit-sdk";
import {
  commitEdits,
  deleteEntity,
  fetchEditableSchema,
  fetchEditPending,
  putEntityEdit,
} from "@/api/client";
import type { EditableKind, EditableSchema, EditScalar } from "@/api/types";
import { useViewer } from "./ViewerContext";
import { useViewerStore } from "./store";
import { applyOverrides } from "./overrides";
import "./PropertyPanel.css";

const AUTHOR = "local-user";
const PROVENANCE = { source: "UI" as const };

interface EditTarget {
  key: string;
  name: string;
  kind: EditableKind;
  value: unknown;
  pset?: string;
  enumValues?: string[];
}

function coerceNumber(kind: EditableKind, raw: string): EditScalar | undefined {
  if (kind !== "int" && kind !== "float") return raw;
  const n = Number(raw);
  if (raw.trim() === "" || Number.isNaN(n)) return undefined;
  if (kind === "int" && !Number.isInteger(n)) return undefined;
  return n;
}

export function PropertyPanel({ modelId }: { modelId: string }) {
  const ctx = useViewer();
  const selectedId = useViewerStore((s) => s.selectedId);
  const overrides = useViewerStore((s) => s.overrides);
  const loadOverrides = useViewerStore((s) => s.loadOverrides);
  const bumpChanges = useViewerStore((s) => s.bumpChanges);
  const flagPendingModelReload = useViewerStore((s) => s.flagPendingModelReload);

  const [query, setQuery] = useState("");
  const [toggled, setToggled] = useState<Record<string, boolean>>({});
  const [schema, setSchema] = useState<EditableSchema | null>(null);
  const [schemaFailed, setSchemaFailed] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [localEdits, setLocalEdits] = useState<Record<string, EditScalar>>({});
  const [pendingCount, setPendingCount] = useState(0);
  const [deleted, setDeleted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    loadOverrides(modelId).catch(() => {});
    fetchEditPending(modelId)
      .then((list) => setPendingCount(list?.length ?? 0))
      .catch(() => {});
  }, [modelId, loadOverrides]);

  useEffect(() => {
    setToggled({});
    setQuery("");
    setEditing(null);
    setLocalEdits({});
    setDeleted(false);
    setError(null);
    setNotice(null);
    setSchema(null);
    setSchemaFailed(false);
    if (!selectedId) return;
    fetchEditableSchema(modelId, selectedId)
      .then((s) => setSchema(s))
      .catch(() => setSchemaFailed(true));
  }, [modelId, selectedId]);

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

  const q = query.trim().toLowerCase();
  const searching = q !== "";

  const isOpen = (id: string, index: number) =>
    searching || (id in toggled ? toggled[id] : index === 0);

  const matches = (name: string, value: unknown) =>
    name.toLowerCase().includes(q) ||
    (value != null && String(value).toLowerCase().includes(q));

  const refreshPending = () =>
    fetchEditPending(modelId)
      .then((list) => setPendingCount(list?.length ?? 0))
      .catch(() => {});

  const save = (target: EditTarget, value: EditScalar) => {
    if (!selectedId || deleted) return;
    const payload = target.pset
      ? { psets: { [target.pset]: { [target.name]: value } }, author: AUTHOR, provenance: PROVENANCE }
      : { fields: { [target.name]: value }, author: AUTHOR, provenance: PROVENANCE };
    putEntityEdit(modelId, selectedId, payload)
      .then(() => {
        setLocalEdits((prev) => ({ ...prev, [target.key]: value }));
        setError(null);
        setEditing(null);
        refreshPending();
      })
      .catch((e: Error) => setError(e.message));
  };

  const submitDraft = (target: EditTarget) => {
    const value = coerceNumber(target.kind, draft);
    if (value === undefined) {
      setError("无效数字");
      return;
    }
    setEditing(null);
    if (value === (target.value ?? "")) return;
    save(target, value);
  };

  const commit = () => {
    commitEdits(modelId)
      .then(() => {
        setPendingCount(0);
        setLocalEdits({});
        setError(null);
        setNotice("已提交，模型重转中…");
        bumpChanges();
        flagPendingModelReload();
      })
      .catch((e: Error) => setError(e.message));
  };

  const remove = () => {
    if (!entity || !selectedId || deleted) return;
    if (!window.confirm(`删除构件「${entity.name || selectedId}」？提交后生效。`)) return;
    deleteEntity(modelId, selectedId, { author: AUTHOR, provenance: PROVENANCE })
      .then(() => {
        setDeleted(true);
        setNotice("构件已标记删除，提交后生效");
        setError(null);
        refreshPending();
      })
      .catch((e: Error) => setError(e.message));
  };

  const displayValue = (t: EditTarget): EditScalar | undefined =>
    t.key in localEdits ? localEdits[t.key] : (t.value as EditScalar);

  const renderValueCell = (t: EditTarget) => {
    const value = displayValue(t);
    if (t.kind === "bool") {
      return (
        <input
          type="checkbox"
          checked={Boolean(value)}
          disabled={deleted}
          aria-label={`编辑 ${t.name}`}
          onChange={(e) => save(t, e.target.checked)}
        />
      );
    }
    if (editing === t.key) {
      if (t.kind === "enum") {
        const options = t.enumValues ?? [];
        return (
          <select
            className="editable-input"
            aria-label={`编辑 ${t.name}`}
            autoFocus
            defaultValue={value == null ? "" : String(value)}
            onChange={(e) => {
              setEditing(null);
              save(t, e.target.value === "" ? null : e.target.value);
            }}
            onKeyDown={(e) => {
              if (e.key === "Escape") setEditing(null);
            }}
            onBlur={() => setEditing(null)}
          >
            <option value="">（空）</option>
            {options.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        );
      }
      return (
        <input
          className="editable-input"
          type={t.kind === "int" || t.kind === "float" ? "number" : "text"}
          step={t.kind === "int" ? 1 : "any"}
          aria-label={`编辑 ${t.name}`}
          value={draft}
          autoFocus
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submitDraft(t);
            if (e.key === "Escape") setEditing(null);
          }}
          onBlur={() => submitDraft(t)}
        />
      );
    }
    return (
      <span
        className="editable-value"
        title={deleted ? undefined : "点击编辑"}
        onClick={() => {
          if (deleted) return;
          setEditing(t.key);
          setDraft(value == null ? "" : String(value));
          setError(null);
        }}
      >
        {value == null || value === "" ? "（空）" : String(value)}
      </span>
    );
  };

  const fieldTargets: EditTarget[] = (schema?.fields ?? []).map((f) => ({
    key: `field:${f.name}`,
    name: f.name,
    kind: f.kind,
    value: f.value,
    enumValues: f.enumValues,
  }));

  const visibleFields = fieldTargets.filter(
    (t) => !searching || matches(t.name, displayValue(t))
  );

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
          {pendingCount > 0 && (
            <p className="pending-banner">
              有未提交修改（{pendingCount}）
              <button type="button" className="pending-commit-btn" onClick={commit}>
                提交
              </button>
            </p>
          )}
          {notice && <p className="property-notice">{notice}</p>}
          {error && <p className="editable-error">{error}</p>}
          {!deleted && (
            <button type="button" className="delete-entity-btn" onClick={remove}>
              删除构件
            </button>
          )}
          {schema && (
            <>
              <section className="property-set editable-section">
                <h3 className="property-set-title">可编辑属性</h3>
                <table>
                  <tbody>
                    {visibleFields.map((t) => (
                      <tr key={t.name} data-testid={`field-${t.name}`}>
                        <td className="property-name">{t.name}</td>
                        <td className="property-value">{renderValueCell(t)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
              {schema.psets.map((pset, index) => {
                const targets = pset.properties
                  .map((p) => ({
                    key: `pset:${pset.name}.${p.name}`,
                    name: p.name,
                    kind: p.kind,
                    value: p.value,
                    pset: pset.name,
                  }))
                  .filter(
                    (t) =>
                      !searching ||
                      matches(t.name, displayValue(t)) ||
                      pset.name.toLowerCase().includes(q)
                  );
                if (searching && targets.length === 0) return null;
                const sid = `schema-pset-${pset.name}`;
                return (
                  <section key={pset.name} className="property-set">
                    <h3
                      className="property-set-title"
                      onClick={() =>
                        setToggled((prev) => ({ ...prev, [sid]: !isOpen(sid, index) }))
                      }
                    >
                      {isOpen(sid, index) ? "▾ " : "▸ "}
                      <span>{pset.name}</span>
                    </h3>
                    {isOpen(sid, index) && (
                      <table>
                        <tbody>
                          {targets.map((t) => (
                            <tr key={t.name} data-testid={`pset-${pset.name}.${t.name}`}>
                              <td className="property-name">{t.name}</td>
                              <td className="property-value">{renderValueCell(t)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </section>
                );
              })}
            </>
          )}
          {schemaFailed && (
            <>
              <p className="property-notice">编辑服务不可用，只读模式</p>
              {entity.propertySets.map((pset, index) => {
                const props = (pset.properties ?? []).filter(
                  (p) => !searching || matches(p.name, p.value) || pset.name.toLowerCase().includes(q)
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
                          {props.map((prop, i) => {
                            const overridden =
                              (selectedId && overrides[selectedId]?.[prop.name]) !== undefined;
                            return (
                              <tr
                                key={`${prop.name}-${i}`}
                                className={overridden ? "overridden" : ""}
                              >
                                <td className="property-name">
                                  {overridden && (
                                    <span className="override-dot" title="历史 override" />
                                  )}
                                  {prop.name}
                                </td>
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
                            );
                          })}
                        </tbody>
                      </table>
                    )}
                  </section>
                );
              })}
            </>
          )}
        </div>
      )}
    </aside>
  );
}
