---
work_package_id: WP03
title: One review, one cycle; cited cycles exist
dependencies:
- WP02
requirement_refs:
- FR-008
- FR-009
- FR-010
- FR-012
- FR-013
- FR-014
- NFR-001
- C-006
- SC-003
planning_base_branch: fix/3044-approval-honesty
merge_target_branch: fix/3044-approval-honesty
branch_strategy: Planning artifacts for this mission were generated on fix/3044-approval-honesty. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/3044-approval-honesty unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-approval-honesty-01M78J9S
base_commit: f232057521c37fdab258f161b3f5ebaf990fc54c
created_at: '2026-11-13T03:59:49.319347+00:00'
subtasks:
- T013
- T014
- T015
- T016
- T017
- T018
phase: Phase 2 - Refusals and cycles
history:
- at: '2026-11-12T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/review/
create_intent:
- tests/specify_cli/cli/commands/agent/test_approval_honesty_cycles.py
- tests/review/test_review_cycle_adoption.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/review/cycle.py
- src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py
- tests/specify_cli/cli/commands/agent/test_approval_honesty_cycles.py
- tests/review/test_review_cycle_adoption.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – One review, one cycle; cited cycles exist

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check `review_ref` in the event log (`spec-kitty agent tasks status --mission approval-honesty-01M78J9S`).
- **You must address all feedback** before your work is complete.
- **Report progress** with `spec-kitty agent tasks add-history WP03 --note "..." --mission approval-honesty-01M78J9S`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

There are three defects on the review-cycle side of an approval:

- **#7571 / #3451.** When the reviewer already wrote `review-cycle-N.md` after claiming, the
  approval allocates `review-cycle-(N+1).md` with a synthesized body. One review is then recorded
  as two cycles. The plan squad reproduced this on the base: +2 cycles per review.
- **#7570.** An approval citing "cycle 4 APPROVE", or a `review-cycle://…/review-cycle-4.md`
  reference, is accepted although no such cycle exists.
- **#6709.** Open edge semantics: a repeat approval after a rejection reuses an older cycle; a
  feedback file on an already-approved work package; a damaged slot; an empty file; and the writer
  name.

**Done when:**
- **Adoption (FR-008).** On an unforced approval the approval adopts an existing cycle, writes
  nothing, and references it (`review-cycle://` pointer). The cycle must be **adoptable**, which
  means all of:
  1. it is valid (`validate_review_artifact_file`);
  2. **no status event references it** (`review_ref`, `review_result.reference`,
     `evidence.review.reference`);
  3. its cycle number N is greater than every cycle number referenced in the WP's event log;
  4. its `reviewer_agent` is `same_review_identity`-equal (WP01) to the reviewer of record.
- **Non-adoptable (FR-014).** A post-claim cycle file (condition 3 holds, but condition 1 or 4
  fails) refuses an unforced approval with **`REVIEW_CYCLE_NOT_ADOPTABLE`**. The refusal names the
  file and the canonical route: rename it to `review-feedback-N.md` and pass
  `--review-feedback-file`.
- **Stale cycles (FR-009).** A cycle that fails condition 2 or 3 (written before, or already
  answered by, an earlier verdict) is never adopted.
- **Citations (FR-010).** A citation must point at an existing, valid cycle that is not referenced
  by a recorded rejection and whose N is greater than every cycle number referenced in the log
  **before the latest claim**. Otherwise the approval refuses with
  **`REVIEW_CYCLE_CITATION_MISSING`**, naming the expected path. A citation is either:
  - an `--approval-ref` that is a `review-cycle://` pointer; or
  - an `--approval-ref` or `--note` whose text contains an explicit `cycle N`, `cycle-N` or
    `review-cycle-N` form (case-insensitive; other prose is ignored).
- **Forced moves.** A forced approval writes **no** review cycle; the move is not a review
  (FR-006, story 2 case 4). An arbiter override already writes none.
- **Done.** `approved -> done` writes no cycle (unchanged; pinned, FR-012).
- **#6709.** A `--review-feedback-file` on approval keeps today's guarded write (#6652 leg), and
  adoption is skipped. A feedback file on an already-approved work package, a damaged slot and an
  empty file all keep today's warn-and-continue behaviour, pinned by tests (FR-012).
