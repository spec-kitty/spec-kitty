# Code grounding: rollback-anchor P0s (#5686, #5666)

Pre-spec brownfield squad, 2026-10-05, read-only. Lenses run as profile-loaded subagents:
`researcher-robbie` (related issues), `architect-alphonso` (design, gates and tests). The
`debugger-debbie` reproducer was lost to a container restart, so the orchestrator ran that
lens itself. Base: `origin/main` 14d653bb plus the red-first PR #5762 (merge 49acf3b1).

## 1. Reproduction (live evidence)

```
SPEC_KITTY_RUN_P0_REPRO=1 uv run --frozen pytest tests/consolidation/test_rollback_anchor_p0_repro.py -q -n0
2 failed in 5.40s
```

- `test_second_abort_never_reports_restored_over_an_unrecorded_landing` fails because of the
  product: "--abort reported a full restore (target outcome: already_at_snapshot) while main is
  still at the unrecorded landing 9018a0e instead of the pre-consolidation snapshot 406de3d".
- `test_failed_reconciliation_rollback_keeps_a_concurrent_target_commit` also fails because of
  the product: "the reconciliation-FAIL rollback reset main to 406de3d and discarded the
  concurrent commit 7576123".

The CLI-level reproducers in the issue bodies (released 4.0.0rc5 and `origin/main`
394427245 / 7c2dbd4eb) show the same two mechanisms end to end.

## 2. Root causes (file:line on this checkout)

### #5686: `begin_attempt` re-anchors over a kill-left landing

- `run_state.py:355-367`: the phase recorder `_records_post_mutation_tips` records post tips
  only when a phase exits. A SIGKILL inside a phase therefore leaves a moved run-movable
  branch with no post tip.
- `rollback.py:266-268` (`_restore_target`) and `:271-297` (`begin_attempt`): on the next
  attempt, the live tip matches neither the snapshot nor the previous post tip, so it is
  treated as "someone else moved it between attempts" and becomes `restore_targets[branch]`.
  The record holds no fact that tells "the previous attempt died mid-phase" apart from "the
  previous attempt exited cleanly".
- `rollback.py:375-376`: `live == restore_to` gives `ALREADY_AT_SNAPSHOT`, which counts as a
  full restore. `--abort` (`cli/commands/consolidate.py:469`) then clears the record and
  prints "Branches restored to their pre-consolidation commits" while the target still holds
  a squash that was never reconciled.
- The call site is `phase_claim.py:503-515` (`_capture_snapshot_and_begin_attempt`), at the
  end of the claim, before the post-mutation span.

### #5666: second restore path with a live-tip CAS expectation

- `phase_gate.py:150-152` calls `_rollback_target_after_failed_reconciliation` on FAIL and on
  REFUSE.
- `phase_gate.py:179-221`: `current_sha = _resolve_ref_sha(...)`, then
  `restore_branch_ref(..., expected_current_sha=current_sha)`. Because the expected value is
  the tip that was just read, any tip passes the compare-and-swap. The function then
  hard-resets the primary checkout (`_refresh_primary_checkout_after_merge`).
- It raises `typer.Exit(1)` inside the #5385 single door (`executor.py:383-391`). The door's
  `_report_rollback` then runs `rollback_to_snapshot`, finds `main` already at the snapshot,
  and prints `unchanged main`, so the discard is hidden.
- The door on its own already does the right thing: it compare-and-swaps against the
  RECORDED post tip (`_phase_mission_to_target` is a recorded phase). It reports a concurrent
  commit as `NOT_RESTORED (moved by another actor)` and resyncs checkouts through
  `restore_branch_ref(resync_checkouts=True)`.

### Branch-moving call sites (adopt-when-provable feasibility)

| Site | Branch | New SHA known before the write? |
|---|---|---|
| `lanes/consolidation.py:1360` (`advance_branch_ref`, rebase) | mission / target | yes |
| `lanes/consolidation.py:1445` (`advance_branch_ref`, merge/squash) | mission / target | yes |
| `consolidation/mission_number/bake.py:575` (`advance_branch_ref`) | mission | yes |
| `safe_commit` → `advance_branch_ref_for_commit` (`git/ref_advance.py:798`, `commit_helpers.py:1113`) | coord / target | yes (correction by the post-spec squad) |
| coord-strand heal (`git revert`), `git merge` in worktrees | coord / mission | no |

