#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj
"""agent_tui.py —— opencode 风格的终端交互（textual TUI）。

区分显示：思考内容（reasoning，灰色斜体）/ 实际回复（text，正常色）/
工具调用（独立 box 框：running→completed/error，含输入输出）。
流程与 server 实际设计一致：创建项目（kind 必选）→ 项目会话 → 对话（SSE）→ HITL。

运行：python3 agent_tui.py（需 textual：pip install textual）
依赖服务：edit :8100 / cad :8200 / server :8090（未起自动拉起，端口一一对应）。
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, RichLog, Static

REPO = Path(__file__).resolve().parents[3]
DATA_DIR = os.environ.get("VIEWER_DATA_DIR", str(REPO / "data"))
SERVER_PORT = int(os.environ.get("VIEWER_SERVER_PORT", "8090"))
EDIT_PORT = int(os.environ.get("VIEWER_EDIT_PORT", "8100"))
CAD_PORT = int(os.environ.get("VIEWER_CAD_PORT", "8200"))
LOG_DIR = Path(os.environ.get("TMPDIR", "/tmp"))


def url(port, path):
    return f"http://127.0.0.1:{port}{path}"


def http_json(method, port, path, body=None, timeout=60):
    req = urllib.request.Request(url(port, path), method=method)
    req.add_header("Content-Type", "application/json")
    data = None if body is None else json.dumps(body).encode("utf-8")
    with urllib.request.urlopen(req, data, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def is_alive(port, path="/health"):
    try:
        with urllib.request.urlopen(url(port, path), timeout=1):
            return True
    except urllib.error.HTTPError:
        return True
    except OSError:
        return False


def launch(name, cwd, cmd):
    env = os.environ.copy()
    # 共享 VIEWER_DATA_DIR（AGENTS 硬规则：edit-service/cad 与 Go server 必须同一 data 绝对路径，
    # 否则 stage/run script 时 edit-service 找不到 Go 写的 uploads/{id} 文件 → 404 model not found）
    env["VIEWER_DATA_DIR"] = DATA_DIR
    with open(LOG_DIR / f"agent_demo_{name}.log", "a") as f:
        subprocess.Popen(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True, env=env)


def ensure_services():
    if not is_alive(EDIT_PORT):
        launch("edit", REPO / "services/ifc",
               ["uv", "run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(EDIT_PORT)])
    if not is_alive(CAD_PORT):
        launch("cad", REPO / "services/cad",
               ["uv", "run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(CAD_PORT)])
    if not is_alive(SERVER_PORT, "/api/v1/chat/sessions"):
        launch("server", REPO / "server", ["go", "run", "./cmd/server"])
    deadline = time.time() + 90
    while not is_alive(SERVER_PORT, "/api/v1/chat/sessions"):
        if time.time() > deadline:
            raise RuntimeError(f"server :{SERVER_PORT} 90s 内未就绪，看 {LOG_DIR}/agent_demo_server.log")
        time.sleep(2)


def sse_frames(cid):
    """会话 SSE 帧生成器：(event, data)；session.idle/error 后停止。"""
    req = urllib.request.Request(url(SERVER_PORT, f"/api/v1/chat/sessions/{cid}/events"))
    with urllib.request.urlopen(req, timeout=600) as r:
        event, data_lines = None, []
        while True:
            line = r.readline()
            if not line:
                break
            line = line.decode("utf-8", "replace").rstrip("\r\n")
            if line == "":
                if event or data_lines:
                    try:
                        data = json.loads("\n".join(data_lines)) if data_lines else {}
                    except ValueError:
                        data = {"raw": "\n".join(data_lines)}
                    yield event, data
                    if event in ("session.idle", "session.error"):
                        return
                event, data_lines = None, []
            elif line.startswith("event:"):
                event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:"):].strip())


# ---- UI 组件 ----------------------------------------------------------------

class SetupScreen(ModalScreen):
    """项目选择：历史项目（会话）列表优先，选中即进入项目会话；或 n 新建项目。

    接口与前端 LibraryPage 一致（GET /api/v1/chat/sessions 拉历史会话）。
    dismiss 结果：
      ("session", chatSessionId, projectId) —— 进历史项目会话
      ("new", title, kind)                  —— 新建项目 + 会话
    """

    def __init__(self, **kw):
        super().__init__(**kw)
        self.sessions = []
        self.mode = "pick"  # pick -> new

    def compose(self) -> ComposeResult:
        yield Static("加载历史项目…", id="list")
        yield Static("")
        yield Static("输入序号进入历史项目，或 n 新建项目", id="hint")
        yield Input(placeholder="n", id="pick")
        yield Static("", id="formtitle")
        yield Input(placeholder="项目名（回车=未命名项目）", id="title")
        yield Input(placeholder="项目类型：1=cad 2=ifc 3=cad->ifc（默认 1）", id="kind")

    def on_mount(self) -> None:
        self.query_one("#title", Input).display = False
        self.query_one("#kind", Input).display = False
        self.query_one("#title", Input).styles.display = "none"
        self.query_one("#kind", Input).styles.display = "none"
        self.query_one("#formtitle", Static).update("")
        self.load_sessions()

    @work(thread=True)
    def load_sessions(self) -> None:
        # 等服务就绪（后台 prepare_services 拉起中），再拉历史项目会话列表
        app = self.app
        deadline = time.time() + 95
        while not getattr(app, "services_ready", False):
            if time.time() > deadline:
                break
            time.sleep(0.5)
        try:
            r = http_json("GET", SERVER_PORT, "/api/v1/chat/sessions", timeout=10)
            self.sessions = r.get("data") or []
        except Exception as e:
            self.sessions = []
            app.call_from_thread(self.query_one("#list", Static).update,
                                 f"[red]拉历史项目失败：{e}[/]\n[dim]可直接 n 新建[/]")
            app.call_from_thread(self.query_one("#pick", Input).focus)
            return
        if not self.sessions:
            app.call_from_thread(self.query_one("#list", Static).update,
                                 "[dim]（暂无历史项目，输 n 新建）[/]")
        else:
            lines = ["[bold]历史项目（会话）——点序号进入：[/]"]
            for i, s in enumerate(self.sessions, 1):
                pid = s.get("projectId") or "-"
                when = s.get("createdAt", "")[:16].replace("T", " ")
                lines.append(f"  [{i}] {s.get('title','未命名')}  [dim]({pid} · {when})[/]")
            app.call_from_thread(self.query_one("#list", Static).update, "\n".join(lines))
        app.call_from_thread(self.query_one("#pick", Input).focus)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        val = event.value.strip()
        if self.mode == "pick":
            if val.lower() == "n" or not self.sessions:
                self.to_new_form()
                return
            try:
                idx = int(val) - 1
                s = self.sessions[idx]
                self.dismiss(("session", s.get("chatSessionId"), s.get("projectId")))
            except (ValueError, IndexError):
                self.query_one("#hint", Static).update("[red]无效序号[/] 输入序号或 n")
                self.query_one("#pick", Input).value = ""
            return
        if event.input.id == "title":
            self.query_one("#kind", Input).focus()
            return
        title = self.query_one("#title", Input).value.strip() or "未命名项目"
        kind = {"1": "cad", "2": "ifc", "3": "cad->ifc"}.get(
            self.query_one("#kind", Input).value.strip() or "1")
        if kind is None:
            self.query_one("#kind", Input).value = ""
            return
        self.dismiss(("new", title, kind))

    def to_new_form(self) -> None:
        self.mode = "new"
        self.query_one("#hint", Static).update("新建项目（kind 决定 Agent 派发方向）")
        self.query_one("#pick", Input).styles.display = "none"
        self.query_one("#formtitle", Static).update("项目名 + 项目类型：")
        self.query_one("#title", Input).styles.display = "block"
        self.query_one("#kind", Input).styles.display = "block"
        self.query_one("#title", Input).focus()


class QuestionScreen(ModalScreen):
    """HITL：ask_user 提问，收集回答。"""

    def __init__(self, question: str, **kw):
        super().__init__(**kw)
        self.question = question

    def compose(self) -> ComposeResult:
        yield Static(f"[bold yellow]❓ 需要确认[/]\n{self.question}", id="qtext")
        yield Input(placeholder="输入回答后回车", id="answer")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())


class AgentApp(App):
    TITLE = "AI_IFC Agent"
    SUB_TITLE = "opencode 风格终端"
    CSS = """
    Screen { layout: vertical; }
    #status { height: 1; background: $surface; color: $text; padding: 0 1; }
    #messages { height: 1fr; border: round $primary; overflow-y: auto; }
    #messages Static { padding: 0 1; }
    #inputrow { height: 3; }
    Input { margin: 0 1; }
    """

    def __init__(self):
        super().__init__()
        self.cid = self.pid = self.title = self.kind = None
        self.streams = {}  # partID -> (Static, accumulated_text)
        self.services_ready = False
        self.service_error = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("…", id="status")
        yield VerticalScroll(id="messages")
        yield Footer()
        yield Input(placeholder="输入消息（/plans 看方案历史 /quit 退出）", id="chatinput")

    def on_mount(self) -> None:
        # 立即弹首次设置表单（不等服务），服务后台准备——用户马上能打字
        self.query_one("#chatinput", Input).disabled = True
        self.set_status("服务启动中…")
        self.prepare_services()
        self.push_screen(SetupScreen(), self.on_setup_result)

    @work(thread=True)
    def prepare_services(self) -> None:
        """后台拉起依赖服务（edit/cad/server），start_project 前轮询就绪。"""
        try:
            ensure_services()
            self.services_ready = True
            self.service_error = ""
        except RuntimeError as e:
            self.services_ready = False
            self.service_error = str(e)

    def on_setup_result(self, result) -> None:
        """SetupScreen 提交回调（textual 8：dismiss 结果经 push_screen callback）。
        ("session", cid, pid) → 直接进历史项目会话；("new", title, kind) → 新建。"""
        if not result:
            return
        if result[0] == "session":
            _, cid, pid = result
            self.cid, self.pid = cid, pid
            self.enter_session(cid, pid)
        else:
            _, title, kind = result
            self.start_project(title, kind)

    @work(thread=True)
    def enter_session(self, cid: str, pid: str) -> None:
        """进入历史项目会话：等服务就绪（后台 prepare_services）后启用输入。"""
        deadline = time.time() + 95
        while not self.services_ready:
            if time.time() > deadline:
                self.call_from_thread(self.emit, f"[red]服务未就绪：{self.service_error}[/]")
                return
            time.sleep(0.5)
        self.call_from_thread(self.emit,
            f"[bold green]✓ 进入历史项目会话 {cid}（项目 {pid}）[/]\n[dim]可以开始对话了[/]")
        self.call_from_thread(self.ui_ready, f"项目 {pid} · 会话 {cid}")

    def on_question_result(self, result) -> None:
        """QuestionScreen 回答回调。"""
        if result is not None:
            self.send_answer(result)

    @work(thread=True)
    def start_project(self, title: str, kind: str) -> None:
        # 等服务就绪（表单已先弹出，这里最多等 95s）
        deadline = time.time() + 95
        while not self.services_ready:
            if time.time() > deadline:
                self.call_from_thread(self.emit, f"[red]服务未就绪：{self.service_error}[/]")
                return
            time.sleep(0.5)
        self.call_from_thread(self.set_status, "创建项目…")
        try:
            r = http_json("POST", SERVER_PORT, "/api/v1/chat/projects", {"title": title, "kind": kind})
            if r.get("code") != 0:
                self.call_from_thread(self.emit, f"[red]创建项目失败：{r}[/]")
                return
            pid = r["data"]["projectId"]
            s = http_json("POST", SERVER_PORT, "/api/v1/chat/sessions", {"title": title, "projectId": pid})
            cid = s["data"]["chatSessionId"]
            self.cid, self.pid = cid, pid
            self.call_from_thread(self.emit,
                f"[bold green]✓ 项目 {pid}（{kind}）→ 会话 {cid}[/]\n[dim]可以开始对话了[/]")
            self.call_from_thread(self.ui_ready, f"项目 {pid} · {kind} · 会话 {cid}")
        except Exception as e:
            self.call_from_thread(self.emit, f"[red]初始化失败：{e}[/]")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "chatinput" or self.cid is None:
            return
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        if text in ("/quit", "exit"):
            self.exit()
            return
        if text == "/plans":
            self.show_plans()
            return
        self.emit(f"\n[bold blue]你> [/]{text}")
        self.run_turn(text)

    @work(thread=True)
    def run_turn(self, text: str) -> None:
        try:
            http_json("POST", SERVER_PORT, f"/api/v1/chat/sessions/{self.cid}/messages", {"text": text}, timeout=10)
        except Exception as e:
            self.call_from_thread(self.emit, f"[red]发消息失败：{e}[/]")
            return
        # 当前 assistant 段：正文/reasoning 分块缓冲
        cur = {"text": "", "reasoning": ""}
        for event, data in sse_frames(self.cid):
            self.handle_frame(event, data, cur)

    def handle_frame(self, event: str, data: dict, cur: dict) -> None:
        if event == "message.part.delta" and data.get("delta"):
            part = str(data.get("partID", ""))
            d = data["delta"]
            if "reasoning" in part:
                cur["reasoning"] += d
                self.call_from_thread(self.stream, part, d, "dim italic")
            else:
                cur["text"] += d
                self.call_from_thread(self.stream, part, d, "")
        elif event == "message.part.updated":
            part = data.get("part", {})
            ptype = part.get("type")
            if ptype == "reasoning":
                cur["reasoning"] = ""
            elif ptype == "text":
                cur["text"] = ""
            elif ptype == "tool":
                self.call_from_thread(self.render_tool, part)
        elif event == "subagent.status":
            self.call_from_thread(self.emit,
                f"\n[cyan]⊞ 子agent {data.get('subagentId','')} {data.get('status','')} {data.get('task','')}[/]")
        elif event == "question.ask":
            self.active_question_id = data.get("interruptId", "")
            self.call_from_thread(self.push_screen, QuestionScreen(data.get("question", "")), self.on_question_result)
        elif event == "session.error":
            self.call_from_thread(self.emit, f"\n[red]错误：{data}[/]")

    def render_tool(self, part: dict) -> None:
        st = part.get("state", {})
        name = st.get("title", part.get("tool", "工具"))
        status = st.get("status", "running")
        color = {"running": "yellow", "completed": "green", "error": "red"}.get(status, "white")
        icon = {"running": "◌", "completed": "✓", "error": "✗"}.get(status, "?")
        lines = [f"[{color}]┌─ {icon} {name}[/]"]
        if st.get("input"):
            lines.append(f"[dim]  入参: {st['input'][:200]}[/]")
        if st.get("output"):
            lines.append(f"[{color}]  输出: {st['output'][:400]}[/]")
        if st.get("error"):
            lines.append(f"[red]  错误: {st['error'][:400]}[/]")
        lines.append(f"[{color}]└─[/]")
        self.emit("\n".join(lines))

    @work(thread=True)
    def send_answer(self, answer: str) -> None:
        try:
            http_json("POST", SERVER_PORT, f"/api/v1/chat/sessions/{self.cid}/answer",
                      {"interruptId": self.active_question_id, "answer": answer}, timeout=10)
        except Exception as e:
            self.call_from_thread(self.emit, f"[red]回答提交失败：{e}[/]")

    @work(thread=True)
    def show_plans(self) -> None:
        try:
            r = http_json("GET", SERVER_PORT, f"/api/v1/projects/{self.pid}/plan_history", timeout=15)
            self.call_from_thread(self.emit, "[dim]" + json.dumps(r.get("data"), ensure_ascii=False, indent=2)[:2000] + "[/]")
        except Exception as e:
            self.call_from_thread(self.emit, f"[red]拉方案历史失败：{e}[/]")

    def emit(self, msg: str = "") -> None:
        """写一个完整段落（RichLog 风格，无 end 参数——段落整体追加）。"""
        msgs = self.query_one("#messages", VerticalScroll)
        if msg:
            msgs.mount(Static(msg, markup=True))
            msgs.scroll_end(animate=False)

    def stream(self, part_id: str, delta: str, style: str = "") -> None:
        """打字机增量：持续更新同一 part 的 Static（区分 reasoning/text）。"""
        msgs = self.query_one("#messages", VerticalScroll)
        if part_id not in self.streams:
            st = Static("", markup=True)
            msgs.mount(st)
            self.streams[part_id] = [st, ""]
            msgs.scroll_end(animate=False)
        st, acc = self.streams[part_id]
        acc += delta
        self.streams[part_id][1] = acc
        st.update(f"[{style}]{acc}[/]" if style else acc)
        msgs.scroll_end(animate=False)

    def close_stream(self, part_id: str) -> None:
        """段落结束：part 定型，不再更新。"""
        self.streams.pop(part_id, None)

    def set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    def ui_ready(self, status_text: str) -> None:
        """初始化完成后的 UI 收尾（必须在 UI 线程执行）。"""
        self.set_status(status_text)
        inp = self.query_one("#chatinput", Input)
        inp.disabled = False
        inp.focus()


def main():
    if not sys.stdin.isatty():
        sys.exit("agent_tui.py 需要交互终端")
    AgentApp().run()


if __name__ == "__main__":
    main()
