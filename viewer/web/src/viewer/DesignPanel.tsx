// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

// DesignPanel: script-as-source editing (W-0013).
//
// The build script is the model's single source of truth. Designers edit the
// PARAMS form (generated from the script's PARAMS block); technical users can
// drill down into a plain-text script editor (textarea + line numbers).
// Both paths stage into the same WPS-style staging chain (undo/redo/discard/
// save); 试跑 runs the staged script into uploads without a version.
// Legacy IFC-only models (no script, 404) degrade to a hint.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchScript,
  fetchScriptParams,
  fetchScriptVersions,
  stageScript,
  stageScriptParams,
  scriptUndo,
  scriptRedo,
  discardScript,
  runScript,
  saveScript,
  postScriptDiff,
  fetchStagingDiff,
} from "@/api/client";
import type { ScriptDiffResponse, ScriptState, ScriptVersionsResponse } from "@/api/types";
import { useViewerStore } from "./store";
import { applyDrafts, draftOf, flattenParams, type ParamField } from "./scriptEdit";
import "./DesignPanel.css";

function fmtVal(v: unknown): string {
  return v === undefined ? "（空）" : JSON.stringify(v);
}

export function ParamChangesSummary({ changes }: { changes: ScriptDiffResponse["params_changes"] }) {
  if (changes.length === 0) return <div className="design-diff-item">PARAMS 无变化</div>;
  return (
    <>
      {changes.map((c) => (
        <div key={c.key} className="design-diff-item">
          {c.action === "modified" && `${c.key}: ${fmtVal(c.old)} → ${fmtVal(c.new)}`}
          {c.action === "added" && `${c.key}: 新增 = ${fmtVal(c.new)}`}
          {c.action === "removed" && `${c.key}: 删除（原 ${fmtVal(c.old)}）`}
        </div>
      ))}
    </>
  );
}

