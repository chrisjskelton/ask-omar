# Changelog

## 0.1.2 — Verified installation

- Installation requires the full release commit and refuses a modified checkout.
- The installer refuses symlinked destinations and preserves launchers it did not install.
- Installed application files come only from the verified commit, excluding caches and untracked files.
- The command-line launcher uses the absolute Python interpreter checked during installation.
- Uninstall preserves unrecognized files at Ask Omar's launcher paths.

## 0.1.1 — Command access controls

- Pi's unrestricted Bash tool is replaced by Ask Omar's command tool.
- Ask First shows the exact command with Allow once, Allow for 15 minutes, and Deny.
- Temporary grants cover routine commands in later requests for up to 15 minutes and end early on New conversation or service restart.
- Timeouts identify the last tool or shell command Pi was using when available.
- Ask for Recognized Risks runs most commands without asking and prompts for risks Omar recognizes; Block Commands disables the shell command tool.
- Always Allow — Dangerous runs every shell command without approval and requires separate confirmation in Settings.
- Direct read-only Pi tools remain automatic to keep routine inspection quick.
- Except in Always Allow, recognised high-risk commands require fresh approval, including during temporary grants and Ask for Recognized Risks.
- High-risk recognition also covers partitioning tools, low-level output overwrites, recursive permission and ownership changes, and privileged or host-connected containers.
- The high-risk check is an additional warning gate, not a sandbox or comprehensive shell analyser.
- Commands are bounded to 60 seconds, 32 KiB of command text, and 64 KiB of captured output.
- The assistant prompt prefers direct read-only tools and focused shell commands instead of bundled command chains.

## 0.1.0 — First experimental release

- Omarchy bar assistant powered by an existing Pi installation and provider connection.
- Follow-up conversations, local answer history, Scratchpad, capture shortcuts and optional Voxtype dictation.
- Command-specific Allow once / Deny controls for recognized risky commands; no sandbox claim.
- Private stdin transport for copied text, questions and saved notes.
- Explicit input limits and visible save failures instead of silent note truncation.
- Query transport that remains connected while backend approval waits are active.
- Optional history retention, safer configuration/state handling and documented removal.
- Save-time byte limits keep large Unicode answers from making saved notes and drafts disappear after restarting.
- Bounded local requests accept a full Unicode Scratchpad and clearly reject requests above 5 MiB.
- Root plugin manifest, explicit companion-service setup, installation tests and CI.

This is a personal desktop tool, initially tested on Omarchy 4.0.3-1 and Pi 0.85.1. Broad compatibility and unattended operation are not promised.
