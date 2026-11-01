---
affected_files: []
cycle_number: 1
mission_slug: human-slug-handle-parity-01M6BV06
reproduction_command: spec-kitty agent tasks move-task WP02 --to approved --mission human-slug-handle-parity-01M6BV06 --agent reviewer-renata
reviewed_at: '2026-11-01T17:31:48Z'
reviewer_agent: reviewer-renata
wp_id: WP02
---

Approved by reviewer-renata: approval:WP02

# Review record — WP02 (Two paths, one answer)

Reviewer: reviewer-renata (pi/deepseek-v4.1-flash-1017). Verdict: **approved**.

## What I checked

- **T004** pins the command's own entry point (`implement_phases.detect_mission_context`),
  not the helper it calls: the human slug, the composed slug and the mid8 all return
  `(None, "smoke-test-01M6BTQX")`, an unknown handle still exits 2 with the "No mission
  found" text, and a shared human slug exits 2 (text) / 1 (`--json`) naming both
  candidates. Red-first proven by reverting WP01's rung in the lane: 4 of 7 rows failed,
  including the ambiguity row, which reported "not found" instead of the candidates.
- **T005** is the durable half: one matrix runs the same handles through the identity
  resolver and the read-path bare-modern fold and asserts the same *expected directory*
  (not merely that the two agree — the `expected_slug` column is the real assertion, so a
  change that made both paths wrong together still fails). The ambiguity case asserts both
  paths refuse and name both composed slugs. Red without WP01's fold for the human-slug
  row and for the ambiguity case.
- **T006** replaces the stale `--mission` example (the retired `NNN-` shape) with the four
  accepted forms, wording consistent with `mission_type.py`. `docs/api/cli-commands.md`
  carries the regenerated `spec-kitty implement` section only: the full builder could not
  run here (its per-command `--help` capture has a hardcoded 30 s subprocess timeout and
  this host is at load ~200), so the section was regenerated with the builder's own
  `capture_help` + `render_section`, and the resulting diff is that one block — 6
  insertions, 3 deletions, nothing else in the file. No test asserts the old string.
- **T007** is a `docs/changelog/unreleased/` fragment (the repository's convention for PR
  entries), not an edit of `CHANGELOG.md`; 768 characters, bold impact-first lead with
  `(#6278)`, before/after, `## What to do`. `check_changelog_style` reports 0 errors and
  `check_spelling --pass unreleased` 0 findings over the fragment.
- No personal data, machine-local path, `TODO`, skip or `xfail` in the diff; no gate
  weakened.

## Suites run

- `tests/specify_cli/cli/commands/test_selector_resolution.py` +
  `tests/specify_cli/cli/commands/agent/test_implement_mission_handle.py` — 44 passed.
- `tests/architectural/test_no_legacy_terminology.py` — 98 passed (one first-run failure
  was an empty `packs/internal` in the fresh lane worktree; `make sync-packs` fixed it, and
  the same check is green — an environment gap, not the diff).
- `scripts.docs.check_changelog_style` — 0 errors. `scripts.docs.check_spelling --pass
  unreleased` — 0 findings. ruff + mypy on every changed Python file — clean.
- Pre-review regression gate: no new failures (both WPs).

## Findings

None requiring a change. Recorded for the record:

- The parity matrix does not cover the *unknown handle* case on both paths; the ambiguity
  case is the interesting half and it is covered. A future change that makes one path
  accept a handle the other refuses on a new form would still be caught by the human-slug
  rows, which are the ones that drifted.
- The regenerated CLI-reference section depends on the builder's rendering, which the
  freshness gate re-derives in CI; if that gate disagrees, the section must be rebuilt on
  a host where the full builder can complete.
