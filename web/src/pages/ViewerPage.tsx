// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { fetchModel, createChatSession, createChatSessionByProject, type ChatSession } from "@/api/client";
import type { ModelInfo } from "@/api/types";
import { ViewerProvider } from "@/viewer/ViewerContext";
import { Toolbar } from "@/viewer/Toolbar";
import { ModelTreePanel } from "@/viewer/ModelTreePanel";
import { PropertyPanel } from "@/viewer/PropertyPanel";
import { IssuePanel } from "@/viewer/IssuePanel";
import { DiffPanel } from "@/viewer/DiffPanel";
import { DesignPanel } from "@/viewer/DesignPanel";
import { ChatSidebar } from "@/viewer/ChatSidebar";
import { useViewerStore } from "@/viewer/store";
import DxfViewer from "@/dxfviewer/DxfViewer";
import "./ViewerPage.css";

// web-ifc+three 体积大且默认引擎是 xeokit——动态分包，仅切换到 webifc 时加载
const IfcLiteViewer = lazy(() => import("@/ifcviewer/IfcLiteViewer"));

// IFC 渲染引擎开关（用户级偏好，默认 xeokit）：webifc 为 web-ifc+three 并存
// 渐进路线（W-0044）。dxf 不参与切换。
type ViewerEngine = "xeokit" | "webifc";
const ENGINE_KEY = "viewerEngine";

function readEngine(): ViewerEngine {
  return localStorage.getItem(ENGINE_KEY) === "webifc" ? "webifc" : "xeokit";
}

export default function ViewerPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const projectId = searchParams.get("project") ?? undefined;
  const [reloadKey, setReloadKey] = useState(0);
  const [status, setStatus] = useState<ModelInfo["status"] | null>(null);
  const [kind, setKind] = useState<ModelInfo["kind"] | null>(null);
  const prevStatus = useRef<ModelInfo["status"] | null>(null);
  const [session, setSession] = useState<ChatSession | null>(null);
  const setChatOpen = useViewerStore((s) => s.setChatOpen);
  const pendingModelReload = useViewerStore((s) => s.pendingModelReload);
  const clearPendingModelReload = useViewerStore((s) => s.clearPendingModelReload);
  const stagedPreview = useViewerStore((s) => s.stagedPreview);
  const modelCreated = useViewerStore((s) => s.modelCreated);
  const clearModelCreated = useViewerStore((s) => s.clearModelCreated);
  const navigate = useNavigate();
  const [stagedBanner, setStagedBanner] = useState(false);

  // 模型状态轮询：converting→ready 自动重载查看器（AI commit 后走这条路刷新）
  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    const check = () =>
      fetchModel(id)
        .then((m) => {
          if (!cancelled) {
            setStatus(m.status);
            setKind(m.kind ?? "ifc");
          }
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
    // A3：URL 带 project 参数 → 绑定项目会话（1 session = 1 project）；否则绑模型会话（现状）
    const sessionPromise = projectId
      ? createChatSessionByProject("项目对话", projectId)
      : createChatSession("项目对话", id);
    sessionPromise
      .then((s) => {
        if (!cancelled) setSession(s);
      })
      .catch(() => {
        /* chat 服务不可用时页面其余功能不受影响 */
      });
    return () => {
      cancelled = true;
    };
  }, [id, projectId]);

  // 首次进入自动展开一次（让入口可发现）；之后由 Toolbar 按钮控制
  useEffect(() => {
    if (session) setChatOpen(true);
  }, [session?.chatSessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  // model.created：AI init_model 创建新模型 → 切到新模型渲染（保留 project 参数）。
  // nonce 保证连续多个新模型都触发；消费后清零。
  useEffect(() => {
    if (!modelCreated) return;
    const target = modelCreated.modelId;
    clearModelCreated();
    if (target === id) {
      setReloadKey((k) => k + 1); // 同一模型重载（理论上 init_model 是新 id，兜底）
      return;
    }
    const qs = projectId ? `?project=${encodeURIComponent(projectId)}` : "";
    navigate(`/view/${target}${qs}`, { replace: true });
  }, [modelCreated, id, projectId, navigate, clearModelCreated]);

  // IFC 引擎切换（key 变化触发查看器整树重挂载，与 reloadKey 同机制）
  const [engine, setEngine] = useState<ViewerEngine>(readEngine);
  const switchEngine = (next: ViewerEngine) => {
    localStorage.setItem(ENGINE_KEY, next);
    setEngine(next);
  };

  // AI 中间结果预览（viewer.staged → stagedPreview，nonce 保证连续事件都触发）：
  // - dxf：render.json 直挂，快 → 自动 reloadKey+1
  // - ifc + webifc：IfcLiteViewer 直读 downloads，快 → 自动重挂
  // - ifc + xeokit：重转 XKT 慢且闪烁 → 画布角标，点击才 reload
  useEffect(() => {
    if (!stagedPreview || stagedPreview.modelId !== id) return;
    if (stagedPreview.kind === "dxf" || engine === "webifc") {
      setReloadKey((k) => k + 1);
      setStagedBanner(false);
    } else {
      setStagedBanner(true);
    }
  }, [stagedPreview, id, engine]);

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
      {kind === null ? null : kind === "dxf" ? (
        // DesignPanel 纯 REST+store（无 viewer context 依赖），直接挂侧栏即可
        <div className="viewer-split">
          <DxfViewer key={reloadKey} modelId={id} />
          <aside className="design-side">
            <DesignPanel modelId={id} />
          </aside>
        </div>
      ) : engine === "webifc" ? (
        <div className="viewer-split">
          <button
            type="button"
            className="engine-switch-btn"
            onClick={() => switchEngine("xeokit")}
          >
            xeokit 引擎
          </button>
          <Suspense fallback={<div className="viewer-status">引擎加载中…</div>}>
            <IfcLiteViewer key={`${reloadKey}-webifc`} modelId={id} />
          </Suspense>
          <aside className="design-side">
            <DesignPanel modelId={id} />
          </aside>
        </div>
      ) : (
        <ViewerProvider key={`${reloadKey}-xeokit`} modelId={id}>
          {stagedBanner && (
            <button
              type="button"
              className="staged-preview-btn"
              onClick={() => {
                setReloadKey((k) => k + 1);
                setStagedBanner(false);
              }}
            >
              AI 中间结果 · 点击预览
            </button>
          )}
          <button
            type="button"
            className="engine-switch-btn"
            onClick={() => switchEngine("webifc")}
          >
            web-ifc 引擎
          </button>
          <Toolbar id={id} />
          <ModelTreePanel />
          <PropertyPanel modelId={id} />
          <IssuePanel modelId={id} />
          <DiffPanel modelId={id} />
          <DesignPanel modelId={id} />
        </ViewerProvider>
      )}
      {session && <ChatSidebar session={session} />}
    </div>
  );
}
