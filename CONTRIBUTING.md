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
