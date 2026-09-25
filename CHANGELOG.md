# Changelog

## 0.1.1 — Brokered system access

- Pi's unrestricted Bash tool is replaced by an Ask Omar-owned command broker.
- Ask First shows the exact command with Allow once, Allow for this question, and Deny.
- Question grants expire after 15 minutes and are revoked when the request finishes or stops.
- Block Commands disables the shell command tool; explicitly enabled Allow All runs commands without asking.
- Direct read-only Pi tools remain automatic to keep routine inspection quick.
- Mandatory catastrophic hard blocks remain active in every mode; Ask First also shows recognised-risk warnings.
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
