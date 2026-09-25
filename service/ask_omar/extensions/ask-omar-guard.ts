/**
 * Ask Omar command broker for headless Pi.
 *
 * Pi's built-in bash tool is disabled by the launcher. This extension exposes
 * the only model-controlled shell path, enforces the internal off / ask / full
 * modes, and bounds command runtime and output. Ask First shows exact commands,
 * supports a short grant across requests, and hard-blocks catastrophic
 * patterns. Mandatory hard blocks remain active in Allow All.
 *
 * Config: ~/.config/ask-omar/guard.json (auto-created with defaults on
 * first load if missing). Edit and save to fine-tune patterns at runtime.
 * Disabling the guard or emptying hard-blocks via that file is ignored so
 * an agent cannot turn the brake off by rewriting its own config.
 */

import { readFileSync, existsSync, mkdirSync, readdirSync, renameSync, unlinkSync, writeFileSync } from "node:fs";
import { spawn } from "node:child_process";
import { join, dirname } from "node:path";
import { homedir } from "node:os";
import { randomUUID } from "node:crypto";
import { Type } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

interface PatternRule {
  pattern: string;
  reason: string;
  description: string;
}

interface GuardConfig {
  version?: number;
  enabled: boolean;
  hardBlocked: PatternRule[];
  confirmRequired: PatternRule[];
}

const GUARD_CONFIG_VERSION = 5;
const LEGACY_POWER_PATTERN = "\\b(shutdown|reboot|halt|poweroff)\\b";
const LEGACY_ROOT_WIPE_PATTERN = "\\brm\\s+(-[a-z]*r[a-z]*f?|--recursive).*\\s+/\\s*$";
const ROOT_WIPE_PATTERN = "\\brm\\s+(-[a-z]*r[a-z]*f?|--recursive).*\\s+/[\\s'\"]*(?:$|[;&|])";
const ROOT_WIPE_GLOB_PATTERN = "\\brm\\s+(-[a-z]*r[a-z]*f?|--recursive).*\\s+/\\*";
const ROOT_WIPE_DOT_PATTERN = "\\brm\\s+(-[a-z]*r[a-z]*f?|--recursive).*\\s+/\\.(?:\\s|$|[;&|'\"])";
const ROOT_WIPE_SLASHSLASH_PATTERN = "\\brm\\s+(-[a-z]*r[a-z]*f?|--recursive).*\\s+//";
const ROOT_WIPE_QUOTED_PATTERN = "\\brm\\s+(-[a-z]*r[a-z]*f?|--recursive).*['\"]\\/['\"]";

const GUARD_TAMPER_RULE: PatternRule = {
  pattern: "",
  reason: "Ask Omar guard tampering",
  description: "disable or replace Ask Omar's command guard",
};

const SHELL_COMMAND_RULE: PatternRule = {
  pattern: "",
  reason: "Shell command",
  description: "run this shell command",
};

