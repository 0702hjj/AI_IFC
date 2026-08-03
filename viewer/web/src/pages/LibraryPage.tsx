// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  listModels,
  uploadModel,
  deleteModel,
  retryModel,
  downloadUrl,
  createChatProject,
  fetchModel,
} from "@/api/client";
import type { ModelInfo } from "@/api/types";
import "./LibraryPage.css";

const MAX_SIZE = 200 * 1024 * 1024;

function formatSize(size: number): string {
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
  if (size >= 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${size} B`;
}

function validateFile(file: File): string | null {
  if (!file.name.toLowerCase().endsWith(".ifc")) return "仅支持 .ifc 文件";
  if (file.size > MAX_SIZE) return "文件超过 200MB 限制";
  return null;
}

export default function LibraryPage() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [error, setError] = useState<string>("");
  const [uploading, setUploading] = useState(false);
  const [creatingProject, setCreatingProject] = useState(false);
  const [naming, setNaming] = useState(false);
  const [projectName, setProjectName] = useState("");
  const navigate = useNavigate();

  const confirmCreate = async () => {
    setCreatingProject(true);
    try {
      const m = await createChatProject(projectName.trim() || "AI 项目");
      // 等初始化转换完成（ready）再跳转，避免项目页加载未就绪的 XKT 失败
      for (let i = 0; i < 30; i++) {
        const cur = await fetchModel(m.id);
        if (cur.status === "ready") break;
        if (cur.status === "failed") throw new Error(cur.error || "初始化转换失败");
        await new Promise((r) => setTimeout(r, 1000));
      }
      navigate(`/view/${m.id}`);
    } catch (e) {
      setError((e as Error).message);
      setCreatingProject(false);
    }
  };
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      setModels(await listModels());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!models.some((m) => m.status === "converting")) return;
    const timer = setInterval(refresh, 2000);
    return () => clearInterval(timer);
  }, [models, refresh]);

  const doUpload = useCallback(
    async (file: File) => {
      const err = validateFile(file);
      if (err) {
        setError(err);
        return;
      }
      setError("");
      setUploading(true);
      try {
        await uploadModel(file);
        await refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setUploading(false);
      }
    },
    [refresh],
  );

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) doUpload(file);
    e.target.value = "";
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) doUpload(file);
  };

  const onDelete = async (m: ModelInfo) => {
    if (!window.confirm(`删除模型「${m.name}」?`)) return;
    try {
      await deleteModel(m.id);
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

      <div
        className={`dropzone${dragOver ? " dragover" : ""}`}
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".ifc"
          hidden
          onChange={onFileChange}
        />
        {uploading ? "上传中…" : "点击选择或拖拽 .ifc 文件到此处上传（≤200MB）"}
      </div>

      {error && <div className="error-banner">{error}</div>}

      <table>
        <thead>
          <tr>
            <th>名称</th>
            <th>大小</th>
            <th>状态</th>
            <th>上传时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {models.length === 0 && (
            <tr>
              <td colSpan={5} className="empty">
                暂无模型
              </td>
            </tr>
          )}
          {models.map((m) => (
            <tr key={m.id}>
              <td>{m.name}</td>
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
