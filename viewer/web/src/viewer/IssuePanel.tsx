import { useEffect, useState } from "react";
import {
  createIssue,
  deleteIssue,
  fetchChanges,
  issueAssetUrl,
  listIssues,
  updateIssue,
} from "@/api/client";
import type { ChangeEntry, Issue, IssueStatus } from "@/api/types";
import { useViewer } from "./ViewerContext";
import { useViewerStore } from "./store";
import "./IssuePanel.css";

const STATUS_LABELS: Record<IssueStatus, string> = {
  open: "Open",
  checking: "Checking",
  resolved: "Resolved",
};

export function IssuePanel({ modelId }: { modelId: string }) {
  const ctx = useViewer();
  const selectedId = useViewerStore((s) => s.selectedId);
  const setSelected = useViewerStore((s) => s.setSelected);
  const changesVersion = useViewerStore((s) => s.changesVersion);

  const [tab, setTab] = useState<"issues" | "history">("issues");
  const [issues, setIssues] = useState<Issue[]>([]);
  const [changes, setChanges] = useState<ChangeEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    listIssues(modelId)
      .then(setIssues)
      .catch((e: Error) => setError(e.message));
  }, [modelId]);

  useEffect(() => {
    if (tab !== "history") return;
    fetchChanges(modelId)
      .then(setChanges)
      .catch((e: Error) => setError(e.message));
  }, [modelId, tab, changesVersion]);

  const captureScreenshot = (): Promise<Blob | null> =>
    new Promise((resolve) => {
      const canvas = document.getElementById("xeokit-canvas") as HTMLCanvasElement | null;
      if (!canvas || !canvas.toBlob) return resolve(null);
      try {
        canvas.toBlob((b) => resolve(b), "image/png");
      } catch {
        resolve(null);
      }
    });

  const submit = async () => {
    if (!ctx || !selectedId || !title.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const metaObjects = ctx.metaModel?.metaObjects as unknown as Record<
        string,
        { name?: string; type?: string }
      > | undefined;
      const meta = metaObjects?.[selectedId];
      const cam = ctx.viewer.camera;
      const screenshot = await captureScreenshot();
      const created = await createIssue(
        modelId,
        {
          entityId: selectedId,
          entityName: meta?.name ?? "",
          entityType: meta?.type ?? "",
          title: title.trim(),
          comment,
          camera: {
            eye: [...cam.eye] as [number, number, number],
            look: [...cam.look] as [number, number, number],
            up: [...cam.up] as [number, number, number],
          },
        },
        screenshot
      );
      setIssues((prev) => [created, ...prev]);
      setTitle("");
      setComment("");
      setFormOpen(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const locate = (iss: Issue) => {
    if (!ctx) return;
    ctx.viewer.cameraFlight.flyTo({
      eye: iss.camera.eye,
      look: iss.camera.look,
      up: iss.camera.up,
    });
    const objects = ctx.viewer.scene.objects as unknown as Record<string, unknown>;
    if (objects[iss.entityId]) setSelected(iss.entityId);
  };

  const changeStatus = async (iss: Issue, status: IssueStatus) => {
    try {
      const updated = await updateIssue(modelId, iss.id, { status });
      setIssues((prev) => prev.map((x) => (x.id === iss.id ? updated : x)));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const remove = async (iss: Issue) => {
    if (!window.confirm(`删除 Issue「${iss.title}」？`)) return;
    try {
      await deleteIssue(modelId, iss.id);
      setIssues((prev) => prev.filter((x) => x.id !== iss.id));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <section className={`issue-panel${collapsed ? " collapsed" : ""}`}>
      <header className="issue-panel-header" onClick={() => setCollapsed((v) => !v)}>
        <span className="issue-tabs">
          <button
            type="button"
            className={`issue-tab${tab === "issues" ? " active" : ""}`}
            onClick={(e) => {
              e.stopPropagation();
              setTab("issues");
              setCollapsed(false);
            }}
          >
            Issues（{issues.length}）
          </button>
          <button
            type="button"
            className={`issue-tab${tab === "history" ? " active" : ""}`}
            onClick={(e) => {
              e.stopPropagation();
              setTab("history");
              setCollapsed(false);
            }}
          >
            修改历史
          </button>
        </span>
        {tab === "issues" && (
          <button
            type="button"
            className="issue-new-btn"
            disabled={!selectedId}
            title={selectedId ? "" : "先在模型中选中一个构件"}
            onClick={(e) => {
              e.stopPropagation();
              setFormOpen((v) => !v);
            }}
          >
            新建 Issue
          </button>
        )}
      </header>
      {!collapsed && (
        <div className="issue-panel-body">
          {error && <p className="issue-error">{error}</p>}
          {tab === "history" && (
            <ul className="issue-list change-list">
              {changes.map((c) => (
                <li key={c.id} className="change-item" data-testid="change-item">
                  <span className="change-time">{new Date(c.createdAt).toLocaleString()}</span>
                  <span className="change-entity">{c.entityName || c.entityId}</span>
                  <span className="change-field">{c.field}</span>
                  <span className="change-diff">
                    {c.oldValue || "（空）"} → {c.newValue || "（空）"}
                  </span>
                  <span className="change-author">{c.author}</span>
                </li>
              ))}
              {changes.length === 0 && <li className="issue-empty">暂无修改记录</li>}
            </ul>
          )}
          {tab === "issues" && formOpen && (
            <div className="issue-form">
              <input
                placeholder="标题"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
              <textarea
                placeholder="备注（可选）"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
              />
              <button type="button" disabled={!title.trim() || submitting} onClick={submit}>
                {submitting ? "提交中…" : "提交"}
              </button>
            </div>
          )}
          {tab === "issues" && (
            <ul className="issue-list">
            {issues.map((iss) => (
              <li key={iss.id} className="issue-item">
                <span className={`issue-status-dot issue-status-${iss.status}`} />
                <button type="button" className="issue-title" onClick={() => locate(iss)}>
                  {iss.title}
                </button>
                <span className="issue-entity">{iss.entityName || iss.entityId}</span>
                {iss.screenshot && (
                  <img
                    className="issue-thumb"
                    src={issueAssetUrl(modelId, iss)}
                    alt="截图"
                  />
                )}
                <select
                  aria-label="状态"
                  value={iss.status}
                  onChange={(e) => changeStatus(iss, e.target.value as IssueStatus)}
                >
                  {(Object.keys(STATUS_LABELS) as IssueStatus[]).map((s) => (
                    <option key={s} value={s}>
                      {STATUS_LABELS[s]}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="issue-delete-btn"
                  aria-label="删除 Issue"
                  onClick={() => remove(iss)}
                >
                  ✕
                </button>
              </li>
            ))}
              {issues.length === 0 && <li className="issue-empty">暂无 Issue</li>}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
