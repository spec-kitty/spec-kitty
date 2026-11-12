---
type: reference
updated: 2026-11-12
audience: operator and reviewer of this Mission
---

# Foldable-issue discovery (#7598)

Open-issue search on 2026-11-12 (coordination teardown, late projection, resume, abort remedy,
archived Mission, reclaim, squash projection, "did not land", accept next steps).

| Issue | Verdict | Reason |
|---|---|---|
| #7491 | CORE | Member of #7598 |
| #4041 | CORE | Member of #7598 |
| #5867 | CORE | Member of #7598 |
| #7599 | CORE | Member of #7598 |
| #7600 | CORE | Member of #7598 |
| #4380 item 2 | **FOLD (proposed)** | `consolidation/phase_teardown.py:980-985` says the marker "was left intact so the branch, its worktree and the marker stay consistent... re-run `consolidate --resume`", which misdescribes the case where the worktree is already gone. One string, same file and refusal domain as #7491. |
| #4380 item 1 | REFS | orchestrator-api maps a plain `CoordinationTeardownError` (no `error_code`) to `PREFLIGHT_FAILED`; larger, orchestrator-api contract surface |
| #7301 | REFS | Teardown refusals ending in a traceback; needs exception handling in `phase_teardown.py` / `bookkeeping_projection.py`; medium size |
| #5784 | REFS | `--abort` cannot undo a kill-left landing it cannot prove; a design gap behind the #7600 "moved by another actor" case |
| #7540 | REFS | Largely closed by PR #7567; its `--abort` teardown item overlaps #7600 |
| #7359, #7358, #7360, #7276, #5001 | REFS | Parent epics |
| #5791 | EXCLUDE | Reconciliation attribution after `--release-branch` |
| #7121, #7300 | EXCLUDE | Data-loss correctness of late coordination commits, not messages |
| #5748, #5371, #5755 | EXCLUDE | Distinct resume crashes |
| #7553, #7565 | EXCLUDE | `next` after accept, runtime domain (PR #7591) |

## Overlap with open work

- **PR #7591** (next lifecycle): `consolidation/done_bookkeeping.py`, `status/__init__.py`. No overlap.
- **PR #7596** (review context, draft): reads `lanes/single_branch_landing.py` and
  `mission_runtime/resolution.py`, which the #7599 fix reads but does not edit. No edit overlap.
- **Sub-epic C, `fix/7546-settled-placement-surface`** (not on origin when checked): likely
  shares `src/specify_cli/acceptance/__init__.py` (the accept path-convention message). This
  Mission edits only `_build_acceptance_instructions` there and leaves placement to C.
  `git/ref_advance.py` sits beside safe-commit; this Mission touches only the
  `RefAdvanceDirtyWorktreeError` message, not commit placement.
