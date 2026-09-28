# Security

Ask Omar 0.1 is experimental. Use the latest release; older snapshots receive no separate security maintenance.

Please report vulnerabilities privately through [GitHub private vulnerability reporting](https://github.com/chrisjskelton/ask-omar/security/advisories/new). Include the affected version, a minimal reproduction using invented data, and the impact. Do not post credentials, personal information, screenshots of private work, or exploit details in a public issue. There is no guaranteed response time for this personal project.

## Trust model

Ask Omar runs as your desktop user. Pi can read files and run commands with that user's permissions. Commands may use the network. Elevation depends on your operating system's authentication and privilege policy.

Pi's native Bash tool is disabled. Model-generated commands can run only through Ask Omar's command tool. The default **Ask First** mode shows the complete command and offers Allow once, Allow for 15 minutes, or Deny. A temporary grant covers routine commands in later requests until 15 minutes pass; New conversation or a service restart ends it early. **Ask for Recognized Risks** runs most commands automatically and asks about risks Omar recognizes, while **Block Commands** removes the command tool. **Always Allow — Dangerous** runs every command without approval and requires a separate confirmation in Settings.

Commands have a 60-second execution limit, a 32 KiB command limit, and a 64 KiB combined output limit. Except in Always Allow, Ask Omar requests fresh approval for a small set of clearly high-risk patterns, including recursive forced deletion (`rm -rf`), disk and partition changes, low-level output overwrites, recursive permission or ownership changes, privilege elevation, host-connected containers, power controls, downloaded code piped into a shell and fork bombs. This is an additional warning gate, not a sandbox or comprehensive shell analysis; equivalent actions can be expressed in ways it does not recognise. Pi's direct read-only tools do not prompt and can access files with your user permissions. Untrusted content can influence an agent; review proposed commands with the same care as commands in a terminal and do not enable Always Allow around untrusted content.

Expected boundaries include private local state and Unix-socket access across user accounts, keeping private UI payloads out of process arguments, matching approvals to the pending command, expiring temporary grants after 15 minutes or a conversation reset, and not executing an action merely because an external document requests it. Reports about failures of those controls are welcome.

Ask Omar does not implement provider authentication. Pi owns that integration. Provider retention and privacy depend on your chosen provider and account settings. See [privacy and retention](README.md#privacy-and-retention).
