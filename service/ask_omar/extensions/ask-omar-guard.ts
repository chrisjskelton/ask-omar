/**
 * Ask Omar's focused command gate for headless Pi.
 *
 * Pi's built-in Bash tool is disabled. This extension provides the only
 * model-controlled shell tool, applies the selected access mode, and always
 * asks again before a small set of recognisably high-risk commands. It is an
 * approval aid, not a sandbox or a comprehensive shell analyser.
 */

import { spawn } from "node:child_process";
import { Type } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

interface RiskRule {
  pattern: RegExp;
  reason: string;
  description: string;
}

const EXECUTABLE_PATH = String.raw`(?:\/(?:[A-Za-z0-9._+-]+\/)*)?`;
const COMMAND_WRAPPER = String.raw`(?:`
  + String.raw`${EXECUTABLE_PATH}(?:sudo|doas)\s+(?:-[^\s]+\s+)*|`
  + String.raw`${EXECUTABLE_PATH}env\s+(?:(?:-[^\s]+|[A-Za-z_][A-Za-z0-9_]*=(?:"[^"]*"|'[^']*'|\S+))\s+)*|`
  + String.raw`${EXECUTABLE_PATH}command\s+(?:-[^\s]+\s+)*`
  + String.raw`)*`;
const SHELL_EXECUTABLE = String.raw`["']?${EXECUTABLE_PATH}(?:ba|da|z|k)?sh\b`;
const REMOTE_SHELL_PIPE = new RegExp(
  String.raw`\b(?:curl|wget)\b[^|\n]*\|\s*${COMMAND_WRAPPER}${SHELL_EXECUTABLE}`,
  "i",
);

const RISK_RULES: RiskRule[] = [
  {
    pattern: /\brm\b(?=[^;&|\n]*(?:-[a-z]*r|-[a-z]*R|--recursive|--dir))(?=[^;&|\n]*(?:-[a-z]*f|--force))/i,
    reason: "Recursive forced deletion",
    description: "permanently delete files and folders recursively",
  },
  {
    pattern: /\b(?:mkfs(?:\.[a-z0-9]+)?|wipefs|blkdiscard)\b/i,
    reason: "Disk or filesystem erasure",
    description: "erase a disk or filesystem",
  },
  {
    pattern: /\bdd\b[^;&|\n]*\bof=\/?dev\//i,
    reason: "Raw device write",
    description: "write directly to a device and destroy data",
  },
  {
    pattern: /\b(?:sudo|doas|pkexec)\b/i,
    reason: "Elevated privileges",
    description: "run a command with administrator privileges",
  },
  {
    pattern: /\b(?:shutdown|reboot|halt|poweroff)\b/i,
    reason: "System power control",
    description: "shut down or restart the computer",
  },
  {
    pattern: REMOTE_SHELL_PIPE,
    reason: "Downloaded code execution",
    description: "download code and run it immediately",
  },
  {
    pattern: /:\(\)\{\s*:\|:&\s*\};:/,
    reason: "Fork bomb",
    description: "start an uncontrolled number of processes",
  },
];

function normalizeForRiskCheck(command: string): string {
  const continuations = command.replace(/(\\+)\n/g, (_match, slashes: string) => {
    const literalBackslashes = "\\".repeat(Math.floor(slashes.length / 2));
    return slashes.length % 2 === 0 ? `${literalBackslashes}\n` : literalBackslashes;
  });
  return continuations
    .replace(/\\([^\n])/g, "$1");
}

