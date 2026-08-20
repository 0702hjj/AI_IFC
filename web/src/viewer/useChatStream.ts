// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// useChatStream：ChatSidebar 的会话流 hook——历史回填 + SSE 监听 + 消息/子 agent 状态机。
// 从 ChatSidebar.tsx 抽出（W-0049 文件行数门控），事件处理逻辑逐字保留。
import { useEffect, useRef, useState } from "react";
import { chatEventsUrl, fetchChatMessages, type ChatSession } from "@/api/client";
import { useViewerStore } from "./store";
import { WELCOME, type ChatMsg, type SubagentGroup, type SubagentPart } from "./chatStreamTypes";
import { extractErrText, fmtInput, mapStatus, parseEventData } from "./chatStreamUtils";

export interface ChatQuestion {
  interruptId: string;
  question: string;
}

export function useChatStream(session: ChatSession) {
  const flagPendingModelReload = useViewerStore((s) => s.flagPendingModelReload);
  const flagStagedPreview = useViewerStore((s) => s.flagStagedPreview);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [subagents, setSubagents] = useState<SubagentGroup[]>([]);
  const [busy, setBusy] = useState(false);
  const [connLost, setConnLost] = useState(false);
  const [question, setQuestion] = useState<ChatQuestion | null>(null);
  const rolesRef = useRef<Map<string, string>>(new Map());

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
    // 会话连续：重新打开时回填历史消息（text/reasoning/tool 三种 part 都还原）。
    // 切会话时子 agent 边栏整组清空——分组属会话态，跨会话残留会错挂到新会话头上。
    setSubagents([]);
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

    // viewer.staged：run_script 沙箱成功后的中间产物就绪（每次成功都推，一个 turn 可多次）。
    // 只写 store（含 nonce），由 ViewerPage 按管线分流决定立即重载还是出角标；不进消息流。
    es.addEventListener("viewer.staged", (e) => {
      const d = parseEventData(e);
      if (!d || typeof d.modelId !== "string" || !d.modelId) return;
      if (d.kind !== "ifc" && d.kind !== "dxf") return;
      flagStagedPreview({ modelId: d.modelId, kind: d.kind });
    });

    // question.ask：HITL 提问（ask_user 中断）——前端弹输入框收集回答，经 /answer 续跑。
    es.addEventListener("question.ask", (e) => {
      const d = parseEventData(e);
      if (!d || typeof d.interruptId !== "string" || !d.interruptId) return;
      setQuestion({ interruptId: d.interruptId, question: String(d.question ?? "") });
    });

    return () => es.close();
  }, [session.chatSessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  return { messages, setMessages, subagents, busy, setBusy, connLost, question, setQuestion };
}
