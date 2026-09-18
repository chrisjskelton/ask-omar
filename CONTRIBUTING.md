# Contributing

Ask Omar is currently an experimental Omarchy plugin. Contributions should
preserve these principles:

1. Express outcomes rather than implementation details.
2. Discover capabilities instead of assuming specific installed apps.
3. Keep fixed desktop actions structured and reviewable. Pi may use its explicitly
   granted `read`, `grep`, `find`, `ls`, and `bash` tools; preserve the command
   guard, confirmation UI, and clear reporting around that access.
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

The static site lives in `docs/`. Preview it with `python -m http.server 8000 --directory docs`, and use the manually triggered **Publish site**
GitHub Actions workflow after GitHub Pages is enabled with Actions as its source.
Record demo media with invented data and review every frame for private content.