const DEFAULT_CONFIG: GuardConfig = {
  version: GUARD_CONFIG_VERSION,
  enabled: true,
  hardBlocked: [
    { pattern: ROOT_WIPE_PATTERN, reason: "Wipe root filesystem", description: "delete everything on the system" },
    { pattern: ROOT_WIPE_GLOB_PATTERN, reason: "Wipe root filesystem", description: "delete everything on the system" },
    { pattern: ROOT_WIPE_DOT_PATTERN, reason: "Wipe root filesystem", description: "delete everything on the system" },
    { pattern: ROOT_WIPE_SLASHSLASH_PATTERN, reason: "Wipe root filesystem", description: "delete everything on the system" },
    { pattern: ROOT_WIPE_QUOTED_PATTERN, reason: "Wipe root filesystem", description: "delete everything on the system" },
    { pattern: "\\bdd\\b.*\\bof=/dev/", reason: "Raw disk write", description: "write directly to a disk, destroying data" },
    { pattern: "\\bmkfs\\b", reason: "Filesystem format", description: "format a filesystem, erasing all data" },
    { pattern: ":\\(\\)\\{\\s*:\\|:&\\s*\\};:", reason: "Fork bomb", description: "spawn infinite processes" },
    { pattern: "\\biptables\\s+-F\\b", reason: "Firewall flush", description: "remove all firewall rules" },
    { pattern: "\\bnft\\b.*\\bflush\\b", reason: "Firewall flush", description: "remove all firewall rules" },
    {
      pattern: "\\b(curl|wget)\\b[^|;]*\\|\\s*(?:sudo\\s+)?(?:ba)?sh\\b",
      reason: "Remote code pipe",
      description: "download and run remote code through a shell",
    },
    {
      pattern: "\\b(shutil\\.rmtree|os\\.system|subprocess\\.(?:call|run|Popen))\\b[^\\n]*['\"]\\/",
      reason: "Interpreter root wipe",
      description: "delete everything on the system through an interpreter",
    },
    {
      pattern: "(?:^|[;&|()]\\s*)(?:(?:sudo|command)\\s+|env\\s+(?:(?:-[^\\s]+|[A-Za-z_][A-Za-z0-9_]*=\\S+)\\s+)*\\s*)?(?:[^\\s;&|()]+/)?(?:setsid|nohup|daemonize|disown|systemd-run)\\b",
      reason: "Detached process",
      description: "start a process outside Ask Omar's Stop and timeout controls",
    },
  ],
  confirmRequired: [
    { pattern: LEGACY_POWER_PATTERN, reason: "System power control", description: "shut down or restart the system, which can discard unsaved work or interrupt file operations" },
    { pattern: "\\brm\\s+(-[a-z]*r[a-z]*f?|--recursive)\\b", reason: "Recursive deletion", description: "delete a folder and everything inside it" },
    { pattern: "\\brm\\s+(-[a-z]*f[a-z]*r?|--force)\\b", reason: "Force deletion", description: "force-delete a file, ignoring protections" },
    { pattern: "\\bfind\\b.*-delete", reason: "Find-based deletion", description: "delete files found by a search" },
    { pattern: "\\bfind\\b.*-exec\\s+rm\\b", reason: "Find-based rm execution", description: "delete files by running rm through find" },
    { pattern: "\\bgit\\s+clean\\s+(-[a-z]*f[a-z]*d?|--force)\\b", reason: "Git clean (force)", description: "permanently remove untracked files and directories" },
    { pattern: "\\brsync\\b.*--delete", reason: "Rsync delete", description: "delete files not present in the source" },
    { pattern: "\\bsudo\\b", reason: "Elevated privileges", description: "run a command with administrator access" },
    { pattern: "\\bdoas\\b", reason: "Elevated privileges", description: "run a command with administrator access" },
    { pattern: "\\bchmod\\b.*\\b777\\b", reason: "World-writable permissions", description: "make files writable by everyone on the system" },
    { pattern: "\\bchmod\\b.*[+=][0-7]*s", reason: "Setuid or setgid permissions", description: "make a program run with elevated privileges" },
    { pattern: "\\bchmod\\s+-R\\b", reason: "Recursive permission change", description: "change permissions on all files in a folder" },
    { pattern: "\\bchown\\s+-R\\b", reason: "Recursive ownership change", description: "change ownership of all files in a folder" },
    { pattern: "\\bkillall\\b", reason: "Mass process termination", description: "stop all processes matching a name" },
    { pattern: "\\bpkill\\s+(-9|-KILL|-SIGKILL)\\b", reason: "Force kill processes", description: "force-stop processes" },
    { pattern: "\\bsystemctl\\s+(stop|disable|mask)\\b", reason: "Disabling system services", description: "stop or disable a system service" },
    { pattern: "\\b(truncate|shred)\\b", reason: "Destructive file operation", description: "destroy file contents" },
  ],
};

function configPath(): string {
  const configHome = process.env.XDG_CONFIG_HOME || join(homedir(), ".config");
  return join(configHome, "ask-omar", "guard.json");
}

function accessConfigPath(): string {
  const configHome = process.env.XDG_CONFIG_HOME || join(homedir(), ".config");
  return join(configHome, "ask-omar", "config.toml");
}

interface AccessConfigSnapshot {
  path: string;
  contents: Buffer | null;
}

