// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// ChatSidebar：挂在项目页右侧的 AI 对话侧边栏（可展开/收敛、可拖拽宽度）。
// 会话由 ViewerPage 在进入页面时建立/复用，经 props 传入；本组件只负责
// 消息流（SSE 流式渲染）、输入发送、中途终止与系统事件提示。
//
// 渲染三种 part（对齐 opencode GUI）：
//   - text      assistant 走 markdown；user 纯文本
//   - reasoning 思考链（可折叠，默认收起）
//   - tool      工具调用卡片：标题 + 状态图标 + 可折叠 input/output/error
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { postChatMessage, abortChatSession, chatEventsUrl, fetchChatMessages, type ChatSession } from "@/api/client";
import { useViewerStore } from "./store";
import "./ChatSidebar.css";

type ToolStatus = "running" | "completed" | "error";
interface ToolInfo {
  name: string;
  title?: string;
  status: ToolStatus;
  input?: string;
  output?: string;
  error?: string;
}
interface ChatMsg {
  id: string;
  role: "user" | "assistant" | "system";
  kind: "text" | "tool" | "reasoning" | "system";
  text?: string;
  tool?: ToolInfo;
}

// 子 agent 边栏分组：一个 subagentId 一组（persona 徽章 + 运行状态 + part 流）。
interface SubagentPart {
  id: string;
  kind: "text" | "tool";
  text?: string;
  tool?: ToolInfo;
}
interface SubagentGroup {
  id: string;
  persona: string;
  task?: string;
  status: "running" | "finished";
  parts: SubagentPart[];
}

const WELCOME = "已绑定当前项目，告诉 AI 要修改什么、或从零建造什么吧。";

function mapStatus(s?: string): ToolStatus {
  if (s === "completed") return "completed";
  if (s === "error" || s === "failed") return "error";
  return "running";
}

// 把任意 input（object/string）格式化为可展示文本。
function fmtInput(input: unknown): string | undefined {
  if (input == null || input === "") return undefined;
  if (typeof input === "string") return input;
  try {
    return JSON.stringify(input, null, 2);
  } catch {
    return String(input);
  }
}

// 安全提取 session.error 的错误文本（opencode 的 error 字段可能是对象/字符串/嵌套，统一兜底防 [object Object]）。
function extractErrText(d: any): string {
  const err = d?.error ?? d?.properties?.error;
  if (typeof err === "string") return err;
  if (err && typeof err === "object") return err.message || err.error || err.name || JSON.stringify(err).slice(0, 300);
  if (typeof d?.message === "string") return d.message;
  return JSON.stringify(d).slice(0, 300);
}

// 安全解析 SSE 帧：非法 JSON 跳过（返回 undefined），不中断事件流。
function parseEventData(e: Event): any | undefined {
  try {
    return JSON.parse((e as MessageEvent).data);
  } catch {
    return undefined;
  }
}