export function DesignPanel({ modelId }: { modelId: string }) {
  const [state, setState] = useState<ScriptState | null>(null);
  const [noScript, setNoScript] = useState(false);
  const [params, setParams] = useState<Record<string, unknown> | null>(null);
  const [paramsError, setParamsError] = useState<string | null>(null);
  const [versions, setVersions] = useState<ScriptVersionsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [mode, setMode] = useState<"form" | "editor">("form");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [editorText, setEditorText] = useState("");
  const [stagingDiff, setStagingDiff] = useState<ScriptDiffResponse | null>(null);
  const [bigDiff, setBigDiff] = useState<ScriptDiffResponse | null>(null);
  const gutterRef = useRef<HTMLPreElement>(null);

  const fields = useMemo<ParamField[]>(() => (params ? flattenParams(params) : []), [params]);

  const refresh = useCallback(async () => {
    const s = await fetchScript(modelId);
    setState(s);
    const [p, v] = await Promise.all([
      fetchScriptParams(modelId).catch((e: Error) => {
        setParamsError(e.message);
        return null;
      }),
      fetchScriptVersions(modelId).catch(() => null),
    ]);
    if (p) {
      setParams(p.params);
      setParamsError(null);
      // reset form drafts from the fresh params (同一 staging 源)
      const d: Record<string, string> = {};
      for (const f of flattenParams(p.params)) d[f.name] = draftOf(f);
      setDrafts(d);
    }
    if (v) setVersions(v);
  }, [modelId]);

  useEffect(() => {
    refresh().catch(() => setNoScript(true));
  }, [refresh]);

  // entering the editor syncs its text from the current staged script
  useEffect(() => {
    if (mode === "editor" && state) setEditorText(state.script);
  }, [mode, state]);

  const run = async (fn: () => Promise<unknown>, reloadModel = false) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await refresh();
      if (reloadModel) useViewerStore.getState().flagPendingModelReload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const stageParams = () => {
    if (!params) return;
    let next: Record<string, unknown>;
    try {
      next = applyDrafts(params, fields, drafts);
    } catch (e) {
      setError((e as Error).message);
      return;
    }
    run(() => stageScriptParams(modelId, next));
  };

  const lineCount = editorText === "" ? 1 : editorText.split("\n").length;

  if (noScript) return <div className="design-panel">该模型无构建脚本</div>;
  if (!state) return <div className="design-panel">加载脚本参数…</div>;

  const scripts = versions?.scripts ?? [];

  return (
    <div className="design-panel">
      <div className="design-panel-header">
        <span>脚本参数</span>
        <span className="design-staged">暂存 {state.staged}/{state.maxSteps}</span>
      </div>

      <div className="design-actions">
        <button onClick={() => setMode("form")} disabled={busy || mode === "form"}>参数表单</button>
        <button onClick={() => setMode("editor")} disabled={busy || mode === "editor"}>脚本编辑器</button>
      </div>

      {mode === "form" && paramsError && (
        <div className="design-error">PARAMS 解析失败：{paramsError}（可用脚本编辑器）</div>
      )}

      {mode === "form" && params && (
        <div className="design-form">
          {fields.map((f) => (
            <label key={f.name} className="design-field">
              <span>{f.name}</span>
              {f.type === "boolean" ? (
                <input
                  type="checkbox"
                  aria-label={f.name}
                  checked={drafts[f.name] === "true"}
                  onChange={(e) => setDrafts({ ...drafts, [f.name]: String(e.target.checked) })}
                />
              ) : f.type === "json" ? (
                <textarea
                  aria-label={f.name}
                  rows={2}
                  value={drafts[f.name] ?? ""}
                  onChange={(e) => setDrafts({ ...drafts, [f.name]: e.target.value })}
                />
              ) : (
                <input
                  type="text"
                  aria-label={f.name}
                  value={drafts[f.name] ?? ""}
                  onChange={(e) => setDrafts({ ...drafts, [f.name]: e.target.value })}
                />
              )}
            </label>
          ))}
          {fields.length === 0 && <div className="design-selected">PARAMS 为空</div>}
          <div className="design-actions">
            <button onClick={stageParams} disabled={busy}>暂存修改</button>
          </div>
        </div>
      )}

      {mode === "editor" && (
        <div className="script-editor">
          <div className="script-editor-body">
            <pre className="script-gutter" data-testid="script-gutter" ref={gutterRef}>
              {Array.from({ length: lineCount }, (_, i) => i + 1).join("\n")}
            </pre>
            <textarea
              aria-label="脚本编辑器文本"
              className="script-textarea"
              spellCheck={false}
              value={editorText}
              onChange={(e) => setEditorText(e.target.value)}
              onScroll={(e) => {
                if (gutterRef.current) gutterRef.current.scrollTop = e.currentTarget.scrollTop;
              }}
            />
          </div>
          <div className="design-actions">
            <button onClick={() => run(() => stageScript(modelId, editorText))} disabled={busy}>
              暂存脚本
            </button>
          </div>
        </div>
      )}

      <div className="design-actions">
        <button onClick={() => run(() => scriptUndo(modelId))} disabled={busy || !state.canUndo}>撤销</button>
        <button onClick={() => run(() => scriptRedo(modelId))} disabled={busy || !state.canRedo}>重做</button>
        <button onClick={() => run(() => discardScript(modelId))} disabled={busy || state.staged === 0}>放弃暂存</button>
        <button onClick={() => run(() => runScript(modelId), true)} disabled={busy}>试跑</button>
        <button onClick={() => run(() => saveScript(modelId), true)} disabled={busy || state.staged === 0} className="primary">
          保存大版本
        </button>
      </div>

      <div className="design-actions">
        {stagingDiff ? (
          <button onClick={() => setStagingDiff(null)} disabled={busy}>收起</button>
        ) : (
          <button
            onClick={() => run(async () => setStagingDiff(await fetchStagingDiff(modelId)))}
            disabled={busy || state.staged < 2}
          >
            暂存改动
          </button>
        )}
      </div>
      {stagingDiff && (
        <div className="design-diff">
          <div>暂存步 {stagingDiff.from} → {stagingDiff.to}（+{stagingDiff.stats.added} -{stagingDiff.stats.removed}）</div>
          <ParamChangesSummary changes={stagingDiff.params_changes} />
          <pre className="script-diff-pre" data-testid="staging-diff-text">{stagingDiff.text_diff}</pre>
        </div>
      )}

      {scripts.length > 1 && (
        <div className="design-versions">
          <div className="design-panel-header">大版本对比</div>
          <div className="design-actions">
            <select data-testid="diff-base" defaultValue={scripts[scripts.length - 2].version}>
              {scripts.map((v) => <option key={v.version} value={v.version}>{v.version}</option>)}
            </select>
            <select data-testid="diff-target" defaultValue={scripts[scripts.length - 1].version}>
              {scripts.map((v) => <option key={v.version} value={v.version}>{v.version}</option>)}
            </select>
            <button
              data-testid="diff-compare"
              disabled={busy}
              onClick={() => {
                const base = (document.querySelector('[data-testid="diff-base"]') as HTMLSelectElement)?.value;
                const target = (document.querySelector('[data-testid="diff-target"]') as HTMLSelectElement)?.value;
                if (base && target) run(async () => setBigDiff(await postScriptDiff(modelId, base, target)));
              }}
            >
              对比
            </button>
          </div>
          {bigDiff && (
            <div className="design-diff">
              <div>{bigDiff.base} → {bigDiff.target}（+{bigDiff.stats.added} -{bigDiff.stats.removed}）</div>
              <ParamChangesSummary changes={bigDiff.params_changes} />
              <pre className="script-diff-pre" data-testid="big-diff-text">{bigDiff.text_diff}</pre>
            </div>
          )}
        </div>
      )}

      {error && <div className="design-error">{error}</div>}
    </div>
  );
}
