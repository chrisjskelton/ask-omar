# Ask Omar

**A little help, right in your Omarchy top bar.**

Omar handles the quick questions and small desktop jobs that would otherwise send you off to a terminal or a browser. Type in the top bar and the answer opens right underneath. Notes, screenshots and dictation are one click away.

![Ask Omar beneath the Omarchy top bar, showing a shortcut cheat sheet](docs/media/ask-omar-topbar.png)

[Install](#install) · [Guide](docs/GUIDE.md) · [Security](SECURITY.md) · [Product page](https://aboutme.md/ask-omar) · [Releases](https://github.com/chrisjskelton/ask-omar/releases)

## What it does

- **Ask, then follow up.** *What's the shortcut to move a window to workspace 2?* *Sort my Downloads folder by file type.* Omar answers, or does the job, and remembers the conversation while you're using it.
- **Keep a Scratchpad.** Up to 20 local notes for paths, prompts and half-finished thoughts. They stay on your computer and aren't sent with your questions unless you paste them in.
- **Grab what's on screen.** Take a screenshot or a recording from the bar. Omar copies the file's path, ready to paste into a question or a terminal. With Scratchpad open, a screenshot goes into your note.
- **Say it instead.** With [Voxtype](https://voxtype.io) installed, hold the mic and talk. Nothing is sent until you press Enter.
- **Skip the AI.** Start with "google" to search the web, or type `open` and a link.

The AI runs through [Pi](https://pi.dev), a separate app you install and sign in to. Everything else here works without it.

## Why I built it

I got hooked on Omarchy while moving over from macOS. Omar started as a box in the top bar where I could ask how the desktop worked. Then it picked up the other things I kept reaching for, like notes and a quick screenshot.

I still use Pi in a terminal for big jobs. Omar is for everything I'd never open a terminal for. I don't come from a software background, and I built it for people who don't either. It looks simple because I use it every day and fix whatever annoys me.

## Install

You'll need Omarchy 4, Python 3.11 or newer (as `python`), Node 22.18 or newer, `make`, `git` and Omarchy's standard tools, and for the AI, [Pi](https://pi.dev) signed in to a provider. I've tested this release on Omarchy 4.0.3-1 with Pi 0.99.1. Read [Permissions](#permissions-and-the-guard) first. It's short.

Copy the full commit for the latest release from the [release notes](https://github.com/chrisjskelton/ask-omar/releases), then run:

```bash
omarchy plugin add https://github.com/chrisjskelton/ask-omar.git --yes
cd ~/.config/omarchy/plugins/ask-omar.assistant
ASK_OMAR_COMMIT=<full commit from the release notes>
git -c advice.detachedHead=false checkout --detach "$ASK_OMAR_COMMIT"
make setup ASK_OMAR_COMMIT="$ASK_OMAR_COMMIT"
omarchy plugin enable ask-omar.assistant
```

This pins Omar to the release you picked and adds its background service, the `ask-omar` commands and two app-menu entries. Setup never uses `sudo`, and everything it installs lives in your home folder. The last line puts Omar in your bar.

To connect the AI, run `pi`, type `/login` and sign in to your provider. Then:

```bash
ask-omar setup
omarchy-shell ask-omar open
```

`ask-omar setup` tells you anything left to do. Never paste passwords, tokens or sign-in codes into Omar.

## Permissions and the guard

Omarchy lets me decide how much an AI can do on my computer. On my Mac, Apple makes that call for me. So Omar runs as you, and you choose how often it checks with you first.

It can open your files, run programs and use the network, just as you can in a terminal. It isn't a sandbox. Reading files never asks, but every shell command goes through Ask Omar. **Ask First**, the default, shows you each one and waits for **Allow once**, **Allow for 15 minutes** or **Deny**. **Settings → Safety** also has **Ask for Recognized Risks**, which only stops for commands that look dangerous, **Block Commands** and **Always Allow — Dangerous**.

The risk check is a warning, not a lock. It spots things like `rm -rf` and `sudo` by what the command says, so the same damage done another way, like running a script, can slip past it. Only Ask First, with no 15-minute allowance running, shows you every command. **Stop** doesn't undo what already ran. The [guide](docs/GUIDE.md#permissions-and-the-guard) and [SECURITY.md](SECURITY.md) have the detail. A marketplace listing isn't a security review.

## Privacy and retention

Ask Omar has no telemetry. Your notes, past answers and settings stay on your computer. Your questions, and whatever Omar reads to answer them, go through Pi to your AI provider, and your provider's settings decide what they keep. Ask Omar never handles your provider sign-in. The guide lists [what's kept, and for how long](docs/GUIDE.md#privacy-and-retention).

## Update

Read the new release notes, copy their full commit, then run:

```bash
cd ~/.config/omarchy/plugins/ask-omar.assistant
git fetch origin
ASK_OMAR_COMMIT=<full commit from the release notes>
git -c advice.detachedHead=false checkout --detach "$ASK_OMAR_COMMIT"
make setup ASK_OMAR_COMMIT="$ASK_OMAR_COMMIT"
omarchy-restart-shell
```

Don't skip the last line: the bar keeps running the old widget until the shell restarts. `omarchy plugin update` only updates the widget, not the background service.

## Remove

```bash
cd ~/.config/omarchy/plugins/ask-omar.assistant
make uninstall
omarchy plugin remove ask-omar.assistant
```

`make uninstall` removes the background service, commands and menu entries. Run in a terminal, it then asks whether to delete your notes, history and settings too, and the answer defaults to no. Pi and your provider sign-ins aren't touched.

## More

The [guide](docs/GUIDE.md) has everything else, including troubleshooting. The [changelog](CHANGELOG.md) says what's new and the [roadmap](docs/ROADMAP.md) what's next. [Issues and ideas](CONTRIBUTING.md) are welcome.

MIT licensed. Built on Omarchy, Pi and Voxtype, and not affiliated with or endorsed by any of them.
