# Changelog

## 0.1.4 — One install route and safer notes

- Ask Omar now installs one way: `omarchy plugin add` from GitHub, then `make setup` in the plugin folder. `make install` no longer copies the widget, which removes the upgrade path that would have refused future releases. Older copied widgets are detected, and `make uninstall` removes them if unmodified.
- `make uninstall` never deletes files from a widget checkout; remove the checkout with `omarchy plugin remove`.
- An unreadable, oversized or unrecognised saved-state file is kept as `state.json.unreadable-…` instead of being overwritten, and Scratchpad says so. If it can't be moved aside, saves are refused rather than overwriting it.
- The widget detects when it and the background service are different versions (for example after `omarchy plugin update`) and asks you to run `make setup`.
- Questions reuse a successful Pi sign-in check for up to 10 minutes instead of running `pi auth check` and scanning installed apps every time.
- Only requests that start with “google”, “search google”, “search the web” or “web search” open Google. “search my Downloads for …” now goes to Omar.
- Ask for Recognized Risks no longer offers “Allow for 15 minutes”, which had no effect in that mode.
- A temporary command grant now ends whenever the conversation ends, including Stop, a model change, a failed request and the idle reset. Previously Stop and model changes kept it.
- Removed unused action matching, app discovery and usage scoring, and stopped telling the AI about buttons that no longer exist.
- Documentation now states that the high-risk prompt is a warning rather than a boundary, explains what Pi does, and lists everything that ends a temporary grant, and describes the permission pattern accurately (only recursive world-writable changes are flagged). The unpublished `docs/` product page and old demo were removed.

## 0.1.3 — Safe managed lifecycle

- Upgrades update managed application files without deleting unknown nested files.
- Uninstall removes only unchanged files recorded by Ask Omar and preserves modified or unknown content.
- Managed removal refuses path traversal and never follows nested symlinks.
- Plugin upgrades and removal preserve modified files, unknown files and marketplace source checkouts.
- Marketplace setup pins the full release commit before enabling the plugin.

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
