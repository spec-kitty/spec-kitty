---
work_package_id: WP02
title: Record the rationale and the per-PR changelog fragment
dependencies:
- WP01
requirement_refs:
- FR-007
- SC-004
- NFR-001
planning_base_branch: issue-7206-corpus-advisory-budget
merge_target_branch: issue-7206-corpus-advisory-budget
branch_strategy: Planning artifacts for this mission were generated on issue-7206-corpus-advisory-budget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7206-corpus-advisory-budget unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
phase: Phase 2 - Documentation
history:
- at: '2026-11-05T15:16:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent:
- docs/changelog/unreleased/7206-corpus-advisory-budget.fixed.md
execution_mode: planning_artifact
owned_files:
- docs/development/reference/ci-gate-mechanics.md
- docs/changelog/unreleased/7206-corpus-advisory-budget.fixed.md
role: implementer
tags: []
task_type: documentation
tracker_refs:
- '#7206'
---

# Work Package Prompt: WP02 – Record the rationale and the per-PR changelog fragment

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi` (implementation sub-agent)

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.

---

## Objectives & Success Criteria

A maintainer reading the lane's reference page must find the budget, the measurement behind it, the
formula, and why the obvious alternative (sharding the selection) is not available. The change must
also be recorded where this repository records changes: a per-PR fragment under
`docs/changelog/unreleased/`.

Definition of Done:

- `docs/development/reference/ci-gate-mechanics.md` states, next to its existing "Corpus tests have
  one advisory owner" bullet, the measured p95 against the old cap, the derived cap with the #5378
  formula, the incomplete-not-failed behaviour of a killed run, and the two guards that rule out a
  path shard.
- `docs/changelog/unreleased/7206-corpus-advisory-budget.fixed.md` exists, leads with the impact and
  `(#7206)`, gives before/after, and is under 1,200 characters.
- `uv run --frozen python -m scripts.docs.check_docs_freshness --ci` reports `errors=0`,
  `scripts.docs.check_changelog_style` and `scripts.docs.check_spelling --pass unreleased` pass.

## Context

- WP01 lands the numbers and the behaviour; take the wording from `research.md` and the workflow
  comment, not from memory.
- The reference page already documents the lane's ownership (the `-m corpus` suite is advisory, the
  blocking homes are the router jobs). Extend that bullet; do not start a new page or an ADR.
- Fragment rules: `docs/changelog/unreleased/README.md` — `<id>.<section>.md`, entry exactly as it
  reads in the changelog, no heading, `[Unreleased]`-shaped entries are rejected by
  `check_changelog_style`.

## Detailed Guidance

### T007 — The reference page

Add to the advisory-owner bullet (or as a short paragraph under it):

- the measured p95 (20.3 min over 55 runs) against the retired 20-minute cap, and that four runs
  were killed at the budget with no failing test;
- the derived cap (31) and the rule (`ceil((max-suite + 0:30) × 1.5)`, the #5378 convention, now
  enforced for this job by `tests/ci/test_nightly_timeout_headroom.py`);
- that a killed run reports INCOMPLETE/advisory through its notice step and is never green;
- why a path shard is not available, naming `tests/ci/test_corpus_blocking_home.py` (tree-wide
  corpus reach, #3008) and `tests/ci/test_contracts_routing.py` (one pytest invocation).

Keep it to the page's voice: short declarative bullets, links to the guards by path.

### T008 — The changelog fragment

`docs/changelog/unreleased/7206-corpus-advisory-budget.fixed.md`, one entry:

```markdown
- **The advisory corpus suite no longer runs out of budget on unrelated PRs** (#7206). **Before:** ...
  **After:** ...
```

State the user-visible effect (the advisory check stops showing a 20-minute cancellation on PRs whose
diff has nothing to do with packs; when it genuinely runs out of time it says so instead of looking
like a failing test), the measured basis (p95 20.3 min → cap 31 derived by the recorded-headroom
rule) and that the suite's selection is unchanged. Under 1,200 characters. Rename the file to
`<pr>.fixed.md` once the pull request exists.

### T009 — Verify

```
uv run --frozen python -m scripts.docs.check_docs_freshness --ci
uv run --frozen python -m scripts.docs.check_changelog_style
uv run --frozen python -m scripts.docs.check_spelling --pass unreleased
```

Record each result in the PR's "Tests run" section with its error count.

## Branch Strategy

Planning artifacts were generated on `issue-7206-corpus-advisory-budget`. This WP's changes merge
back into that branch; the pull request targets `main`, and `main` is never a push target.

## Test Strategy

Documentation-only WP: the checks above plus the docs-index freshness gate are its tests. No prose
claim may exceed what `research.md` measured.

## Definition of Done

- [ ] The reference page carries the measurement, the derivation and the rejected shard.
- [ ] The fragment passes style, spelling and the 1,200-character limit.
- [ ] `check_docs_freshness --ci` is `errors=0`.
- [ ] The fragment is renamed to the PR number before the flip to ready for review.

## Risks & Mitigations

- **Doc drift**: cite the guards by path so a rename turns into a dead link a reviewer can see.
- **Over-claiming**: no figure may appear here that is not in `research.md`.

## Reviewer Guidance

Does the page tell a maintainer *why* 31 and not 20, and where to re-measure? Does the fragment read
as impact-first, with the issue reference, and without claiming the suite got faster?
