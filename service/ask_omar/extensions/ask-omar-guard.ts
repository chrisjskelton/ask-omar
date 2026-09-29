/**
 * Ask Omar's focused command gate for headless Pi.
 *
 * Pi's built-in Bash tool is disabled. This extension provides the only
 * model-controlled shell tool, applies the selected access mode, and always
 * asks again before a small set of recognisably high-risk commands. It is an
 * approval aid, not a sandbox or a comprehensive shell analyser.
 */

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
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
const CONTAINER_HOST_ACCESS: RiskRule = {
  pattern: /\b(?:docker|podman)\b/i,
  reason: "Privileged container access",
  description: "give a container broad access to the host computer",
};
const CONTAINER_HOST_NAMESPACES = new Set([
  "--pid", "--network", "--net", "--userns", "--uts", "--ipc",
]);
const CONTAINER_GLOBAL_BOOLEAN_OPTIONS = new Set([
  "--debug", "--help", "--remote", "--syslog", "--tls", "--tlsverify", "--transient-store", "-D",
]);
const CONTAINER_GLOBAL_VALUE_OPTIONS = new Set([
  "--config", "--connection", "--context", "--events-backend", "--host", "--identity",
  "--log-level", "--root", "--runroot", "--runtime", "--storage-driver", "--url", "-c", "-H", "-l",
]);
const CONTAINER_BOOLEAN_OPTIONS = new Set([
  "--detach", "--disable-content-trust", "--help", "--init", "--interactive", "--oom-kill-disable",
  "--privileged", "--publish-all", "--read-only", "--remove", "--replace", "--rm", "--sig-proxy", "--tty",
  "-d", "-i", "-P", "-t",
]);
const CONTAINER_VALUE_OPTIONS = new Set([
  "--add-host", "--annotation", "--attach", "--blkio-weight-device", "--cap-add",
  "--blkio-weight", "--cap-drop", "--cgroup-parent", "--cgroupns", "--cidfile", "--cpu-period",
  "--cpu-quota", "--cpu-rt-period", "--cpu-rt-runtime", "--cpu-shares", "--cpus", "--cpuset-cpus",
  "--cpuset-mems", "--device", "--device-cgroup-rule", "--device-read-bps", "--device-read-iops",
  "--device-write-bps", "--device-write-iops", "--dns", "--dns-option", "--dns-search",
  "--domainname", "--entrypoint", "--env", "--env-file", "--expose", "--gpus", "--group-add",
  "--health-cmd", "--health-interval", "--health-retries", "--health-start-interval",
  "--health-start-period", "--health-timeout", "--hostname", "--ip", "--ip6", "--isolation",
  "--label", "--label-file", "--link", "--link-local-ip", "--log-driver", "--log-opt", "--mac-address",
  "--memory", "--memory-reservation", "--memory-swap", "--memory-swappiness", "--mount", "--name",
  "--network-alias", "--oom-score-adj", "--pids-limit", "--platform", "--publish", "--pull", "--restart",
  "--runtime", "--security-opt", "--shm-size", "--stop-signal",
  "--stop-timeout", "--storage-opt", "--sysctl", "--tmpfs", "--ulimit", "--user", "--volume",
  "--volume-driver", "--volumes-from", "--workdir",
]);
const CONTAINER_SHORT_VALUE_OPTIONS = new Set(["-a", "-c", "-e", "-h", "-l", "-m", "-p", "-u", "-v", "-w"]);
const SHELL_SEPARATOR = /^(?:;|&&|\|\||\||&)$/;
const HOST_SOCKET = /\/(?:var\/)?run\/(?:docker|podman)\.sock(?:$|:)/i;

function shellTokens(command: string): string[] {
  const tokens = command.match(/"(?:\\.|[^"\\])*"|'[^']*'|&&|\|\||[;&|]|[^\s;&|]+/g) ?? [];
  return tokens.map((token) => {
    if ((token.startsWith('"') && token.endsWith('"'))
        || (token.startsWith("'") && token.endsWith("'"))) {
      return token.slice(1, -1);
    }
    return token;
  });
}