`advance_branch_ref` (`git/ref_advance.py:599-680`) is the single choke point for the
update-ref advances. If an intended SHA is written ahead of the compare-and-swap
`update-ref`, then `live == intent` proves the move was this run's.

## 3. Related issues (classification)

| Issue | Class | Reason |
|---|---|---|
| #5687 (P1) | FOLD IN: reset + `--abort` deadlock | Retiring the FAIL path stops the reset. The deadlock (an outcome is NOT_RESTORED forever) is closed by the operator release (`--release-branch`). Resume re-basing its window after a pull stays out of scope. |
| #5372 / #5667 | CROSS-REF | The flag-adoption half (stale `--target`/`--strategy`/`--push` on an auto-resumed record) is a separate seam (`resolve.py:244`, `executor.py:281`). The #5667 half (a stale `pre_mutation_target_sha` window base after a full restore causes a false FAIL) no longer loses data once the FAIL path is retired. It changes `target_expected_old_sha`, which the open PR #5724 consumes, so it is deferred. |
| #5048(a) | CROSS-REF | A different anchor (the PASS anchor is re-armed, `phase_teardown.py:276-283`); it is largely fixed and fails closed. |
| #5638 | OUT OF SCOPE | Fixing it needs a new sanctioned destructive checkout site. It overlaps #5611 (operator's local mission, the same coord status files at teardown) and #5644. |

## 4. Gates pinning the area

- `tests/consolidation/test_single_rollback_authority.py`: the door/caller pin. Its
  resyncing-restore scan bans only `restore_branch_ref(..., resync_checkouts=True)` outside
  `rollback.py`, which is why the non-resync FAIL-path restore went unseen. The fix adds
  `_rollback_target_after_failed_reconciliation` to `_RETIRED_NAMES` and widens the scan: no
  `restore_branch_ref` call of any kind in the consolidation executor family outside
  `rollback.py`.
- Path-scope gates that list `phase_gate.py` are unaffected by deleting a function:
  `test_coord_read_residuals_closeout.py`, `test_exemption_registry_ratchet.py`,
  `test_layer_rules.py`, `test_no_write_side_rederivation.py`.
- `test_destructive_op_routing.py` (the `_refresh_primary_checkout_after_merge` census) is
  re-run.

## 5. Why the existing tests missed both defects

- #5686: every kill-window test stops after one rollback (`test_rollback_authority.py:355`,
  `test_consolidate_abort_rollback.py:109`). None runs `begin_attempt` again before a second
  abort. The truth table row `("S", None, "X", "X")` and
  `test_begin_attempt_drops_the_post_tip_of_a_branch_moved_between_attempts` pin "keep a move
  made between attempts" with no input for an interrupted attempt, which encodes the bug
  for the kill case.
- #5666: `test_refuse_restores_target.py` races only the helper's own read-to-write gap, by
  monkeypatching, not the real window between the advance and the gate. The other gate
  tests call `_phase_reconcile_before_teardown` outside the door and assert `main == pre_sha`,
  which pins the helper as the restorer.

## 6. Operator decision (2026-10-05)

Adopt when provable, refuse otherwise, plus an explicit operator release. A kill-left move is
adopted as this run's only when the live tip equals an intended SHA written ahead of the
`update-ref`. Any other unexplained move makes the re-run refuse before mutating, with a named
code, and `--abort` reports NOT restored. `consolidate --abort --release-branch <b> --release-reason
"..."` lets the operator keep a tip that cannot be proven and clear the record. The report
shows such a branch as kept by the operator, never as restored.

## 7. Post-spec squad (2026-10-05): `reviewer-renata` and `debugger-debbie`, dispositions

