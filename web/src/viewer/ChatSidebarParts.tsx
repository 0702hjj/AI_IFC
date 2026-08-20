// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// ChatSidebar 的展示子组件（W-0049 从 ChatSidebar.tsx 抽出，渲染逻辑逐字保留）：
//   - ToolCard       工具调用卡片：标题 + 状态图标 + 可折叠 input/output/error
//   - SubagentPanel  子 agent 边栏：按 subagentId 分组展示 text/tool 片段
//   - ReasoningBlock 思考链（可折叠，默认收起）
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { SubagentGroup, ToolInfo } from "./chatStreamTypes";

// --- 可折叠的工具调用卡片：标题常显（状态图标 + title），input/output/error 默认折叠 ---
export function ToolCard({ tool }: { tool: ToolInfo }) {
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
export function SubagentPanel({ groups }: { groups: SubagentGroup[] }) {
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
export function ReasoningBlock({ text }: { text: string }) {
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

// assistant 文本气泡走 markdown（对齐 opencode GUI）；user 纯文本。
export function MarkdownBubble({ text }: { text: string }) {
  return (
    <div className="chat-bubble chat-markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  );
}
