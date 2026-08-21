// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  listModels,
  deleteModel,
  deleteChatProject,
  retryModel,
  downloadUrl,
  createChatProject,
  createChatSessionByProject,
  listChatSessions,
  fetchModel,
  type ChatSession,
} from "@/api/client";
import type { ModelInfo } from "@/api/types";
import "./LibraryPage.css";

const KIND_OPTIONS = [
  { value: "cad", label: "CAD 项目（aidxf 管线，默认）" },
  { value: "ifc", label: "IFC 项目（aiifc 管线）" },
  { value: "cad->ifc", label: "CAD→IFC 管线" },
] as const;

function formatSize(size: number): string {
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
  if (size >= 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${size} B`;
}


export default function LibraryPage() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [error, setError] = useState<string>("");
  const [creatingProject, setCreatingProject] = useState(false);
  const [naming, setNaming] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [projectKind, setProjectKind] = useState<"ifc" | "cad" | "cad->ifc">("cad");
  const navigate = useNavigate();

  const confirmCreate = async () => {
    setCreatingProject(true);
    try {
      const p = await createChatProject(projectName.trim() || "AI 项目", projectKind);
      // 项目会话（1 session = 1 project，幂等）：先绑项目
      if (p.projectId) {
        await createChatSessionByProject(p.title || "AI 项目", p.projectId);
      }
      if (p.id) {
        // 兼容：有首模型（旧行为）→ 等转换完成跳查看器
        for (let i = 0; i < 30; i++) {
          const cur = await fetchModel(p.id);
          if (cur.status === "ready") break;
          if (cur.status === "failed") throw new Error(cur.error || "初始化转换失败");
          await new Promise((r) => setTimeout(r, 1000));
        }
        navigate(`/view/${p.id}${p.projectId ? `?project=${p.projectId}` : ""}`);
      } else {
        // 空白项目（2026-08-20）：无模型——刷新会话列表，用户从历史项目进入项目会话
        await refreshSessions();
        setNaming(false);
        setError(`项目「${p.title}」已创建（空白项目）——点上方历史项目进入项目会话`);
      }
    } catch (e) {
      setError((e as Error).message);
      setCreatingProject(false);
    }
  };

  const refresh = useCallback(async () => {
    try {
      setModels(await listModels());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  const refreshSessions = useCallback(async () => {
    try {
      setSessions(await listChatSessions());
    } catch {
      // 会话列表不可用不影响模型库主体
    }
  }, []);

  useEffect(() => {
    refresh();
    refreshSessions();
  }, [refresh, refreshSessions]);

  useEffect(() => {
    if (!models.some((m) => m.status === "converting")) return;
    const timer = setInterval(refresh, 2000);
    return () => clearInterval(timer);
  }, [models, refresh]);




  const onDelete = async (m: ModelInfo) => {
    if (!window.confirm(`删除模型「${m.name}」?`)) return;
    try {
      await deleteModel(m.id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  // 删除项目（级联：项目 + 会话 + 方案 + 项目下模型）——历史项目入口的清理。
  const onDeleteProject = async (s: ChatSession) => {
    if (!s.projectId) return;
    if (!window.confirm(`删除项目「${s.title}」?（连带会话/方案/项目下模型）`)) return;
    try {
      await deleteChatProject(s.projectId);
      await refreshSessions();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const onRetry = async (m: ModelInfo) => {
    try {
      await retryModel(m.id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="library">
      <div className="library-header">
        <h1>模型库</h1>
        {naming ? (
          <div className="project-naming">
            <input
              autoFocus
              value={projectName}
              placeholder="给项目起个名，如：两层小楼"
              onChange={(e) => setProjectName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") confirmCreate(); if (e.key === "Escape") setNaming(false); }}
            />
            <select
              className="kind-select"
              value={projectKind}
              onChange={(e) => setProjectKind(e.target.value as "ifc" | "cad" | "cad->ifc")}
              aria-label="项目类型"
            >
              {KIND_OPTIONS.map((k) => (
                <option key={k.value} value={k.value}>{k.label}</option>
              ))}
            </select>
            <button className="chat-entry-btn" disabled={creatingProject} onClick={confirmCreate}>
              {creatingProject ? "初始化中…" : "创建"}
            </button>
            <button className="chat-entry-cancel" onClick={() => setNaming(false)}>取消</button>
          </div>
        ) : (
          <button className="chat-entry-btn" onClick={() => setNaming(true)}>
            新建空白项目（AI 建模）
          </button>
        )}
      </div>

      {sessions.length > 0 && (
        <section className="history-section">
          <h2>历史项目（会话）</h2>
          <ul className="history-list">
            {sessions.map((s) => (
              <li key={s.chatSessionId}>
                <Link
                  to={s.modelId ? `/view/${s.modelId}${s.projectId ? `?project=${s.projectId}` : ""}` : "#"}
                  onClick={(e) => { if (!s.modelId) e.preventDefault(); }}
                >
                  <span className="history-title">{s.title}</span>
                  <span className="history-time">{new Date(s.createdAt).toLocaleString()}</span>
                </Link>
                {s.projectId && (
                  <button className="history-delete" onClick={() => onDeleteProject(s)}>删除</button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* 上传入口已隐藏（2026-08-21）：模型不再由用户直接上传——经 agent 在项目会话内生成。
          后端转化/显示链（upload→convert→XKT/render）保留，agent 建模型产物展示。 */}

      {error && <div className="error-banner">{error}</div>}

      <table>
        <thead>
          <tr>
            <th>名称</th>
            <th>类型</th>
            <th>大小</th>
            <th>状态</th>
            <th>上传时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {models.length === 0 && (
            <tr>
              <td colSpan={6} className="empty">
                暂无模型
              </td>
            </tr>
          )}
          {models.map((m) => (
            <tr key={m.id}>
              <td>{m.name}</td>
              <td>
                <span className={`kind-badge kind-${m.kind ?? "ifc"}`}>
                  {(m.kind ?? "ifc").toUpperCase()}
                </span>
              </td>
              <td>{formatSize(m.size)}</td>
              <td>
                <span className={`status status-${m.status}`}>
                  {m.status === "converting" && "转换中"}
                  {m.status === "ready" && "就绪"}
                  {m.status === "failed" && "失败"}
                </span>
              </td>
              <td>{new Date(m.createdAt).toLocaleString()}</td>
              <td className="actions">
                {m.status === "ready" && (
                  <>
                    <Link to={`/view/${m.id}`}>查看</Link>
                    <a href={downloadUrl(m.id)} download={m.name}>
                      下载
                    </a>
                    <button onClick={() => onDelete(m)}>删除</button>
                  </>
                )}
                {m.status === "failed" && (
                  <>
                    <span className="error-tip" title={m.error}>
                      错误详情
                    </span>
                    <button onClick={() => onRetry(m)}>重试</button>
                    <button onClick={() => onDelete(m)}>删除</button>
                  </>
                )}
                {m.status === "converting" && (
                  <button onClick={() => onDelete(m)}>删除</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
