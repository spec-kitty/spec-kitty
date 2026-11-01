---
work_package_id: WP02
title: Record the change and hand the routing half over
dependencies:
- WP01
requirement_refs:
- C-003
- SC-004
planning_base_branch: issue-6516-status-lock-dir-name-ssot
merge_target_branch: issue-6516-status-lock-dir-name-ssot
branch_strategy: Planning artifacts for this mission were generated on issue-6516-status-lock-dir-name-ssot. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6516-status-lock-dir-name-ssot unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-status-lock-dir-name-ssot-01M68JA7
base_commit: 74cb509376963a1878c4a76758562faa17ef305e
created_at: '2026-10-31T08:52:00.000000+00:00'
subtasks:
- T007
- T008
- T009
history:
- at: '2026-10-31T08:52:00Z'
  actor: claude
  action: created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/changelog/
create_intent:
- docs/changelog/CHANGELOG.md
execution_mode: planning_artifact
owned_files:
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
tracker_refs:
- '6516'
---

# WP02 — Record the change and hand the routing half over

## ⚡ Do This First: Load Agent Profile

Load **`python-pedro`** (implementer) with the `/spk-charter-profile-load` skill before reading
anything else. The review runs under **`reviewer-renata`**.

## Objective

Record the shipped change for a maintainer, and give issue #6516's second half a filed follow-up
instead of quietly leaving it out. Spec: C-003, SC-004.

The second half, quoted from the issue: *"The second gap is in CI routing: a change to
`src/specify_cli/status/` does not route `tests/audit/test_no_legacy_path_literals.py`."* That is
why #6367's PR shipped the literal without CI noticing, and why #6582 only surfaced it in the
nightly. Fixing it means a router path group (`.github/workflows/ci-router.yml`) and/or a module
registry row (`.github/ci-module-registry.yml`, census-gated) — a per-PR job-cost decision for the
maintainer, and out of scope for this mission (C-003).

## Context

- `CHANGELOG.md` at the repository root is a symlink to `docs/changelog/CHANGELOG.md`; edit the
  target.
- Entry shape used by the neighbouring `[Unreleased]` entries: bold, impact-first lead sentence,
  then before/after, with the `(#NNNN)` reference in the lead. Keep it under 1,200 characters.
- The change is not user-facing in the "new feature" sense, but it is maintainer/operator
  relevant: the status lock's directory name now has one owner and the audit gate covers the
  module again. Say that, and say that lock locations did **not** change.

## Subtasks

### T007 — Changelog entry *(WP02)*

Add one entry under `[Unreleased]` in `docs/changelog/CHANGELOG.md`:

- Lead: what changes for a maintainer (the runtime-state directory name has one owner; the
  status-lock and review-lock modules are back under the runtime-home guard).
- Before/after: `_NON_GIT_LOCK_HOME`/`LOCK_DIR` hand-rolled `".spec-kitty"` and `status/locking.py`
  was allowlisted in the FR-010 audit gate (#6582) → both take the name from
  `specify_cli.paths.RUNTIME_STATE_DIR_NAME` and the allowlist shrank by two entries.
- State explicitly that the lock **locations** are unchanged (repository-local, #6367).
- Reference `(#6516)`. Under 1,200 characters. No new section, no reflow of neighbouring entries.

### T008 — File the routing follow-up *(WP02)*

```bash
gh issue create --repo spec-kitty/spec-kitty \
  --title "ci: a src/specify_cli/status/** diff does not route tests/audit/**" \
  --label "domain:ci" --label "priority:P2" --label "from:dev" \
  --body "<body>"
```

The body must state: the gap (issue #6516's second half), the evidence (a `status/` diff selects
the `status` shard but no audit job; #6367 shipped a hand-rolled literal that only the nightly
caught), the candidate fix surfaces (the `status` path group in `.github/workflows/ci-router.yml`,
and/or a `.github/ci-module-registry.yml` registry row — noting `tests/audit` is currently in the
"no per-PR lane" group), the cost consideration (a new per-PR job), and a link back to #6516 and
to this PR. Do **not** label it `status:claimed` and do not assign it.

Record the created issue number in the PR's `## Deferred` section later; do not add it to this
mission's issue matrix.

### T009 — Docs freshness and terminology *(WP02)*

```bash
uv run python -m scripts.docs.check_docs_freshness --ci
uv run pytest tests/architectural/test_no_legacy_terminology.py -q
```

`check_docs_freshness --ci` must report `errors=0`. Do **not** run the full docs-reference
regenerator: the installed CLI's global asset cache is shared with the other agents running on
this host, so a full rebuild is non-deterministic here. If the freshness check flags an index that
this diff genuinely changes, regenerate only that surface and say so in your report.

## Branch Strategy

Planning base and merge target: `issue-6516-status-lock-dir-name-ssot`. Worktree per the lane in
`lanes.json`.

```bash
spec-kitty agent action implement WP02 --agent python-pedro --mission status-lock-dir-name-ssot-01M68JA7
```

## Definition of Done

- [ ] One `[Unreleased]` changelog entry, `(#6516)` in the lead, under 1,200 characters, no
      neighbouring entry reflowed.
- [ ] The entry says the lock locations are unchanged.
- [ ] A follow-up issue exists on `spec-kitty/spec-kitty` describing the routing gap with the
      candidate fix surfaces; its number is in your report.
- [ ] `check_docs_freshness --ci` errors=0; `test_no_legacy_terminology.py` green.
- [ ] No claim that the routing gap itself is fixed.

## Risks

- The freshness check reads a concurrently rebuilt global cache shared with other agents; verify
  with the check, do not rebuild the whole reference.
- The changelog lives at `docs/changelog/CHANGELOG.md` through a symlink; a top-level
  `CHANGELOG.md` edit is the same file — do not create a second copy.

## Reviewer guidance

Confirm the entry's claim matches the diff in WP01 (one owner, two consumers, two drained
exemptions, unchanged locations), that the follow-up issue exists and does not claim work the
mission already did, and that freshness/terminology checks are green with the commands recorded.
