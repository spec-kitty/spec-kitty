---
work_package_id: WP07
title: Status transition pipeline takes the fact
dependencies:
- WP04
- WP06
requirement_refs:
- FR-003
- NFR-002
planning_base_branch: claude/sleepy-hamilton-5lelee
merge_target_branch: claude/sleepy-hamilton-5lelee
branch_strategy: Planning artifacts for this mission were generated on claude/sleepy-hamilton-5lelee. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/sleepy-hamilton-5lelee unless the human explicitly redirects the landing branch.
subtasks:
- T032
- T033
- T034
- T035
- T036
- T037
phase: Phase 2 - Seams
history:
- at: '2026-09-28T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/coordination/status_transition.py
create_intent:
- tests/status/test_transition_request_owned.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/coordination/status_transition.py
- src/specify_cli/coordination/commit_router.py
- src/specify_cli/coordination/write_seam.py
- src/specify_cli/status/models.py
- src/specify_cli/status/transition_pipeline.py
- src/specify_cli/status/emit.py
- src/specify_cli/status/bootstrap.py
- src/specify_cli/agent_tasks_ports.py
- tests/specify_cli/coordination/test_status_transition.py
- tests/status/test_transition_request_owned.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Status transition pipeline takes the fact

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then load the action-scoped governance with `spec-kitty charter context --action implement --json`. Read `.kittify/charter/charter.md` if this session has not read it yet.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?** Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress.** As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

The status pipeline carries the **validated ownership fact** end to end and never re-derives ownership when it holds one (FR-003). Its readers collapse three things into one `owned: OwnedCheckout | None`:

- the parallel `effective_root: Path | None`;
- the `owned_mission: OwnedMission | None`;
- the transaction's `primary_root`.

Done means:

1. **`TransitionRequest.owned`.**
   - `TransitionRequest` has `owned: OwnedCheckout | None`.
   - The legacy `effective_root` and `owned_mission` fields remain as the **transitional dual keyword**: `TransitionRequest` is one of the six shared seams, and the legacy fields are deleted in WP18.
   - Every pipeline reader reads only the collapsed fact.
2. **No re-validation with a fact.** When a fact is present, nothing in `coordination/status_transition.py`, `status/transition_pipeline.py`, `status/emit.py`, `status/bootstrap.py`, `coordination/commit_router.py`, `coordination/write_seam.py` or `agent_tasks_ports.py` calls `resolve_owned_mission` or `resolve_ownership_claim`. The re-validation at `status_transition.py:897-918` survives **only** as the clearly marked legacy-keyword branch that WP18 deletes.
3. **Transaction converted.**
   - `BookkeepingTransaction.acquire` takes `owned=` (this is the out-of-map completion of WP06 T030; see Context).
   - An owned transaction appends through `EventLogWriteContract.primary_checkout_append(feature_dir, owned=fact)`.
   - `_TransactionIdentity.primary_root` is gone; `identity.owned` carries it.
4. **Ports carry the fact.** `MissionHandle.owned` is added, and the ports route placement and commits through it.
5. **NFR-002 / FR-003 through the CLI.** `agent mission finalize-tasks --owned-checkout P` performs **exactly one** ownership validation. This is **red on the base**, where the bootstrap read re-validates (see T037). `agent tasks move-task --owned-checkout P` performs exactly one as well.
6. **Nothing changes for non-owned missions.** All status-transition, bootstrap, pipeline, commit-router and write-seam tests stay green. The existing owned `move-task`/`mark-status`/finalize tests (FR-022) stay green without edits.

