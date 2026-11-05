# Tasks: `consolidate --skip-lanes` records an evidence window it can judge

**Mission**: issue-7209-skip-lanes-planning-commit-01M6P3JR
**Plan**: [plan.md](plan.md) · **Spec**: [spec.md](spec.md)
**Branch**: `issue-7209-skip-lanes-planning-commit`

## Task outline

| ID | Task | Work package | Requirement refs |
|----|------|--------------|------------------|
| T001 | Red-first: the three `--skip-lanes` CLI nodes still refuse `EVIDENCE_WINDOW_UNCOMPUTABLE` on the pre-fix tree; make the fixture declare the `owned_files` a real Mission declares | WP01 | FR-001, SC-001 |
| T002 | Red-first: focused tests for the synthesized-manifest evidence base (positive control, evidence-axis pass, `IMPLEMENTATION_MISSING`, `REVIEW_NOT_INDEPENDENT`, unresolvable base, determinism) | WP01 | FR-001, FR-002, FR-004, NFR-002, NFR-003, SC-002, SC-003 |
| T003 | Implement `_resolve_planning_base_commit` and record it on the synthesized manifest | WP01 | FR-001, FR-002, NFR-001, NFR-002, NFR-003, C-001, C-002 |
| T004 | Green: the three CLI nodes complete; the new module passes | WP01 | SC-001, SC-002, SC-003 |
| T005 | Red-first: a test pinning the `EVIDENCE_WINDOW_UNCOMPUTABLE` line and recovery text for a Mission with no `lanes.json` | WP02 | FR-003, SC-004 |
| T006 | Implement the honest line and the working remedy in `wp_evidence` | WP02 | FR-003, C-003 |
| T007 | `--skip-lanes` operator note in the merge how-to | WP03 | C-003, SC-004 |
| T008 | Changelog fragment (`.fixed`) for the PR | WP03 | — |

## Work packages

### WP01 — Synthesized-manifest evidence base (P1)

The core fix. Resolve the target-branch commit immediately before the Mission's planning
artifacts appeared, record it as the synthesized manifest's `planning_commit_sha`, and prove —
through the pre-existing CLI entry point and a focused evidence-axis module — that the window is
real, deterministic, fail-closed, and no more permissive than a recorded one.

- **Owned files**: `src/specify_cli/consolidation/entry_preflight.py`,
  `tests/consolidation/test_skip_lanes_evidence_window.py`,
  `tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py`.

### WP02 — Refusal text for an unresolvable window (P2)

When no base can be resolved, keep the refusal and make its recovery performable in the
no-`lanes.json` topology, without dropping the recorded-but-unpinned `finalize-tasks` advice.

- **Owned files**: `src/specify_cli/consolidation/wp_evidence.py`,
  `tests/consolidation/test_evidence_window_refusal_text.py`.
- **Depends on**: WP01 (the recovery must describe the shape WP01 just stopped producing in the
  common case).

### WP03 — Operator docs and changelog (P3)

State what `--skip-lanes` now records and what still refuses; add the per-PR changelog fragment.

- **Owned files**: `docs/guides/how-to/missions/merge-mission.md`,
  `docs/changelog/unreleased/7209-skip-lanes-evidence-window.fixed.md`.
- **Depends on**: WP01, WP02.

## Safeguards

- The gates stay: no attestation, no new code path around `evaluate_evidence`, and the same
  `IMPLEMENTATION_MISSING` / `REVIEW_NOT_INDEPENDENT` strictness on the synthesized window.
- The fixture change is fixture realism (`owned_files`), never an assertion relaxation, a skip or
  an xfail.
- No change to `lanes.json` persistence, the coordination-teardown seam (#7198/#7199), or the
  accept-diagnostics work (#7222/#7223).
- No full heavy suite in-mission; targeted suites plus the touched modules' neighbours.
