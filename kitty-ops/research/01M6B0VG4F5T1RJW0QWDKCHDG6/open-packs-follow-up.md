# Draft issue for spec-kitty-open-packs: internal doctrine still tells agents to edit CHANGELOG.md

**Title:** Internal pack: write changelog fragments, not CHANGELOG.md edits; stop "keep both sides" changelog conflict advice

**Body:**

## Problem

Core now records changelog entries as per-PR fragments: a pull request adds
`docs/changelog/unreleased/<id>.<section>.md` (section: `breaking`, `upgrade-notes`, `added`, `changed`,
`fixed`, `internal`) and never edits `docs/changelog/CHANGELOG.md`. The release assembles the
fragments with `python -m scripts.release.changelog_fragments assemble --write`. The style and US
spelling gates run on each fragment, and `validate_release --mode tag` refuses while any is left.
See `docs/changelog/unreleased/README.md` and ADR `<number>` in spec-kitty/spec-kitty (landing PR `#<n>`).

The internal pack still tells agents to edit the changelog file. When it conflicts, it tells them
to keep both sides. That advice re-added duplicate entries three times in the 2026-10-31/11-01
landing run, once left a second `updated:` key, and once landed a duplicate on `main`.

## Places to change (pinned `packs/internal` at `ecda7b00c789`)

| File | Today | Change to |
|---|---|---|
| `procedures/landing-contributor-prs.procedure.yaml`, step "Rebase onto current main…" | "Where docs/changelog/CHANGELOG.md conflicts, keep both sides' entries." | "If the PR still edits CHANGELOG.md, move its entry into a `docs/changelog/unreleased/` fragment instead of resolving the conflict." |
| same file, step "Update the PR body, changelog and docs" | "add an entry under [Unreleased] in docs/changelog/CHANGELOG.md … Commit it as its own `docs(landing):` commit" | "add the entry as `docs/changelog/unreleased/<pr>.<section>.md` (the entry text unchanged: bold impact lead with refs, then before and after, under 1,200 characters); run `python -m scripts.docs.check_changelog_style`" |
| `procedures/issue-to-mission-delivery.procedure.yaml`, compaction step | "keep both sides' entries when docs/changelog/CHANGELOG.md conflicts" | drop it (fragments do not conflict) |
| same file, step "Update the changelog and docs" | "add an entry under [Unreleased] in docs/changelog/CHANGELOG.md" | "add a `docs/changelog/unreleased/<id>.<section>.md` fragment" |
| `procedures/semi-auto-delivery.procedure.yaml`, "Closeout the canonical way" | "update docs/changelog" | "add a changelog fragment in `docs/changelog/unreleased/`" |
| `skills/land-pr.skill.md` step 9, `skills/mission-from-issue.skill.md` step 8, `skills/semi-auto.skill.md` step 8, `skills/land-pr.skill.yaml` description | "changelog" / "update `docs/changelog`" | name the fragment explicitly |
| `styleguides/spec-kitty-docs-lint-config.styleguide.yaml`, `structural_lint_config.frontmatter_in_scope_exclusions` | no entry for the fragment directory | add `"changelog/unreleased/**"` (fragments are entries, not pages). Core overlays it today through `scripts/docs/_page_scope.lint_config_without_fragments`; once upstream lists it the overlay is a no-op and can be dropped. Also check lines ~148 and ~186, which list `changelog` / `CHANGELOG.md`. |

Then run `spec-kitty charter pack regenerate-graph` and bump the core pin with
`spec-kitty charter pack vendor --pack internal --ref <sha>`.

## Follow-ups that depend on the other two landing changes (fill in once they land)

- **Docs retrieval index off PRs (change 2):** the same procedures tell agents to run
  `docs_index --write` and `freshen_adr_inventory` on every doc or ADR change. Once core
  regenerates them on `main`, replace that with "do not regenerate the index or inventory in a PR".
- **Merge queue (change 3):** replace `gh pr merge <n> --rebase --auto` hand-offs and the
  rebase-and-re-run loop with "add to the merge queue", and tell the fleet not to push to a
  queued PR (a push evicts it).