function snapshotAccessConfig(): AccessConfigSnapshot {
  const path = accessConfigPath();
  try {
    return { path, contents: readFileSync(path) };
  } catch {
    return { path, contents: null };
  }
}

function configuredAccessMode(contents: string): AccessMode | null {
  let inAgent = false;
  for (const line of contents.split("\n")) {
    const table = line.match(/^\s*\[([^\]]+)\]\s*(?:#.*)?$/);
    if (table) {
      inAgent = table[1].trim() === "agent";
      continue;
    }
    if (!inAgent) continue;
    const match = line.match(/^\s*system_access\s*=\s*["'](ask|off|full)["']\s*(?:#.*)?$/);
    if (match) return match[1] as AccessMode;
    if (/^\s*system_access\s*=/.test(line)) return null;
  }
  return "ask";
}

function restoreAccessConfig(snapshot: AccessConfigSnapshot, expectedMode: AccessMode): void {
  let current: Buffer | null = null;
  try {
    current = readFileSync(snapshot.path);
  } catch {
    // A missing file means Ask First, unless another mode was explicitly active.
  }
  const currentMode = current === null ? "ask" : configuredAccessMode(current.toString("utf8"));
  if (currentMode === expectedMode) return;

  try {
    if (snapshot.contents === null) {
      unlinkSync(snapshot.path);
      return;
    }
    mkdirSync(dirname(snapshot.path), { recursive: true, mode: 0o700 });
    const temporary = `${snapshot.path}.guard-${process.pid}-${randomUUID()}`;
    writeFileSync(temporary, snapshot.contents, { mode: 0o600 });
    renameSync(temporary, snapshot.path);
  } catch {
    // The service still holds the authoritative in-memory mode. A later config
    // write or service restart will surface the filesystem error to the user.
  }
}

function looksLikeGuardTampering(command: string): boolean {
  if (/\bask-omar\s+set-access\b/i.test(command)) return true;

  const mutation = /(?:>>?|tee\b|\bcp\b|\bmv\b|\binstall\b|\bdd\b|\btruncate\b|\bsed\b[^\n]*\s-i|\bperl\b[^\n]*\s-i|\brm\b|\bchmod\b|\bchown\b|\bcat\b\s*>)/i;
  if (!mutation.test(command)) return false;

  const guardTarget = /(?:^|[\s"'`/=])(?:~|\$HOME|\$\{HOME\}|\/[^;\s]*)?(?:\.config\/ask-omar\/)?guard\.json\b|ask-omar-guard\.ts\b/i;
  if (guardTarget.test(command)) return true;

  const configTarget = /(?:^|[\s"'`/=])(?:~|\$HOME|\$\{HOME\}|\/[^;\s]*)?\.config\/ask-omar\/config\.toml\b/i;
  if (!configTarget.test(command)) return false;

  // Provider/model edits are a supported Omar workflow. Block direct access-mode
  // edits and operations that can replace or remove the complete config file.
  return /\bsystem_access\b|\b(?:cp|mv|install|dd|truncate|rm|chmod|chown)\b/i.test(command);
}

function loadConfig(): GuardConfig {
  const path = configPath();
  if (!existsSync(path)) {
    // Write defaults so users can see and edit them.
    try {
      mkdirSync(dirname(path), { recursive: true, mode: 0o700 });
      writeFileSync(path, JSON.stringify(DEFAULT_CONFIG, null, 2) + "\n", { mode: 0o600 });
    } catch {
      // If we can't write, use built-in defaults.
    }
    return DEFAULT_CONFIG;
  }
  try {
    const raw = readFileSync(path, "utf-8");
    const user = JSON.parse(raw);
    const configuredHardBlocks = Array.isArray(user.hardBlocked) ? user.hardBlocked : [];
    const mandatoryHardBlocks = DEFAULT_CONFIG.hardBlocked.filter(
      (required) => !configuredHardBlocks.some((entry) => entry?.pattern === required.pattern),
    );
    const config: GuardConfig = {
      version: user.version ?? 1,
      // enabled:false is ignored — an agent must not be able to disable the brake
      // by rewriting this file. Users who need an escape hatch use a real terminal.
      enabled: true,
      // User rules can extend, but never replace, the mandatory safety floor.
      hardBlocked: [...mandatoryHardBlocks, ...configuredHardBlocks],
      confirmRequired: Array.isArray(user.confirmRequired) && user.confirmRequired.length > 0
        ? user.confirmRequired
        : DEFAULT_CONFIG.confirmRequired,
    };

    // Version 1 made power commands unconditional hard blocks. Migrate exact
    // built-ins only so custom rules stay intact.
    if ((config.version ?? 1) < 2) {
      const hadLegacyPowerRule = config.hardBlocked.some((rule) => rule.pattern === LEGACY_POWER_PATTERN);
      config.hardBlocked = config.hardBlocked
        .filter((rule) => rule.pattern !== LEGACY_POWER_PATTERN)
        .map((rule) => rule.pattern === LEGACY_ROOT_WIPE_PATTERN ? { ...rule, pattern: ROOT_WIPE_PATTERN } : rule);
      if (hadLegacyPowerRule && !config.confirmRequired.some((rule) => rule.pattern === LEGACY_POWER_PATTERN)) {
        config.confirmRequired = [DEFAULT_CONFIG.confirmRequired[0], ...config.confirmRequired];
      }
      config.version = 2;
    }

    // Versions 3 and 4 expand hard blocks and risk-specific descriptions.
    // Version 4 also drops safe exceptions: every non-blocked shell command
    // now requires explicit approval, regardless of the local config version.
    if ((config.version ?? 1) < GUARD_CONFIG_VERSION) {
      const ensureHard = (pattern: string, rule: PatternRule) => {
        if (!config.hardBlocked.some((entry) => entry.pattern === pattern)) {
          config.hardBlocked = [...config.hardBlocked, rule];
        }
      };
      for (const rule of DEFAULT_CONFIG.hardBlocked) ensureHard(rule.pattern, rule);
      for (const rule of DEFAULT_CONFIG.confirmRequired) {
        if (!config.confirmRequired.some((entry) => entry.pattern === rule.pattern)) {
          config.confirmRequired = [...config.confirmRequired, rule];
        }
      }
      // Broaden legacy pkill -9 only rule when still present.
      config.confirmRequired = config.confirmRequired.map((rule) =>
        rule.pattern === "\\bpkill\\s+-9\\b"
          ? { ...rule, pattern: "\\bpkill\\s+(-9|-KILL|-SIGKILL)\\b" }
          : rule,
      );
      config.version = GUARD_CONFIG_VERSION;
      try {
        writeFileSync(path, JSON.stringify(config, null, 2) + "\n", { mode: 0o600 });
      } catch {
        // Continue with the migrated in-memory config if the file is read-only.
      }
    }
    return config;
  } catch {
    return DEFAULT_CONFIG;
  }
}

type GuardDecision =
  | { kind: "hard-block"; rule: PatternRule }
  | { kind: "confirm"; rule: PatternRule };

export function evaluateCommand(command: string, config: GuardConfig): GuardDecision {
  if (looksLikeGuardTampering(command)) {
    return { kind: "hard-block", rule: GUARD_TAMPER_RULE };
  }

  // Hard blocks always win, including when a compound command also contains a
  // safe cleanup. This ordering is the guard's critical safety invariant.
  for (const rule of config.hardBlocked) {
    try {
      if (new RegExp(rule.pattern, "i").test(command)) return { kind: "hard-block", rule };
    } catch {
      // Invalid regex in config — skip it.
    }
  }

  // Preserve specific descriptions for recognized risks, but confirmation is
  // no longer conditional on matching one of these finite patterns.
  for (const rule of config.confirmRequired) {
    try {
      if (new RegExp(rule.pattern, "i").test(command)) return { kind: "confirm", rule };
    } catch {
      // Invalid regex in config — skip it.
    }
  }

  return { kind: "confirm", rule: SHELL_COMMAND_RULE };
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
const TEMPORARY_GRANT_MS = 15 * 60_000;
const OUTPUT_LIMIT_BYTES = 64 * 1024;
const COMMAND_LIMIT_BYTES = 32 * 1024;

function accessMode(): AccessMode {
  const value = String(process.env.ASK_OMAR_SYSTEM_ACCESS || "ask").toLowerCase();
  return value === "off" || value === "full" ? value : "ask";
}

function stopProcess(pid: number | undefined, signal: NodeJS.Signals): void {
  if (!pid) return;
  try {
    process.kill(-pid, signal);
  } catch {
    // The process may already have exited.
  }
}

function stopCommandProcesses(
  unitName: string | null,
  commandId: string,
  rootPid: number | undefined,
  signal: NodeJS.Signals,
): void {
  if (unitName) {
    const killer = spawn(
      "systemctl",
      ["--user", "kill", `--signal=${signal}`, "--kill-whom=all", `${unitName}.scope`],
      { detached: false, stdio: "ignore" },
    );
    killer.on("error", () => {});
    killer.unref();
  }
  stopProcess(rootPid, signal);
  const marker = Buffer.from(`ASK_OMAR_COMMAND_ID=${commandId}`);
  try {
    for (const entry of readdirSync("/proc")) {
      if (!/^\d+$/.test(entry) || Number(entry) === process.pid) continue;
      try {
        if (!readFileSync(`/proc/${entry}/environ`).includes(marker)) continue;
        const pid = Number(entry);
        try { process.kill(pid, signal); } catch {}
        stopProcess(pid, signal);
      } catch {
        // Processes may exit while /proc is being scanned.
      }
    }
  } catch {
    // The systemd scope remains the primary process boundary.
  }
}

function executeShell(command: string, cwd: string, signal?: AbortSignal): Promise<CommandResult> {
  if (signal?.aborted) throw new Error("Command cancelled before it started.");

  return new Promise((resolve, reject) => {
    const commandId = randomUUID();
    const directSpawn = process.env.ASK_OMAR_TEST_DIRECT_SPAWN === "1";
    const unitName = directSpawn ? null : `ask-omar-command-${randomUUID()}`;
    const executable = directSpawn ? "/bin/bash" : "systemd-run";
    const args = directSpawn
      ? ["-lc", command]
      : ["--user", "--scope", "--quiet", "--collect", "--unit", unitName!, "/bin/bash", "-lc", command];
    const child = spawn(executable, args, {
      cwd,
      env: { ...process.env, ASK_OMAR_COMMAND_ID: commandId },
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

    const finish = (code: number | null, afterEscalation = false) => {
      if (settled) return;
      if (killTimer && !afterEscalation) return;
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
      stopCommandProcesses(unitName, commandId, child.pid, "SIGTERM");
      killTimer ??= setTimeout(() => {
        stopCommandProcesses(unitName, commandId, child.pid, "SIGKILL");
        child.stdout.destroy();
        child.stderr.destroy();
        finish(null, true);
      }, 1000);
      killTimer.unref();
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
    child.once("close", finish);
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

      const decision = evaluateCommand(command, loadConfig());
      if (decision.kind === "hard-block") {
        throw new Error(
          `Ask Omar blocked this command because it could ${decision.rule.description}. `
          + "If you still need to do this, open a terminal and run it yourself.",
        );
      }

      if (mode === "ask") {
        if (Date.now() >= temporaryGrantUntil) {
          if (!ctx.hasUI) {
            throw new Error(
              "Ask Omar blocked this command because approval is required and the approval panel is unavailable.",
            );
          }
          const title = `Omar wants to ${decision.rule.description}\nCommand: ${command}`;
          const choice = await ctx.ui.select(
            title,
            ["Allow once", "Allow for 15 minutes", "Deny"],
          );
          if (choice === "Allow for 15 minutes") {
            temporaryGrantUntil = Date.now() + TEMPORARY_GRANT_MS;
          } else if (choice !== "Allow once") {
            throw new Error(
              `Command denied (${decision.rule.reason}). Do not ask for the same permission in chat.`,
            );
          }
        }
      }

      const accessSnapshot = snapshotAccessConfig();
      let result: CommandResult;
      try {
        result = await executeShell(command, ctx.cwd, signal);
      } finally {
        restoreAccessConfig(accessSnapshot, mode);
      }
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
