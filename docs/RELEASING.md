# Release ownership

Ask Omar's application, installer, tests, README and release screenshots live in this repository. The public product page is https://aboutme.md/ask-omar.

The canonical brochureware route and its assets live in the private `aboutme.md` Astro repository at `artifacts/aboutme-md/`. That app owns its static build and deployment. `ops-stack` owns infrastructure configuration and operational guidance. This repository has no separate product page; the README is the source of truth for behaviour, and the brochure summarises it.

Before publishing a release:

1. Run the test suite and root plugin validation against the exact release commit.
2. Review security, private data and Git author/committer identities; do not push private history or scratch/demo recording files.
3. Keep `main` fixed while it is under marketplace review. Verify the README install command against the intended full commit and test installation/update/removal in an isolated environment.
4. Update the README/gallery/marketplace preview together and check the aboutme.md page against the README.
   Bump the version in `manifest.json`, `service/ask_omar/__init__.py` and `widgetVersion` in `plugin/AskOmar.qml` together (`tests/test_version.py` checks them).
5. Run remote CI, then publish the reviewed experimental tag and release notes. Put the release's full 40-character commit in the notes and marketplace issue so users can verify their checkout before installation. Verify repository and website links before announcing.
6. Remove superseded branches only after their work is merged or preserved privately and the final release is verified.

There is currently no demo video. Record any new one on the current release with invented data, and show the approval panel if the demo runs a command.
