// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

// DesignPanel: edit the design-JSON element behind the selected IFC component.
//
// Flow (per the iteration plan):
//   select a component → read Pset_AIIFC.designKey → load design JSON →
//   edit params (wall t/kind, opening w/h/sill/along/type, slab t/predef) →
//   stage (WPS-style) → regenerate IFC → save as a big version.
// Also exposes undo/redo/discard (staging) and version diff (big versions only).

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchDesign,
  stageDesign,
  designUndo,
  designRedo,
  discardDesign,
  regenerateDesign,
  saveDesign,
  fetchDesignVersions,
  postDesignDiff,
} from "@/api/client";
import type { DesignState, DesignVersionsResponse, DesignDiffResponse } from "@/api/types";
import { useViewer } from "./ViewerContext";
import { useViewerStore } from "./store";
import { DESIGN_PARAM_SCHEMA, findElementByKey, updateElement, type DesignElement } from "./designEdit";
import "./DesignPanel.css";

function designKeyOfMeta(psets: Array<{ name?: string; properties?: Array<{ name: string; value: unknown }> }>): string | null {
  const pset = psets.find((p) => p.name === "Pset_AIIFC");
  const prop = pset?.properties?.find((p) => p.name === "designKey");
  return typeof prop?.value === "string" && prop.value ? prop.value : null;
}

export function DesignPanel({ modelId }: { modelId: string }) {
  const selectedId = useViewerStore((s) => s.selectedId);
  const viewerCtx = useViewer();
  const metaObjects = viewerCtx?.metaModel
    ? (viewerCtx.metaModel.metaObjects as unknown as Record<string, { propertySets?: Array<{ name?: string; properties?: Array<{ name: string; value: unknown }> }> }>)
    : null;
  const selectedMeta = selectedId && metaObjects ? metaObjects[selectedId] : undefined;
  const designKey = selectedMeta ? designKeyOfMeta(selectedMeta.propertySets ?? []) : null;

  const [state, setState] = useState<DesignState | null>(null);
  const [versions, setVersions] = useState<DesignVersionsResponse | null>(null);
  const [diff, setDiff] = useState<DesignDiffResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [s, v] = await Promise.all([fetchDesign(modelId), fetchDesignVersions(modelId)]);
    setState(s);
    setVersions(v);
  }, [modelId]);

  useEffect(() => { refresh().catch((e) => setError(String(e))); }, [refresh]);

  const element = useMemo<DesignElement | null>(
    () => (state?.design && designKey ? findElementByKey(state.design, designKey) : null),
    [state?.design, designKey]
  );

  const [draft, setDraft] = useState<Record<string, string>>({});
  useEffect(() => {
    if (!element) { setDraft({}); return; }
    const d: Record<string, string> = {};
    for (const f of DESIGN_PARAM_SCHEMA[element.kind]) {
      const v = element.data[f.field];
      d[f.field] = v == null ? "" : String(v);
    }
    setDraft(d);
  }, [element?.key]);

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError(null);
    try { await fn(); await refresh(); }
    catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  };

  const applyAndStage = () => {
    if (!element || !state) return;
    const patch: Record<string, unknown> = {};
    for (const f of DESIGN_PARAM_SCHEMA[element.kind]) {
      const raw = draft[f.field]?.trim();
      if (raw === "") continue;
      patch[f.field] = f.type === "number" ? Number(raw) : raw;
    }
    const next = updateElement(state.design, element, patch);
    run(() => stageDesign(modelId, next));
  };

  const regenerateAndSave = () =>
    run(async () => {
      await regenerateDesign(modelId);
      await saveDesign(modelId);
    });

  if (!state) return <div className="design-panel">加载设计参数…</div>;

  const selectedLabel = element
    ? `${element.storey} ${element.kind} ${element.key}`
    : (selectedId ? "选中构件无 designKey（非 design JSON 生成）" : "未选中构件");

  return (
    <div className="design-panel">
      <div className="design-panel-header">
        <span>Design 编辑</span>
        <span className="design-staged">暂存 {state.staged}/{state.maxSteps}</span>
      </div>
      <div className="design-selected">{selectedLabel}</div>

      {element && (
        <div className="design-form">
          {DESIGN_PARAM_SCHEMA[element.kind].map((f) => (
            <label key={f.field} className="design-field">
              <span>{f.label}</span>
              {f.type === "select" ? (
                <select value={draft[f.field] ?? ""} onChange={(e) => setDraft({ ...draft, [f.field]: e.target.value })}>
                  {(f.options ?? []).map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
              ) : (
                <input type="text" value={draft[f.field] ?? ""} onChange={(e) => setDraft({ ...draft, [f.field]: e.target.value })} />
              )}
            </label>
          ))}
          <div className="design-actions">
            <button onClick={applyAndStage} disabled={busy}>暂存修改</button>
            <button onClick={() => run(() => designUndo(modelId))} disabled={busy || !state.canUndo}>撤销</button>
            <button onClick={() => run(() => designRedo(modelId))} disabled={busy || !state.canRedo}>重做</button>
          </div>
          <div className="design-actions">
            <button onClick={() => run(() => discardDesign(modelId))} disabled={busy}>放弃暂存</button>
            <button onClick={regenerateAndSave} disabled={busy || state.staged === 0} className="primary">重生成 + 保存大版本</button>
          </div>
        </div>
      )}

      {versions && versions.designs.length > 1 && (
        <div className="design-versions">
          <div className="design-panel-header">大版本对比</div>
          <div className="design-actions">
            <select data-testid="diff-base" defaultValue={versions.designs[versions.designs.length - 2].version}>
              {versions.designs.map((v) => <option key={v.version} value={v.version}>{v.version}</option>)}
            </select>
            <select data-testid="diff-target" defaultValue={versions.designs[versions.designs.length - 1].version}>
              {versions.designs.map((v) => <option key={v.version} value={v.version}>{v.version}</option>)}
            </select>
            <button onClick={() => {
              const base = (document.querySelector('[data-testid="diff-base"]') as HTMLSelectElement)?.value;
              const target = (document.querySelector('[data-testid="diff-target"]') as HTMLSelectElement)?.value;
              if (base && target) run(() => postDesignDiff(modelId, base, target).then(setDiff));
            }} disabled={busy}>对比</button>
          </div>
          {diff && (
            <div className="design-diff">
              <div>引擎：{diff.engine} · 新增 {diff.added} · 删除 {diff.removed} · 修改 {diff.modified}</div>
              {diff.changed.map((c) => (
                <div key={c.key} className="design-diff-item">
                  <b>{c.human_label ?? c.key}</b>
                  {c.action ? ` [${c.action}]` : (c.changes ?? []).map((ch) => ` ${ch.field}: ${JSON.stringify(ch.old)}→${JSON.stringify(ch.new)}`)}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {error && <div className="design-error">{error}</div>}
    </div>
  );
}
