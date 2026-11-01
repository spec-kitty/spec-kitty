# Change 1 research: per-PR changelog fragments

Op `01M6B0VG4F5T1RJW0QWDKCHDG6`. Read against `origin/main` at `bf8d27ce`.

## Findings

- **The brief's default directory would bring the conflict back.** Every `*.md` under `docs/` must
  have a row in `docs/development/page-inventory.yaml` (`check_docs_freshness.py:683`,
  `INVENTORY-INCOMPLETE`), an entry in `docs/development/docs-retrieval-index.yaml`
  (`docs_index.py:209` walks `docs/**/*.md`), frontmatter with a 50-180 character `description`,
  and passes about 15 other `docs_root.rglob("*.md")` scanners (`scripts/docs/*`,
  `tests/docs/test_docs_structural_lint.py`). A fragment at `docs/changelog/unreleased/<pr>.<section>.md`
  would make every PR edit both shared generated files, which is the conflict this change removes.
  **Decision: fragments live in a root-level `changelog.d/`**, outside `docs/`, so no docs gate sees them.
- **`.github/CHANGELOG.md` is not separate.** Like the root `CHANGELOG.md`, it is a symlink to
  `docs/changelog/CHANGELOG.md`. Nothing to migrate.
- **Section headings are fixed and ordered.** `check_changelog_style.SECTION_ORDER` is Breaking,
  Upgrade Notes, Added, Changed, Fixed, Internal. The brief's "💥 Breaking" is not a heading in the file.
  `####` subheadings are allowed only under Fixed; the current `[Unreleased]` section has none, so
  fragments are headingless and the release editor groups them if wanted.
- **The style guard and the spelling pass read only the `[Unreleased]` section**, located by
  `validate_release.unreleased_section`. Wrapping one fragment in a synthetic
  `## [Unreleased]` / `### <Section>` changelog lets the same rules run unchanged, with findings mapped
  back to the fragment's own lines. No rule is duplicated.
- **The frontmatter `updated:` key is a second conflict point** in the changelog (the 2026-11-01
  run once left a duplicated `updated:` key). Fragments do not touch it; the assembly step sets it.
- **Release tooling** (`extract_changelog.py`, `validate_release.py`, `release.yml:351`) reads the
  assembled `CHANGELOG.md`. Assembling first (`python -m scripts.release.changelog_fragments assemble --write`)
  keeps them unchanged. `validate_release --mode tag` gains a refusal while any fragment is left unassembled,
  so a tag cannot ship notes that miss entries.
- **CI routing:** a `changelog.d/`-only PR matches no filter group in `ci-router.yml`; the always-on
  `docs-lint` job (`ci-router.yml:886-899`) runs the style guard and the spelling check, which now
  cover fragments. The `unmatched` catch-all only fires for `src/**`, so nothing else changes.
- **PR number at authoring time.** A contributor writes the fragment before the PR exists, so the id
  may be the PR number, the issue number or a short slug (`[0-9a-z][0-9a-z-]*`). Two fragments with the
  same name are a visible add/add conflict, never a silent duplicate.

## Docs and doctrine to update

Core: `docs/development/how-to/pr-landing.md`, `docs/development/how-to/review-gates.md`,
`RELEASE_CHECKLIST.md`, `scripts/release/README.md`, `CLAUDE.md` (the `__init__.py` rule).
Open-packs follow-up (not edited here): the landing skill and internal-pack doctrine that tell agents
to edit `CHANGELOG.md`.
