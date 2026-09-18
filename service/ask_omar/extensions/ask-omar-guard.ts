/**
 * Ask Omar Guard — dangerous command confirmation for headless Pi.
 *
 * Intercepts bash tool calls, checks against configurable patterns, and
 * prompts the RPC client (Ask Omar) to confirm before dangerous commands
 * run. Truly catastrophic commands are hard-blocked with no override.
 *
 * Config: ~/.config/ask-omar/guard.json (auto-created with defaults on
 * first load if missing). Edit and save to fine-tune patterns at runtime.
 * Disabling the guard or emptying hard-blocks via that file is ignored so
 * an agent cannot turn the brake off by rewriting its own config.
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

const GUARD_CONFIG_VERSION = 3;
const LEGACY_POWER_PATTERN = "\\b(shutdown|reboot|halt|poweroff)\\b";
const LEGACY_ROOT_WIPE_PATTERN = "\\brm\\s+(-[a-z]*r[a-z]*f?|--recursive).*\\s+/\\s*$";
const ROOT_WIPE_PATTERN = "\\brm\\s+(-[a-z]*r[a-z]*f?|--recursive).*\\s+/[\\s'\"]*(?:$|[;&|])";
const ROOT_WIPE_GLOB_PATTERN = "\\brm\\s+(-[a-z]*r[a-z]*f?|--recursive).*\\s+/\\*";
const ROOT_WIPE_DOT_PATTERN = "\\brm\\s+(-[a-z]*r[a-z]*f?|--recursive).*\\s+/\\.(?:\\s|$|[;&|'\"])";
const ROOT_WIPE_SLASHSLASH_PATTERN = "\\brm\\s+(-[a-z]*r[a-z]*f?|--recursive).*\\s+//";
const ROOT_WIPE_QUOTED_PATTERN = "\\brm\\s+(-[a-z]*r[a-z]*f?|--recursive).*['\"]\\/['\"]";
const LEGACY_SAFE_BUILD_PATTERN = "rm\\s+-rf?\\s+\\./?(node_modules|dist|build|\\.next|target|\\.cache|\\.tmp)\\b";
const SAFE_BUILD_PATTERN = "rm\\s+-rf?\\s+\\./?(node_modules|dist|build|\\.next|target|\\.cache|\\.tmp)";
const LEGACY_SAFE_TMP_PATTERN = "rm\\s+-rf?\\s+/tmp/";
const SAFE_TMP_PATTERN = "rm\\s+-rf?\\s+/tmp/(?!\\.{1,2}$)[A-Za-z0-9._-]+";

const GUARD_TAMPER_RULE: PatternRule = {
  pattern: "",
  reason: "Ask Omar guard tampering",
  description: "disable or replace Ask Omar's command guard",
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
  safeExceptions: [
    SAFE_BUILD_PATTERN,
    SAFE_TMP_PATTERN,
  ],
};

function configPath(): string {
  const configHome = process.env.XDG_CONFIG_HOME || join(homedir(), ".config");
  return join(configHome, "ask-omar", "guard.json");
}

function looksLikeGuardTampering(command: string): boolean {
  const target = /(?:^|[\s"'`/=])((?:~|\$HOME|\$\{HOME\}|\/[^;\s]*)?(?:\.config\/ask-omar\/)?guard\.json|ask-omar-guard\.ts)\b/i;
  if (!target.test(command)) return false;
  // Reading the guard is fine; rewriting, replacing, or deleting it is not.
  return /(?:>>?|tee\b|\bcp\b|\bmv\b|\binstall\b|\bdd\b|\btruncate\b|\bsed\b[^\n]*\s-i|\bperl\b[^\n]*\s-i|\brm\b|\bchmod\b|\bchown\b|\bcat\b\s*>)/i.test(
    command,
  );
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
      // enabled:false is ignored — an agent must not be able to disable the brake
      // by rewriting this file. Users who need an escape hatch use a real terminal.
      enabled: true,
      hardBlocked: Array.isArray(user.hardBlocked) && user.hardBlocked.length > 0
        ? user.hardBlocked
        : DEFAULT_CONFIG.hardBlocked,
      confirmRequired: Array.isArray(user.confirmRequired) && user.confirmRequired.length > 0
        ? user.confirmRequired
        : DEFAULT_CONFIG.confirmRequired,
      safeExceptions: Array.isArray(user.safeExceptions)
        ? user.safeExceptions
        : DEFAULT_CONFIG.safeExceptions,
    };

    // Version 1 shipped broader safe exceptions and made power commands
    // unconditional hard blocks. Migrate exact built-ins only so custom rules
    // stay intact.
    if ((config.version ?? 1) < 2) {
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
      config.version = 2;
    }

    // Version 3 expands root-wipe / remote-pipe hard blocks and privilege confirms.
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
  | { kind: "allow" }
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

    // Always enforce. enabled:false in guard.json is ignored on load.
    const config = loadConfig();
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
        return {
          block: true,
          reason:
            `Denied by user via Allow once / Deny (${rule.reason}). ` +
            "Do not ask them to confirm this same command in chat. " +
            "Wait for a new explicit request if they want to try again.",
        };
      }

      ctx.ui.notify(`Command allowed: ${rule.reason}`, "info");
      return undefined;
    }

    return undefined;
  });
}
