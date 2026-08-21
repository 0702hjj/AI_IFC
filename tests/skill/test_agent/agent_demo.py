#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj
"""agent_demo.py —— 终端一键对话测试（业务流与 server 实际设计一致）。

流程（与前端 A3 / agent 工具面完全一致）：
  1. 创建项目（kind 必选：cad | ifc | cad->ifc）  -> POST /api/v1/chat/projects
  2. 创建项目会话（绑定 projectId）              -> POST /api/v1/chat/sessions
  3. 对话（SSE 流式）                             -> POST .../messages + GET .../events
  4. HITL（ask_user 中断 -> 回答）                -> POST .../answer
  5. 方案查看                                    -> GET /api/v1/projects/{pid}/plan_history

端口一一对应（可 env 覆盖）：server :8090 / edit-service :8100 / cad-edit-service :8200。
启动前自动探测端口，未起则拉起（edit/cad 用 uv run uvicorn，server 用 go run）。
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

REPO = Path(__file__).resolve().parents[3]
DATA_DIR = os.environ.get("VIEWER_DATA_DIR", str(REPO / "data"))
SERVER_PORT = int(os.environ.get("VIEWER_SERVER_PORT", "8090"))
EDIT_PORT = int(os.environ.get("VIEWER_EDIT_PORT", "8100"))
CAD_PORT = int(os.environ.get("VIEWER_CAD_PORT", "8200"))
LOG_DIR = Path(os.environ.get("TMPDIR", "/tmp"))


def url(port, path):
    return f"http://127.0.0.1:{port}{path}"


def http_json(method, port, path, body=None, timeout=60):
    """调用 REST 端点并解 envelope；HTTP/网络错误统一抛 RuntimeError。"""
    req = urllib.request.Request(url(port, path), method=method)
    req.add_header("Content-Type", "application/json")
    data = None if body is None else json.dumps(body).encode("utf-8")
    try:
        with urllib.request.urlopen(req, data, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return json.loads(raw)
        except ValueError:
            raise RuntimeError(f"HTTP {e.code}: {raw}") from e
    except OSError as e:
        raise RuntimeError(f"连接失败 {url(port, path)}: {e}") from e


def is_alive(port, path="/health"):
    try:
        with urllib.request.urlopen(url(port, path), timeout=1):
            return True
    except urllib.error.HTTPError:
        return True  # 有 HTTP 响应即活着（404 也算）
    except OSError:
        return False


def launch(name, cwd, cmd):
    logf = LOG_DIR / f"agent_demo_{name}.log"
    print(f"  [up] 启动 {name}: {' '.join(cmd)}  ->  {logf}")
    with open(logf, "a") as f:
        subprocess.Popen(
            cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, start_new_session=True,
        )


def ensure_services():
    """探测并拉起三个服务（端口一一对应，未起才拉起）。"""
    print("== 服务检查 ==")
    if not is_alive(EDIT_PORT):
        uv = shutil.which("uv")
        if not uv:
            sys.exit("未找到 uv——edit-service 无法启动（AGENTS：services/ifc 用 uv run）")
        launch("edit", REPO / "services/ifc",
               ["uv", "run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(EDIT_PORT)],
               )
    else:
        print(f"  [ok] edit-service    :{EDIT_PORT}")
    if not is_alive(CAD_PORT):
        uv = shutil.which("uv")
        if not uv:
            sys.exit("未找到 uv——cad-edit-service 无法启动")
        launch("cad", REPO / "services/cad",
               ["uv", "run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(CAD_PORT)],
               )
    else:
        print(f"  [ok] cad-edit-service:{CAD_PORT}")
    if not is_alive(SERVER_PORT, "/api/v1/chat/sessions"):
        launch("server", REPO / "server", ["go", "run", "./cmd/server"])
    else:
        print(f"  [ok] server           :{SERVER_PORT}")
    # 等待 server 就绪（go run 编译需时；最多 90s）
    deadline = time.time() + 90
    while not is_alive(SERVER_PORT, "/api/v1/chat/sessions"):
        if time.time() > deadline:
            sys.exit(f"server :{SERVER_PORT} 90s 内未就绪，看 {LOG_DIR}/agent_demo_server.log")
        time.sleep(2)
    print(f"  [ok] server            :{SERVER_PORT}  就绪")


def llm_status():
    cfg = REPO / "server" / "server_config.json"
    try:
        c = json.loads(cfg.read_text())
        key = c.get("llmAPIKey") or os.environ.get("VIEWER_LLM_API_KEY", "")
        model = c.get("llmModel") or os.environ.get("VIEWER_LLM_MODEL", "")
    except (OSError, ValueError):
        return "（读不到 server_config.json，未知）"
    if not key:
        return "⚠️  llmAPIKey 为空 → 回退 scriptedModel 离线模式（确定性 mock，无真实智能回复）"
    return f"✅  LLM 已配置（model={model or '默认'}）"


def sse_frames(cid):
    """订阅会话 SSE 流，逐帧产出 (event, data_dict)；turn 结束（idle/error）自动返回。"""
    req = urllib.request.Request(url(SERVER_PORT, f"/api/v1/chat/sessions/{cid}/events"))
    with urllib.request.urlopen(req, timeout=300) as r:
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


def create_project_flow():
    """第一步：创建项目（kind 必选）→ 创建项目会话。返回 (cid, pid)。"""
    print("\n== 创建项目 ==")
    title = input("项目名 [回车=未命名项目]: ").strip() or "未命名项目"
    print("项目类型（kind 必选，决定 Agent 派发方向）：")
    print("  1) cad      —— 生成 CAD 图纸（默认）")
    print("  2) ifc      —— 生成 IFC 模型")
    print("  3) cad->ifc —— 先 CAD 后 IFC 管线")
    choice = input("选择 [1]: ").strip() or "1"
    kind = {"1": "cad", "2": "ifc", "3": "cad->ifc"}.get(choice)
    while kind is None:
        choice = input("无效，重新选择 [1/2/3]: ").strip()
        kind = {"1": "cad", "2": "ifc", "3": "cad->ifc"}.get(choice)
    resp = http_json("POST", SERVER_PORT, "/api/v1/chat/projects", {"title": title, "kind": kind})
    if resp.get("code") != 0:
        sys.exit(f"创建项目失败: {resp}")
    pid = resp["data"]["projectId"]
    print(f"  [项目] {pid}  kind={resp['data']['kind']}  models={resp['data']['models']}")
    sresp = http_json("POST", SERVER_PORT, "/api/v1/chat/sessions", {"title": title, "projectId": pid})
    if sresp.get("code") != 0:
        sys.exit(f"创建会话失败: {sresp}")
    cid = sresp["data"]["chatSessionId"]
    print(f"  [会话] {cid}")
    return cid, pid


def chat_loop(cid, pid):
    """对话主循环：发消息 -> SSE 流式显示 -> HITL 回答 -> 命令。"""
    print("\n== 对话（输入 /plans 看方案历史 /quit 退出）==")
    while True:
        try:
            text = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见")
            return
        if text in ("/quit", "exit", "q"):
            print("再见")
            return
        if text == "/plans":
            r = http_json("GET", SERVER_PORT, f"/api/v1/projects/{pid}/plan_history", timeout=15)
            print(json.dumps(r.get("data"), ensure_ascii=False, indent=2))
            continue
        if not text:
            continue
        try:
            http_json("POST", SERVER_PORT, f"/api/v1/chat/sessions/{cid}/messages", {"text": text}, timeout=10)
        except RuntimeError as e:
            print(f"  发消息失败: {e}")
            continue
        run_sse(cid)


def run_sse(cid):
    """读一轮事件流：文本增量流式打印；question.ask 弹问答；idle/error 结束。"""
    buf = []  # 当前 assistant 段增量累积
    try:
        for event, data in sse_frames(cid):
            if event == "message.part.delta":
                # 文本增量（field=text；reasoning 增量也一并流式打印）
                if data.get("delta"):
                    buf.append(data["delta"])
                    sys.stdout.write(data["delta"])
                    sys.stdout.flush()
            elif event == "message.updated":
                info = data.get("info", {})
                role = info.get("role")
                if role == "user":
                    pass
                elif role == "assistant" and buf:
                    print()
                    buf = []
            elif event == "subagent.status":
                print(f"\n  [子agent] {data.get('id','?')} {data.get('status','')} {data.get('task','')}")
            elif event == "question.ask":
                if buf:
                    print()
                    buf = []
                iid = data.get("interruptId", "")
                print(f"\n  ❓ {data.get('question','')}")
                answer = input("答> ").strip()
                if answer:
                    http_json("POST", SERVER_PORT, f"/api/v1/chat/sessions/{cid}/answer",
                              {"interruptId": iid, "answer": answer}, timeout=10)
            elif event == "session.error":
                print(f"\n  [错误] {data}")
                return
    except KeyboardInterrupt:
        print("\n  （中断本轮）")
    if buf:
        print()
    print()


def main():
    if sys.stdin.isatty():
        print(llm_status())
    ensure_services()
    cid, pid = create_project_flow()
    chat_loop(cid, pid)


if __name__ == "__main__":
    main()
