---
work_package_id: WP06
title: Decision record and operator documentation
dependencies:
- WP03
- WP04
- WP05
requirement_refs:
- FR-015
planning_base_branch: issue-5668-approved-claim-bound
merge_target_branch: issue-5668-approved-claim-bound
branch_strategy: Planning artifacts for this mission were generated on issue-5668-approved-claim-bound. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5668-approved-claim-bound unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-approved-claim-bound-01M444QR
base_commit: 1571015860025be91d106c4f550b3c6b6b1a6246
created_at: '2026-10-04T23:27:38.738943+00:00'
subtasks:
- T024
- T025
- T026
phase: Phase 4 - Documentation
history:
- at: '2026-10-04T19:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/adr/4.x/
create_intent:
- docs/adr/4.x/2026-10-04-3-approval-stamp-bounds-the-approved-claim.md
execution_mode: code_change
owned_files:
- docs/adr/4.x/2026-10-04-3-approval-stamp-bounds-the-approved-claim.md
- docs/adr/4.x/index.md
- docs/adr/3.x/2026-09-29-1-closed-world-refuse-on-mixed-lanes.md
- docs/changelog/CHANGELOG.md
- CLAUDE.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP06 – Decision record and operator documentation

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt. If the skill is not available, run `.venv/bin/spec-kitty agent profile show scribe-sally` and apply the resolved profile.

- **Profile**: `scribe-sally`
- **Role**: `implementer`
- **Agent/tool**: `implementer`

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task.** Check the `review_ref` field in the event log (`.venv/bin/spec-kitty agent tasks status --mission approved-claim-bound-01M444QR`). If this work package was returned from review, every feedback item is part of your work.

---

## Objectives & Success Criteria

The decision and its operator impact are recorded (spec FR-015).

- A new ADR in `docs/adr/4.x/` with a forward pointer from ADR `2026-09-29-1`.
- An `[Unreleased]` changelog entry with an upgrade note.
- The consolidation section of `CLAUDE.md` describes the new rule.

Implementation command: `.venv/bin/spec-kitty agent action implement WP06 --agent implementer --mission approved-claim-bound-01M444QR`

## Context & Constraints

Read first, in this order:

1. `.kittify/charter/charter.md` (binding) and `spec-kitty charter context --action implement --json`.
2. `kitty-specs/approved-claim-bound-01M444QR/spec.md`, `plan.md` (sections D-1 to D-6), `research.md`, `data-model.md`, `contracts/consolidate-refusals.md`.
3. `kitty-specs/approved-claim-bound-01M444QR/research/code-grounding.md` for file and line references. Line numbers were taken at `9adc68803f`; re-locate by symbol name (`codegraph explore "<symbol>"`).

Rules that bind every work package of this mission:

- **CLI binary**: always `.venv/bin/spec-kitty` and `.venv/bin/python -m pytest`. The bare `spec-kitty` on PATH is a stale install. Never `uv run`.
- **No heavy suites**: never `make test-full`, never a bare `tests/architectural/` run. Run the files named in this prompt.
- **Test economy**: each new test must pin one distinct behaviour. No test per helper, no duplicate of an existing pin. Prefer extending a parametrized test over adding a sibling.
- **Quality**: `ruff check` and `mypy --strict` clean on changed files, complexity <= 15, no new `# noqa` or `# type: ignore`. Format check: `uv run --frozen ruff format --check --force-exclude <changed files>`.
- **Status imports**: import status symbols only through the `specify_cli.status` facade. Git reads go through `consolidation/git_probes.py`; do not shell out to git directly from new consolidation code.
- **Byte-identity**: no existing refusal code or text changes. New texts are additions.
- **No fail-open**: an absent approval stamp is never replaced by the lane tip, in product code or by a test switch (spec C-003).
- **Terminology**: Mission and work package; `--mission`, never `--feature`.
- **Commits**: conventional messages; every commit ends with the trailer `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`. No AI model or tool identifiers in commit messages.
- **Tracers**: do not edit `kitty-specs/approved-claim-bound-01M444QR/tracers/*.md` in a lane worktree (parallel lanes would conflict). Put tooling friction and unplanned design decisions in this prompt's Activity Log and in your hand-back report; the orchestrator records them.

## Branch Strategy

- **Strategy**: see `branch_strategy` in the frontmatter (written by `finalize-tasks`)
- **Planning base branch**: issue-5668-approved-claim-bound
- **Merge target branch**: issue-5668-approved-claim-bound

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; use the workspace path `spec-kitty agent action implement` resolves, do not construct it.

## Subtasks & Detailed Guidance

### Subtask T024 – ADR

