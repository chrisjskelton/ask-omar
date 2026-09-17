/**
 * Ask Omar Guard — dangerous command confirmation for headless Pi.
 *
 * Intercepts bash tool calls, checks against configurable patterns, and
 * prompts the RPC client (Ask Omar) to confirm before dangerous commands
 * run. Truly catastrophic commands are hard-blocked with no override.
 *
 * Config: ~/.config/ask-omar/guard.json (auto-created with defaults on
 * first load if missing). Edit and save to fine-tune patterns at runtime.
 */

import { readFileSync, existsSync, mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { homedir } from "node:os";
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
  safeExceptions: string[];
}

const GUARD_CONFIG_VERSION = 2;
const LEGACY_POWER_PATTERN = "\\b(shutdown|reboot|halt|poweroff)\\b";
const LEGACY_ROOT_WIPE_PATTERN = "\\brm\\s+(-[a-z]*r[a-z]*f?|--recursive).*\\s+/\\s*$";
const ROOT_WIPE_PATTERN = "\\brm\\s+(-[a-z]*r[a-z]*f?|--recursive).*\\s+/[\\s'\"]*(?:$|[;&|])";
const LEGACY_SAFE_BUILD_PATTERN = "rm\\s+-rf?\\s+\\./?(node_modules|dist|build|\\.next|target|\\.cache|\\.tmp)\\b";
const SAFE_BUILD_PATTERN = "rm\\s+-rf?\\s+\\./?(node_modules|dist|build|\\.next|target|\\.cache|\\.tmp)";
const LEGACY_SAFE_TMP_PATTERN = "rm\\s+-rf?\\s+/tmp/";
const SAFE_TMP_PATTERN = "rm\\s+-rf?\\s+/tmp/(?!\\.{1,2}$)[A-Za-z0-9._-]+";

const DEFAULT_CONFIG: GuardConfig = {
  version: GUARD_CONFIG_VERSION,
  enabled: true,
  hardBlocked: [
    { pattern: ROOT_WIPE_PATTERN, reason: "Wipe root filesystem", description: "delete everything on the system" },
    { pattern: "\\bdd\\b.*\\bof=/dev/", reason: "Raw disk write", description: "write directly to a disk, destroying data" },
    { pattern: "\\bmkfs\\b", reason: "Filesystem format", description: "format a filesystem, erasing all data" },
    { pattern: ":\\(\\)\\{\\s*:\\|:&\\s*\\};:", reason: "Fork bomb", description: "spawn infinite processes" },
    { pattern: "\\biptables\\s+-F\\b", reason: "Firewall flush", description: "remove all firewall rules" },
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
    { pattern: "\\bchmod\\b.*\\b777\\b", reason: "World-writable permissions", description: "make files writable by everyone on the system" },
    { pattern: "\\bchmod\\s+-R\\b", reason: "Recursive permission change", description: "change permissions on all files in a folder" },
    { pattern: "\\bchown\\s+-R\\b", reason: "Recursive ownership change", description: "change ownership of all files in a folder" },
    { pattern: "\\bkillall\\b", reason: "Mass process termination", description: "stop all processes matching a name" },
    { pattern: "\\bpkill\\s+-9\\b", reason: "Force kill processes", description: "force-stop processes" },
    { pattern: "\\bsystemctl\\s+(stop|disable|mask)\\b", reason: "Disabling system services", description: "stop or disable a system service" },
    { pattern: "\\b(truncate|shred)\\b", reason: "Destructive file operation", description: "destroy file contents" },
  ],
  safeExceptions: [
    SAFE_BUILD_PATTERN,
    SAFE_TMP_PATTERN,
  ],
};