- **Rename (FR-013).** `create_rejected_review_cycle` becomes `create_review_cycle`, and
  `create_rejected_review_cycle` stays as an alias. **Callers keep calling the alias**, so existing
  `mock.patch` targets still intercept.
- **Honest body.** The approval cycle's `reviewer_agent`, its body ("Approved by <reviewer of
  record>.", plus `Reference: <--approval-ref>` only when the caller gave one) and its
  `reproduction_command` all use the reviewer of record. No synthetic `approval:` token.
- **Requirements:** FR-006 (cycle side), FR-008, FR-009, FR-010, FR-012, FR-013, FR-014; NFR-001,
  NFR-003; C-006; SC-003.

## Context & Constraints

- Read `plan.md` §"One review, one cycle", `research.md` R5-R7, `data-model.md` "ReviewCycle",
  and decisions `review_cycles`, `non_adoptable_cycle` and `adoption_rule`.
- **The artifact frontmatter has no verdict field** (`review/artifacts.py:218`). The event log is
  the sole verdict authority. Never add or read a frontmatter verdict.
- `review-cycle-N.md` is a **tool-owned** filename (see the `review_feedback_source_path`
  docstring, `cycle.py:148`). The reviewer's own route is `review-feedback-N.md`.
- **Placement.** Read cycle directories through the existing `_review_cycle_read_candidate_dirs` /
  `_review_cycle_wp_dir` and build pointers with `build_review_cycle_pointer`. Do **not** add a new
  `dir / f"review-cycle-{n}.md"` join from user text: `tests/architectural/test_untrusted_path_containment.py`
  inventories such sinks, and #7546 owns placement. Resolve citations through
  `resolve_review_cycle_pointer`.
- **Codes.** Define `REVIEW_CYCLE_CITATION_MISSING` and `REVIEW_CYCLE_NOT_ADOPTABLE` in
  `review/cycle.py`, next to the cycle grammar. They are move-task-only, have no
  `SINGLE_BRANCH_*` alias, and exit 1.
- **Do not change** the commit/revert durability machinery
  (`_persist_review_cycle_with_queue`, `revert_committed_verdict_write`), except that an
  **adopted** cycle must never be reverted. Adoption returns a signal marked as not written by this
  command. A pointer to an adopted file that is not committed is treated like a local-only write.
- **Do not touch** consolidation, `workflow*.py`, `prompt_builder.py` or `status/__init__.py`.

## Branch Strategy

- **Planning base branch**: `fix/3044-approval-honesty` (via the Mission topic branch)
- **Merge target branch**: `fix/3044-approval-honesty`

Workspace: `spec-kitty agent action implement WP03 --agent <name> --mission approval-honesty-01M78J9S`.

## Subtasks & Detailed Guidance

### Subtask T013 – Red-first tests

