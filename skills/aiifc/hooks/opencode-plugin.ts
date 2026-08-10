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
import { existsSync, realpathSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { PluginModule } from "@opencode-ai/plugin";

const THIS_DIR = path.dirname(fileURLToPath(import.meta.url));
const VALIDATE_SCRIPT = path.join(THIS_DIR, "validate_script.py");

const CONTRACT_MARKERS = ["def build(params", "PARAMS ="];
const SPAWN_TIMEOUT_MS = 30_000;

function isBuildScript(filePath: string, content: string): boolean {
  if (!filePath.endsWith(".py")) return false;
  return CONTRACT_MARKERS.some((m) => content.includes(m));
}

/** Python 探测：AIIFC_PYTHON → 仓库 edit-service venv → python3（降级链）。 */
function findPython(): string {
  const fromEnv = process.env.AIIFC_PYTHON;
  if (fromEnv) return fromEnv;
  const repoRoot = path.resolve(THIS_DIR, "..", "..", "..", "..");
  const venvPython = path.join(
    repoRoot, "viewer", "edit-service", ".venv", "bin", "python",
  );
  if (existsSync(venvPython)) return venvPython;
  return "python3";
}

function runValidation(filePath: string, args: string[]): Promise<string | null> {
  return new Promise((resolve) => {
    const proc = spawn(findPython(), [VALIDATE_SCRIPT, filePath, ...args], {
      stdio: ["ignore", "pipe", "pipe"],
      timeout: SPAWN_TIMEOUT_MS,
    });
    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (d) => { stdout += d; });
    proc.stderr.on("data", (d) => { stderr += d; });
    proc.on("error", () => resolve(null));
    proc.on("close", () => {
      if (stdout.trim().length === 0) {
        console.warn("[aiifc-hooks] validate_script.py 无输出:", stderr.trim());
        resolve(null);
        return;
      }
      resolve(stdout.trim());
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
      const content = typeof args?.content === "string" ? args.content : "";
      if (!isBuildScript(filePath, content)) return;

      const raw = await runValidation(filePath, ["--sandbox-timeout", "30"]);
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