export function ChatSidebar({ session }: { session: ChatSession }) {
  const chatOpen = useViewerStore((s) => s.chatOpen);
  const setChatOpen = useViewerStore((s) => s.setChatOpen);
  const flagPendingModelReload = useViewerStore((s) => s.flagPendingModelReload);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [subagents, setSubagents] = useState<SubagentGroup[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [connLost, setConnLost] = useState(false);
  const rolesRef = useRef<Map<string, string>>(new Map());
  const bottomRef = useRef<HTMLDivElement | null>(null);

  // upsert：按 id 更新或追加一条消息。
  const upsert = (msg: ChatMsg) =>
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.id === msg.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = { ...next[idx], ...msg };
        return next;
      }
      return [...prev, msg];
    });

  // upsertSubPart：把带 subagentId 的 part 并入对应子 agent 分组（无则忽略）。
  const upsertSubPart = (subID: string, part: SubagentPart) =>
    setSubagents((prev) =>
      prev.map((g) => {
        if (g.id !== subID) return g;
        const idx = g.parts.findIndex((p) => p.id === part.id);
        if (idx >= 0) {
          const parts = [...g.parts];
          parts[idx] = { ...parts[idx], ...part };
          return { ...g, parts };
        }
        return { ...g, parts: [...g.parts, part] };
      }),
    );

  useEffect(() => {
    // 会话连续：重新打开时回填历史消息（text/reasoning/tool 三种 part 都还原）
    fetchChatMessages(session.chatSessionId)
      .then((msgs) => {
        const history: ChatMsg[] = [];
        for (const m of msgs) {
          rolesRef.current.set(m.info.id, m.info.role);
          const role = m.info.role === "user" ? "user" : "assistant";
          for (const p of m.parts) {
            if (p.type === "text" && p.text) {
              history.push({ id: p.id || m.info.id, role, kind: "text", text: p.text });
            } else if (p.type === "reasoning" && p.text) {
              history.push({ id: p.id || `r-${m.info.id}`, role: "assistant", kind: "reasoning", text: p.text });
            } else if (p.type === "tool") {
              const st = p.state || {};
              history.push({
                id: p.id || `t-${m.info.id}-${p.tool}`,
                role: "assistant",
                kind: "tool",
                tool: {
                  name: p.tool || "tool",
                  title: st.title,
                  status: mapStatus(st.status),
                  input: fmtInput(st.input),
                  output: st.output,
                  error: st.error,
                },
              });
            }
          }
        }
        setMessages((prev) => {
          // 与 SSE 增量合并而非覆盖（W-0006）：SSE 先到、历史后到时按 id 去重，历史在前、增量在后
          const live = prev.filter((m) => m.id !== "welcome");
          if (history.length === 0 && live.length === 0)
            return [{ id: "welcome", role: "system", kind: "system", text: WELCOME }];
          const liveIds = new Set(live.map((m) => m.id));
          return [...history.filter((h) => !liveIds.has(h.id)), ...live];
        });
      })
      .catch(() =>
        setMessages((prev) =>
          prev.length > 0 ? prev : [{ id: "welcome", role: "system", kind: "system", text: WELCOME }],
        ),
      );

    const es = new EventSource(chatEventsUrl(session.chatSessionId));

    // 断连提示；EventSource 原生自动重连（带 Last-Event-ID，服务端补发 missed 事件），open 后恢复
    es.addEventListener("error", () => setConnLost(true));
    es.addEventListener("open", () => setConnLost(false));

    es.addEventListener("message.updated", (e) => {
      const d = parseEventData(e);
      if (!d) return;
      const info = d.info ?? d;
      if (info?.id && info?.role) rolesRef.current.set(info.id, info.role);
    });

    // message.part.updated：建立 part 行 / 更新 tool state。
    // 真实结构：d.part = {type, text, messageID, id, ...tool 有 state}（无 delta 字段）。
    // 文本增量在独立的 message.part.delta 事件，故此处 text/reasoning 只"建行不覆盖"。
    // 带 subagentId 字段的帧是子 agent 事件 → 分流右侧边栏，不进主消息流。
    es.addEventListener("message.part.updated", (e) => {
      const d = parseEventData(e);
      if (!d) return;
      const part = d.part;
      if (!part) return;
      if (d.subagentId) {
        if (part.type === "text") {
          upsertSubPart(d.subagentId, { id: part.id, kind: "text", text: part.text || "" });
        } else if (part.type === "tool") {
          const st = part.state || {};
          upsertSubPart(d.subagentId, {
            id: part.id,
            kind: "tool",
            tool: {
              name: part.tool || "tool",
              title: st.title,
              status: mapStatus(st.status),
              input: fmtInput(st.input),
              output: st.output,
              error: st.error,
            },
          });
        }
        return;
      }
      if (part.type === "text") {
        if (rolesRef.current.get(part.messageID) === "user") return; // 用户输入已本地乐观插入
        setMessages((prev) =>
          prev.some((m) => m.id === part.id)
            ? prev // 已存在：text 交给 delta 累加，不覆盖
            : [...prev, { id: part.id, role: "assistant", kind: "text", text: part.text || "" }],
        );
      } else if (part.type === "reasoning") {
        setMessages((prev) =>
          prev.some((m) => m.id === part.id)
            ? prev
            : [...prev, { id: part.id, role: "assistant", kind: "reasoning", text: part.text || "" }],
        );
      } else if (part.type === "tool") {
        const st = part.state || {};
        upsert({
          id: part.id,
          role: "assistant",
          kind: "tool",
          tool: {
            name: part.tool || "tool",
            title: st.title,
            status: mapStatus(st.status),
            input: fmtInput(st.input),
            output: st.output,
            error: st.error,
          },
        });
      }
    });

    // message.part.delta：真正的流式文本增量（text/reasoning 都累加到 m.text）。
    // 结构：d = {sessionID, messageID, partID, field:"text", delta:"xxx"}。
    // 带 subagentId 的增量并入边栏分组的 part 文本。
    es.addEventListener("message.part.delta", (e) => {
      const d = parseEventData(e);
      if (!d || d.field !== "text" || !d.delta) return;
      if (d.subagentId) {
        setSubagents((prev) =>
          prev.map((g) => {
            if (g.id !== d.subagentId) return g;
            const idx = g.parts.findIndex((p) => p.id === d.partID);
            if (idx < 0) return g; // part 行还没建，等 part.updated
            const parts = [...g.parts];
            parts[idx] = { ...parts[idx], text: (parts[idx].text || "") + d.delta };
            return { ...g, parts };
          }),
        );
        return;
      }
      setMessages((prev) => {
        const idx = prev.findIndex((m) => m.id === d.partID);
        if (idx < 0) return prev; // part 行还没建，等 part.updated
        const next = [...prev];
        next[idx] = { ...next[idx], text: (next[idx].text || "") + d.delta };
        return next;
      });
    });

    // subagent.status：子 agent 生命周期（started → 建组；finished → 组状态置完成）
    es.addEventListener("subagent.status", (e) => {
      const d = parseEventData(e);
      if (!d?.subagentId) return;
      if (d.status === "started") {
        setSubagents((prev) =>
          prev.some((g) => g.id === d.subagentId)
            ? prev
            : [...prev, { id: d.subagentId, persona: d.persona || "agent", task: d.task, status: "running", parts: [] }],
        );
      } else if (d.status === "finished") {
        setSubagents((prev) =>
          prev.map((g) => (g.id === d.subagentId ? { ...g, status: "finished" } : g)),
        );
      }
    });

    // part 被移除（消息重写 / abort 中止进行中的 part）→ 同步删行，避免残留
    es.addEventListener("message.part.removed", (e) => {
      const d = parseEventData(e);
      const id = d?.part?.id;
      if (!id) return;
      setMessages((prev) => prev.filter((m) => m.id !== id));
    });

    es.addEventListener("session.status", (e) => {
      const d = parseEventData(e);
      if (!d) return;
      setBusy(d.status?.type === "busy" || d.status?.type === "retry");
    });
    es.addEventListener("session.idle", () => setBusy(false));

    // 会话级错误（如模型调用失败）→ 红色系统消息。error 字段可能是对象，需安全提取避免 [object Object]。
    es.addEventListener("session.error", (e) => {
      const d = parseEventData(e);
      if (!d) return;
      setMessages((prev) => [
        ...prev,
        { id: `err-${Date.now()}`, role: "system", kind: "system", text: `❌ ${extractErrText(d)}` },
      ]);
    });

    const sys = (type: string) => (e: Event) => {
      const data = parseEventData(e);
      if (!data) return;
      const text =
        type === "viewer.committed"
          ? `✅ 修改已落盘（版本 ${data.version || "?"}），模型转换中…`
          : `⚠️ 落盘失败（${data.step}）：${data.reason}`;
      if (type === "viewer.committed") flagPendingModelReload(); // 标记待刷新：前端轮询到 ready 即重载画布
      setMessages((prev) => [...prev, { id: `sys-${Date.now()}`, role: "system", kind: "system", text }]);
    };
    es.addEventListener("viewer.committed", sys("viewer.committed"));
    es.addEventListener("viewer.notify_failed", sys("viewer.notify_failed"));

    return () => es.close();
  }, [session.chatSessionId]); // eslint-disable-line react-hooks/exhaustive-deps

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
                <div className="chat-bubble chat-markdown">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
                </div>
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

