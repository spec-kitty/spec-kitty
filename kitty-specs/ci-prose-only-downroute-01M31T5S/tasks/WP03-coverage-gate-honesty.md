---
work_package_id: WP03
title: Coverage-gate honesty for prose-only files
dependencies:
- WP01
requirement_refs:
- FR-009
planning_base_branch: feat/ci-prose-only-downroute
merge_target_branch: feat/ci-prose-only-downroute
branch_strategy: Planning artifacts for this mission were generated on feat/ci-prose-only-downroute. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/ci-prose-only-downroute unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ci-prose-only-downroute-01M31T5S
base_commit: 43247abc920ed8d04c350ad59402eeb60039f526
created_at: '2026-09-21T12:12:09.083028+00:00'
subtasks:
- T011
- T012
- T013
history:
- created by /spec-kitty.tasks 2026-09-21 (added post-adversarial-squad, F1)
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent: []
execution_mode: code_change
owned_files:
- scripts/ci/aggregate_source.py
- tests/ci/test_aggregate_source.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

```
/ad-hoc-profile-load python-pedro
```

Then proceed to the Objective.

## Objective

Close the coverage-gate false-red the down-route would otherwise introduce (squad
Paula F1). `scripts/ci/aggregate_source.py` builds `critical.diff.patch` — the
immutable diff the `ci-aggregate.yml` diff-cover ≥90% gate scores. When a prose-only
change hits a **critical-path** module (`CRITICAL_PATHS` includes
`src/specify_cli/status/*`), the down-route makes that module *unselected*, so its
coverage is backfilled STALE and the changed docstring lines score as uncovered →
the PR false-fails on a docstring edit. Fix: exclude proven-prose-only `.py` from the
critical diff patch, so there is no coverable changed line to score — exactly the
trivially-green path a docs-only PR already takes.

Read `contracts/prose-only-classifier.md` (ci-aggregate wiring contract) and
`research.md` R8 first.

## Context

- `aggregate_source.py:78` writes `critical.diff.patch` from `CRITICAL_PATHS`
  git pathspecs; it has the base/head diff available (it runs in the aggregate
  context).
- There is precedent: `ci-aggregate.yml:328-344` already excludes "census-dead"
  surfaces from the diff-cover denominator — so an exclusion mechanism is idiomatic
  here.
- A prose-only line genuinely needs no test coverage; excluding it is honest, not a
  gate weakening. Do NOT touch the ≥90% threshold or the SELECTED/UNSELECTED backfill
  policy.

## Subtasks

### T011 — Red-first test (`tests/ci/test_aggregate_source.py`)

Add a test proving that a critical-path `.py` whose diff is docstring/comment-only is
**absent** from the resulting `critical.diff.patch`, while a critical-path `.py` with
a real code change **remains** in it. Use a realistic base/head pair (e.g. a
`src/specify_cli/status/*` file). Watch it fail before T012.

### T012 — Exclude prose-only critical files from the patch

In `aggregate_source.py`, after computing the critical diff, drop from the patch any
`.py` file whose base→head content is `prose_only.is_prose_only(...)`. Reuse the
WP01 classifier (single source of truth — the exclusion set must match WP02's
reduction). Fetch base/head via the same git mechanism already used to build the
diff. Fail-closed: if the classifier cannot prove prose-only (or a blob is missing),
the file STAYS in the patch (scored as today).

### T013 — Verify no regression to the honest path

Confirm `tests/ci/test_aggregate_source.py` and `tests/ci/test_reconcile_shards.py`
pass, and that a mixed PR (prose + real critical code) still scores the real code.
ruff/format/mypy clean on the touched files; no new suppressions.

## Branch Strategy

Planning/base and local merge target: `feat/ci-prose-only-downroute` (then PR'd to
`skupstream/main` by the operator). Enter via `spec-kitty implement WP03` after WP01
is approved/done — independent of WP02 (disjoint files), can run its own lane.

## Definition of Done

- A docstring/comment-only critical-path `.py` is excluded from `critical.diff.patch`;
  a real code change is not (proven by T011).
- Classifier reused (no second prose definition); fail-closed on uncertainty.
- Threshold and backfill policy untouched; ci-aggregate tests green.
- ruff/format/mypy clean.

## Risks / Reviewer guidance

- **Honesty is the whole point**: reviewer must confirm the exclusion only ever
  removes provably prose-only files — a false exclusion would hide a real
  coverage regression (the mirror image of F1). The classifier's fail-closed
  guarantee (WP01) is load-bearing here too.
- Confirm the exclusion set is computed from the SAME classifier WP02 uses, so
  ci-modules reduction and diff-cover exclusion can never disagree.
