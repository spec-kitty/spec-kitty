# Quickstart — ATDD / red-first strategy & entry-point map

Every defect carries an issue-pinned scenario demonstrably RED before the fix, GREEN after (NFR-002).
Entry points below are pre-existing unless marked NEW.

## Per-SC red-first map

| SC | Defect | WP | Test entry point | Red-first shape |
|----|--------|----|------------------|-----------------|
| SC-001 | write-side record + populated location + resolvable ref, parity with →planned on a shared fixture | WP01 | `tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py`; parity in `tests/characterization/test_trio_pure_cores.py` | reject onto `in_review→in_progress` with feedback `F`; assert committed cycle, populated body == `F`, `review_ref` resolvable; compare field-for-field **by value** to the `→planned` record from the same `F` |
| SC-002 | no-rationale rejection on re-implement edge refused | WP01 | `test_tasks_move_task_seam.py` | no-rationale `in_review→in_progress` → observable non-zero refusal; paired with an accepted with-rationale rejection on the same fixture |
| SC-003 | fix-mode generation failure → visible warning, no silent feedback-less substitution | WP02 | `tests/agent/test_workflow_review_cycle_pointer.py`; NEW `tests/agent/test_build_implement_prompt_lines.py` | force `generate_fix_prompt` to raise → assert visible (console) warning; positive control: success path renders feedback |
| SC-004 | feedback renders on single-branch AND coordination topologies | WP02 | `test_workflow_review_cycle_pointer.py` (add coord fixture) | **coord half is red-first** (F4 independent-red): with a record already present, coord render finds no `review_ref` until the `STATUS_STATE` re-route lands; single-branch is the parity control |
| SC-005 | end-to-end, no pre-seeding: reviewer text → reject re-implement edge → same text in regenerated prompt, both topologies | WP01+WP02 (integration) | `test_workflow_review_cycle_pointer.py` (end-to-end flow) | one continuous flow, NO fixture pre-seeding of the record; fails if any of the four write gates OR the render path is unfixed (anti-mask) |
| FR-008 (conditional #3451) | review-cycle counter double-increment on re-implement edge | WP01 | `test_tasks_move_task_seam.py` | ONLY if it reproduces: assert `cycle_number` increments exactly once (not twice) on a re-implement rejection |

## NFR-003 non-regression guard (WP01)

Keep existing arbiter-override coverage green (the `in_review → {approved,done}` forward-emit path,
`is_arbiter_override` / `arb_review_ref`). The predicate excludes those edges by construction; the existing
tests are the guard that proves no regression.

## Pure-unit coverage (Sonar new-code, both WPs)

- WP01: `is_review_rejection_edge` truth-table unit test (all lane pairs incl. aliases + arbiter-forward =
  False) in `tests/characterization/test_trio_pure_cores.py`; a focused test for the extracted
  `_mt_persist_rejection_cycle` helper.
- WP02: direct branch tests for `build_implement_prompt_lines` and the re-routed read helpers.

## Blast radius to run (per CLAUDE.md test policy)

`make test-fast` + `tests/specify_cli/cli/commands/agent/` + `tests/agent/` + `tests/characterization/`
(the module + owning-subsystem dirs for the touched files). Not a whole-repo suite.

## Reference commands

```bash
# reproduce the write-side loss (red) on the re-implement edge
.venv/bin/spec-kitty agent tasks move-task WP01 --to in_progress --review-feedback-file feedback.md
# inspect the emitted event's review_ref (should be resolvable review-cycle://, not synthetic review:WP01)
# regenerate the fix-mode prompt and confirm the feedback text is present
.venv/bin/spec-kitty implement WP01
```
