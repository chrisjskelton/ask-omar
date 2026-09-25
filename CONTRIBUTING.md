# Contributing

Ask Omar is currently an experimental Omarchy plugin. Contributions should
preserve these principles:

1. Express outcomes rather than implementation details.
2. Discover capabilities instead of assuming specific installed apps.
3. Keep fixed desktop actions structured and reviewable. Pi may use its direct
   `read`, `grep`, `find`, and `ls` tools. Shell commands must go through Ask
   Omar's broker; preserve its access modes, approval UI, runtime limits, and
   clear reporting.
4. Keep local actions useful when the AI backend is unavailable.
5. Store configuration and state in XDG user directories.
6. Never modify packaged files under `/usr/share/omarchy`.

Run before submitting a change:

```bash
make test
make validate
```

The root `manifest.json` is the marketplace entry point. `make setup` installs
only the companion backend for a marketplace checkout; `make install` also
installs and enables the widget. The test suite includes fake-command install,
update and removal checks, so it does not change your desktop.

The standalone release preview lives in `docs/`. Preview it with
`python -m http.server 8000 --directory docs`. The production page at
https://aboutme.md/ask-omar is an Astro route in the private `aboutme.md`
repository, deployed to the existing VPS static root. See [release ownership](docs/RELEASING.md).
Record demo media with invented data and review every frame for private content.
