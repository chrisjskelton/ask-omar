# Ask Omar

**A little help, right in your Omarchy top bar.**

Omar handles the quick questions and small desktop jobs that would otherwise send you off to a terminal or a browser. Type in the top bar and the answer opens right underneath. Notes, screenshots and dictation are one click away.

![Ask Omar beneath the Omarchy top bar, showing a shortcut cheat sheet](docs/media/ask-omar-topbar.png)

[Install](#install) · [Product page](https://aboutme.md/ask-omar) · [Releases](https://github.com/chrisjskelton/ask-omar/releases) · [Security](SECURITY.md)

Two things to know up front. Omar runs as you, and by default it shows you every shell command and waits for your OK. The AI side runs through [Pi](https://pi.dev), a separate app you install and sign in to. Notes, capture and dictation work without it.

## Things to try

- *What's the shortcut to move a window to workspace 2?*
- *Switch to the next wallpaper.*
- *Sort the files in ~/Downloads into folders by type.*

Omar can read and search your files, and run shell commands when you let it, starting from your home folder. How far it gets depends on the model you choose.

Some requests skip the AI entirely. Start with "google" or "search the web for" and Omar opens a Google search in your browser: `google hyprland gaps`. Type `open` and a full link, like `open https://omarchy.org`, and it opens that page. Neither goes to Pi, so both work before you've set Pi up.

## What's in the bar

- **Follow-ups.** Omar remembers the conversation until you press **New** or leave it for 30 minutes (you can change that in the config). Pressing **Stop**, switching model or safety mode, restarting Ask Omar, or a request that fails also starts a fresh one.
- **Scratchpad.** Up to 20 notes for paths, prompts and half-finished thoughts. They stay on your computer and aren't included when you ask Omar something. To show Omar a note, copy it into your question.
- **Capture.** Click the camera for a screenshot, or right-click for a region, a window, the current screen, a 5-second delay or a silent screen recording. Omar copies the file's path so you can paste it into a question or a terminal. With Scratchpad open, a screenshot goes into your note instead.
- **Dictation.** With [Voxtype](https://voxtype.io) installed, click the mic to start and stop, or hold it while you talk. Your words are typed where you're writing, and nothing is sent until you press Enter.
- **Past answers.** Settings → Past answers keeps your recent questions and answers. Opening one lets you read it again; it doesn't pick that conversation back up.

## Why I built it

I got hooked on Omarchy while moving over from macOS. Omar started as a box in the top bar where I could ask how the desktop worked. Then it picked up the other things I kept reaching for: somewhere to jot down paths and prompts, and a quick way to grab what's on screen.

I still use Pi in a terminal for big pieces of work that take a while. Omar is for everything I'd never open a terminal for. I don't come from a software development background, and I built this for people who don't either.

Omarchy lets me decide how much an AI can do on my computer. On my Mac, Apple makes that call for me. So Omar runs with my permissions, and you choose how often it checks with you first.

It looks simple because I kept using it and fixing whatever annoyed me. It's a personal project and it will keep improving. [Issues and ideas](CONTRIBUTING.md) are welcome, and the [roadmap](docs/ROADMAP.md) lists what isn't built yet.

## Install

You'll need Omarchy 4, Python 3.11 or newer (as `python`), Node 22.18 or newer, `make` and `git`. For the AI side you'll also need [Pi](https://pi.dev), signed in to a provider. I've tested this release on Omarchy 4.0.3-1 with Pi 0.99.1.

Copy the full commit for the latest release from the [release notes](https://github.com/chrisjskelton/ask-omar/releases), then run:

```bash
omarchy plugin add https://github.com/chrisjskelton/ask-omar.git --yes
cd ~/.config/omarchy/plugins/ask-omar.assistant
ASK_OMAR_COMMIT=<full commit from the release notes>
git -c advice.detachedHead=false checkout --detach "$ASK_OMAR_COMMIT"
make setup ASK_OMAR_COMMIT="$ASK_OMAR_COMMIT"
omarchy plugin enable ask-omar.assistant
```

The first line downloads the widget and leaves it switched off. The checkout pins it to the release you picked, and `make setup` won't run if the folder doesn't match that commit exactly. If a tool it needs is missing, setup stops and says which before it installs anything. Then it adds the background service, the `ask-omar` commands and two app-menu entries. It doesn't use `sudo`, and everything it installs lives in your home folder. The last line puts Omar in your bar.

To connect the AI, run `pi`, type `/login` and sign in to your provider. Then:

```bash
ask-omar setup
omarchy-shell ask-omar open
```

`ask-omar setup` checks Pi and tells you anything left to do. The first time, Omar uses Pi's default model, or the first one Pi lists, and you can pick another in Settings. Never paste passwords, tokens or sign-in codes into Omar.

Finding Ask Omar in the Omarchy marketplace means it's listed there, not that anyone has checked its security.

## Permissions and the guard

Omar runs as you. It can open your files, run programs and use the network, just as you can in a terminal. It isn't a sandbox. Whether it can get admin rights depends on how your system handles `sudo` and passwords.

**Reading never asks.** Omar can read and search any file you can, in every mode.

**Commands go through the guard.** Pi's own shell tool is switched off, so every command Omar wants to run goes through Ask Omar instead, and follows the mode you pick in **Settings → Safety**:

| Mode | What happens |
|---|---|
| **Ask First** (default) | You see every command before it runs and choose **Allow once**, **Allow for 15 minutes** or **Deny**. |
| **Ask for Recognized Risks** | Everyday commands, ordinary deletes included, run without asking. Omar only stops for ones that look dangerous. |
| **Block Commands** | No shell commands at all. Omar can still read and search your files. |
| **Always Allow — Dangerous** | Everything runs without asking, destructive commands included. Settings asks you to confirm before turning it on. |

**Allow for 15 minutes** lets everyday commands run without asking, for this question and the ones after it, until the 15 minutes are up or the conversation ends. Commands that look dangerous still ask.

**The risk check is a warning, not a lock.** In every mode except Always Allow, Omar stops and asks before commands that look dangerous, such as `rm -rf`, `sudo`, wiping or partitioning a disk, shutting down, piping a download straight into a shell, or turning down Ask Omar's own safety setting. It goes by what the command says, so the same damage done another way, like running a script, can slip past it. Only Ask First, with no 15-minute allowance running, shows you every command.

A few more things worth knowing:

- When you ask Omar to delete something, it's told to move it to the Trash so you can get it back. That's an instruction to the AI, not a guarantee, and in Ask for Recognized Risks an ordinary delete runs without asking.
- **Stop** cancels the current task. It doesn't undo anything already done.
- A command is stopped after 60 seconds or 64 KiB of output. Anything it leaves running in the background stops when the conversation ends.
- If you don't answer an approval within 90 seconds, the request is cancelled and the next question starts a fresh conversation.

Read commands as carefully as you would in a terminal, and don't leave Always Allow on while Omar reads things you don't trust. [SECURITY.md](SECURITY.md) has the full detail.

## Privacy and retention

Ask Omar has no telemetry. Your notes, past answers and settings stay on your computer, in `~/.local/state/ask-omar` and `~/.config/ask-omar`. Your user permissions protect them; Ask Omar doesn't encrypt them.

What leaves your computer: your questions, and whatever Omar reads to answer them, go through Pi to your AI provider, and your provider's own settings decide what they keep. You sign in to your provider in Pi, and Ask Omar never handles that sign-in. Ask Omar starts Pi with its own fixed set of tools and without your Pi extensions, skills or context files, and the conversation lives only in memory. Web searches open Google, and commands Omar runs can use the network.

What's kept, and for how long:

- **Past answers:** up to the newest 100. Clear them in Settings, or set `limit = 0` under `[history]` in `~/.config/ask-omar/config.toml` to keep none.
- **Scratchpad:** up to 20 notes of 20,000 characters each. Screenshots added to a note are private copies, and deleting the note doesn't delete them.
- **A question you started but didn't send:** comes back for up to 24 hours.
- **Pi's background log:** private, and trimmed to its last 1 MiB whenever a new conversation starts.
- **Your original screenshots and recordings:** stay wherever Omarchy saved them.

If Ask Omar's saved-data file is ever damaged, Ask Omar keeps a copy as `state.json.unreadable-…`, loads what it can, and tells you in Scratchpad.

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

Don't skip the last line: the bar keeps running the old widget until the shell restarts. `omarchy plugin update` only updates the widget, not the background service. If you use it anyway, the new widget shows "Finish updating Ask Omar" and tells you what's left to do.

## Remove

```bash
cd ~/.config/omarchy/plugins/ask-omar.assistant
make uninstall
omarchy plugin remove ask-omar.assistant
```

`make uninstall` switches the widget off and removes the background service, commands and app-menu entries, leaving alone any you've edited. When you run it in a terminal, it then asks whether to delete your notes, history and settings too. The answer defaults to no, and if you keep them they come back when you reinstall. `omarchy plugin remove` deletes the widget folder. Pi and your provider sign-ins aren't touched, and nothing your provider holds is erased.

## Troubleshooting

- **Setup won't replace a file:** you or another program changed it, or Ask Omar didn't put it there. Move the named file somewhere safe and run setup again.
- **Setup says the checkout is at the wrong commit, or has changes:** run the checkout line again with the full commit from the release notes, and move any local changes out of the plugin folder.
- **The widget says the background service isn't installed, or "Finish updating Ask Omar":** follow the [Update](#update) steps, then run `ask-omar setup`. If it only says the bar is running an older widget, run `omarchy-restart-shell`.
- **Pi is missing or signed out:** install Pi, run `pi` and sign in with `/login`, then run `ask-omar setup` again.
- **The mic is greyed out:** dictation needs Voxtype. Everything else works without it.
- **A note won't save:** keep the editor open, since your text is still there, and fix what the message names, such as a note that's too long. If it says the notes file couldn't be read or moved aside, fix that file's permissions, run `systemctl --user restart ask-omar.service`, then save again.
- **Anything else:** `systemctl --user status ask-omar.service` and `journalctl --user -u ask-omar.service -n 40` show what the service is doing. Check the output for anything private before you share it.

## How it fits together

```text
Omarchy widget → ask-omar command → private Unix socket → Python user service → Pi → your provider
                                                     ↘ local notes and history
```

The service uses only Python's standard library. Pi runs the AI and talks to your provider. Omarchy supplies the desktop and capture tools, and Voxtype the optional dictation.

## Gallery

![Scratchpad with example notes](docs/media/ask-omar-scratchpad.png)
![Capture choices](docs/media/ask-omar-capture.png)

MIT licensed. Built on Omarchy, Pi and Voxtype, and not affiliated with or endorsed by any of them.