- **Files**: new `tests/specify_cli/cli/commands/agent/test_approval_honesty_cycles.py` (CLI end-to-end, reusing WP01's fixture helpers with an unforced claim).
- **Cases**:
  1. **#7571/#3451.** The claimant writes a valid `review-cycle-1.md` (frontmatter `reviewer_agent` = claimant) after the claim, then approves. Expect no `review-cycle-2.md`, and the event reference names `review-cycle-1.md`.
  2. **No reviewer cycle.** The claimant approves. Exactly one new cycle (today's behaviour, kept).
  3. **Stale cycle (FR-009).** Cycle 1 is approved and referenced; then a rejection writes and references cycle 2; then rework, a new claim, and an approval. Cycle 1 is not adopted, and a new cycle 3 is written and referenced.
  4. **Citation missing.** Only cycle 1 exists. `--note "cycle 4 APPROVE"` and `--approval-ref review-cycle://<m>/<wp>/review-cycle-4.md` both refuse with `REVIEW_CYCLE_CITATION_MISSING` naming the path, writing nothing (byte-identical log and cycle directory).
  5. **Citation of a rejection's cycle.** Refused.
  6. **Citation of a cycle from before the latest claim.** Refused.
  7. **Valid citation.** The claimant wrote cycle 1 post-claim and cites it with `--note "cycle 1 APPROVE"`. Accepted; it adopts cycle 1 and writes no cycle 2.
  8. **Non-adoptable.** A post-claim `review-cycle-1.md` with no frontmatter, and one attributed to another identity. Both refuse `REVIEW_CYCLE_NOT_ADOPTABLE`, naming the file and the `review-feedback-N.md` route.
  9. **Feedback-file leg.** A `--review-feedback-file review-feedback-1.md` on approval writes one cycle carrying the feedback (unchanged). With a post-claim cycle file also present, no adoption happens and today's write runs; document the outcome in the test.
  10. **Forced approval** writes no review cycle.
  11. **#6709 pins.** `approved -> done` with a feedback file warns and writes no cycle. An empty feedback file on approval warns and writes the synthesized cycle (today's behaviour).
  12. **Honest body.** The written cycle's body and `reproduction_command` name the reviewer of record, and the file contains no `approval:<WP>` token.
- Pure unit tests in the new `tests/review/test_review_cycle_adoption.py` for the probe and the citation parser: regex forms, case-insensitivity, prose that must **not** match (for example "recycle 2", "cycle time"), and the ordering rules. Add a self-mutation check: break condition 2, 3 or 4 in a copy of the inputs and assert the probe changes its answer (non-vacuity).
- **Commit**: `test(review): pin one review one cycle and cited-cycle existence (red, #7571 #7570 #3451)`.

### Subtask T014 – Rename the writer, keeping an alias

- Rename the function to `create_review_cycle` in `review/cycle.py` and add `create_rejected_review_cycle = create_review_cycle` with a comment citing #6709.
- Update docstrings that name it as a rejection-only writer.
- **Do not** change callers' imports. The patches in `test_tasks_move_task_seam.py:635-737/776/1302/1328`, `test_move_task_durability.py:1616/1730` and `test_tasks_materialization.py:332/355` target the alias name in the importing modules. Run those three files to prove they still intercept.

### Subtask T015 – Adoption probe and citation verifier (`review/cycle.py`)

- `cycle_numbers_referenced(events, wp_id) -> set[int]`: every `review-cycle://` pointer (parse it with `validate_review_cycle_pointer`, then take N from the filename) found in `review_ref`, `review_result.reference` and `evidence.review.reference` of the WP's events. Optionally restrict to events up to an index, for the "before the latest claim" rule.
- `find_adoptable_review_cycle(*, repo_root, mission_slug, wp_slug, wp_id, events, reviewer_of_record) -> AdoptionResult`:
  - `AdoptionResult` is either `adopt(path, pointer)`, `none` or `not_adoptable(path, reason)`.
  - Scan the existing read candidate directories for `review-cycle-N.md` files whose N is greater than `max(cycle_numbers_referenced)` (0 if none) and that no event references.
  - Exactly one valid, identity-equal candidate → `adopt`. Any such post-claim candidate that is invalid or attributed to another identity → `not_adoptable`.
  - Several valid identity-equal candidates → take the highest N and report the others in a warning, since nothing references them.
- `parse_cycle_citation(text) -> int | None` and `verify_cycle_citation(...) -> None | refusal reason` implement the FR-010 rules.
- Add the two code constants. Keep each function ≤ complexity 10, with pure helpers and no git calls; file reads only, through the existing guarded readers.

### Subtask T016 – Honest approval write (`tasks_verdict_persistence.py`)

- `_approval_write_skip_reason` (`:743`): add a "forced move is not a review" skip when `st.force` and the move is not an arbiter override. Warn about a dropped feedback file through the existing `_warn_feedback_file_not_recorded`.
- `_persist_approved_review_cycle` (`:843`):
  - With no feedback file, call the adoption probe first. On `adopt`, return a durability signal that names the adopted cycle and the pointer, marked so the revert path never deletes or reverts it (check `VerdictDurabilitySignal` fields; add a narrowly named field if needed).
  - `reviewer_agent` comes from the reviewer of record (`st.request.effective_reviewer` after WP01), not `st.reviewer or st.agent or st.actor`.
  - Body: `Approved by <reviewer>.` plus `\nReference: <approval_ref>` only when `--approval-ref` was given and is not a cycle pointer.
  - `reproduction_command` keeps `--agent <reviewer>`.
- WP01's executor overwrite already turns the evidence reference into the cycle pointer; check that it handles the adopted signal too. If it does not, the fix belongs in WP01's file: make a minimal, rationale-noted edit there (ownership-map leeway).

### Subtask T017 – Refuse before any write

- Add one helper, `_mt_require_honest_review_cycle(st)`, in `tasks_verdict_persistence.py` (WP03-owned). It:
  1. runs the citation verifier on `--approval-ref` and `--note`;
  2. runs the adoption probe and refuses on `not_adoptable` (unforced only).

  It raises `ActionContextError(code, message)`, exactly like `_mt_require_independent_approval`.
- Call it from `_mt_require_independent_approval` in `tasks_move_task.py` (WP01-owned): **one call line**, recorded as ownership-map leeway. That function already runs before every cycle write, and a plain call adds no McCabe branch to `_do_move_task` (which is at 15).
- Confirm the ordering against `_do_move_task` (about lines 2056-2063) and `_mt_finalize_plan`: the helper must run before `_persist_approved_review_cycle`.
- Pass the probe result forward on `st` so the write does not scan twice.

### Subtask T018 – Validation

```bash
make test-fast
.venv/bin/python -m pytest -q tests/specify_cli/cli/commands/agent/test_approval_honesty_cycles.py tests/review/test_review_cycle_adoption.py tests/specify_cli/cli/commands/agent/test_approval_honesty_identity.py tests/specify_cli/cli/commands/agent/test_approval_honesty_claimant.py
.venv/bin/python -m pytest -q tests/review tests/status tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py tests/specify_cli/cli/commands/agent/test_move_task_durability.py tests/specify_cli/cli/commands/agent/test_tasks_materialization.py tests/integration/test_review_cycle_rejection_only.py tests/integration/test_review_durability_matrix.py tests/agent/test_workflow_review_cycle_pointer.py
.venv/bin/python -m pytest -q tests/architectural/test_untrusted_path_containment.py tests/architectural/test_status_state_read_dir_single_authority.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_verdict_vocab_single_source.py
.venv/bin/ruff check <changed>; .venv/bin/ruff format --check --force-exclude <changed>; .venv/bin/mypy <changed src>; .venv/bin/ruff check --select C901 <changed src>
```

**NFR-001:** time `move-task --to approved` on the 4670 fixture (median of 5) on the base and on
this branch, and record both numbers in `add-history`. The budget is ≤ 10% slower.

## Test Strategy

- Red-first through the CLI, plus pure unit tests of the probe and parser with self-mutation checks.
- Byte-identical refusals (NFR-003) for the citation and non-adoptable cases.

## Risks & Mitigations

- **The revert path deletes the reviewer's adopted file.** Mitigation: an explicit signal field, plus a test that forces the later emit to fail after adoption (see the existing WP11 revert tests in `test_move_task_durability.py`) and asserts the file survives.
- **Citation regex false positives.** Mitigation: explicit forms only, with negative unit cases.
- **Placement drift.** Mitigation: existing resolvers only, and the untrusted-path gate run.
- **Dead mint functions** (`synthetic_auto_approval_ref` and `synthetic_approval_ref` may have no `src/` caller after WP01). Mitigation: if `test_no_dead_symbols` or `__all__` flags them, delete the mints but keep the prefix constants and classifiers, which readers still need for historical records.

## Review Guidance

- Case 1 is red on the base (two cycles) and green after (one).
- The adopted file survives an emit failure.
- No frontmatter verdict is introduced or read.
- The out-of-map call line in `tasks_move_task.py` is a single line with its rationale recorded.

## Progress & Status

`spec-kitty agent tasks add-history WP03 --note "<what you did>" --mission approval-honesty-01M78J9S`.

Implementation command:

```bash
spec-kitty agent action implement WP03 --agent <name> --mission approval-honesty-01M78J9S
```
