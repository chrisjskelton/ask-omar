# Changelog

## 0.1.6 — Quicker setup and safer deletes

- Setup no longer overwrites a program file you've changed, or one Ask Omar didn't install. It stops before changing anything and tells you which file.
- Omar is told to move things to the Trash when you ask it to delete them, so you can usually get them back.
- `make setup` no longer runs the developer tests, so it finishes in seconds with a few lines of output.
- `make uninstall` asks whether to delete your notes, history and settings too.
- Deleting a file with hyphens in its name is no longer mistaken for `rm -rf`.
- After an update, if the bar is still running the old widget, Ask Omar now tells you to run `omarchy-restart-shell` instead of running setup again.

## 0.1.5 — Fixes from a full review of 0.1.4

- A saved-state file that loads but has entries Ask Omar can't read is now kept as `state.json.unreadable-…`, and everything readable is loaded and saved straight away. If that save fails, Scratchpad says so. Before, those entries were dropped and the file was overwritten on the next save.
- Questions go to the background service even when Pi isn't ready. They still wait while the widget and service are from different releases. Links and Google searches now work before Pi is set up, and a question refused because Pi isn't ready ends any temporary command grant, as documented.
- Listing models, checking your Pi sign-in and the setup check no longer load your own Pi extensions, skills or context files. Only the AI session was isolated before.
- A sign-in check that overlaps a provider change is cached for the provider it actually checked.
- The widget's setup messages point to the README's install steps instead of suggesting a bare `make setup`.
- Moving from an old clone install now uses the current uninstaller, and the README says what happens to bar settings and changed files.
- Updates now end with `omarchy-restart-shell`. The running bar keeps the old widget until the shell restarts, which the docs and setup output didn't say.
- The docs say what the 60-second limit covers, which Google search phrases work, and how to recover from a blocked save.

## 0.1.4 — One install route and safer notes

- Ask Omar now installs one way: `omarchy plugin add` from GitHub, then `make setup` in the plugin folder. `make install` no longer copies the widget, which removes the upgrade path that would have refused future releases. Older copied widgets are detected, and `make uninstall` removes them if unmodified.
- `make uninstall` never deletes files from a widget checkout; remove the checkout with `omarchy plugin remove`.
- Setup no longer refuses the Python bytecode caches that uninstalling 0.1.3 or earlier leaves in `~/.local/share/ask-omar`, and the service no longer writes them.
- An unreadable, oversized or unrecognized saved-state file is kept as `state.json.unreadable-…` instead of being overwritten, and Scratchpad says so. If it can't be moved aside, saves are refused rather than overwriting it.
- The widget detects when it and the background service are different versions (for example after `omarchy plugin update`) and asks you to run `make setup`.
- Questions reuse a successful Pi sign-in check for up to 10 minutes instead of running `pi auth check` and scanning installed apps every time.
- Only explicit search phrases such as “google …” or “search the web for …” open Google. “search my Downloads for …” now goes to Omar.
- Ask for Recognized Risks no longer offers “Allow for 15 minutes”, which had no effect in that mode.
- A temporary command grant now ends whenever the conversation ends, including Stop, a model change, a failed AI request and the idle reset. Previously Stop and model changes kept it.
- Removed unused action matching, app discovery and usage scoring, and stopped telling the AI about buttons that no longer exist.
- Documentation now states that the high-risk prompt is a warning rather than a boundary, explains what Pi does, and lists everything that ends a temporary grant, and describes the permission pattern accurately (only recursive world-writable changes are flagged). The unpublished `docs/` product page and old demo were removed.

## 0.1.3 — Safe managed lifecycle

- Upgrades update managed application files without deleting unknown nested files.
- Uninstall removes application files only when they're unchanged, and preserves modified or unknown content there. Launchers, the service and menu entries are removed when they carry Ask Omar's marker.
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
