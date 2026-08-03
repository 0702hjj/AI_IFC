// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchModel, createChatSession, type ChatSession } from "@/api/client";
import type { ModelInfo } from "@/api/types";
import { ViewerProvider } from "@/viewer/ViewerContext";
import { Toolbar } from "@/viewer/Toolbar";
import { ModelTreePanel } from "@/viewer/ModelTreePanel";
import { PropertyPanel } from "@/viewer/PropertyPanel";
import { IssuePanel } from "@/viewer/IssuePanel";
import { DiffPanel } from "@/viewer/DiffPanel";
import { ChatSidebar } from "@/viewer/ChatSidebar";
import { useViewerStore } from "@/viewer/store";
import "./ViewerPage.css";

export default function ViewerPage() {
  const { id } = useParams<{ id: string }>();
  const [reloadKey, setReloadKey] = useState(0);
  const [status, setStatus] = useState<ModelInfo["status"] | null>(null);
  const prevStatus = useRef<ModelInfo["status"] | null>(null);
  const [session, setSession] = useState<ChatSession | null>(null);
  const setChatOpen = useViewerStore((s) => s.setChatOpen);
  const pendingModelReload = useViewerStore((s) => s.pendingModelReload);
  const clearPendingModelReload = useViewerStore((s) => s.clearPendingModelReload);

  // 模型状态轮询：converting→ready 自动重载查看器（AI commit 后走这条路刷新）
  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    const check = () =>
      fetchModel(id)
        .then((m) => {
          if (!cancelled) setStatus(m.status);
        })
        .catch(() => {});
    check();
    const timer = setInterval(check, 2000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [id]);

  useEffect(() => {
    // reload 触发：① converting→ready（UI edit 路径，首次上传同理）；
    // ② AI commit 后 viewer.committed 置的 pendingModelReload + 轮询到 ready
    //    （AI 改的小模型重转常 <2s，会错过 converting 窗口，故用 pending 兜底）
    const fromConverting = prevStatus.current === "converting" && status === "ready";
    const fromPending = status === "ready" && pendingModelReload;
    if (fromConverting || fromPending) {
      setReloadKey((k) => k + 1);
      if (fromPending) clearPendingModelReload();
    }
    prevStatus.current = status;
  }, [status, pendingModelReload, clearPendingModelReload]);

  // chat 会话：进入项目页即建立并绑定当前 modelId（会话永远 bound）
  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    createChatSession("项目对话", id)
      .then((s) => {
        if (!cancelled) setSession(s);
      })
      .catch(() => {
        /* chat 服务不可用时页面其余功能不受影响 */
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  // 首次进入自动展开一次（让入口可发现）；之后由 Toolbar 按钮控制
  useEffect(() => {
    if (session) setChatOpen(true);
  }, [session?.chatSessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!id) {
    return (
      <div className="viewer-page">
        <div className="viewer-status viewer-error">
          <p>缺少模型 ID</p>
          <Link to="/">返回模型库</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="viewer-page">
      <ViewerProvider key={reloadKey} modelId={id}>
        <Toolbar id={id} />
        <ModelTreePanel />
        <PropertyPanel modelId={id} />
        <IssuePanel modelId={id} />
        <DiffPanel modelId={id} />
      </ViewerProvider>
      {session && <ChatSidebar session={session} />}
    </div>
  );
}