function configPath(): string {
  const configHome = process.env.XDG_CONFIG_HOME || join(homedir(), ".config");
  return join(configHome, "ask-omar", "guard.json");
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
    const config: GuardConfig = {
      version: user.version ?? 1,
      enabled: user.enabled ?? DEFAULT_CONFIG.enabled,
      hardBlocked: user.hardBlocked ?? DEFAULT_CONFIG.hardBlocked,
      confirmRequired: user.confirmRequired ?? DEFAULT_CONFIG.confirmRequired,
      safeExceptions: user.safeExceptions ?? DEFAULT_CONFIG.safeExceptions,
    };

    // Version 1 shipped broader safe exceptions and made power commands
    // unconditional hard blocks. Migrate exact built-ins only so custom rules
    // stay intact.
    if ((config.version ?? 1) < GUARD_CONFIG_VERSION) {
      const hadLegacyPowerRule = config.hardBlocked.some((rule) => rule.pattern === LEGACY_POWER_PATTERN);
      config.hardBlocked = config.hardBlocked
        .filter((rule) => rule.pattern !== LEGACY_POWER_PATTERN)
        .map((rule) => rule.pattern === LEGACY_ROOT_WIPE_PATTERN ? { ...rule, pattern: ROOT_WIPE_PATTERN } : rule);
      if (hadLegacyPowerRule && !config.confirmRequired.some((rule) => rule.pattern === LEGACY_POWER_PATTERN)) {
        config.confirmRequired = [DEFAULT_CONFIG.confirmRequired[0], ...config.confirmRequired];
      }
      config.safeExceptions = config.safeExceptions.map((pattern) => {
        if (pattern === LEGACY_SAFE_BUILD_PATTERN) return SAFE_BUILD_PATTERN;
        if (pattern === LEGACY_SAFE_TMP_PATTERN) return SAFE_TMP_PATTERN;
        return pattern;
      });
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
  | { kind: "allow" }
  | { kind: "hard-block"; rule: PatternRule }
  | { kind: "confirm"; rule: PatternRule };

export function evaluateCommand(command: string, config: GuardConfig): GuardDecision {
  // Hard blocks always win, including when a compound command also contains a
  // safe cleanup. This ordering is the guard's critical safety invariant.
  for (const rule of config.hardBlocked) {
    try {
      if (new RegExp(rule.pattern, "i").test(command)) return { kind: "hard-block", rule };
    } catch {
      // Invalid regex in config — skip it.
    }
  }

  // Safe exceptions must match the entire command. A safe prefix must never
  // mask a dangerous second command joined with ;, &&, ||, or a pipe.
  for (const pattern of config.safeExceptions) {
    try {
      if (new RegExp(`^(?:${pattern})\\s*$`, "i").test(command.trim())) return { kind: "allow" };
    } catch {
      // Invalid regex in config — skip it.
    }
  }

  for (const rule of config.confirmRequired) {
    try {
      if (new RegExp(rule.pattern, "i").test(command)) return { kind: "confirm", rule };
    } catch {
      // Invalid regex in config — skip it.
    }
  }

  return { kind: "allow" };
}

export default function (pi: ExtensionAPI) {
  pi.on("tool_call", async (event, ctx) => {
    if (event.toolName !== "bash") return undefined;

    const config = loadConfig();
    if (!config.enabled) return undefined;

    const command = String(event.input?.command ?? "");
    const decision = evaluateCommand(command, config);

    if (decision.kind === "hard-block") {
      return {
        block: true,
        reason: `Ask Omar blocked this command because it could ${decision.rule.description}. If you still need to do this, open a terminal and run it yourself.`,
      };
    }

    if (decision.kind === "confirm") {
      const rule = decision.rule;

      if (!ctx.hasUI) {
        return {
          block: true,
          reason: `Ask Omar blocked this command because it could ${rule.description}, and there is no confirmation panel available. If you still need to do this, open a terminal and run it yourself.`,
        };
      }

      const title = `Omar wants to ${rule.description}\nCommand: ${command}`;
      const choice = await ctx.ui.select(title, ["Allow", "Deny"]);

      if (choice !== "Allow") {
        ctx.ui.notify(`Command denied: ${rule.reason}`, "warning");
        return { block: true, reason: `Denied by user: ${rule.reason}` };
      }

      ctx.ui.notify(`Command allowed: ${rule.reason}`, "info");
      return undefined;
    }

    return undefined;
  });
}
