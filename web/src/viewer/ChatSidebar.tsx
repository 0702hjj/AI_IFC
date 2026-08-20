// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// ChatSidebar：挂在项目页右侧的 AI 对话侧边栏（可展开/收敛、可拖拽宽度）。
// 会话由 ViewerPage 在进入页面时建立/复用，经 props 传入；本组件只负责
// 输入发送、中途终止与外壳渲染——消息流状态机（历史回填 + SSE 监听）在
// useChatStream，part 展示子组件（ToolCard/SubagentPanel/ReasoningBlock）在
// ChatSidebarParts，SSE 解析纯函数在 chatStreamUtils（W-0049 行数门控拆分）。
import { useEffect, useRef, useState } from "react";
import { postChatMessage, abortChatSession, type ChatSession } from "@/api/client";
import { useViewerStore } from "./store";
import { useChatStream } from "./useChatStream";
import { MarkdownBubble, ReasoningBlock, SubagentPanel, ToolCard } from "./ChatSidebarParts";
import "./ChatSidebar.css";

export function ChatSidebar({ session }: { session: ChatSession }) {
  const chatOpen = useViewerStore((s) => s.chatOpen);
  const setChatOpen = useViewerStore((s) => s.setChatOpen);
  const { messages, setMessages, subagents, busy, setBusy, connLost } = useChatStream(session);
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, chatOpen]);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    setMessages((prev) => [...prev, { id: `u-${Date.now()}`, role: "user", kind: "text", text }]);
    try {
      await postChatMessage(session.chatSessionId, text);
    } catch (e) {
      setBusy(false);
      setMessages((prev) => [
        ...prev,
        { id: `e-${Date.now()}`, role: "system", kind: "system", text: `发送失败：${(e as Error).message}` },
      ]);
    }
  };

  const stop = async () => {
    try {
      await abortChatSession(session.chatSessionId);
    } catch {
      /* 即使 abort 请求失败，session.idle 事件也会把 busy 清掉 */
    }
  };

  if (!chatOpen) return null;

  return (
    <aside className="chat-sidebar" style={{ width: getSidebarWidth() }}>
      <header className="chat-sidebar-header">
        <span>AI 对话</span>
        <button className="chat-collapse" onClick={() => setChatOpen(false)} title="收起">
          ✕
        </button>
      </header>
      <div className="chat-resizer" onMouseDown={startResize} title="拖拽调整宽度" />
      {connLost && <div className="chat-conn-lost">⚠ 连接中断，正在重连…</div>}
      {subagents.length > 0 && <SubagentPanel groups={subagents} />}
      <div className="chat-messages">
        {messages.map((m) => {
          if (m.kind === "tool" && m.tool) return <ToolCard key={m.id} tool={m.tool} />;
          if (m.kind === "reasoning") return <ReasoningBlock key={m.id} text={m.text || ""} />;
          return (
            <div key={m.id} className={`chat-msg chat-msg-${m.role}`}>
              {m.text && (m.role === "assistant" ? (
                <MarkdownBubble text={m.text} />
              ) : (
                <div className="chat-bubble">{m.text}</div>
              ))}
            </div>
          );
        })}
        {busy && <div className="chat-msg chat-msg-assistant"><div className="chat-typing">AI 正在工作…</div></div>}
        <div ref={bottomRef} />
      </div>
      <div className="chat-inputbar">
        <textarea
          value={input}
          placeholder={session.modelId ? "描述修改需求…" : "描述想建的模型…"}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
        />
        {busy ? (
          <button className="chat-stop" onClick={stop} title="停止 AI 当前执行">⏹ 停止</button>
        ) : (
          <button className="chat-primary" disabled={!input.trim()} onClick={send}>发送</button>
        )}
      </div>
    </aside>
  );
}

// --- 宽度持久化（P-C 拖拽） ---
const WIDTH_KEY = "chatSidebarWidth";
const MIN_W = 300;
const MAX_W = 720;
function getSidebarWidth(): number {
  const saved = Number(localStorage.getItem(WIDTH_KEY));
  return saved >= MIN_W && saved <= MAX_W ? saved : 380;
}
function startResize(e: React.MouseEvent) {
  e.preventDefault();
  const aside = (e.currentTarget as HTMLElement).parentElement as HTMLElement;
  const startX = e.clientX;
  const startW = aside.offsetWidth;
  const onMove = (ev: MouseEvent) => {
    // 侧边栏贴右，鼠标左移 = 变宽
    const w = Math.min(MAX_W, Math.max(MIN_W, startW + (startX - ev.clientX)));
    aside.style.width = `${w}px`;
  };
  const onUp = () => {
    localStorage.setItem(WIDTH_KEY, String(aside.offsetWidth));
    window.removeEventListener("mousemove", onMove);
    window.removeEventListener("mouseup", onUp);
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
  };
  document.body.style.cursor = "col-resize";
  document.body.style.userSelect = "none";
  window.addEventListener("mousemove", onMove);
  window.addEventListener("mouseup", onUp);
}
