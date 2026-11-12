---
type: reference
updated: 2026-11-12
audience: mission implementers and reviewers (software-engineer persona)
---

# Code grounding: approval honesty (#7569, #7570, #7571, #7573)

Base: `origin/main` 89217ac8 (shallow clone, 50 commits). The squad (code grounding, evidence
mining, fold discovery) produced these findings read-only. A separate fresh-context reviewer
then challenged them. Corrections from that pass are folded in and marked **[2nd]**.
Line numbers refer to 89217ac8.

## 1. How an approval through `move-task` gets its identity

Pipeline:

1. `_mt_run_decision` → `_mt_gather_late_facts` → `_mt_approval_facts`
   (`cli/commands/agent/tasks_move_task.py:1657-1671`):
   - reviewer = `--reviewer`, else **`git config user.name`** (`_detect_reviewer_name`, `:2226-2238`);
   - reference = `--approval-ref`, else **`auto-approval:<WP>:<date>`** (`review/cycle.py:116`).
2. `decide_transition` → `_approval_evidence` (`tasks_transition_core.py:1024-1033`) builds
   `evidence.review`.
3. `_mt_finalize_plan` (`tasks_move_task_executor.py:97`):
   - sets `actor` = `--agent`, else the newest `in_review` claimant, else `"user"` (`:143`; the #4670 fix);
   - writes the approved review cycle (`_persist_approved_review_cycle`,
     `tasks_verdict_persistence.py:843-974`);
   - **only when that write is durable**, overwrites `evidence.review` with the cycle's reviewer and a
     `review-cycle://` pointer (`:147-158`).
4. Per hop (`tasks_move_task_hops.py`): `actor` (`:155-179`, `--agent` wins), `review_result`
   (`:107-152`), and `policy_metadata.tool = req.effective_reviewer` (`:257`).

| Persisted field | Source |
|---|---|
| `actor` | `--agent` → `in_review` claimant → `"user"`. Fixed by #4670 (PR #4717). |
| `evidence.review.reviewer` / `.reference` | Durable write: cycle `reviewer_agent` + `review-cycle://`. Otherwise: **git user + `auto-approval:`**. |
| `review_result` | Durable: from the cycle. Otherwise: `evidence.review` (git user + `auto-approval:`). |
| `policy_metadata.tool` | **Always** `--reviewer`, else **git user**, on every approved/done hop, durable or not. |
| cycle `reviewer_agent` | `--reviewer` → `--agent` → `actor` (`verdict_persistence.py:914`). Never the git user, but can be `"user"`. |

Sub-paths that always keep the git user and `auto-approval:`:
- `approved -> done`: the cycle write is skipped (`verdict_persistence.py:760-762`);
- arbiter override (`:745-746`);
- `--no-auto-commit`;
- a damaged approval slot.

**Two synthetic tokens per approval [2nd].** The cycle body and the non-durable `plan_review_result`
use `approval:<WP>` (`verdict_persistence.py:918`, `hops.py:93`). The evidence uses
`auto-approval:<WP>:<date>`. The two records of one approval therefore disagree.

**Why real data is mostly non-durable [2nd].** This repo's `.kittify/config.yaml:9` sets
`auto_commit: false`. On released CLIs (≤ rc8) that made the approval cycle write `local_only`,
so the overwrite never ran. The unreleased #3933 fix (`tasks_move_task.py:693`) makes the default
path durable. Example of the resulting mismatch: `lane-code-verification-01M76AC0` WP05 (2026-11-12).
- `review-cycle-1.md`: `claude-reviewer::reviewer-renata`, `approval:WP05`.
- Event 7 s later: reviewer `Claude`, `auto-approval:WP05:20261112`, `policy_metadata.tool: "Claude"`.

**#7569 is an incomplete #4670 fix, not a regression.** PR #4717 re-sourced `actor` and the
rendered completion commands only. `_mt_approval_facts` and `policy_metadata.tool` were never
routed through the claimant resolver. This is inferred from the code: the clone is too shallow to
prove it from history.

## 2. Review-cycle artifacts

- **One writer.** `create_rejected_review_cycle` (`review/cycle.py:1523`) is the only writer of
  `review-cycle-N.md`. Its callers are `verdict_persistence.py:952` (approval), `:992` (rejection),
  and `tasks_materialization.py:240` (`_persist_review_feedback`). `agent action review` writes
  nothing; it prints the draft path (`workflow.py:2595-2610`).
- **Numbering.** N = max of the parsed cycle numbers + 1 (`review/artifacts.py:393-430`).
- **#7571.** The approval write is gated only on the event-log slot (`verdict_persistence.py:743-763`).
  Adopt-or-allocate reuses an existing file only when reviewer, body and affected files all match
  (`cycle.py:1017-1027`). A reviewer's own approved `review-cycle-N.md` never matches the
  synthesized `Approved by X: approval:WP` body, so the approval allocates N+1.
- **#7570.** `--approval-ref` and `--note` are stored verbatim and never parsed.
  `validate_review_cycle_pointer` / `resolve_review_cycle_pointer` (`cycle.py:521`, `:568`) are never
  called from move-task. Their only outside caller is the review prompt in `workflow_cores.py:289`
  [2nd].

## 3. Reviewer identity on each path

- **Review claim.** `agent action review` requires `--agent` and records an unforced
  `for_review -> in_review` with actor `build_status_actor(role=reviewer, …)`
  (`workflow_executor.py:1988-2035`).
- **Independence.** Judged on event `actor` only, through `actor_identities_independent`
  (`consolidation/preflight.py:654-672`).
- **No claimant check (#7573).** Nothing compares the approver with the `in_review` claimant.
  `_mt_require_independent_approval` (`tasks_move_task.py:1263-1300`) refuses only placeholder
  identities and the implementer, and `--force` bypasses it (`:1281`). "supervisor" appears nowhere
  in `src/`. A supervisor passing `--agent <self>` becomes both the actor and the cycle's
  `reviewer_agent`.
- **Commands that teach or emit the approval without full identity:**
  - `src/charter/offering/skills/spk-run-verdict-capture/SKILL.md:24` (core, editable) shows the
    approval with no `--agent`;
  - the rendered completion commands (`workflow_executor.py:2280-2287`) pass `--agent` only;
  - `runtime/next/runtime_bridge_decision_mapping.py:318` prints the approval with no `--agent` [2nd];
  - `packs/built-in/.../review/prompt.md:292` uses `--actor <name>` (upstream in open-packs).

## 4. Where the fabricated reviewer is read [2nd: not only ledger noise]

- **Independence gates.** `preflight._independent_reviewer_confirmed` and `wp_evidence`
  `REVIEW_NOT_INDEPENDENT` read `actor` only.
- **`approved_bound._is_claimed_review_verdict`** (`:250-259`) counts **any** approved `review_result`
  that leaves `in_review` after a claim, including one move-task synthesized. This is #5721
  residual route (a).
- **`acceptance/matrix.py:1240-1270`** stamps criteria `pass` and persists
  `verified_by = result.reviewer` into the committed `acceptance-matrix.json`. The git-user name
  therefore spreads into a second artifact.
- **`consolidation/done_bookkeeping.py`.** `:110-133` resolves the actor from `SPEC_KITTY_AGENT`,
  then the git user, then `$USER`. `:398-408` mints the `lane-approved:<WP>` and
  `snapshot-review:<WP>` references, which `SYNTHETIC_REVIEW_REF_PREFIXES` (`cycle.py:85`) does not
  list.
- **Bypass doors that record whatever the caller asserts, unchecked:**
  `agent status emit --review-result-json/--evidence-json` (`status.py:396-470`) and
  `orchestrator-api transition` (`wp_lifecycle.py:848-890`).

## 5. Contract constraint: a reviewer is required [2nd]

A non-empty reviewer, verdict and reference are enforced in core by:
- `status/emit.py:464-477` (`_build_done_evidence`);
- `status/wp_state.py:744-761` (every exit from `in_review`);
- `wp_state.py:764-790` (evidence must equal `review_result`);
- `status/validate.py:275-314`;
- `status/review_result_parse.py:34-38`.

`spec_kitty_events` `ReviewVerdict.reviewer` has `min_length=1`. A null reviewer, recorded as
"explicitly unreviewed", would need changes to these core validators **and** a
`spec-kitty-events` release.

## 6. Tests that pin today's behaviour

These need re-pinning (10 files) [2nd: list extended]:
- `tests/agent/test_review_feedback_pointer_2x_unit.py:168-170,309,371-394`
- `tests/agent/cli/commands/test_tasks_helpers.py:264-292`
- `tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py:302-312`
- `tests/integration/test_review_durability_matrix.py:526`

These are fixture-only (historical records, still valid):
- `tests/consolidation/test_approved_bound.py:173-187`
- `tests/terminus/test_forced_approval_restamp.py`
- `tests/review/test_synthetic_review_ref_grammar.py`
- `tests/review/test_cycle.py:244`
- `tests/agent/test_workflow_review_cycle_pointer.py:147-166`

Architectural gates touching these modules (none pins `_detect_reviewer_name`):
- `test_status_events_writes_gate.py`
- `test_no_write_side_rederivation.py`
- `test_exemption_registry_ratchet.py`
- `test_no_read_side_bypass.py`
- `test_status_state_read_dir_single_authority.py`
- `test_verdict_vocab_single_source.py`
- `test_untrusted_path_containment.py`
- `test_timing_coverage_invariant.py`
- `test_issue_matrix_json_migration_completeness.py`
- the source-text call-site counter in `test_verdict_attribution_4670.py:434-462`

Cheap end-to-end seams, measured:
- `test_verdict_attribution_4670.py`: 8 passed, 4.8 s;
- `test_move_task_approval_evidence.py`: 2 passed, 3.8 s.

## 7. Sizes, complexity and churn

| File | Lines |
|---|---|
| `tasks_move_task.py` | 2331 |
| `tasks_move_task_gates.py` | 1703 |
| `review/cycle.py` | 1757 |
| `tasks_verdict_persistence.py` | 1082 |
| `tasks_move_task_executor.py` | 619 |
| `tasks_move_task_hops.py` | 456 |

Complexity (C901): `_do_move_task` = **15, at the ceiling** (do not grow it).
`create_rejected_review_cycle` = 11. The functions this mission will touch are ≤ 10.

Churn: `tasks_move_task.py` has had 40+ commits since 2026-08-14, among them #6715, #6400, #7159
and #3933.

## 8. Baseline

`make test-fast` on unmodified 89217ac8: **3017 passed, 7 skipped, 0 failed** (192.9 s).