| # | Finding | Disposition | Evidence |
|---|---|---|---|
| R1 / D3 | Clearing an attempt marker at an orderly exit re-creates #5686 after a FAIL with a foreign commit (re-anchor over unreconciled L under F) | changed: the boolean marker became per-branch `unsettled_refs`, settled only by a restoring rollback outcome or a PASS | spec FR-003/FR-004, US4 AS2; data-model lifecycle |
| R2 | The refusal check ran after the heal and the attestations (moves of its own, plus false refusals) | accepted: a read-only pre-check before both; `begin_attempt` accepts this process's own pre-claim moves | spec FR-005, edge cases |
| R3 / D7 | Intent lifecycle, chains, fail-closed persistence | accepted: per-branch chain `[base, new…]`, base must equal the expected tip, cleared per branch by the recorder, at `begin_attempt` and on a full restore; sink failure aborts the advance | spec FR-006; data-model |
| R4 | A kill after the PASS during bookkeeping commits on the target | changed: a reconciliation PASS settles the target | spec FR-003, edge cases |
| R5 | Release preconditions, audit | accepted: applies only where the outcome would be NOT_RESTORED; bound to the SHA; lane/unknown names refused; warning printed with the reason in the report. Durable audit beyond the console is deferred (the record is the audit while it exists) | spec US3 |
| R6 | FR-007 vs tests / ADR A2 | accepted: completes A2; truth table and between-attempts test re-pinned | plan IC-03; tests |
| R7 | No tool-mediated undo for an unprovable landing | deferred_with_rationale: needs an operator decision on an attested destructive restore; follow-up issue | spec Out of Scope |
| R8 | US1 positive control must assert a clean checkout and a full restore | accepted | spec US1 AS3 |
| R9 | US2 AS1 vague | accepted | spec US2 AS1 |
| R10 | Refusal is idempotent and keeps the record | accepted | spec US2 AS2 |
| R11 | Nested recorders | accepted: intents cleared per branch; taint uses entry-time expectations | data-model, recorder |
| R12 | SC-001 without the env var; self-mutation in SC-004 | accepted | spec SC-001/SC-004 |
| R13 | FR-002 scope | accepted: consolidation executor family only | spec FR-002 |
| D1 | Kill between `update-ref` and the resync leaves the checkout behind HEAD, so the restore refuses | accepted | spec FR-012 |
| D2 | A foreign commit between phases plus this run's next commit on top is recorded as ours, so the door discards it | accepted | spec FR-011, US1 AS2 |
| D4 | The refusal is raised by the caller, not `begin_attempt` | accepted | plan IC-03 |
| D5 | The #5666 repro imports the retired helper | accepted: rewritten to drive the gate through the door | spec FR-010 |
| D6 | `safe_commit` advances have a known SHA | accepted: the sink covers `advance_branch_ref_for_commit` too | §2 table |
| D8 | Resume recovery resets a behind-HEAD checkout before the refusal | deferred_with_rationale: a checkout resync proven pure by #5613, not a ref move; documented residual | spec Out of Scope |

## 8. Post-tasks squad (2026-10-05): `planner-priti`, dispositions

| Finding | Disposition | Evidence |
|---|---|---|
| HIGH: WP01 must run `tests/terminus` and integration, because the door's target restore never ran on FAIL before | accepted: test scope widened; re-pins allowed as leeway; positive control on lanes and coord | WP01 prompt |
| HIGH: settling at `_record_reconciliation_pass` runs before the projection proof | changed: settle after the door span completes, in `executor.py` | WP03 objective 4 |
| HIGH: `own_moves` could launder an unreconciled post tip into the restore target | accepted: when the pre-move tip was the effective post, keep T and carry the live tip as the post | WP02 T007 |
| MEDIUM: ordering WP02 → WP03 | accepted: WP03 names the dependent suites in Done-when | WP03 |
| MEDIUM: both parallel lanes edit the repro file | changed: marker removal moved to WP03 | WP02, WP03 |
| MEDIUM: `test_merge_cli_golden.py` pins the flags; reason flag name | accepted: owned by WP04; flag renamed `--release-reason` | WP04; spec |
| MEDIUM: WP03 too big | accepted: T011 split into WP06 (phase 1) | WP06 |
| MEDIUM: missing production-path scenarios (pre-attestation/heal refusal, orderly exit, C-002 text, post-PASS resume) | accepted | WP03 T014/T015 |
| MEDIUM: in-span moves without an intent (`bake.py:389`, plain `safe_commit`) | accepted as a fail-closed residual; one tested; recorded in the ADR | WP03, WP05 |
| LOW: CHANGELOG symlink, operator docs | accepted | WP05 owned files |
| LOW: `released_refs` cleared at `begin_attempt`, `"*"` expansion, module docstring, WP04 red-first, NFR-002 | accepted (NFR-002 is covered by the existing NFR-001 rollback timing test in `test_rollback_authority.py`) | WP02, WP04 |