// --- 可折叠的工具调用卡片：标题常显（状态图标 + title），input/output/error 默认折叠 ---
function ToolCard({ tool }: { tool: ToolInfo }) {
  const [open, setOpen] = useState(false);
  const icon = tool.status === "completed" ? "✓" : tool.status === "error" ? "✗" : "⟳";
  const statusCls = `chat-tool-${tool.status}`;
  const detail = tool.input || tool.output || tool.error;
  return (
    <div className={`chat-toolcard ${statusCls}`}>
      <div className="chat-toolcard-head" onClick={() => detail && setOpen((v) => !v)} role={detail ? "button" : undefined}>
        <span className="chat-tool-icon">{icon}</span>
        <span className="chat-tool-title">{tool.title || tool.name}</span>
        {detail && <span className="chat-tool-chevron">{open ? "▾" : "▸"}</span>}
      </div>
      {open && detail && (
        <div className="chat-tool-detail">
          {tool.input && <pre className="chat-tool-block chat-tool-input">{tool.input}</pre>}
          {tool.output && <pre className="chat-tool-block chat-tool-output">{tool.output}</pre>}
          {tool.error && <pre className="chat-tool-block chat-tool-error">{tool.error}</pre>}
        </div>
      )}
    </div>
  );
}

// --- 可折叠的子 agent 边栏：按 subagentId 分组展示子 agent 的 text/tool 片段 ---
// 生成过程中自动出现（subagent.status started），主会话消息流不受影响。
function SubagentPanel({ groups }: { groups: SubagentGroup[] }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="chat-subagents" data-testid="subagent-panel">
      <div className="chat-subagents-head" onClick={() => setOpen((v) => !v)} role="button">
        <span>🤖 子 Agent（{groups.length}）</span>
        <span className="chat-tool-chevron">{open ? "▾" : "▸"}</span>
      </div>
      {open &&
        groups.map((g) => (
          <div key={g.id} className="chat-subagent-group" data-subagent-id={g.id}>
            <div className="chat-subagent-title">
              <span className="chat-subagent-badge">{g.persona}</span>
              <span className={`chat-subagent-status chat-subagent-${g.status}`}>
                {g.status === "finished" ? "✓" : "⟳"}
              </span>
            </div>
            {g.task && <div className="chat-subagent-task">{g.task}</div>}
            <div className="chat-subagent-parts">
              {g.parts.map((p) =>
                p.kind === "tool" && p.tool ? (
                  <ToolCard key={p.id} tool={p.tool} />
                ) : (
                  <div key={p.id} className="chat-subagent-text">{p.text}</div>
                ),
              )}
            </div>
          </div>
        ))}
    </div>
  );
}

// --- 可折叠的思考链：默认收起，点击展开 ---
function ReasoningBlock({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="chat-reasoning">
      <div className="chat-reasoning-head" onClick={() => setOpen((v) => !v)} role="button">
        <span>💭 思考过程</span>
        <span className="chat-tool-chevron">{open ? "▾" : "▸"}</span>
      </div>
      {open && <div className="chat-reasoning-body">{text}</div>}
    </div>
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
