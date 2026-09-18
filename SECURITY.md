# Security

Ask Omar 0.1 is experimental. Use the latest release; older snapshots receive no separate security maintenance.

Please report vulnerabilities privately through [GitHub private vulnerability reporting](https://github.com/chrisjskelton/ask-omar/security/advisories/new). Include the affected version, a minimal reproduction using invented data, and the impact. Do not post credentials, personal information, screenshots of private work, or exploit details in a public issue. There is no guaranteed response time for this personal project.

## Trust model

Ask Omar runs as your desktop user. Pi can read files and run commands with that user's permissions. Commands may use the network. Elevation depends on your operating system's authentication and privilege policy.

The command guard recognizes known command patterns and offers Allow once / Deny for some actions. It is not a sandbox, an exhaustive dangerous-command detector, or isolation from other processes running as you. Untrusted content can influence an agent; use it with the same care as a terminal agent.

Expected boundaries include private local state and Unix-socket access across user accounts, keeping private UI payloads out of process arguments, matching approvals to the pending command, and not executing an action merely because an external document requests it. Reports about failures of those controls are welcome. A guard regex bypass alone does not establish OS isolation that the product does not promise.

Ask Omar does not implement provider authentication. Pi owns that integration. Provider retention and privacy depend on your chosen provider and account settings. See [privacy and retention](README.md#privacy-and-retention).
