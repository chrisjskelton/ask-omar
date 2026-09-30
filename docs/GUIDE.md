# Ask Omar guide

Everything the [README](../README.md) leaves out: how each part works, what the safety modes do, what's kept, and what to do when something goes wrong. [SECURITY.md](../SECURITY.md) has the full trust model.

- [Asking Omar](#asking-omar)
- [Scratchpad](#scratchpad)
- [Capture](#capture)
- [Dictation](#dictation)
- [Permissions and the guard](#permissions-and-the-guard)
- [Privacy and retention](#privacy-and-retention)
- [Install, update and remove in detail](#install-update-and-remove-in-detail)
- [Troubleshooting](#troubleshooting)
- [How it fits together](#how-it-fits-together)

## Asking Omar

Type in the top bar and the answer opens underneath. A few things to try:

- *What's the shortcut to move a window to workspace 2?*
- *Switch to the next wallpaper.*
- *Sort the files in ~/Downloads into folders by type.*

Omar can read and search your files, and run shell commands when you let it, starting from your home folder. How far it gets depends on the model you choose.

**Models.** The first time, Omar uses Pi's default model, or the first one Pi lists. You can pick another in Settings.

**Follow-ups.** Omar remembers the conversation until you press **New** or leave it for 30 minutes. You can change the 30 minutes with `idle_timeout_minutes` under `[conversation]` in `~/.config/ask-omar/config.toml`. Pressing **Stop**, switching model or safety mode, restarting Ask Omar, or a request that fails also starts a fresh conversation.

**Shortcuts that skip the AI.** Start with "google" or "search the web for" and Omar opens a Google search in your browser: `google hyprland gaps`. Type `open` and a full link, like `open https://omarchy.org`, and it opens that page. Neither goes to Pi, so both work before you've set Pi up.

**Past answers.** Settings → Past answers keeps your recent questions and answers. Opening one lets you read it again; it doesn't pick that conversation back up.

## Scratchpad

![Scratchpad with example notes](media/ask-omar-scratchpad.png)

Up to 20 notes for paths, prompts and half-finished thoughts. They stay on your computer and aren't included when you ask Omar something. To show Omar a note, copy it into your question.

## Capture

![Capture choices](media/ask-omar-capture.png)

Click the camera for a screenshot, or right-click for a region, a window, the current screen, a 5-second delay or a silent screen recording. Omar copies the file's path so you can paste it into a question or a terminal. With Scratchpad open, a screenshot goes into your note instead.

## Dictation

With [Voxtype](https://voxtype.io) installed, click the mic to start and stop, or hold it while you talk. Your words are typed where you're writing, and nothing is sent until you press Enter. Without Voxtype the mic is greyed out, and everything else still works.

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
- Never paste passwords, tokens or sign-in codes into Omar.
- Finding Ask Omar in the Omarchy marketplace means it's listed there, not that anyone has checked its security.

Read commands as carefully as you would in a terminal, and don't leave Always Allow on while Omar reads things you don't trust.

## Privacy and retention

Ask Omar has no telemetry. Your notes, past answers and settings stay on your computer, in `~/.local/state/ask-omar` and `~/.config/ask-omar`. Your user permissions protect them; Ask Omar doesn't encrypt them.

What leaves your computer: your questions, and whatever Omar reads to answer them, go through Pi to your AI provider, and your provider's own settings decide what they keep. You sign in to your provider in Pi, and Ask Omar never handles that sign-in. Ask Omar starts Pi with its own fixed set of tools and without your Pi extensions, skills or context files, and the conversation lives only in memory. Web searches open Google, and commands Omar runs can use the network.

What's kept, and for how long:

- **Past answers:** the newest 100 by default (change `limit` under `[history]`). Clear them in Settings, or set `limit = 0` under `[history]` in `~/.config/ask-omar/config.toml` to keep none.
- **Scratchpad:** up to 20 notes of 20,000 characters each. Screenshots added to a note are private copies, and deleting the note doesn't delete them.
- **A question you started but didn't send:** comes back for up to 24 hours.
- **Pi's background log:** private, and trimmed to its last 1 MiB whenever a new conversation starts.
- **Your original screenshots and recordings:** stay wherever Omarchy saved them.

If Ask Omar's saved-data file is ever damaged, Ask Omar keeps a copy as `state.json.unreadable-…`, loads what it can, and tells you in Scratchpad.

## Install, update and remove in detail

The commands are in the README's [Install](../README.md#install), [Update](../README.md#update) and [Remove](../README.md#remove) sections. This is what they do.

**Install.** `omarchy plugin add` downloads the widget and leaves it switched off. The checkout pins it to the release you picked, and `make setup` won't run if the folder doesn't match that commit exactly. If a tool it needs is missing, setup stops and says which before it installs anything. Then it adds the background service, the `ask-omar` commands and two app-menu entries. It doesn't use `sudo`, and everything it installs lives in your home folder. `omarchy plugin enable` puts Omar in your bar. After you sign in to Pi, `ask-omar setup` checks Pi and tells you anything left to do.

**Update.** Always finish with `omarchy-restart-shell`: the bar keeps running the old widget until the shell restarts. `omarchy plugin update` only updates the widget, not the background service. If you use it anyway, the new widget shows "Finish updating Ask Omar" and tells you what's left to do.

**Remove.** `make uninstall` switches the widget off and removes the background service, commands and app-menu entries, leaving alone any you've edited. When you run it in a terminal, it then asks whether to delete your notes, history and settings too. The answer defaults to no, and if you keep them they come back when you reinstall. `omarchy plugin remove` deletes the widget folder. Pi and your provider sign-ins aren't touched, and nothing your provider holds is erased.

## Troubleshooting

- **Setup won't replace a file:** you or another program changed it, or Ask Omar didn't put it there. Move the named file somewhere safe and run setup again.
- **Setup says the checkout is at the wrong commit, or has changes:** run the checkout line again with the full commit from the release notes, and move any local changes out of the plugin folder.
- **The widget says the background service isn't installed, or "Finish updating Ask Omar":** follow the README's [Update](../README.md#update) steps, then run `ask-omar setup`. If it only says the bar is running an older widget, run `omarchy-restart-shell`.
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
