# Release ownership

Ask Omar's application, installer, tests, README and release screenshots live in this repository. The public product page is https://aboutme.md/ask-omar.

The canonical brochureware route and its assets live in the private `aboutme.md` Astro repository at `artifacts/aboutme-md/`. That app owns its static build and deployment. `ops-stack` owns infrastructure configuration and operational guidance. The standalone HTML/CSS in this repository is a release preview snapshot, not a second production deployment. GitHub Pages is not used for the production site.

Before publishing a release:

1. Run the test suite and root plugin validation against the exact release commit.
2. Review security, private data and Git author/committer identities; do not push private history or scratch/demo recording files.
3. Verify the README install command against the intended tag and test installation/update/removal in an isolated environment.
4. Update the README/gallery/marketplace preview together and keep the aboutme.md demo in sync.
5. Run remote CI, then publish the reviewed experimental tag and release notes. Verify repository and website links before announcing.
6. Remove superseded branches only after their work is merged or preserved privately and the final release is verified.

The current demo is 49.2 seconds, silent and captioned. It joins real recordings and omits response waits; dictation is documented but not demonstrated in this cut.