- **Purpose**: the change reverses two recorded decisions: the claim builder's "approved commit SHAs come from lane-branch git tips (never status rows)" and Decision 1 of ADR `docs/adr/3.x/2026-09-29-1-closed-world-refuse-on-mixed-lanes.md` ("applies only to mixed lanes").
- **Steps**:
  1. Read `docs/adr/4.x/index.md` and the newest ADR in that directory for the house format and frontmatter (Divio type, `updated:` date). Confirm `2026-10-04-3` is the next free id; if another ADR took it, use the next.
  1a. Facts established during implementation that the ADR must state correctly (the plan's wording is older):
     - On a mission with no coordination branch the claim base is the **target tip** (the status placement), not the mission branch; on a coordination topology it is the coordination branch tip.
     - A commit added to a lane while `consolidate` is running was already failed by the existing content checks ("un-attributable") and rolled back. The gate re-check replaces that generic failure with the named refusal, the commit, the work package and the remedy; say this plainly, do not describe it as closing a silent pass.
     - A lane with no commit beyond the claim base is not checked (nothing can land from it), so a `done` work package with no `approved` event on an empty lane is not refused. This differs from the letter of FR-005 and is deliberate.
     - On a mixed lane a canceled work package's newest **stamped** event is a covered point; an unstamped canceled attestation gives none.
  2. Write `docs/adr/4.x/2026-10-04-3-approval-stamp-bounds-the-approved-claim.md`: context (issue 5668, reproduced in four combinations), decision (the approval stamp is the authority; lane-level bound; refuse at claim time and at the gate; unstamped approvals fail closed with an attestation; mixed lanes keep the closed world first), consequences (upgrade impact for missions approved before 4.0.0rc5; every claim reads the event log once), alternatives rejected (from `kitty-specs/{MS}/research.md` R-1 to R-7), and the named residuals (spec, Known residuals).
  3. Add it to `docs/adr/4.x/index.md`.
  4. In the 3.x ADR add a short dated note pointing forward to the new ADR; do not rewrite its decisions.
  5. Regenerate the docs retrieval index: `.venv/bin/python scripts/docs/docs_index.py --write`, then `.venv/bin/python scripts/docs/check_docs_freshness.py --ci` (errors must be 0). Generated index files are an expected out-of-map edit.
- **Files**: the two ADR files, the index.

### Subtask T025 – Changelog

- **Steps**:
  1. `docs/changelog/CHANGELOG.md`, section `## [Unreleased]`: under "Upgrade Notes" add that a mission approved with a release before 4.0.0rc5 now refuses on `consolidate` with `APPROVAL_STAMP_MISSING` until the work package is re-reviewed or attested with `--attest-approved-reviewed`.
  2. Under the fixes heading the section uses: a bold impact-first lead with the issue reference `(#5668)`, then before and after in two or three sentences, naming the three codes and the flag.
  2a. Also record the orchestrator-api change: `consolidate-mission` can now refuse with `PREFLIGHT_FAILED` and reports `data.preflight_error_code`; the contract version is 1.10.0 (WP07 bumps it).
  3. Run the changelog fixture tests if they exist for the unreleased section (`ls tests/docs`; run the files whose names mention changelog).
- **Files**: `docs/changelog/CHANGELOG.md`.

### Subtask T026 – CLAUDE.md

- **Steps**:
  1. In the "Consolidation & Preflight Patterns" part of `CLAUDE.md`, add one paragraph in the style of its neighbours: **Approved claim is bounded by the approval stamp (#5668).** State the rule, the three codes, where it runs (`consolidation/approved_bound.py`, the claim builder, the gate, `orchestrator-api consolidate-mission`), the attestation flag and what it never lifts, and the residuals.
  2. Correct any sentence in that file the change made false (search for "lane-branch git tips" and "only to mixed lanes").
  3. Run `.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q`.
- **Files**: `CLAUDE.md`.


## Test Strategy

```bash
.venv/bin/python scripts/docs/check_docs_freshness.py --ci
.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q
```

No new test is added by this work package.

## Risks & Mitigations

- **Writing rules.** The charter's writing doctrine applies: name the reader (an operator who hit a refusal), one Divio type per document, plain language.
- **Index drift.** Forgetting the docs index regeneration fails a docs gate in CI.

## Review Guidance

- The ADR states the reversal of the two earlier decisions explicitly and names the residuals.
- The changelog entry has the upgrade note.
- `CLAUDE.md` no longer says the claim comes from lane tips without the bound.
- Confirm the implementer ran `ruff check`, the format check and `mypy --strict` on the changed files and that all were clean.
- Reviewer and implementer are different agents. Judge each new test: does it pin a distinct behaviour, and would it fail if the behaviour were removed?

## Activity Log

> Entries are appended in chronological order (oldest first). Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-10-04T19:45:00Z – system – Prompt created.

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status> --mission approved-claim-bound-01M444QR` to change WP status, and `spec-kitty agent tasks mark-status <Txxx> --status done --mission approved-claim-bound-01M444QR` for subtasks.
