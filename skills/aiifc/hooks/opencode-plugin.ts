/**
 * aiifc hooks — opencode 形态「校验即事件」（W-0025）。
 *
 * 注册 `tool.execute.after`：agent 用 write/edit 工具写入/编辑**构建脚本**
 * （*.py 且内容含 `def build(params` 或 `PARAMS =` 契约特征）时，spawn
 * hooks/validate_script.py（静态契约校验 + 可选沙箱试跑），结果回填为事件：
 *
 *   - output.title   —— 简短标题（UI 可见）
 *   - output.output  —— 一行事件摘要（model 可见，不塞完整错误）
 *   - output.metadata —— 完整事件载荷（aiifc:// URI，见 hooks/README.md）
 *
 * 安装：把本文件（或软链）放到 opencode 的 `.opencode/plugin/` 目录
 * （例如 `.opencode/plugin/aiifc-hooks.ts`）。opencode 自动加载 *.ts 插件。
 * 类型仅 import type，运行时零依赖。
 */
import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { PluginModule } from "@opencode-ai/plugin";

const THIS_DIR = path.dirname(fileURLToPath(import.meta.url));
const VALIDATE_SCRIPT = path.join(THIS_DIR, "validate_script.py");

const CONTRACT_MARKERS = ["def build(params", "PARAMS ="];
/** 沙箱试跑超时（秒），传给 validate_script.py 的 --sandbox-timeout。 */
const SANDBOX_TIMEOUT_S = 30;
/** 插件 spawn 兜底超时（ms）：必须显著大于沙箱超时（90s = 3×30s）。
 *  挂死脚本先被沙箱自行掐断并产 timed_out 事件（失败即事件）；
 *  插件超时只兜残余挂死进程，并按进程组 SIGKILL 清场防孤儿沙箱残留。 */
const SPAWN_TIMEOUT_MS = 90_000;

function isBuildScript(filePath: string, content: string): boolean {
  if (!filePath.endsWith(".py")) return false;
  return CONTRACT_MARKERS.some((m) => content.includes(m));
}

/** 从 hooks 目录（软链安装经 import.meta.url 解析到真实目录）或复制安装目录
 *  （.opencode/plugin/）逐级向上找仓库根：含 AGENTS.md 或 .git 的目录。
 *  两种安装形态深度不同，不得用固定层级数硬编码。 */
function findRepoRoot(): string {
  let dir = THIS_DIR;
  for (let i = 0; i < 8; i++) {
    if (existsSync(path.join(dir, "AGENTS.md")) || existsSync(path.join(dir, ".git"))) {
      return dir;
    }
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return THIS_DIR;
}

/** Python 探测：AIIFC_PYTHON → 仓库 edit-service venv → python3（降级链）。 */
function findPython(): string {
  const fromEnv = process.env.AIIFC_PYTHON;
  if (fromEnv) return fromEnv;
  const venvPython = path.join(
    findRepoRoot(), "viewer", "edit-service", ".venv", "bin", "python",
  );
  if (existsSync(venvPython)) return venvPython;
  return "python3";
}

function runValidation(filePath: string, args: string[]): Promise<string | null> {
  return new Promise((resolve) => {
    const proc = spawn(findPython(), [VALIDATE_SCRIPT, filePath, ...args], {
      stdio: ["ignore", "pipe", "pipe"],
      // detached：子进程独立进程组，超时可按负 pid 杀全组，防孤儿沙箱继续跑。
      detached: process.platform !== "win32",
    });
    let stdout = "";
    let stderr = "";
    let settled = false;
    function finish(value: string | null) {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(value);
    }
    const timer = setTimeout(() => {
      console.warn("[aiifc-hooks] validate_script.py 超时，终止进程组");
      // 平台限制（W-0025 标注）：进程组 SIGKILL（负 pid）只在 POSIX（Linux/macOS）
      // 可用——本项目主目标平台。win32 无进程组信号语义：detached 关闭、兜底只
      // 杀父进程，validate_script.py 派生的沙箱子进程可能成为孤儿残留（挂死脚本
      // 本身有 --sandbox-timeout 兜底掐断并产 timed_out 事件，此处仅最外层防线）。
      if (proc.pid && process.platform !== "win32") {
        try {
          process.kill(-proc.pid, "SIGKILL");
        } catch {
          proc.kill("SIGKILL");
        }
      } else {
        proc.kill("SIGKILL");
      }
      finish(null);
    }, SPAWN_TIMEOUT_MS);
    proc.stdout.on("data", (d) => { stdout += d; });
    proc.stderr.on("data", (d) => { stderr += d; });
    proc.on("error", () => finish(null));
    proc.on("close", () => {
      if (stdout.trim().length === 0) {
        console.warn("[aiifc-hooks] validate_script.py 无输出:", stderr.trim());
        finish(null);
        return;
      }
      finish(stdout.trim());
    });
  });
}

export default {
  id: "aiifc-script-hooks",
  server: async () => ({
    "tool.execute.after": async (input, output) => {
      const { tool, args } = input;
      if (tool !== "write" && tool !== "edit") return;
      const filePath = typeof args?.filePath === "string" ? args.filePath : "";
      let content = typeof args?.content === "string" ? args.content : "";
      if (tool === "edit") {
        // opencode edit 工具载荷是 {filePath, oldString, newString}（write 才是 content）。
        // 替换区不含契约特征时回读磁盘（替换区外仍可能保留 PARAMS = / def build(params）。
        content = typeof args?.newString === "string" ? args.newString : "";
        if (!isBuildScript(filePath, content)) {
          try {
            content = readFileSync(filePath, "utf-8");
          } catch {
            content = "";
          }
        }
      }
      if (!isBuildScript(filePath, content)) return;

      const raw = await runValidation(
        filePath, ["--sandbox-timeout", String(SANDBOX_TIMEOUT_S)],
      );
      if (raw === null) return;
      let event: { uri?: string; ok?: boolean; errors?: string[]; mode?: string };
      try {
        event = JSON.parse(raw);
      } catch {
        console.warn("[aiifc-hooks] 事件 JSON 解析失败:", raw.slice(0, 200));
        return;
      }
      if (!event.uri) return;

      output.title = `aiifc: script contract ${event.ok ? "validated" : "validation-failed"}`;
      const n = (event.errors ?? []).length;
      output.output = event.ok
        ? `${event.uri}（${event.mode ?? "static"}）`
        : `${event.uri} — ${n} issue${n === 1 ? "" : "s"}（${event.mode ?? "static"}）`;
      output.metadata = { aiifcEvent: event };
    },
  }),
} satisfies PluginModule;