function dangerousContainerValue(option: string, value: string): boolean {
  if (CONTAINER_HOST_NAMESPACES.has(option)) return value.toLowerCase() === "host";
  if (option === "-v" || option === "--volume") {
    return /^\/?:(?:\/|$)/.test(value) || HOST_SOCKET.test(value);
  }
  if (option === "--mount") {
    return /(?:^|,)(?:source|src)=\/?(?:,|$)/i.test(value) || HOST_SOCKET.test(value);
  }
  return false;
}

function hasContainerHostAccess(command: string): boolean {
  const tokens = shellTokens(command);
  for (let index = 0; index + 2 < tokens.length; index++) {
    const executable = tokens[index].split("/").pop()?.toLowerCase();
    if (executable !== "docker" && executable !== "podman") continue;

    let subcommandIndex = index + 1;
    while (subcommandIndex < tokens.length && tokens[subcommandIndex].startsWith("-")) {
      const token = tokens[subcommandIndex];
      const equalsAt = token.indexOf("=");
      const rawOption = equalsAt === -1 ? token : token.slice(0, equalsAt);
      const option = rawOption.startsWith("--") ? rawOption.toLowerCase() : rawOption;
      if (equalsAt !== -1 || CONTAINER_GLOBAL_BOOLEAN_OPTIONS.has(option)) {
        subcommandIndex += 1;
      } else if (CONTAINER_GLOBAL_VALUE_OPTIONS.has(option) || option.startsWith("--")) {
        subcommandIndex += 2;
      } else {
        subcommandIndex += 1;
      }
    }
    if (!/^(?:run|create)$/i.test(tokens[subcommandIndex] ?? "")) continue;

    for (let optionIndex = subcommandIndex + 1; optionIndex < tokens.length;) {
      const token = tokens[optionIndex];
      if (SHELL_SEPARATOR.test(token) || token === "--") break;
      if (!token.startsWith("-")) break; // The first positional argument is the image.
      if (/^--privileged(?:=|$)/i.test(token)) return true;
      if (/^-v./i.test(token) && dangerousContainerValue("-v", token.slice(2).replace(/^=/, ""))) {
        return true;
      }

      const equalsAt = token.indexOf("=");
      const rawOption = equalsAt === -1 ? token : token.slice(0, equalsAt);
      const option = rawOption.startsWith("--") ? rawOption.toLowerCase() : rawOption;
      const inlineValue = equalsAt === -1 ? "" : token.slice(equalsAt + 1);
      if (inlineValue && dangerousContainerValue(option, inlineValue)) return true;

      const takesSeparateValue = equalsAt === -1
        && (CONTAINER_HOST_NAMESPACES.has(option)
          || CONTAINER_VALUE_OPTIONS.has(option)
          || CONTAINER_SHORT_VALUE_OPTIONS.has(option)
          || (option.startsWith("--")
            && !CONTAINER_BOOLEAN_OPTIONS.has(option)
            && !(tokens[optionIndex + 1] ?? "").startsWith("-")));
      if (takesSeparateValue) {
        const value = tokens[optionIndex + 1] ?? "";
        if (dangerousContainerValue(option, value)) return true;
        optionIndex += 2;
      } else {
        optionIndex += 1;
      }
    }
  }
  return false;
}

