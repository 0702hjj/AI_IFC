import { useEffect, useState } from "react";
import { fetchEditVersions, postEditDiff } from "@/api/client";
import type { DiffResponse, EditVersion } from "@/api/types";
import { useViewer } from "./ViewerContext";
import { useViewerStore } from "./store";
import "./DiffPanel.css";

type Rgb = [number, number, number];

export const DIFF_COLORS: { added: Rgb; changed: Rgb } = {
  added: [0.13, 0.77, 0.13],
  changed: [1, 0.84, 0.1],
};

type SceneObjects = Record<string, { colorize: Rgb | null }>;

export function DiffPanel({ modelId }: { modelId: string }) {
  const ctx = useViewer();
  const open = useViewerStore((s) => s.diffOpen);

  const [versions, setVersions] = useState<EditVersion[]>([]);
  const [versionsLoaded, setVersionsLoaded] = useState(false);
  const [base, setBase] = useState("");
  const [target, setTarget] = useState("current");
  const [result, setResult] = useState<DiffResponse | null>(null);
  const [skipped, setSkipped] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    fetchEditVersions(modelId)
      .then((res) => {
        setVersions(res.versions);
        setVersionsLoaded(true);
        setBase((b) => b || res.versions[0]?.version || "");
      })
      .catch((e: Error) => setError(e.message));
  }, [open, modelId]);

  const sceneObjects = (): SceneObjects =>
    (ctx?.viewer.scene.objects ?? {}) as unknown as SceneObjects;

  const clearColorize = (diff: DiffResponse | null) => {
    if (!diff) return;
    const objects = sceneObjects();
    for (const guid of [...diff.added, ...diff.changed.map((c) => c.guid)]) {
      const obj = objects[guid];
      if (obj) obj.colorize = null;
    }
  };

  const applyColorize = (diff: DiffResponse) => {
    const objects = sceneObjects();
    let missing = 0;
    const paint = (guid: string, color: Rgb) => {
      const obj = objects[guid];
      if (obj) obj.colorize = color;
      else missing += 1;
    };
    diff.added.forEach((g) => paint(g, DIFF_COLORS.added));
    diff.changed.forEach((c) => paint(c.guid, DIFF_COLORS.changed));
    setSkipped(missing);
  };

  const compare = async () => {
    if (!base || !target) return;
    setLoading(true);
    setError(null);
    try {
      const diff = await postEditDiff(modelId, base, target);
      clearColorize(result);
      setResult(diff);
      applyColorize(diff);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const clear = () => {
    clearColorize(result);
    setResult(null);
    setSkipped(0);
  };

  const locate = (guid: string) => {
    if (!ctx) return;
    const objects = ctx.viewer.scene.objects as unknown as Record<string, unknown>;
    const obj = objects[guid];
    if (!obj) return;
    ctx.viewer.cameraFlight.flyTo(obj);
    useViewerStore.getState().setSelected(guid);
  };

  if (!open) return null;

  return (
    <section className="diff-panel">
      <header className="diff-panel-header">版本对比</header>
      <div className="diff-panel-body">
        {error && <p className="diff-error">{error}</p>}
        {versionsLoaded && versions.length === 0 && (
          <p className="diff-empty">暂无版本可对比</p>
        )}
        {versions.length > 0 && (
          <div className="diff-controls">
            <label>
              Base
              <select
                aria-label="base 版本"
                value={base}
                onChange={(e) => setBase(e.target.value)}
              >
                {versions.map((v) => (
                  <option key={v.version} value={v.version}>
                    {v.version}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Target
              <select
                aria-label="target 版本"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
              >
                <option value="current">current</option>
                {versions.map((v) => (
                  <option key={v.version} value={v.version}>
                    {v.version}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" disabled={loading || !base} onClick={compare}>
              {loading ? "对比中…" : "对比"}
            </button>
            <button type="button" disabled={!result} onClick={clear}>
              清除
            </button>
          </div>
        )}
        {skipped > 0 && (
          <p className="diff-skipped">
            {skipped} 个构件在当前模型中不存在，已跳过着色
          </p>
        )}
        {result && (
          <div className="diff-result">
            <section className="diff-section">
              <h3 className="diff-section-title diff-added">
                新增（{result.added.length}）
              </h3>
              <ul className="diff-list">
                {result.added.map((g) => (
                  <li key={g} className="diff-guid diff-guid-added">
                    {g}
                  </li>
                ))}
              </ul>
            </section>
            <section className="diff-section">
              <h3 className="diff-section-title diff-removed">
                删除（{result.removed.length}）
              </h3>
              <ul className="diff-list">
                {result.removed.map((g) => (
                  <li key={g} className="diff-guid diff-guid-removed">
                    {g}
                  </li>
                ))}
              </ul>
            </section>
            <section className="diff-section">
              <h3 className="diff-section-title diff-changed">
                修改（{result.changed.length}）
              </h3>
              <ul className="diff-list">
                {result.changed.map((c) => (
                  <li key={c.guid}>
                    <button
                      type="button"
                      className="diff-guid diff-changed-item"
                      onClick={() => locate(c.guid)}
                    >
                      {c.guid}
                    </button>
                    <ul className="diff-changes">
                      {c.changes.map((ch, i) => (
                        <li key={`${ch.field}-${i}`}>
                          <span className="diff-field">{ch.field}</span>
                          {ch.old || "（空）"} → {ch.new || "（空）"}
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        )}
      </div>
    </section>
  );
}