**Mission-wide DoD (post-tasks squad):**
- `grep -rn "bridging: WP07 converts" src` is empty: every bridging call site marked for this WP is converted, including sites in other WPs' files (declared out-of-map edits).
- Every bridging call site this WP adds carries `# bridging: WP<n> converts`, naming the WP that converts it (never a free-form comment, never no marker).
- `TRANSITIONAL(WP18)` markers added by this WP (exact list; any deviation is amended here in the same PR, and WP18 T096 fails on unlisted markers): **18** markers (amended in review cycles 1 and 2: the dual-keyword private helpers and the legacy aliases are marked rather than left unmarked; `transaction._acquire_locked(primary_root=)` is deleted): `coordination/status_transition.py` 4 (the legacy re-validation branch, `read_events_transactional(effective_root=)`, `emit_inner_state_changed_transactional(effective_root=)`, the inner-state door's `owned_mission=` alias); `coordination/commit_router.py` 3 (`commit_for_mission(effective_root=)`, `_resolve_group_placement(effective_root)`, `_commit_partition_group(effective_root=)`); `coordination/write_seam.py` 2 (`_probe_write_target(effective_root=)`, `write_artifact(effective_root=)`); `status/bootstrap.py` 2 (`effective_root`, `owned_mission`); `status/transition_pipeline.py` 1 (`effective_root`); `status/models.py` 3 (`TransitionRequest.effective_root`, `.owned_mission`, `has_owned_root_only`); `agent_tasks_ports.py` 2 (`MissionHandle.effective_root`, the `_placement_for` legacy arm); `status/emit.py` 1 (`_flat_subtasks_dir_resolver(effective_root=)`, added in review cycle 2). The inner-state door's `owned_mission=` marker sits on the signature parameter. Plus 3 `# bridging: WP17 converts` call-line markers (`transaction.py` `safe_commit`, `commit_router.py` `safe_commit`, `transition_pipeline._default_resolve_subtasks_dir`). Check with `grep -c "TRANSITIONAL(WP18)"` per file.
- Red-first proofs are **commits**: the red test commit precedes its fix commit, and the reviewer verifies the order in `git log`.
- Error codes are imported from `OwnedRefusalCode` (WP01); no `OWNED_*` string literal is repeated in `src/` or new tests (Sonar S1192).

## Context & Constraints

**Mission documents.** All live under `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/`:
- `spec.md`: FR-003, NFR-002, FR-022, C-001.
- `plan.md`: IC-04, Staging Strategy, Test Layout.
- `research.md`: R-03, R-16.
- `contracts/owned-checkout-carrier.md`: §2 "Once per command" and §7 (`TransitionRequest` is a named consumer).
- `contracts/architectural-gate.md`: G2's floor names `status_transition.py:917`, and G4 bans `effective_root`.
- `occurrence_map.yaml`.

**Prerequisites.**
- **WP04** exposes `owned=` on `placement_seam` / `mission_context_for` / `resolve_action_context`, and possibly on `resolve_placement_only`.
  - Before calling a `mission_runtime` function, grep its current signature.
  - If it takes `owned=`, pass the fact.
  - If it still takes only `effective_root=`, pass the **bridging expression** `effective_root=owned.owned_root if owned else None`, marked `# bridging: WP<n> converts` with the WP that owns the callee. This is not a new signature.
- **WP06** added:
  - `_TransactionIdentity.owned` (set in `_identity_for_request`);
  - the owned arm of `_read_contract_from_transaction_target`;
  - `EventLogReadContract.primary_checkout(..., owned=)` and `EventLogWriteContract.primary_checkout_append(..., owned=)`;
  - the `transaction.py:644` segment swap.
- **WP02** makes `resolve_owned_mission` return the fact and turns `OwnedMission` into a transitional legacy factory function (marked `TRANSITIONAL(WP18)`) that mints an `OwnedCheckout`; the legacy attribute names resolve through `OwnedCheckout`'s `TRANSITIONAL(WP18)` properties. **New code uses canonical fields only:** `repository_root`, `owned_root`, `mission_dir`, `mission_slug`, `target_branch`, `topology`.

**Staging rules (binding).**
- Conversion is top-down.
- Transitional surfaces are the six shared seams plus every other function marked TRANSITIONAL(WP18). The six shared seams keep a dual keyword until WP18; `TransitionRequest` is one of them.
- **Additional transitional dual keywords introduced here (declared design extension).** These public callees are called with a bare owned root by files converted in later WPs:

  | Callee | Legacy caller(s) with the owner WP |
  |---|---|
  | `commit_for_mission` | `mission_finalize.py:2752` (WP13), `spec_commit_cmd.py:207` (WP16) |
  | `write_seam.write_artifact` | `tasks/issue_matrix.py:403` (WP17), `acceptance/matrix.py:533` (WP15) |
  | `bootstrap_canonical_state` | `mission_finalize.py:194-204` (WP13) |
  | `read_events_transactional` | `tasks_move_task.py:2458,2524` (WP16), `tasks_finalize_validation.py:105` (WP13) |
  | `emit_inner_state_changed_transactional` | `tasks_mark_status.py:415`, `tasks_move_task.py:3122` (WP16) |
  | `MissionHandle` | `tasks_move_task.py:550,2888,2925`, `tasks_mark_status.py:232` (WP16), `review/cycle.py:699` (WP17) |

  The rules for these callees:
  - Each gains `owned: OwnedCheckout | None = None` as the authoritative parameter and keeps its legacy `effective_root` / `owned_mission` parameter with the **same lifetime as the six shared seams' dual keywords**.
  - Converting those callers here would be a large out-of-map edit into five WPs' files, which is why the legacy parameter stays.
  - Mark every legacy parameter with `# TRANSITIONAL(WP18): delete with the dual keywords`.
  - Record this list in the Activity Log as a cross-check. Under the plan's convention these are "other functions marked TRANSITIONAL(WP18)"; WP18 T096 deletes exactly what `grep -rn "TRANSITIONAL(WP18)" src tests` finds.
- The transitional `OwnedMission` legacy factory function and the legacy attribute names live until WP18. Do not add new reads of `.root`/`.primary`/`.directory`/`.slug`/`.target`.

**Declared out-of-map edits.** WP06 owns the first two; the last two have no owner in the pinned map. Declare each in its commit body with a one-line rationale.
- `src/specify_cli/coordination/transaction.py`: convert `acquire(effective_root=)` to `acquire(owned=)` and make the owned append label honest.
  - The sole caller `_acquire_status_transaction` gets the fact only in this WP.
  - The acquire-shape test is WP07-owned.
  - WP06 T030 explicitly deferred this, and WP06 is complete because it is a dependency.
- `tests/specify_cli/coordination/test_owned_status_read_contract.py`: only if a WP06 test pins `acquire` kwargs. None is expected; grep first.
- `tests/status/test_transition_pipeline.py`: its fake resolver takes `effective_root=` (`:75-76`, `:172-176`), and its test targets `transition_pipeline.py`, which this WP owns.
- `tests/status/test_bootstrap.py`: `:549-556` asserts `request.effective_root == owned.root`; the test targets `bootstrap.py`, which this WP owns.

**Occurrence map.**
- `code_symbols` / `tests_fixtures`: rename.
- `serialized_keys`: do not change. This covers status event fields and `CommitReceipt`, and `TransitionRequest` is not serialized.
- `logs_telemetry`: do not change. The `OWNED_TRANSACTION_UNAVAILABLE`, `OWNED_MISSION_PATH_REFUSED` and `OWNED_TOPOLOGY_UNSUPPORTED` strings stay exact.

**Complexity.** The probe on HEAD `df1588860` flags `commit_router._commit_partition_group` at **15** and `_stage_artifacts_in_coord_worktree` at **14** (`.venv/bin/ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=11' src/specify_cli/coordination/commit_router.py`).
- `_commit_partition_group` is touched, so a **campsite extraction commit comes first**.
- `status_transition.py`, `write_seam.py`, `status/*.py` and `agent_tasks_ports.py` show no function at ≥12.
- Re-run the probe after each conversion. A function that would reach ≥12 gets a behaviour-preserving extraction first.

**Terminology.** New prose uses "repository root checkout" and "owned checkout". Keep the existing public names (`primary_checkout_append`, `commit_to_primary_target`).

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `claude/sleepy-hamilton-5lelee`; completed changes must merge back into `claude/sleepy-hamilton-5lelee`.
- **Planning base branch**: `claude/sleepy-hamilton-5lelee`
- **Merge target branch**: `claude/sleepy-hamilton-5lelee`
- **Execution lane**: allocated by `spec-kitty agent mission finalize-tasks` in `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/lanes.json`, which had not been generated when this prompt was written. Use `spec-kitty implement WP07` and the workspace it resolves. Never hand-construct the path.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

**Commit order**:
1. T037 red CLI-count test.
2. T035 campsite extraction.
3. T032.
4. T033 (with the `transaction.py` out-of-map hunk). T037 finalize count turns green here or at T034.
5. T034.
6. T035 conversion.
7. T036.

## Subtasks & Detailed Guidance

### Subtask T032 – `TransitionRequest.owned` (collapses `effective_root` and `owned_mission`; dual keyword)

- **Purpose**: one field carries the validated fact through the status pipeline (contract §7). The two legacy fields keep not-yet-converted callers green until WP18.
- **Steps**:
  1. **Red first** in `tests/status/test_transition_request_owned.py` (markers `unit` + `fast`). In tests, mint facts with `OwnedCheckout._mint(...)`, as WP01's `tests/mission_runtime/test_owned_checkout.py` does (contract §1 allows a `tests/` helper, and G3 scans `src/` only), or take them from the WP02 minter on a real fixture. Never call `OwnedCheckout(...)`, which raises `TypeError` by design. Cover these cases:
     - `TransitionRequest(owned=fact).owned_fact() is fact`.
     - `TransitionRequest(owned_mission=fact).owned_fact() is fact` (legacy alias collapses).
     - Mismatch: `owned=f1, owned_mission=f2` with differing checkout or slug raises `TypeError` at `owned_fact()`.
     - `effective_root=P` alone: `owned_fact()` is `None`, and `has_owned_root_only()` is `True`. This legacy shape is the only one that may still validate.
     - A request built positionally or with no owned fields is unchanged.
  2. Implement in `src/specify_cli/status/models.py` (`TransitionRequest`, `:858-908`):
     - Add `owned: OwnedCheckout | None = None` **after** `owned_mission`, so positional construction is unchanged. Import it under `TYPE_CHECKING` from `mission_runtime`, replacing the `OwnedMission` import at `:22-26`, which keeps the cold-import guarantee (#3866 comment).
     - Add `owned_fact(self) -> OwnedCheckout | None`. It returns `self.owned` or `self.owned_mission`, and raises `TypeError` when both are set and are not the same object and not equal. Do the collapse **at read time, not in `__post_init__`**: existing tests and callers mutate `request.effective_root` / `request.owned_mission` after construction (for example `tests/specify_cli/coordination/test_status_transition.py:1008-1011`, `:1240-1241`).
     - Mark `effective_root` and `owned_mission` with `# TRANSITIONAL(WP18)` and update the class docstring.
  2a. Sketch (read-time collapse; no identity checks here):
     ```python
     def owned_fact(self) -> OwnedCheckout | None:
         """The validated ownership fact; the legacy ``owned_mission`` alias collapses into it (WP18 deletes the alias)."""
         if self.owned is not None and self.owned_mission is not None:
             if self.owned is not self.owned_mission and self.owned != self.owned_mission:
                 raise TypeError("TransitionRequest carries two different ownership facts")
         return self.owned if self.owned is not None else self.owned_mission

     def has_owned_root_only(self) -> bool:
         """TRANSITIONAL(WP18): a legacy caller passed a bare owned root without the fact."""
         return self.effective_root is not None and self.owned_fact() is None
     ```
  3. Do **not** add identity checks (checkout or slug vs `effective_root`) here. They stay at the identity seam (T033), preserving today's `OWNED_MISSION_PATH_REFUSED` behaviour and location.
- **Files**: `src/specify_cli/status/models.py`, `tests/status/test_transition_request_owned.py`.
- **Parallel?**: no. T033 and T034 build on it.
- **Validation checklist**:
  - [ ] The new tests are committed red (`AttributeError`/`TypeError` on the new API), then green.
  - [ ] `tests/status/` stays green, including the `TransitionRequest` users in `test_transition_pipeline.py`.
  - [ ] mypy is clean on `status/models.py` (the dataclass remains non-frozen).
- **Edge cases**:
  - `dataclasses.replace(request, ...)` copies all three fields. `owned_fact()` stays consistent.
  - Equality on the frozen `OwnedCheckout`: use `is` first, then `==`, so two facts minted separately for the same checkout do not raise.

### Subtask T033 – `status_transition`: consume the fact, remove re-validation, owned read contract

- **Purpose**: the transactional status layer stops deriving ownership. It takes the fact from the request and hands it to the transaction and the read contract (FR-003, contract §2).
- **Steps**:
  1. **Red first**: add tests to `tests/specify_cli/coordination/test_status_transition.py`.
     - (a) `_identity_for_request(TransitionRequest(owned=fact, ...))`:
       - it builds the identity from the fact: `feature_dir == fact.mission_dir`, `repo_root == fact.owned_root`, `identity.owned is fact`;
       - it runs with a **tripwire** on `specify_cli.core.checkout_ownership.resolve_ownership_claim` and `specify_cli.core.owned_mission.resolve_owned_mission` that raises `AssertionError` if called;
       - it never calls `_repo_root_for_feature`.
     - (b) Mismatch: `owned=fact` with `effective_root` set to another path, or with `mission_slug` naming another mission, raises `ActionContextError("OWNED_MISSION_PATH_REFUSED")`. This keeps the #3866 guard.
     - (c) `read_events_transactional(feature_dir=..., mission_slug=..., owned=fact)` returns P's events under the same tripwire.
     - (d) The acquire-shape parity test (`:1046-1083`) rewritten to `single["owned"] is fact` and `single["repo_root"] == fact.repository_root`.
     - Rewrite the #3866 tests (`:1198-1310`) from `OwnedMission(...)` construction and `request.owned_mission` onto `owned=`. Keep one test that still threads `owned_mission=` to pin the dual-keyword collapse until WP18.
  2. Implement in `src/specify_cli/coordination/status_transition.py`:
     - Replace the `TYPE_CHECKING` `OwnedMission` import (`:84-86`) with `from mission_runtime import OwnedCheckout`.
     - `_identity_for_request` (`:884-988`):
       - `fact = request.owned_fact()`.
       - If `fact` is set: apply the identity guard (the `request.effective_root` checkout and `mission_slug` must match `fact.owned_root` and `fact.mission_slug`), then `feature_dir, repo_root = fact.mission_dir, fact.owned_root`.
       - `elif request.effective_root is not None`: this is the **legacy keyword branch**. Keep the existing `resolve_owned_mission` call (it yields a fact) inside a block commented `# TRANSITIONAL(WP18): legacy effective_root-only callers; G2 floor offender`.
       - Else: the non-owned path is unchanged.
       - The destination-ref block (`:966-975`) uses `fact`: pass `owned=` or the bridging expression to `resolve_placement_only` (see Context).
     - `_TransactionIdentity` (`:92-101`): delete `primary_root`. `identity.owned` (added by WP06) is the only owned carrier. Replace every `identity.primary_root` read with `identity.owned.repository_root if identity.owned else None`, or restructure (`_resolve_transaction_entry` `:1003`, `_acquire_status_transaction` `:1028-1037`, `emit_inner_state_changed_transactional` `:1654-1700`).
     - `_acquire_status_transaction`: `BookkeepingTransaction.acquire(repo_root=identity.owned.repository_root if identity.owned else identity.repo_root, ..., owned=identity.owned)`.
     - `read_events_transactional` (`:1345-1364`): add `owned: OwnedCheckout | None = None` and keep the legacy `effective_root` (`# TRANSITIONAL(WP18)`). Build the internal `TransitionRequest(owned=owned, effective_root=effective_root, ...)`.
     - `emit_inner_state_changed_transactional` (`:1585-1706`): add `owned=` and keep the legacy `effective_root` and `owned_mission`. Use `request.owned_fact()` / `identity.owned` for the owned checks at `:1654` and `:1670`, and the `BookkeepingWorktreeMissing` re-raise at `:1698`.
  3. Out-of-map `src/specify_cli/coordination/transaction.py` (WP06-owned; declare it):
     - `acquire(..., owned: OwnedCheckout | None = None)` replaces `effective_root` (`:249`). The lock root is `owned.owned_root if owned else repo_root` (`:291-293`).
     - `_acquire_locked(..., owned=)` replaces `primary_root=` (`:299-312`, `:547`). `txn._owned` replaces `_primary_root` (`:195`), and `commit()` reads `self._owned.repository_root` (`:830`).
     - The `safe_commit(effective_root=...)` keyword (`:836`) stays as a bridging expression marked `# bridging: WP17 converts`, because `git/commit_helpers.py` converts in WP17: `effective_root=self.worktree_root if self._owned is not None else None`.
     - `append_events` (`:643`): `if self._owned is not None: primary_checkout_append(self.feature_dir, owned=self._owned)`. The legacy and coordination arms are unchanged.
- **Files**: `src/specify_cli/coordination/status_transition.py`, `tests/specify_cli/coordination/test_status_transition.py`, and the declared hunk in `src/specify_cli/coordination/transaction.py`.
- **Parallel?**: no.
- **Validation checklist**:
  - [ ] `grep -n "resolve_owned_mission" src/specify_cli/coordination/status_transition.py` finds exactly one call site, inside the `TRANSITIONAL(WP18)` legacy branch.
  - [ ] `grep -n "primary_root" src/specify_cli/coordination/status_transition.py src/specify_cli/coordination/transaction.py` finds only comments or unrelated identifiers (`commit_to_primary_target` is fine).
  - [ ] The carried WP06 test `test_finalize_and_read_owned_mission_below_worktrees` stays green, and the owned append now uses `primary_checkout_append(owned=)`. Assert this in one T033 test by recording the contract passed to `append_event_stream_log`.
  - [ ] `tests/specify_cli/coordination/` and `tests/coordination/` stay green.
- **Edge cases**:
  - `OWNED_TRANSACTION_UNAVAILABLE` must still fire for an owned request whose mission has no transactional metadata. Both doors must keep it (`test_batch_door_refuses_owned_mission_without_transaction_like_single`).
  - The lock file must stay at the same path for owned and non-owned missions, because NFR-001 snapshots the lock root.
  - `_read_contract_from_transaction_target`'s owned arm, added by WP06, must stay the first branch.

### Subtask T034 – Pipeline readers: `transition_pipeline`, `emit`, `bootstrap`

- **Purpose**: the pure pipeline and its two shells read the collapsed fact, and bootstrap stops re-validating on every read. This is the concrete source of the extra validation in finalize (T037).
- **Steps**:
  1. **Red first**:
     - `tests/status/test_transition_request_owned.py`: `bootstrap_canonical_state(P_mission_dir, slug, owned=fact, repo_root=fact.repository_root)` seeds WP rows with **zero** calls to `resolve_ownership_claim` (tripwire).
     - `prepare_transition` with `owned=fact` on `in_progress → for_review` passes the fact to the injected resolver as `owned=`.
  2. `src/specify_cli/status/transition_pipeline.py`:
     - `_default_resolve_subtasks_dir(..., owned: OwnedCheckout | None = None)` (`:84-104`) bridges into `resolve_subtasks_gate_dir(..., effective_root=owned.owned_root if owned else None)`, because `missions/_read_path_resolver.py` converts in WP17. Mark the call `# bridging: WP17 converts`.
     - `_infer_review_gates` (`:131-176`) passes `owned=request.owned_fact()` at `:163`.
     - Update `SubtasksDirResolver` (`:64`) and its docstring to say the resolver receives `owned=`.
  3. `src/specify_cli/status/emit.py`: rename `_flat_subtasks_dir_resolver`'s dropped parameter (`:690`) to `owned: OwnedCheckout | None = None`. Keep the `noqa: ARG001` with its D-1 rationale; it is still deliberately dropped. Update the docstring (`:694-699`). There is no other `effective_root` in `emit.py` (`grep -n effective_root src/specify_cli/status/emit.py`).
  4. `src/specify_cli/status/bootstrap.py` `bootstrap_canonical_state` (`:92-198`):
     - Add `owned: OwnedCheckout | None = None`. Keep `effective_root` and `owned_mission` as `# TRANSITIONAL(WP18)`; the owned caller `mission_finalize.py:194-204` converts in WP13.
     - Collapse: `fact = owned or owned_mission`. If `effective_root` is also set, it must equal `fact.owned_root`; raise `TypeError` otherwise.
     - The read at `:151-155` becomes `read_events_transactional(..., repo_root=repo_root, owned=fact)` whenever `fact` is set. This removes the per-read re-validation.
     - The seeding requests (`:170-186`) become `TransitionRequest(..., owned=fact)`.
     - Replace the `TYPE_CHECKING` `OwnedMission` import (`:28`).
  5. Declared out-of-map test updates:
     - `tests/status/test_transition_pipeline.py:75-76,172-176`: the fake resolver keyword becomes `owned`, and the test passes a fact.
     - `tests/status/test_bootstrap.py:549-556`: assert `request.owned_fact() is owned` instead of `request.effective_root == owned.root`.
- **Files**: `src/specify_cli/status/transition_pipeline.py`, `src/specify_cli/status/emit.py`, `src/specify_cli/status/bootstrap.py`, and the tests above.
- **Parallel?**: after T032/T033.
- **Validation checklist**:
  - [ ] `grep -n "effective_root" src/specify_cli/status/*.py` finds only the `TRANSITIONAL(WP18)` legacy parameters in `bootstrap.py` and the `TransitionRequest` fields in `models.py`.
  - [ ] `tests/status/` is fully green.
  - [ ] The T037 finalize count is now 1.
- **Edge cases**:
  - The flat shell must keep **not** threading the root to the subtasks resolver (D-1 parity). Do not "fix" that here.
  - `bootstrap_canonical_state` with `dry_run=True` must also read without re-validating.

### Subtask T035 – `commit_router` / `write_seam` conversions

- **Purpose**: the canonical commit and write seams carry the fact internally, so every owned artifact commit decides placement from `owned` and never from a bare path.
- **Steps**:
  1. **Campsite first** (its own commit, behaviour-preserving): `_commit_partition_group` in `src/specify_cli/coordination/commit_router.py` (`:278-470`, complexity **15**). Extract:
     - the placement/`use_coord` decision (`:298-321`) into `_resolve_group_placement(...)`;
     - the empty-commit-paths / wrong-surface classification (`:388-422`) into `_classify_no_commit_paths(...)`.
     Target ≤ 11. Add focused unit tests for each helper in `tests/coordination/test_commit_router.py`; note that as an out-of-map test edit, or use the WP-owned `tests/status/test_transition_request_owned.py` if you prefer to stay in-map. Run `tests/coordination/test_commit_router*.py` and `tests/specify_cli/coordination/test_commit_router_*.py` before and after with identical results.
  2. **Red first**: in `tests/status/test_transition_request_owned.py`, test that `commit_for_mission(R, slug, (P/plan.md,), msg, policy, kind=PLAN, owned=fact)`:
     - commits on P's branch;
     - makes zero claim calls (tripwire);
     - returns `status == "committed"`.
     Add the same-fixture control `effective_root=P` (legacy) with an identical result.
  3. Convert `commit_router.py`:
     - `commit_for_mission(..., owned: OwnedCheckout | None = None, effective_root: Path | None = None)` (`:187-197`). The legacy keyword is `# TRANSITIONAL(WP18)`. Internally, normalise once: if `effective_root` is set without `owned`, keep today's path-based behaviour by bridging to the internals' legacy branch.
     - The private internals `_commit_partition_group`, the new helpers and `_group_files_by_partition` take `owned` only when the caller holds a fact.
     - Where only a bare root arrives (legacy callers), keep one private bridging variable `owned_root: Path | None` confined to `commit_for_mission`. Do not introduce a new bare-path **parameter** anywhere.
     - Placement calls (`:298-301`, `:242`) use `owned=` or the bridging expression, according to WP04's signature.
     - `safe_commit(...)` (`:432-439`): `**effective_root_kwargs(owned.owned_root if owned else legacy_root)`, marked `# bridging: WP17 converts`. This is the bridging expression, because `commit_helpers` converts in WP17. Drop the module-level `effective_root_kwargs` import (`:44`) if it is no longer needed. Otherwise keep it with a `# bridging` comment.
  4. Convert `write_seam.py` the same way:
     - `write_artifact(..., owned=None, effective_root=None)` (`:462-472`, legacy keyword transitional);
     - `_probe_write_target(..., owned=...)` (`:239-268`, private, fact only);
     - the owned gates at `:533` and `:540` read `owned is None`;
     - the `commit_for_mission(...)` call at `:549-559` passes `owned=`.
- **Files**: `src/specify_cli/coordination/commit_router.py`, `src/specify_cli/coordination/write_seam.py`, `tests/status/test_transition_request_owned.py` (plus any declared out-of-map test edits for the campsite helpers).
- **Parallel?**: yes with T036 after T032, but not with T033 (both touch the transaction flow; keep the commits separate).
- **Validation checklist**:
  - [ ] `.venv/bin/ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=11' src/specify_cli/coordination/commit_router.py src/specify_cli/coordination/write_seam.py` flags nothing you touched. `_stage_artifacts_in_coord_worktree` (14) is untouched unless you edit it; if you do, extract first.
  - [ ] `tests/coordination/test_commit_router.py`, `test_commit_router_fail_loud.py`, `test_commit_router_layering.py`, `test_write_seam_adoption.py`, `tests/specify_cli/coordination/test_commit_router_partition*.py`, `test_commit_router_placement.py` and `test_write_seam_thunk.py` are green.
  - [ ] The existing owned spec-commit and finalize tests (`tests/integration/test_explicit_checkout_commands.py`) are green unchanged. They pass the legacy keyword.
- **Edge cases**:
  - An owned commit must never split into partition groups. Today `groups = [(kind, files)]` when an owned root is set (`:242`); preserve that.
  - The owned write gate skip (`write_seam.py:529-535`, owned single-branch writes never route through coordination) must hold for both keywords.
  - `commit_for_mission` is patched in many tests via `tasks_command_adapters._seam_commit_for_mission` (`*args, **kwargs` passthrough). Adding a keyword does not break those patches; confirm with `grep -rn "commit_for_mission" tests/ | wc -l` and a run of the patched test files.

### Subtask T036 – `agent_tasks_ports.MissionHandle.owned`

- **Purpose**: the task-command ports carry the fact, so `move-task` / `mark-status` placement and commits read P through the fact rather than a bare root (IC-04).
- **Steps**:
  1. **Red first**, in `tests/status/test_transition_request_owned.py`:
     - `RealFsReader().planning_read_dir(MissionHandle(R, slug, owned=fact), kind=TASKS_INDEX)` returns `fact.mission_dir`;
     - `RealCoordCommitRouter().feature_write_dir(MissionHandle(..., owned=fact))` returns P's STATUS dir;
     - `commit_artifact` passes `owned=fact` to the injected `commit_fn` (record the kwargs).
     Add the same-fixture legacy control, `MissionHandle(R, slug, effective_root=P)`, with the same results.
  2. Implement in `src/specify_cli/agent_tasks_ports.py`:
     - `MissionHandle` (`:68-80`): add `owned: OwnedCheckout | None = None` after `effective_root`, which stays as `# TRANSITIONAL(WP18)` because its constructors live in WP16/WP17 files.
     - Add `__post_init__` validation: if both are set, `effective_root.resolve() == owned.owned_root`, else `TypeError`. The dataclass is frozen and immutable after construction, so `__post_init__` is safe here.
     - Replace the three `**({"effective_root": ...})` dict splats (`:249-252`, `:256-259`, `:278-281`) with one private helper, `_placement_for(mission) -> PlacementSeam`, that calls `placement_seam(mission.repo_root, mission.mission_slug, owned=mission.owned)` when `owned` is set and falls back to the legacy keyword otherwise. This removes three `"effective_root"` dict-key sites (G4).
     - `feature_write_dir` (`:336-346`) and `commit_artifact` (`:356-390`): pass `owned=mission.owned` to `commit_fn`, and the legacy `effective_root_kwargs` only when `owned` is `None`.
       - C-001 byte-parity of the mock call shape matters for `test_tasks_cli_contract_coord.py`: a non-owned handle must produce **no** extra keyword.
       - Pass `owned=` only when set, using a small `_owned_kwargs(mission)` typed helper.
  3. Sketch of the private helpers (the names are suggestions):
     ```python
     def _placement_for(mission: MissionHandle) -> PlacementSeam:
         if mission.owned is not None:
             return placement_seam(mission.repo_root, mission.mission_slug, owned=mission.owned)
         # TRANSITIONAL(WP18): legacy bare-root handles (review/cycle.py, WP17)
         return placement_seam(mission.repo_root, mission.mission_slug, **effective_root_kwargs(mission.effective_root))
     ```
     The three `RealFsReader` methods and `feature_write_dir` each call `_placement_for(mission).read_dir(kind)`, which removes the triplicated splat.
- **Files**: `src/specify_cli/agent_tasks_ports.py`, `tests/status/test_transition_request_owned.py`.
- **Parallel?**: yes, after T032.
- **Validation checklist**:
  - [ ] `tests/specify_cli/cli/commands/agent/test_tasks_cli_contract_coord.py`, `test_tasks_cli_contract.py`, `test_owned_checkout_move_task.py` and `tests/integration/test_owned_checkout_mark_status.py` are green unchanged (FR-022).
  - [ ] `grep -n '"effective_root"' src/specify_cli/agent_tasks_ports.py` finds nothing.
  - [ ] mypy is clean; the `follow_imports = "skip"` note (`:241-244`) still applies to the annotated locals.
- **Edge cases**:
  - Non-owned handles must keep calling `resolve_feature_dir_for_mission` in `feature_write_dir` (`:342-345`), byte-identical.
  - The `thread_target_branch` split (`:357-381`) must keep its two distinct call shapes.

### Subtask T037 – NFR-002 exactly-one-validation test (`move-task`, `finalize-tasks`)

- **Purpose**: pin FR-003 / NFR-002 through the real CLI entry point. One owned command invocation performs exactly one ownership validation, and 0 or ≥2 fails.
- **Steps**:
  1. **First commit of the WP (red)**. In `tests/status/test_transition_request_owned.py`, add an `integration` + `git_repo` test class. It uses the WP02 fixture `owned_checkouts`, imported explicitly with `from tests.integration.conftest import owned_checkouts, r_snapshot` and re-exported through `__all__`, because conftest fixtures in `tests/integration/` are not visible from `tests/status/`. The class:
     - clears the workspace caches first (`specify_cli.workspace.context.clear_workspace_resolution_caches` or the name WP05 settled on) (plan: Test Layout);
     - wraps `specify_cli.core.checkout_ownership.resolve_ownership_claim` in a counting wrapper that delegates to the original. `resolve_owned_mission` imports it lazily inside the function (`owned_mission.py:88`), so patching the module attribute intercepts it;
     - invokes through `CliRunner` exactly as a user would.
  2. Cases:
     - **`finalize-tasks`**: `agent mission finalize-tasks --mission <slug> --owned-checkout P --json` gives `count == 1`. This is **red on the base**: `mission_finalize.py:3327` validates once, then `bootstrap_canonical_state` reads through `read_events_transactional(..., effective_root=P)` without the fact (`bootstrap.py:151-155`), which re-validates at `status_transition.py:917`. Record the base count in the Activity Log (expected ≥ 2).
     - **`move-task`**: `agent tasks move-task WP01 --to claimed --mission <slug> --owned-checkout P --json` after a finalize gives `count == 1`. Run it on the base and record the count. If the base is already 1 (the seeding path threads `owned_mission`), this case is the `[ratchet]` guard and the finalize case carries the red-first evidence. Say so in the test docstring.
     - **Positive control on the same fixture**: the same commands without `--owned-checkout`, against a non-owned mission in R, give `count == 0`. This proves the counter actually intercepts: a counter that never fires would make the owned assertion vacuous.
     - `r_snapshot` is unchanged around each owned invocation (NFR-001).
  2a. Counting-wrapper sketch:
     ```python
     @pytest.fixture
     def claim_counter(monkeypatch):
         from specify_cli.core import checkout_ownership
         calls: list[Path | None] = []
         original = checkout_ownership.resolve_ownership_claim
         def _counting(claimed_checkout, *, resolved_primary):
             calls.append(claimed_checkout)
             return original(claimed_checkout, resolved_primary=resolved_primary)
         monkeypatch.setattr(checkout_ownership, "resolve_ownership_claim", _counting)
         return calls
     ```
     Request `claim_counter` **after** the fixture that prepares the mission, or reset `calls.clear()` right before the invocation.
  3. Keep the counting wrapper local to this test module. WP16 T089 re-implements its own copy (about 10 lines) rather than importing from a test module.
- **Files**: `tests/status/test_transition_request_owned.py`.
- **Parallel?**: no. It is the first commit.
- **Validation checklist**:
  - [ ] The red run on the base is recorded with the observed count(s).
  - [ ] It is green after T033/T034 with no edits to the test.
  - [ ] The `count == 0` control is present and green on base and after.
  - [ ] No test-module import. Fixtures come only from `tests/integration/conftest.py`.
- **Edge cases**:
  - `move-task` may run the pre-review gate on `for_review` hops. Keep to the `claimed` hop, or set `SPEC_KITTY_SKIP_PRE_REVIEW_GATE=1` explicitly if you add later hops.
  - The counter must be installed **after** fixture setup (the fixture itself may validate) and **before** the invocation.
  - Different checkouts per test: the workspace caches are module-level (FR-019). Clear them per test.

## Test Strategy

**Red-first map**:

| Requirement | Red-first test | Entry point | Non-vacuity |
|---|---|---|---|
| FR-003 / NFR-002 | T037 `finalize-tasks` count == 1 | real CLI via `CliRunner` | base count ≥ 2 recorded; the same-fixture non-owned control counts 0, which proves the counter fires |
| FR-003 (pipeline) | T033 (a)/(c) and T034 tripwire tests | `_identity_for_request`, `read_events_transactional`, `bootstrap_canonical_state` | a tripwire raises if validation runs; the legacy-keyword control still validates (count 1) |
| FR-022 `[ratchet]` | existing owned tests unchanged | real CLI | must pass without edits |

**Commands** (record commands and counts in the Activity Log and the PR's *Tests run*):

```bash
.venv/bin/python -m pytest tests/status/test_transition_request_owned.py tests/specify_cli/coordination/test_status_transition.py -q
.venv/bin/python -m pytest tests/status/ tests/specify_cli/coordination/ tests/coordination/ -q     # owning subsystem dirs
.venv/bin/python -m pytest tests/integration/test_explicit_checkout_commands.py tests/integration/test_owned_checkout_mark_status.py tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py tests/specify_cli/cli/commands/agent/test_tasks_cli_contract.py tests/specify_cli/cli/commands/agent/test_tasks_cli_contract_coord.py -q   # FR-022 consumers
.venv/bin/python -m pytest tests/architectural/test_layer_rules.py tests/architectural/test_status_module_boundary.py tests/architectural/test_status_unsafe_allowlist.py tests/architectural/test_no_dead_symbols.py -q   # implicated gates only
make test-fast
.venv/bin/ruff check <every touched src and test file>
.venv/bin/ruff format --check <every touched src and test file>
.venv/bin/mypy --strict src/specify_cli/status/models.py src/specify_cli/status/transition_pipeline.py src/specify_cli/status/emit.py src/specify_cli/status/bootstrap.py src/specify_cli/coordination/status_transition.py src/specify_cli/coordination/transaction.py src/specify_cli/coordination/commit_router.py src/specify_cli/coordination/write_seam.py src/specify_cli/agent_tasks_ports.py src/specify_cli/core/owned_mission.py src/specify_cli/git/commit_helpers.py src/specify_cli/missions/_read_path_resolver.py src/specify_cli/coordination/surface_resolver.py src/specify_cli/coordination/status_service.py
```

mypy discipline (plan: Staging Strategy): never drop `--strict`; list callers **and callees** in the same invocation (`follow_imports = "skip"` for `specify_cli.*`). If `--strict` reports pre-existing errors in these files, run the identical command on the planning base, record that count, and show it did not grow; never narrow the file list to hide them.

Do not run `make test-full` or the bare `tests/architectural/` directory. Classify unrelated reds per the `CLAUDE.md` baseline-red gotcha.

## Risks & Mitigations

- **Hidden legacy callers.** Before merging, run `grep -rn "effective_root=" src --include=*.py | grep -v "TRANSITIONAL\|bridging"` and list every remaining site in the Activity Log with its owning WP. Each must be a documented legacy caller from the Context table, a bridging expression, or outside this WP's files.
- **Mock call-shape drift (C-001).** Several tests assert exact `commit_for_mission` kwargs. Pass `owned=` only when set (T036).
- **Silent behaviour change in the legacy branch.** The legacy `effective_root` branch must remain byte-identical until WP18. Do not "simplify" it.
- **Import cycles.** `status/models.py` and `status/bootstrap.py` import `OwnedCheckout` only under `TYPE_CHECKING`, and `status_transition.py` already defers heavy imports. Run `python -c "import specify_cli.status"` in a fresh interpreter to check.

## Review Guidance

- With a fact present, nothing in the pipeline validates. Check the tripwire tests and grep for `resolve_owned_mission`.
- Every legacy parameter carries `# TRANSITIONAL(WP18)`, and the Activity Log lists them for WP18 T096. Check the list against the Context table.
- The `transaction.py` edit is the declared out-of-map completion of WP06 T030, and nothing else in that file changed.
- The campsite extraction commit precedes the `commit_router` conversion, and its helpers have focused tests.
- T037's base count is recorded, and the non-owned counter control exists.
- The implementer ran mypy on every touched source file, and it passed.
- Do not reject the transitional dual keywords before WP18.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Initial entry**:

- 2026-09-28T15:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
- 2026-09-29T01:12:56Z – claude – shell_pid=19362 – Status pipeline now carries the collapsed owned fact (owned_fact()) end to end. Summary:
- T032: TransitionRequest.owned + owned_fact()/has_owned_root_only() (models.py, 3 TRANSITIONAL(WP18) markers).
- T033: _identity_for_request builds from the fact with zero re-validation; _TransactionIdentity.primary_root deleted (identity.owned carries it); BookkeepingTransaction.acquire/commit/append_events converted to owned= (out-of-map completion of WP06 T030, declared).
- T034: transition_pipeline/emit/bootstrap thread owned=; bootstrap_canonical_state's read no longer re-validates -- this was the observed finalize-tasks double-validation gap.
- T035: campsite split of _commit_partition_group (complexity 15->11) then commit_for_mission/write_seam gained owned=.
- T036: MissionHandle.owned + _placement_for/_owned_kwargs helpers in agent_tasks_ports.py (C-001 byte-parity preserved).
- T037: CLI-level NFR-002 proof -- finalize-tasks --owned-checkout now performs exactly ONE ownership validation (was >=2 on base); move-task recorded as [ratchet] (its own re-validation sites are WP16-owned, out of this WP's files).
Fixed a self-introduced dead field: _TransactionIdentity.primary_root was converted-away-from but not deleted; deleted in a follow-up commit.
Tests: tests/status/ tests/specify_cli/coordination/ tests/coordination/ = 1951 passed, 18 skipped. FR-022 consumers (test_owned_checkout_move_task.py, test_owned_checkout_mark_status.py, test_tasks_cli_contract*.py, test_explicit_checkout_commands.py) all green unchanged. mypy --strict on the 14 listed files: 11 pre-existing errors, 0 new (verified against the lane base). Complexity gate clean on touched functions.
Known open item: tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported goes red on this branch (OwnedMission, NEXT_OWNED_TOPOLOGIES, adopt_owned_checkout, resolve_owned_create_root, OwnedCheckoutPathRefused lose their last/only src/ import-site reference once status_transition.py's TYPE_CHECKING OwnedMission import is replaced with OwnedCheckout, per this WP's own explicit T032 instruction). CLAUDE.md lists this exact test as "judged at WP18" (pre-existing-known-red category); flagging for the reviewer/WP18 rather than silently reintroducing the OwnedMission import to paper over it.
- 2026-09-29T02:54:16Z – unknown – Review cycle 1 fix cycle 1 complete — all 10 findings (3 HIGH, 4 MEDIUM, 2 LOW, 1 INFO) resolved.

Commits (7, oldest first):
- 53506696e fix(WP07): resolve new mypy error at mission_finalize.py:2753 (HIGH-3)
- b0976a21f fix(WP07): pin the move-task ownership-validation count at exactly 5 (HIGH-1)
- d73ef330c test(WP07): add T036 tests, retroactively (review cycle 1 HIGH-2)
- a413c850d test(WP07): red-first MEDIUM-4 regression guards for emit_inner_state_changed_transactional
- cbd61967c fix(WP07): key emit_inner_state_changed_transactional's three owned checks on identity.owned (MEDIUM-4)
- 8ca2e0c25 test(WP07): red-first MEDIUM-6 regression guards for legacy per-request threading
- ae11472fd fix(WP07): MEDIUM-5 markers, MEDIUM-6 legacy threading, LOW-8/LOW-9 (review cycle 1)

Findings resolved:
- HIGH-1: move-task ownership-validation count pinned at == 5 exactly (test_move_task_validates_ownership_exactly_once), comment names WP16, no >= ratchet.
- HIGH-2: T036 red-first tests added retroactively for RealFsReader.planning_read_dir, RealCoordCommitRouter.feature_write_dir, commit_artifact, MissionHandle.__post_init__ mismatch guard, _owned_kwargs helper, and the legacy control path (9 new tests). Verified red against the pre-T036 source in a scratch worktree (git worktree add --detach, sha 09f94b0eb^); non-vacuity confirmed for the __post_init__ guard test via an explicit `match=` on the TypeError message (a bare pytest.raises initially passed for the wrong reason — unexpected-kwarg TypeError, not the mismatch guard — caught and fixed).
- HIGH-3: mission_finalize.py:2753 now calls `effective_root_kwargs(owned.root if owned else None)` (TypedDict-typed) instead of a bare dict literal. Re-ran mypy --strict over the FULL 31-file caller set of both `effective_root_kwargs` and `commit_for_mission` (grep -rl across src), not just the WP file list: base 55610f516 = 6 errors in 4 files, head = 6 errors in 4 files, identical set (acceptance/gates_core.py:345,479; acceptance/__init__.py:1130; cli/commands/agent/mission_finalize.py:180; cli/commands/accept.py:147,208) — 0 new. (An incremental-cache run transiently showed a 7th error at tasks/issue_matrix_migration.py:254 on head only; the file is byte-identical to base, and a --no-incremental rerun with matching PYTHONPATH on both sides reproduced exactly 6/6 — confirmed cache artifact, not a real regression.)
- MEDIUM-4: emit_inner_state_changed_transactional's three owned checks (OWNED_TRANSACTION_UNAVAILABLE refusal, _uncommitted_emit short-circuit, BookkeepingWorktreeMissing re-raise) now key on `identity.owned` (computed after _identity_for_request) instead of the bare pre-identity fact/effective_root. Added test_inner_state_owned_only_refuses_without_transaction_metadata, test_inner_state_legacy_only_refuses_without_transaction_metadata (control), test_inner_state_owned_only_reraises_worktree_missing_never_degrades (the fail-open regression guard), test_inner_state_legacy_only_reraises_worktree_missing_unchanged (control) — all red-first against scratch worktree at cbd61967c^ before the fix commit.
- MEDIUM-5: TRANSITIONAL(WP18) markers placed on every kept dual/legacy parameter across the WP07-touched files (exact count below); `primary_root` deleted from `_acquire_locked`'s signature and call site in coordination/transaction.py — confirmed 0 hits for "primary_root" in that file.
- MEDIUM-6: restored the legacy per-request effective_root threading that T034's fact-only rewrite had silently dropped for batch members without a mutated fact. _default_resolve_subtasks_dir and _infer_review_gates now thread `effective_root=request.effective_root if fact is None else None` per request (not just requests[0]). Restored test_effective_root_is_threaded_to_the_resolver (legacy-only threading, alongside the new fact-threading test) and added test_batch_of_legacy_only_requests_each_thread_their_own_effective_root (transition_pipeline unit level) plus test_batch_door_threads_the_second_requests_own_effective_root (coordination/status_transition.py, drives _prepare_batch_in_transaction directly with 2 chained requests, spies on _default_resolve_subtasks_dir to prove requests[1]'s own effective_root reaches the resolver — the first version of this test was vacuous, recording effective_root at the prepare_transition boundary rather than one layer deeper inside _infer_review_gates; rewritten to spy on the actual resolver call). _flat_subtasks_dir_resolver (status/emit.py) updated to accept-and-drop the new effective_root kwarg (D-1 parity) after 16 tests broke on the shape change.
- MEDIUM-7 (red-first history): no history rewritten. Every NEW test this cycle has its own red-first commit before its fix commit (d73ef330c before nothing new needed since HIGH-3/HIGH-1 fixes predated it; a413c850d before cbd61967c; 8ca2e0c25 before ae11472fd). Red proofs recorded via scratch worktrees (git worktree add --detach, never git stash): T036 tests red against 09f94b0eb^, MEDIUM-4 tests red against cbd61967c^, MEDIUM-6 tests red against ae11472fd^ (confirmed via the transition_pipeline unit tests failing None-vs-Path and the coordination batch-door test failing to observe requests[1]'s own root).
- LOW-8: bridging markers ("# bridging: WP17 converts") moved onto the call line itself in all three sites: coordination/transaction.py:845 (safe_commit's effective_root= kwarg), coordination/commit_router.py:492 (**effective_root_kwargs(owned_root)), status/transition_pipeline.py:111 (the resolver's effective_root= kwarg).
- LOW-9: added the owned/owned_mission mismatch check to status/bootstrap.py's `owned or owned_mission` collapse (mirrors TransitionRequest.owned_fact()'s is-then-== semantics, raises TypeError on disagreement) and to write_seam.py's write_artifact, which no longer forwards effective_root and owned unchecked — a mismatch between effective_root and owned.owned_root now raises TypeError before owned_root is computed.
- INFO-10: correcting this Activity Log — the earlier (cycle-1) entry mischaracterizing test_no_dead_symbols as WP07-caused was wrong; it is identically red against the unmodified base and is not attributable to this WP.

Exact final TRANSITIONAL(WP18) marker list, WP07-touched files only (file: count):
- src/specify_cli/coordination/status_transition.py: 4 (lines 926, 1390, 1638, 1693)
- src/specify_cli/coordination/transaction.py: 0 (primary_root deleted entirely; bridging marker only, not TRANSITIONAL)
- src/specify_cli/coordination/commit_router.py: 3 (lines 199, 292, 439)
- src/specify_cli/coordination/write_seam.py: 2 (lines 245, 478)
- src/specify_cli/status/bootstrap.py: 2 (lines 99, 100)
- src/specify_cli/status/transition_pipeline.py: 1 (line 91)
- src/specify_cli/status/models.py: 3 (lines 881, 890, 916 — TransitionRequest.effective_root, .owned_mission, has_owned_root_only() docstring)
- src/specify_cli/status/emit.py: 0
- src/specify_cli/agent_tasks_ports.py: 2 (lines 79, 269 — pre-existing from T036, unchanged this cycle)
Total in WP07-owned files: 17 TRANSITIONAL(WP18) markers, plus 3 "# bridging: WP17 converts" markers (transaction.py:845, commit_router.py:492, transition_pipeline.py:111) — for the coordinator to amend the WP07 DoD and WP18 T096 budget against.
(Note: mission_runtime/resolution.py, mission_runtime/owned_checkout.py, and core/owned_mission.py also carry TRANSITIONAL(WP18) markers from earlier WPs — not WP07-owned, listed separately if needed.)

Test results: tests/status/ tests/specify_cli/coordination/ tests/coordination/ — 1967 passed, 18 skipped, 0 failed.
ruff check: clean (0 issues) on every file touched this cycle.
ruff format --check: clean on every file touched this cycle; commit_router.py/transaction.py/agent_tasks_ports.py show pre-existing format drift confirmed identical on base 55610f516 (unrelated to this cycle, not introduced or worsened).
mypy --strict (full 31-file caller set of effective_root_kwargs + commit_for_mission): base 6 errors/4 files, head 6 errors/4 files — 0 new.
- 2026-09-29T03:41:59Z – unknown – Review cycle 2 fix cycle 2 complete — all 3 remaining findings (1 HIGH, 1 MEDIUM, 7 LOW/folded) resolved.

Commits (4, oldest first):
- 5a214d03c fix(WP07): drop the mission_runtime import from emit.py (review cycle 2 HIGH-1)
- 5b69f9ba9 test(WP07): red-first tests for the canonical checkout-agreement predicate (review cycle 2 MEDIUM)
- bcf6b314b fix(WP07): one canonical checkout-agreement predicate and dual-fact collapse (review cycle 2 MEDIUM)
- 5ede8d06b fix(WP07): pin checkout_root_agrees_with_effective_root on the mission_runtime surface

Findings resolved:
- HIGH-1: reviewer's full 54-file mypy --strict --explicit-package-bases caller-set invocation found 2 new no-redef errors at status/emit.py:81-82, caused by the `if TYPE_CHECKING: from mission_runtime import OwnedCheckout` import 01e925785 added. Removed that import entirely; `_flat_subtasks_dir_resolver`'s dropped-by-design `owned` param is now typed `object | None` (never read, so it does not need the concrete type). Re-verified with a 53-file superset of the reviewer's caller set (grep -rlE over effective_root_kwargs|commit_for_mission|write_artifact\(|bootstrap_canonical_state|read_events_transactional|emit_inner_state_changed_transactional|MissionHandle\(|TransitionRequest\(|BookkeepingTransaction\.acquire, plus every caller of the subtasks-gate resolvers), run with --no-incremental and matched PYTHONPATH on both sides: base 55610f516 = 22 errors in 12 files, head = 22 errors in 12 files, byte-identical set. 0 new errors.
- MEDIUM: created ONE canonical checkout-agreement predicate, `mission_runtime.owned_checkout.checkout_root_agrees_with_effective_root` (exported from the mission_runtime package root, the layer every specify_cli site may import it from), and ONE canonical dual-fact collapse, `specify_cli.status.models.collapse_owned_facts` (TransitionRequest.owned_fact() now delegates to it). The predicate deliberately compares after `.resolve()` on both sides -- pinned with a non-canonical-path test (an effective_root carrying a `..` segment that names the identical checkout as a canonical owned_root) proving the OLD raw `!=` comparison spuriously refused it. All four sites now call the shared predicate/collapse while KEEPING their own existing error type/code/message (per the ruling not to silently change what a caller may depend on): _identity_for_request (ActionContextError/OWNED_MISSION_PATH_REFUSED), bootstrap_canonical_state (its own two TypeErrors), write_artifact (its own TypeError). MissionHandle.__post_init__ already used `.resolve()` -- the correct reference behaviour this generalises from -- and was left untouched, matching the reviewer's four named sites plus the collapse.
  Red-first: committed 5b69f9ba9 (tests only) before bcf6b314b (the fix). Verified red in a scratch worktree at 5a214d03c (the parent commit, before this predicate existed; git worktree add --detach, no git stash): ImportError for the not-yet-existing predicate in tests/mission_runtime/test_owned_checkout.py, plus 3 explicit TypeError/ActionContextError failures in tests/status/test_bootstrap.py, tests/specify_cli/coordination/test_write_seam_owned_agreement.py (new file), and tests/specify_cli/coordination/test_status_transition.py -- each failing for exactly the spurious-refusal reason the fix closes. 62 passed / 3 failed / 1 collection error in that scratch run.
  New/restored tests: 5 predicate unit tests (tests/mission_runtime/test_owned_checkout.py), 4 bootstrap tests including the two previously-untested raises and their controls (tests/status/test_bootstrap.py), 2 write_seam tests (new file tests/specify_cli/coordination/test_write_seam_owned_agreement.py), 1 status_transition test (tests/specify_cli/coordination/test_status_transition.py).
  Follow-up architectural fix: adding the predicate to mission_runtime's package-root surface required pinning it in tests/architectural/test_mission_runtime_surface.py's hand-maintained _PUBLIC_SURFACE list (commit 5ede8d06b) -- that gate went red the moment the new symbol landed; not a red-first case (it is a required completion of the same change, not new behaviour), so it is its own small commit rather than folded into bcf6b314b.
- LOW-3: fixed the stale "resolves and writes back onto request.owned" comment in status_transition.py -- ae11472fd (cycle 1 MEDIUM-6) removed that mutation; the comment now correctly describes the local-variable resolution.
- LOW-4: moved the TRANSITIONAL(WP18) marker on emit_inner_state_changed_transactional's owned_mission from the internal call argument (line ~1693 in cycle 1) onto the SIGNATURE parameter (now line 1642) -- the count for this symbol stays 1 (still 4 total in status_transition.py), now on the line the WP18 grep should actually find.
- LOW-5 (from HIGH-1's commit): _flat_subtasks_dir_resolver's legacy `effective_root` parameter is now also marked TRANSITIONAL(WP18) (it is the same dropped-by-design shape WP18 deletes); the bare `# noqa: ARG001` stays since the parameter is genuinely unused.
- LOW-6: correcting the record -- the ae11472fd commit body (cycle 1) claimed test_emit.py was updated "in the same commit"; it was not (that commit touched no test file; the 16 collateral test_emit.py-family failures it fixed were pre-existing failures from an EARLIER cycle-1 commit's shape change, not new tests added by ae11472fd itself). No history rewrite; flagging the correction here per the review-cycle-2 ruling.
- LOW-7: mission_finalize.py:2759 now calls `effective_root_kwargs(owned)` directly instead of `effective_root_kwargs(owned.root if owned else None)` -- the helper accepts the fact directly and unwraps `owned_root` itself, so the legacy `.root` property read was unnecessary (out-of-map, per the original HIGH-3 fix's own note).

Exact final TRANSITIONAL(WP18) marker list, WP07-touched files only (file: count; net change from cycle 1's 17 -> 18, +1 for emit.py):
- src/specify_cli/coordination/status_transition.py: 4 (lines 929, 1393, 1641, 1642 -- the owned_mission marker moved from the call argument onto the signature parameter at 1642, count unchanged)
- src/specify_cli/coordination/transaction.py: 0 (unchanged -- primary_root deleted entirely in cycle 1)
- src/specify_cli/coordination/commit_router.py: 3 (lines 199, 292, 439 -- unchanged)
- src/specify_cli/coordination/write_seam.py: 2 (lines 246, 479 -- unchanged)
- src/specify_cli/status/bootstrap.py: 2 (lines 100, 101 -- unchanged)
- src/specify_cli/status/transition_pipeline.py: 1 (line 91 -- unchanged)
- src/specify_cli/status/models.py: 3 (lines 912, 921, 947 -- unchanged)
- src/specify_cli/status/emit.py: 1 (line 699 -- NEW this cycle: the effective_root param on _flat_subtasks_dir_resolver, per LOW-5)
- src/specify_cli/agent_tasks_ports.py: 2 (lines 79, 269 -- unchanged)
Total in WP07-owned files: 18 TRANSITIONAL(WP18) markers (was 17), plus the same 3 "# bridging: WP17 converts" markers (transaction.py:845, commit_router.py:492, transition_pipeline.py:111) -- for amending the WP07 DoD / WP18 T096 budget to 18.

Also new this cycle: mission_runtime.owned_checkout.checkout_root_agrees_with_effective_root (exported from the package root, pinned in tests/architectural/test_mission_runtime_surface.py's _PUBLIC_SURFACE), and specify_cli.status.models.collapse_owned_facts (module-level, no __all__ in models.py to update) -- both canonical, neither TRANSITIONAL(WP18) (they are the target state WP18 consolidates onto, not legacy shapes it deletes).

Test results: tests/status/ tests/specify_cli/coordination/ tests/coordination/ tests/mission_runtime/ tests/architectural/test_mission_runtime_surface.py -- 2673 passed, 19 skipped, 0 failed.
ruff check: clean (0 issues) on every file touched this cycle.
ruff format --check: clean on every file touched this cycle.
mypy --strict --explicit-package-bases (53-file superset of the reviewer's 54-file caller set, --no-incremental, matched PYTHONPATH both sides): base 55610f516 = 22 errors/12 files, head = 22 errors/12 files -- 0 new.
- 2026-09-29T04:02:31Z – unknown – Review cycle 3 fix cycle 3 complete -- the one blocking MEDIUM plus the folded LOW resolved.

Commits (3, oldest first):
- c627714b1 test(WP07): red-first pin for MissionHandle's delegation to the canonical predicate (review cycle 3 MEDIUM)
- bf43fb96e fix(WP07): MissionHandle.__post_init__ delegates to the canonical predicate (review cycle 3 MEDIUM)
- bf061e9e6 fix(WP07): checkout_root_agrees_with_effective_root uses resolve_rejecting_loops (review cycle 3 LOW)

Findings resolved:
- MEDIUM (blocking): agent_tasks_ports.py:88's MissionHandle.__post_init__ previously reimplemented the checkout-agreement check inline (self.effective_root.resolve() != self.owned.owned_root) instead of calling mission_runtime.checkout_root_agrees_with_effective_root -- which made the predicate's own docstring, the mission_runtime __all__ comment, the surface-test comment, and the comments in status_transition.py/write_seam.py (all of which claimed MissionHandle already calls it) false. __post_init__ now calls the canonical predicate and keeps its own existing TypeError message (which the T036 tests already match, so no test message changed).
  Red-first: since behaviour is equivalent today (owned_root is always minted resolved, so the inline check and the predicate never disagreed on any real input), a behavioural red test is impossible. Per the reviewer's instruction, pinned the DELEGATION itself instead: test_mission_handle_post_init_delegates_to_the_canonical_predicate monkeypatches agent_tasks_ports.checkout_root_agrees_with_effective_root to always return False and asserts that constructing a MissionHandle with AGREEING roots still raises TypeError -- which only happens if __post_init__ actually calls the imported module-level name.
  Verified red in a scratch worktree at c627714b1 (git worktree add --detach; no git stash) before the fix commit: AttributeError, "module 'specify_cli.agent_tasks_ports' has no attribute 'checkout_root_agrees_with_effective_root'" -- exactly because the name was not yet imported. Green after bf43fb96e's fix.
- LOW (folded): checkout_root_agrees_with_effective_root now resolves BOTH sides with kernel.resolution.resolve_rejecting_loops (the SAME resolver OwnedCheckout._mint uses) instead of plain Path.resolve(). Plain resolve() on a symlink loop raises an uncaught RuntimeError on 3.11/3.12 or silently returns the unresolved path on 3.13+; resolve_rejecting_loops raises a normalized OSError(errno.ELOOP) on every supported interpreter, matching the module's existing fail-closed posture (OwnedCheckout.files()'s own symlink-loop refusal). owned_root is already resolved at mint time, so re-resolving it is idempotent -- only effective_root's resolution semantics change in practice. Added test_a_symlink_loop_in_effective_root_fails_closed; every existing agreement test (none-either-side, identical canonical paths, genuinely different checkout, non-canonical-but-equivalent path, symlink alias) stays green.

Test results: tests/mission_runtime/test_owned_checkout.py tests/specify_cli/cli/commands/agent/test_tasks_ports.py tests/specify_cli/coordination/test_write_seam_owned_agreement.py tests/status/test_bootstrap.py tests/specify_cli/coordination/test_status_transition.py tests/architectural/test_mission_runtime_surface.py tests/status/test_transition_request_owned.py -- 149 passed, 1 skipped (platform cannot create symlinks), 0 failed.
ruff check: clean on every file touched this cycle.
ruff format --check: clean on every file touched this cycle (agent_tasks_ports.py's pre-existing, unrelated format drift confirmed identical to base 55610f516, per prior cycles' record).
mypy --strict --explicit-package-bases (55-file superset of the reviewer's 56-file caller set -- adds mission_runtime/owned_checkout.py and mission_runtime/__init__.py to the prior cycle's 53-file set -- --no-incremental, matched PYTHONPATH both sides): base 55610f516 = 22 errors/12 files, head = 22 errors/12 files, byte-identical set. 0 new.
Marker count: unchanged at 18 TRANSITIONAL(WP18) (per file: status_transition.py 4, transaction.py 0, commit_router.py 3, write_seam.py 2, bootstrap.py 2, transition_pipeline.py 1, models.py 3, emit.py 1, agent_tasks_ports.py 2), plus the same 3 "# bridging: WP17 converts" markers. No new TRANSITIONAL(WP18) markers were added or removed this cycle -- the two new symbols this cycle's fix touches (checkout_root_agrees_with_effective_root's call site in MissionHandle, and the resolve_rejecting_loops swap inside the predicate itself) are both canonical target-state code, not legacy shapes WP18 deletes.