const RISK_RULES: RiskRule[] = [
  {
    pattern: /\brm\b(?=[^;&|\n]*(?:-[a-z]*r|-[a-z]*R|--recursive|--dir))(?=[^;&|\n]*(?:-[a-z]*f|--force))/i,
    reason: "Recursive forced deletion",
    description: "permanently delete files and folders recursively",
  },
  {
    pattern: /\bshred\b/i,
    reason: "Secure file overwrite",
    description: "overwrite a file or device so its contents cannot be recovered",
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
    pattern: /\bdd\b[^;&|\n]*\bof=/i,
    reason: "Output overwrite",
    description: "overwrite the output named in a low-level copy command",
  },
  {
    pattern: /\b(?:fdisk|sfdisk|cfdisk|parted|sgdisk)\b/i,
    reason: "Disk partitioning",
    description: "change a disk's partitions and destroy data",
  },
  {
    pattern: /\bchmod\b(?=[^;&|\n]*(?:-[A-Za-z]*R|--recursive))(?=[^;&|\n]*(?:\b(?:777|0777|1777|7777)\b|\b(?:a|ugo)\+rwx\b))/,
    reason: "Recursive world-writable permissions",
    description: "make a directory tree writable by every user",
  },
  {
    pattern: /\bchown\b[^;&|\n]*(?:-[A-Za-z]*R|--recursive)/,
    reason: "Recursive ownership change",
    description: "change ownership across a directory tree",
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
    pattern: /(?:\bask-omar\b|\bpython(?:3(?:\.\d+)?)?\b[^;&|\n]*\s-m\s+ask_omar)\s+set-access\s+(?:full|unrestricted)\b/i,
    reason: "Safeguard change",
    description: "reduce future command approval prompts",
  },
  {
    pattern: /(?=[^;&|\n]*\b(?:full|unrestricted)\b)(?=[^;&|\n]*\bask-omar\/config\.toml\b)[^;&|\n]*(?:\b(?:sed|perl)\b[^;&|\n]*\s-[A-Za-z]*i[A-Za-z]*\b|(?:^|\s)(?:>>?|tee\b))/i,
    reason: "Safeguard change",
    description: "change Ask Omar's persistent command approval settings",
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
  if (variants.some(hasContainerHostAccess)) return CONTAINER_HOST_ACCESS;
  return RISK_RULES.find((rule) => variants.some((value) => rule.pattern.test(value))) ?? null;
}

type AccessMode = "ask" | "off" | "full" | "unrestricted";

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
let commandSequence = 0;
const PARENT_WATCHED_SHELL = String.raw`
parent_pid=$1
command=$2
unit=$3
launcher_pid=$$
setsid /bin/bash -c '
  parent_pid=$1
  unit=$2
  launcher_pid=$3
  seen_scope=0
  while kill -0 "$parent_pid" 2>/dev/null; do
    state=$(systemctl --user show --property=ActiveState --value "$unit.scope" 2>/dev/null || true)
    case "$state" in
      active|activating|deactivating) seen_scope=1 ;;
      *)
        if [ "$seen_scope" -eq 1 ]; then exit 0; fi
        launcher_state=$(ps -o stat= -p "$launcher_pid" 2>/dev/null || true)
        case "$launcher_state" in ""|Z*) exit 0 ;; esac
        ;;
    esac
    sleep 0.1
  done
  trap "" TERM
  systemctl --user kill --kill-whom=all --signal=SIGTERM "$unit.scope" 2>/dev/null || true
  sleep 1
  systemctl --user kill --kill-whom=all --signal=SIGKILL "$unit.scope" 2>/dev/null || true
' ask-omar-watchdog "$parent_pid" "$unit" "$launcher_pid" </dev/null >/dev/null 2>&1 &
watchdog_pid=$!
systemd-run --user --scope --quiet --collect --expand-environment=no \
  --property=PartOf=ask-omar.service --property=TimeoutStopSec=1s \
  --unit="$unit" -- /bin/bash -lc "$command"
status=$?
if ! systemctl --user is-active --quiet "$unit.scope" 2>/dev/null; then
  kill "$watchdog_pid" 2>/dev/null || true
  wait "$watchdog_pid" 2>/dev/null || true
fi
exit "$status"
`;
const FALLBACK_PARENT_WATCHED_SHELL = String.raw`
parent_pid=$1
command=$2
command_group=$$
setsid /bin/bash -c '
  parent_pid=$1
  command_group=$2
  cleanup_requested=0
  trap "cleanup_requested=1" USR1
  while kill -0 "$parent_pid" 2>/dev/null && [ "$cleanup_requested" -eq 0 ]; do
    wrapper_state=$(ps -o stat= -p "$command_group" 2>/dev/null || true)
    case "$wrapper_state" in ""|Z*) break ;; esac
    sleep 0.1
  done
  trap "" TERM
  found=0
  for pid in $(pgrep -g "$command_group" 2>/dev/null || true); do
    if [ "$pid" != "$command_group" ]; then
      found=1
      kill -TERM "$pid" 2>/dev/null || true
    fi
  done
  [ "$found" -eq 0 ] && exit 0
  sleep 1
  for pid in $(pgrep -g "$command_group" 2>/dev/null || true); do
    [ "$pid" = "$command_group" ] || kill -KILL "$pid" 2>/dev/null || true
  done
' ask-omar-watchdog "$parent_pid" "$command_group" &
watchdog_pid=$!
/bin/bash -lc "$command"
status=$?
kill -USR1 "$watchdog_pid" 2>/dev/null || true
wait "$watchdog_pid" 2>/dev/null || true
exit "$status"
`;

function accessMode(): AccessMode {
  const value = String(process.env.ASK_OMAR_SYSTEM_ACCESS || "ask").toLowerCase();
  return value === "off" || value === "full" || value === "unrestricted" ? value : "ask";
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

function stopUnit(unit: string, signal: NodeJS.Signals): void {
  const systemctl = spawn(
    "/usr/bin/systemctl",
    ["--user", "kill", "--kill-whom=all", `--signal=${signal}`, `${unit}.scope`],
    { detached: true, stdio: "ignore" },
  );
  systemctl.unref();
}

function executeShell(command: string, cwd: string, signal?: AbortSignal): Promise<CommandResult> {
  if (signal?.aborted) throw new Error("Command cancelled before it started.");

  return new Promise((resolve, reject) => {
    const unit = `ask-omar-command-${process.pid}-${++commandSequence}`;
    const runtimeDir = process.env.XDG_RUNTIME_DIR ?? "";
    const useSystemdScope = runtimeDir !== "" && existsSync(`${runtimeDir}/systemd/private`);
    const wrapper = useSystemdScope ? PARENT_WATCHED_SHELL : FALLBACK_PARENT_WATCHED_SHELL;
    const wrapperArguments = useSystemdScope
      ? ["-c", wrapper, "ask-omar-command", String(process.pid), command, unit]
      : ["-c", wrapper, "ask-omar-command", String(process.pid), command];
    const child = spawn(
      "/bin/bash",
      wrapperArguments,
      {
        cwd,
        env: process.env,
        detached: true,
        stdio: ["ignore", "pipe", "pipe"],
      },
    );
    const stdout: Buffer[] = [];
    const stderr: Buffer[] = [];
    let capturedBytes = 0;
    let aborted = false;
    let timedOut = false;
    let outputLimited = false;
    let killTimer: NodeJS.Timeout | undefined;
    let settled = false;
    let terminating = false;

    const finish = (code: number | null, forced = false) => {
      if (settled || (terminating && !forced)) return;
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
      if (terminating) return;
      terminating = true;
      if (useSystemdScope) stopUnit(unit, "SIGTERM");
      stopProcess(child.pid, "SIGTERM");
      killTimer ??= setTimeout(() => {
        if (useSystemdScope) stopUnit(unit, "SIGKILL");
        stopProcess(child.pid, "SIGKILL");
        child.stdout.destroy();
        child.stderr.destroy();
        finish(null, true);
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
    child.stdout.on("data", (chunk: Buffer) => append(stdout, chunk));
    child.stderr.on("data", (chunk: Buffer) => append(stderr, chunk));

    const timeout = setTimeout(() => {
      timedOut = true;
      terminate();
    }, COMMAND_TIMEOUT_MS);
    timeout.unref();
    signal?.addEventListener("abort", abort, { once: true });
    if (signal?.aborted) abort();

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
      const needsApproval = mode !== "unrestricted"
        && (risk !== null || (mode === "ask" && Date.now() >= temporaryGrantUntil));
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
        // A temporary grant only changes anything in Ask First, where routine
        // commands otherwise ask. Other modes offer a single approval.
        const options = mode === "ask"
          ? ["Allow once", "Allow for 15 minutes", "Deny"]
          : ["Allow once", "Deny"];
        const choice = await ctx.ui.select(title, options);
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