export function evaluateCommand(command: string): RiskRule | null {
  const normalized = normalizeForRiskCheck(command);
  const variants = [normalized, normalized.replace(/["']/g, "")];
  return RISK_RULES.find((rule) => variants.some((value) => rule.pattern.test(value))) ?? null;
}

type AccessMode = "ask" | "off" | "full";

interface CommandResult {
  stdout: string;
  stderr: string;
  code: number | null;
  aborted: boolean;
  timedOut: boolean;
  outputLimited: boolean;
}

const COMMAND_TIMEOUT_MS = 60_000;
const DEFAULT_TEMPORARY_GRANT_MS = 15 * 60_000;
const OUTPUT_LIMIT_BYTES = 64 * 1024;
const COMMAND_LIMIT_BYTES = 32 * 1024;

function accessMode(): AccessMode {
  const value = String(process.env.ASK_OMAR_SYSTEM_ACCESS || "ask").toLowerCase();
  return value === "off" || value === "full" ? value : "ask";
}

function temporaryGrantMs(): number {
  const configured = Number.parseInt(process.env.ASK_OMAR_GRANT_DURATION_MS ?? "", 10);
  return configured > 0 ? configured : DEFAULT_TEMPORARY_GRANT_MS;
}

function stopProcess(pid: number | undefined, signal: NodeJS.Signals): void {
  if (!pid) return;
  try {
    process.kill(-pid, signal);
  } catch {
    // The process may already have exited.
  }
}

function executeShell(command: string, cwd: string, signal?: AbortSignal): Promise<CommandResult> {
  if (signal?.aborted) throw new Error("Command cancelled before it started.");

  return new Promise((resolve, reject) => {
    const child = spawn("/bin/bash", ["-lc", command], {
      cwd,
      env: process.env,
      detached: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    const stdout: Buffer[] = [];
    const stderr: Buffer[] = [];
    let capturedBytes = 0;
    let aborted = false;
    let timedOut = false;
    let outputLimited = false;
    let killTimer: NodeJS.Timeout | undefined;
    let settled = false;

    const finish = (code: number | null) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      if (killTimer) clearTimeout(killTimer);
      signal?.removeEventListener("abort", abort);
      resolve({
        stdout: Buffer.concat(stdout).toString("utf8"),
        stderr: Buffer.concat(stderr).toString("utf8"),
        code,
        aborted,
        timedOut,
        outputLimited,
      });
    };

    const terminate = () => {
      stopProcess(child.pid, "SIGTERM");
      killTimer ??= setTimeout(() => {
        stopProcess(child.pid, "SIGKILL");
        child.stdout.destroy();
        child.stderr.destroy();
        finish(null);
      }, 1000);
    };
    const append = (target: Buffer[], chunk: Buffer) => {
      const remaining = OUTPUT_LIMIT_BYTES - capturedBytes;
      if (remaining > 0) target.push(chunk.subarray(0, remaining));
      capturedBytes += chunk.length;
      if (capturedBytes > OUTPUT_LIMIT_BYTES && !outputLimited) {
        outputLimited = true;
        terminate();
      }
    };
    const abort = () => {
      aborted = true;
      terminate();
    };
    signal?.addEventListener("abort", abort, { once: true });
    child.stdout.on("data", (chunk: Buffer) => append(stdout, chunk));
    child.stderr.on("data", (chunk: Buffer) => append(stderr, chunk));

    const timeout = setTimeout(() => {
      timedOut = true;
      terminate();
    }, COMMAND_TIMEOUT_MS);
    timeout.unref();

    child.once("error", (error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      if (killTimer) clearTimeout(killTimer);
      signal?.removeEventListener("abort", abort);
      reject(error);
    });
    child.once("close", (code) => finish(code));
  });
}

export default function (pi: ExtensionAPI) {
  const mode = accessMode();
  let temporaryGrantUntil = Number.parseInt(process.env.ASK_OMAR_GRANT_UNTIL ?? "0", 10) || 0;

  pi.on("session_start", () => {
    const active = pi.getActiveTools().filter((name) => name !== "bash");
    if (mode !== "off" && !active.includes("run_command")) active.push("run_command");
    pi.setActiveTools(active);
  });

  if (mode === "off") return;

  pi.registerTool({
    name: "run_command",
    label: "Run command",
    description: "Run one focused shell command on this computer through Ask Omar's access controls.",
    parameters: Type.Object({
      command: Type.String({ description: "The complete shell command to run" }),
    }, { additionalProperties: false }),
    executionMode: "sequential",

    async execute(_toolCallId, params, signal, _onUpdate, ctx) {
      const command = String(params.command ?? "").trim();
      if (!command) throw new Error("Ask Omar refused an empty command.");
      if (Buffer.byteLength(command, "utf8") > COMMAND_LIMIT_BYTES) {
        throw new Error("Ask Omar refused a command longer than 32 KiB.");
      }

      const risk = evaluateCommand(command);
      const needsApproval = risk !== null || (mode === "ask" && Date.now() >= temporaryGrantUntil);
      if (needsApproval) {
        if (!ctx.hasUI) {
          const reason = risk ? `high-risk command (${risk.reason})` : "command";
          throw new Error(
            `Ask Omar blocked this ${reason} because approval is required and the approval panel is unavailable.`,
          );
        }
        const title = risk
          ? `High-risk command: this could ${risk.description}\nCommand: ${command}`
          : `Omar wants to run this shell command\nCommand: ${command}`;
        const choice = await ctx.ui.select(
          title,
          ["Allow once", "Allow for 15 minutes", "Deny"],
        );
        if (choice === "Allow for 15 minutes") {
          temporaryGrantUntil = Date.now() + temporaryGrantMs();
        } else if (choice !== "Allow once") {
          throw new Error(
            `Command denied (${risk?.reason ?? "Shell command"}). Do not ask for the same permission in chat.`,
          );
        }
      }

      const result = await executeShell(command, ctx.cwd, signal);
      if (result.aborted) throw new Error("Command cancelled.");
      if (result.timedOut) throw new Error("Command stopped after 60 seconds.");
      if (result.outputLimited) throw new Error("Command stopped after producing 64 KiB of output.");

      const parts = [];
      if (result.stdout) parts.push(result.stdout.trimEnd());
      if (result.stderr) parts.push(`stderr:\n${result.stderr.trimEnd()}`);
      if (result.code !== 0) parts.push(`exit code: ${result.code ?? "unknown"}`);
      if (parts.length === 0) parts.push("Command completed with no output.");
      return {
        content: [{ type: "text", text: parts.join("\n") }],
        details: { exitCode: result.code },
      };
    },
  });
}
