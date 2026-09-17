# Roadmap

## Prototype: prove the loop

- Always-visible bar field
- Region capture and voice controls
- Approved local actions
- App/keybinding/command discovery
- Pi RPC answers
- Real-world dogfooding

## Next: operate the desktop

- Structured window tools with layout snapshots and Undo
- Launch-or-focus semantics for discovered applications
- Streaming responses from the service to the bar
- Recent request panel and clear/new-conversation controls
- First-run agent/authentication setup
- Configurable aliases and action packs
- Provider/backend adapter contract

## Later: conversational voice

- Streaming speech-to-text
- End-of-speech detection
- Optional text-to-speech
- Clear listening and hard-mute states
- Interruption during spoken responses

## Future: session launcher (Flue integration)

Ask Omar becomes the front door for structured coding sessions. A session can
begin from an explicit control or a natural-language request, but both routes
must enter the same reviewable launcher panel where the user picks a repo,
selects skills, and chooses a sandbox mode. A request must never silently turn
the current unsandboxed desktop conversation into a sandboxed session.

### UX flow

1. User clicks "Session" or asks Omar to start an isolated session
2. Picks a repo (e.g. example-app) from configured options or types a git URL
3. Selects skills to load (e.g. example-skill)
4. Picks a sandbox mode: Local / E2B / VM
5. Ask Omar sends a request to a Flue server
6. Flue creates an agent with skills loaded, in the selected sandbox, repo cloned
7. Terminal opens into the sandbox
8. Ask Omar steps back — shows session status with a Stop button

### Architecture

- **Flue** (withastro/flue) is the agent harness, built on Pi — same provider
  protocol, models, and auth Ask Omar already uses.
- **Sandbox modes** are Flue's built-in choice:
  - **Local** — `local()` binds to the host. Real filesystem, real processes.
  - **E2B** — `flue add sandbox e2b`. Isolated cloud sandboxes.
  - **VM** — Daytona adapter or custom adapter. Runs on any VPS (Hetzner, etc.).
  - **Virtual** — in-memory filesystem with emulated bash. Cheapest, ephemeral.
- **Skills** are Flue's first-class concept. Workspace skills under
  `.agents/skills/` are discovered automatically.
- Ask Omar's Python backend talks to a Flue server via HTTP for session launches.
  Quick questions continue through the direct Pi CLI path.
- Flue manages the agent, sandbox, skills, and durability. Ask Omar manages
  the launch and steps back.
- The service returns a distinct session-launch proposal, rather than encoding
  launcher state in assistant prose. The existing panel can then render the
  proposal and collect explicit choices without replacing the normal Ask Omar
  input mode.

### Configuration

```toml
[sessions]
enabled = true
flue_url = "http://localhost:3000"

[[sessions.repos]]
name = "example-app"
url = "git@github.com:example/example-app.git"
default_skills = ["example-skill", "another-skill"]
default_sandbox = "local"

[[sessions.repos]]
name = "example-podcast"
url = "git@github.com:example/example-podcast.git"
default_skills = []
default_sandbox = "e2b"
```

### Non-goals

- Ask Omar does not become a terminal, code editor, or session manager.
- Ask Omar does not manage the coding session itself — Flue does that.
- No orchestration, queues, or multi-agent coordination in Ask Omar.
- Natural language may propose a launcher flow, but cannot bypass its explicit
  repository, skill, sandbox, and final-start confirmation choices.

## Migration assessment

A separate, optional onboarding tool can inventory a person's existing Mac
(or other computer) and produce a capability-oriented Omarchy setup plan.
It should translate workflows, not clone platform baggage.

Example capability areas:

- screenshots and screen recording
- browser and bookmarks
- password manager
- terminal and coding workspace
- GitHub identity and credentials
- files and cloud storage
- communications
- accessibility and input preferences

The output should be a reviewable manifest consumed by Ask Omar or an Omarchy
setup agent. No files, credentials, or configuration should migrate without
explicit consent.
