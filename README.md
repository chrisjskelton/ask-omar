# Ask Omar

`0.1.0`

**Ask Omar is one box in the Omarchy top bar. Behind it is an agent that can
actually use the computer. You ask for what you want; it works out how.**

I've gotten kinda hooked on Omarchy. It's becoming the machine I do serious work
on.

It feels agent-first. The agent has become the interface, rather than another app
you open alongside all the other apps and commands you still have to learn.

Ask Omar started as a way to help me move over from macOS. It sat in the top bar,
always open, so I could ask how Omarchy worked or just ask it to do something for
me.

Then it started filling other gaps in how I work with agents: somewhere to keep
the notes and text I carry between sessions, and quick capture for what I want an
agent to see.

Somewhere along the way it stopped being an onboarding aid. It became my front
door into working with the computer.

![Ask Omar working on a request](docs/media/ask-omar-topbar.png)

Ask Omar can handle almost everything I want to do on a computer. I gave it the
privileges it needs to do real work, including the ability to request root
access, because those are no more than the privileges I already give an AI agent
in a terminal.

Omarchy lets me make that call. On my MacBook I don't get to. Apple decides, and
its reasons are good ones.

But it's my computer. I'd rather decide for myself.

That choice is also why Omarchy is turning into my work machine. The apps that
used to crowd my workflow are slipping away, because an agent can do more of the
work directly.

The interface is deliberately simple. It got there through daily use: I kept what
worked and reworked whatever kept annoying me.

I still use Pi in a terminal for real work. Omar is for everything I wouldn't
have opened a terminal for. I'm not a developer by background, and Omar is built
so that doesn't matter.

## What it does today

You type what you want. Most of mine are questions I'd otherwise have Googled:
*what's the shortcut to send a window to the next workspace?* Some are jobs:
*sort my Downloads folder by file type.* Some are help with whatever is already
open in front of me: *read what's on screen and tell me what this error wants.*

Omar answers, or more importantly can just do it for me, using `read`, `grep`,
`find`, `ls`, and `bash`. Follow-ups stay in the same conversation until you
press **New**, or it sits idle for thirty minutes.

Click the bar and a compact panel opens with **New**, settings, and close, ready
for the next ask. When Omar answers, you see his reply (not your question), with
**Reply** underneath and **Show chat** if you want the full thread. Bounce away
and back within about thirty seconds and that reply is still there; after that
the panel goes compact again.

- **Scratchpad.** Auto-saving notes doing two jobs: somewhere to write something
  down fast, and somewhere to keep the paths, prompts, and part-written text you
  carry between agent sessions. Local, and it doesn't add itself to your prompts.
  ([screenshot](#scratchpad))
- **Capture.** Left-click the camera for Omarchy's picker; right-click for a
  region, a window, the whole screen, a delay, or a silent recording. You get the
  file path rather than the image, so you can paste it into Omar or a terminal.
  ([screenshot](#capture))
- **Dictation.** Click to toggle, or hold to talk. Either way you get a draft,
  and nothing is sent until you send it. Runs on Omarchy's
  [Voxtype](https://voxtype.io), so the mic stays inactive until Dictation is
  installed. The mic is the left icon in that same bar group.
- **Past answers.** In Settings. Questions and answers are kept locally, the
  newest hundred by default. Opening one is just reading; it does not reopen
  that conversation.

## What it needs

Omarchy, and [Pi](https://pi.dev). Ask Omar runs Pi headless in the background as
its engine, so Pi has to be installed and signed in to a provider first. It
doesn't install Pi and never handles your credentials.

With no provider and model set, first setup copies Pi's own defaults from
`~/.pi/agent/settings.json` if they are there, and otherwise takes the first
model `pi --list-models` reports. You can pick another in Settings from the
models Pi lists. Reasoning starts at `low`.

Scratchpad and capture need no Pi at all.

## Privacy

No telemetry. Past answers, Scratchpad, configuration, and captures stay on your
machine. What leaves: your requests and whatever context Pi reads go to your
hosted model provider, and a `bash` command can use the network. Uninstalling
leaves Pi, your provider sign-ins, and Ask Omar's configuration and state in
place.

## Install

If you already work with an AI agent, point it at this page and let it do the
install. Otherwise:

```bash
git clone https://github.com/chrisjskelton/ask-omar.git
cd ask-omar
make install
```

The installer writes only to user locations: a systemd user service, the Omarchy
plugin, and Apps launchers. No `sudo`, and nothing under `/usr/share/omarchy` is
touched.

Then open it and check it:

```bash
omarchy-shell ask-omar open
ask-omar setup
```

`setup` tells you whether Pi is installed and signed in, and what to do if it
isn't. An agent can install Pi; only you can sign in to the provider.

## Access, `sudo`, and the guard

Read this part properly.

Omar runs as you, with your permissions. **It is not sandboxed.**

It can request `sudo`. With the default guard on, a recognised command pauses for
**Allow once / Deny**; approve and authenticate, and that command runs with full
root privileges. The guard hard-blocks a short list of catastrophic patterns
(`rm -rf /`, `dd of=/dev/…`, `mkfs`, fork bombs) and asks for one-time approval on
known risky ones. Restart and shutdown are confirmable with a warning rather than
forbidden.

The guard matches known bash text patterns. That is all it does. It cannot catch
every danger, a differently constructed command can walk around it, and it is not
a sandbox or a security boundary. Grant this access on the same terms you would
grant an agent a terminal.

Omar does not watch your screen or attach your window title to every request.
Explicit tools inspect windows or capture pixels only when a task you ask for
needs it.

## Status

Version `0.1.0`, Omarchy only. I use it every day and it will keep
changing. Issues and pull requests welcome. Built on Omarchy, Pi, and Voxtype.
MIT licensed.

## What's next

The next iteration extends that doorway into a sandboxed work zone: Ask Omar as
the launchpad, where you choose a repository, bring in the right skills and
context, and let an agent do real work in an isolated, portable environment. None
of it is in the build yet.

Omar stays the front door. The work gets a workspace to make it happen.

## Gallery

<p align="center">
<a id="scratchpad" href="#scratchpad"><img src="docs/media/ask-omar-scratchpad.png" alt="Scratchpad open from the bar" width="48%" /></a>
&nbsp;
<a id="capture" href="#capture"><img src="docs/media/ask-omar-capture.png" alt="Capture menu from the camera button" width="48%" /></a>
</p>
