# Tasks: Live Fresh-Claim Coverage (#6311)

**Mission**: live-fresh-claim-01M6BV7X
**Branch**: `issue-6311-live-fresh-claim`
**Input**: [spec.md](./spec.md) · [plan.md](./plan.md) · [research.md](./research.md)

The reported fresh compact-actor claim refusal is verified fixed on `main`
(research.md D1–D2). The unguarded seam is the *live* documented flow: every
existing test seeds the status log, pre-fakes the lane worktree and monkeypatches
git. This mission adds exactly that missing guard and nothing else — no
production behaviour changes, no gate changes.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Real-git mission fixture: temp repo, lanes manifest, WP prompt, `planned`-only status log, no pre-made worktree | WP01 | — |
| T002 | Scenario 1 (FR-001/FR-005): one `agent action implement` invocation exits 0, renders the prompt, and the lane path really is a git worktree | WP01 | — |
| T003 | Scenario 2 (FR-002): recorded claim event attributes the claim to the compact identity's tool | WP01 | — |
| T004 | Scenario 3 (FR-003): same compact identity re-run resumes idempotently | WP01 | — |
| T005 | Scenario 4 (FR-004): a different tool is still refused with "already claimed" (positive control) | WP01 | — |
| T006 | Run the module plus the neighbouring #4665/#6311 suites, `ruff`, `mypy`; record results | WP01 | — |

---

## WP01 — Live fresh-claim guard

**Prompt**: [tasks/WP01-live-fresh-claim-guard.md](tasks/WP01-live-fresh-claim-guard.md)

**Summary**
- **Goal**: One integration module that drives the real `agent action implement`
  CLI on a real git repository with a real lanes manifest, pinning the fresh
  compact-actor claim end to end.
- **Priority**: P1.
- **Deliverable**: `tests/specify_cli/cli/commands/agent/test_implement_live_fresh_claim_6311.py`.
- **Definition of Done**: the four scenarios pass on this branch; the
  neighbouring #4665/#6311 modules still pass; `ruff` and `mypy` clean on the
  new file; no production file touched.
