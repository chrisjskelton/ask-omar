# Contributing

Ask Omar is currently an experimental Omarchy plugin. Contributions should
preserve these principles:

1. Express outcomes rather than implementation details.
2. Discover capabilities instead of assuming specific installed apps.
3. Keep fixed desktop actions structured and reviewable. Pi may use its direct
   `read`, `grep`, `find`, and `ls` tools. Shell commands must go through Ask
   Omar's command tool; preserve its access modes, approval UI, runtime limits, and
   clear reporting.
4. Keep local actions useful when the AI backend is unavailable.
5. Store configuration and state in XDG user directories.
6. Never modify packaged files under `/usr/share/omarchy`.

Run before submitting a change:

```bash
make test
make validate
```

The root `manifest.json` is the plugin entry point. The widget is installed with
`omarchy plugin add`, which makes the plugin folder a Git checkout; `make setup`
in that folder installs the companion backend. To try local changes, commit them,
run `omarchy plugin add /path/to/your/ask-omar`, then in the plugin folder run
`make setup ASK_OMAR_COMMIT=$(git rev-parse HEAD)`. The test suite includes
fake-command install, update and removal checks, so it does not change your desktop.

The public product page at https://aboutme.md/ask-omar is an Astro route in the
private `aboutme.md` repository, deployed to the existing VPS static root. See
[release ownership](docs/RELEASING.md). Record demo media with invented data and
review every frame for private content.
