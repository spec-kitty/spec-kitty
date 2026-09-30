---
work_package_id: WP06
title: Status surface authority
dependencies:
- WP02
requirement_refs:
- FR-013
- FR-014
- C-002
planning_base_branch: claude/sleepy-hamilton-5lelee
merge_target_branch: claude/sleepy-hamilton-5lelee
branch_strategy: Planning artifacts for this mission were generated on claude/sleepy-hamilton-5lelee. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/sleepy-hamilton-5lelee unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-owned-checkout-lifecycle-authority-01M3M2ZB
base_commit: 5e2286ec38615a1ad86197e1beb418613df54fef
created_at: '2026-09-28T20:22:45.010856+00:00'
subtasks:
- T027
- T028
- T029
- T030
- T031
phase: Phase 2 - Seams
history:
- at: '2026-09-28T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/coordination/
create_intent:
- tests/specify_cli/coordination/test_owned_status_read_contract.py
- tests/specify_cli/coordination/test_status_surface_owned.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/coordination/status_service.py
- src/specify_cli/coordination/surface_resolver.py
- src/specify_cli/coordination/transaction.py
- tests/specify_cli/coordination/test_owned_status_read_contract.py
- tests/specify_cli/coordination/test_status_surface_owned.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Status surface authority

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then load the action-scoped governance: `spec-kitty charter context --action implement --json`. Read `.kittify/charter/charter.md` if this session has not read it yet.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

An owned `single_branch` checkout P that physically lives under `R/.worktrees/<name>` can read and write its status log. The decision is taken by the canonical coordination surface resolver from the **validated ownership fact**, not from path shape. The coordination protections stay byte-identical for every non-owned caller.

Done means all of the following hold:

1. **#5009 prior art carried.** Commit `4ff6ff0c0` (author Samuel Goff) lands via `git cherry-pick -x`. Its parallel-source test `test_owned_contract_validates_root_and_mission` is dropped (C-002). `test_finalize_and_read_owned_mission_below_worktrees` is red on the planning base and green at the end of this WP (FR-013, US4-AS1).
2. **One classification predicate.** `surface_resolver.primary_read_targets_coord_worktree(path, *, owned)` is the only place the status contract layer asks whether a path targets a coordination worktree. All **six** shape-guard sites in `status_service.py` route through it.
3. **Contracts carry the fact.** `EventLogReadContract` and `EventLogWriteContract` each gain `owned: OwnedCheckout | None = None`. There is **no** new `StatusReadSource` / `EventLogWriteTarget` member (C-002: no parallel status source or label).
4. **Transaction idiom removed; owned read contract at the transaction target.**
   - `transaction.py:644` uses `is_under_worktrees_segment`.
   - The transaction read target for an owned identity is a `primary_checkout` contract carrying the fact.
   - Converting `BookkeepingTransaction.acquire(effective_root=)` to `owned=` is deliberately **left to WP07 T033**; the reason is under T030.
5. **FR-014 ratchet.** A repository-root-labelled read or append of the **same** `.worktrees/<name>` path shape, when that path is a **registered coordination worktree**, is still refused with the existing `StatusContractError` message.
6. **NFR-002.** The owned arm adds **zero** git subprocess calls: the fact already proves registration and branch.

**Mission-wide DoD (post-tasks squad):**
- `grep -rn "bridging: WP06 converts" src` is empty: every bridging call site marked for this WP is converted, including sites in other WPs' files (declared out-of-map edits).
- Every bridging call site this WP adds carries `# bridging: WP<n> converts`, naming the WP that converts it (never a free-form comment, never no marker).
- `TRANSITIONAL(WP18)` markers added by this WP (exact list; any deviation is amended here in the same PR, and WP18 T096 fails on unlisted markers): **0** markers (this WP adds none).
- Red-first proofs are **commits**: the red test commit precedes its fix commit, and the reviewer verifies the order in `git log`.
- Error codes are imported from `OwnedRefusalCode` (WP01); no `OWNED_*` string literal is repeated in `src/` or new tests (Sonar S1192).

## Context & Constraints

- Charter: `.kittify/charter/charter.md` (single canonical authority, ATDD-first C-011, campsite cleaning, gate discipline).
- Mission docs, all under `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/`:
  - `spec.md`: US4, FR-013, FR-014, C-002, NFR-002;
  - `plan.md`: IC-04, IC-13, Staging Strategy, Test Layout;
  - `research.md`: R-10, R-15, R-16 ("Status shape guard");
  - `data-model.md` and `contracts/owned-checkout-carrier.md` §7 (`EventLogReadContract` is a named consumer);
  - `occurrence_map.yaml`.
- **Prerequisites.**
  - WP01 provides `mission_runtime.OwnedCheckout`. Its canonical fields are `repository_root`, `owned_root`, `mission_dir`, `mission_slug`, `topology` and `target_branch`.
  - WP02 makes `resolve_owned_mission` return that fact. It also adds the shared fixtures `owned_checkouts`, `r_snapshot` and `stale_root_copy` to `tests/integration/conftest.py`. Read their docstrings before writing tests.
- **Staging rules (binding, plan: Staging Strategy).**
  - Conversion is top-down: change a signature to `owned: OwnedCheckout | None` only once its callers hold the fact.
  - Transitional surfaces are the six shared seams plus every other function marked TRANSITIONAL(WP18). The six shared seams keep a transitional dual keyword until WP18: `placement_seam`, `mission_context_for`, `resolve_action_context`, `resolve_workspace_for_wp`, `locate_work_package` and `TransitionRequest`. Do not remove the legacy keyword on any of them here.
  - The transitional `OwnedMission` legacy factory function (marked `TRANSITIONAL(WP18)`) and the legacy attribute names (`.root`, `.primary`, `.directory`, `.slug`, `.target`) live until WP18. **New code in this WP uses only the canonical field names.** WP18 deletes the legacy properties, and any new use of them would break there.
- **Occurrence map.**
  - `code_symbols` and `tests_fixtures`: rename.
  - `serialized_keys` and `logs_telemetry`: do not change. This covers `StatusReadSource` / `EventLogWriteTarget` values, `StatusContractError` message strings, and existing `OWNED_*` codes.
  - `filesystem_paths`: do not change.
- **Terminology.** New docstrings and comments use "repository root checkout", "owned checkout" and "coordination worktree". Existing `primary_checkout` enum values and method names are serialized or public names; they stay (do_not_change). Never introduce bare "primary" in new prose, and never "feature".
- **Complexity.** No function this WP touches is at ≥12 today. Checked on HEAD `df1588860` with `.venv/bin/ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=11' <file>`: `status_service.py`, `transaction.py` and `status_transition.py` are clean, and `surface_resolver.py` flags only `resolve_status_surface_with_anchor` (12), which you do not touch. Re-run the probe before and after. If a function you touch would reach ≥12, extract a behaviour-preserving helper in a separate commit first (campsite rule).
- **Out-of-map edit (declared).** The read-contract construction site and the transaction identity live in `src/specify_cli/coordination/status_transition.py`, which WP07 owns. WP07 depends on this WP, so there is no concurrent editing. T030 makes three small, named hunks there; the list is under T030. Record each hunk in the commit body as `Out-of-map (WP07-owned status_transition.py): <hunk> — <one-line rationale>`. Do not touch any other part of that file.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `claude/sleepy-hamilton-5lelee`; completed changes must merge back into `claude/sleepy-hamilton-5lelee`.
- **Planning base branch**: `claude/sleepy-hamilton-5lelee`
- **Merge target branch**: `claude/sleepy-hamilton-5lelee`
- **Execution lane**: allocated by `spec-kitty agent mission finalize-tasks` in `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/lanes.json`, which had not been generated when this prompt was written. Run `spec-kitty implement WP06` and work in the workspace it resolves. Never construct the worktree path by hand.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

**Commit order inside this WP** (red first, then the fix):

1. `git cherry-pick -x 4ff6ff0c0` (T027 carry, red).
2. The T027 adaptation commit (still red for the finalize test).
3. T028 tests (red), then the T028 implementation.
4. T029 tests (red), then the T029 routing.
5. T030 (turns the carried finalize test green).
6. T031 same-path tests. These are ratchets and green on arrival, **except** the owned-accept rows, which are red before T029/T030. Commit those rows with the T028 tests.

## Subtasks & Detailed Guidance

### Subtask T027 – Carry #5009 `4ff6ff0c0`; drop the parallel-source test; add a registered-coordination control

- **Purpose**: land @samuelgoff's genuine red reproduction of O6 with provenance intact (C-006, IC-13), remove the part that encodes a parallel status source (C-002), and add the same-path coordination control FR-014 needs.
- **Steps**:
  1. Inspect first: `git show 4ff6ff0c0 --stat` (one new file, 73 lines) and `git show 4ff6ff0c0`. The file contains three tests:
     - `test_finalize_and_read_owned_mission_below_worktrees`: moves P to `R/.worktrees/owned`, runs `finalize-tasks --owned-checkout`, then reads events via `read_events_transactional(..., effective_root=inside)`.
     - `test_owned_contract_validates_root_and_mission`: uses `EventLogReadContract.owned_checkout(...)`, which does not exist and must never exist (C-002).
     - `test_primary_contract_still_rejects_coordination_shaped_path`.
  2. `git cherry-pick -x 4ff6ff0c0`. Keep the author. Do not amend the commit.
  3. Run it on the carried commit: `.venv/bin/python -m pytest tests/specify_cli/coordination/test_owned_status_read_contract.py -q`. Expected, and to be recorded in the Activity Log:
     - `test_finalize_and_read_owned_mission_below_worktrees`: red. The finalize exit is non-zero with a "coordination worktree" refusal (O6).
     - `test_owned_contract_validates_root_and_mission`: red, `AttributeError`.
     - `test_primary_contract_still_rejects_coordination_shaped_path` (both params): green.
  4. Adaptation commit (trailer `Co-authored-by: Samuel Goff <samuel@defpix.com>`):
     - Delete `test_owned_contract_validates_root_and_mission` entirely, with a module comment: "parallel `owned_checkout` status source dropped per C-002; the owned read is a `primary_checkout` contract carrying the validated fact."
     - Re-point the fixture. The file imports `checkouts`, `git`, `invoke` and `snapshot` from the **test module** `tests.integration.test_explicit_checkout_commands`, and the plan forbids importing shared fixtures from test modules. Replace this with the WP02 fixtures: `from tests.integration.conftest import owned_checkouts, r_snapshot` (re-exported through `__all__`, as the carried file already does for `checkouts`). A conftest in `tests/integration/` is not visible to `tests/specify_cli/coordination/`, so the explicit import is required. If ruff reports F811 on the fixture parameter, keep the `__all__` re-export pattern rather than adding `noqa`.
     - Replace the `invoke("finalize-tasks", inside)` helper with an explicit `CliRunner().invoke(mission_app, ["finalize-tasks", "--mission", <slug>, "--owned-checkout", str(inside), "--json"])`.
     - Replace the before/after tuple with `r_snapshot` (NFR-001: covers R's ignored files, HEAD, index and lock root, excluding exactly P's subtree).
     - Replace the `read_events_transactional(..., effective_root=inside)` read with `read_event_log(EventLogReadContract.primary_checkout(<P mission dir>, owned=<fact>))`. Obtain the fact from the minter `resolve_owned_mission(R, inside, <slug>)`, or by using `OwnedCheckout._mint(...)` in the test. This makes the test exercise this WP's surface rather than a legacy keyword WP18 will delete. The call raises `TypeError` until T029 adds `owned=`; that is acceptable only because the CLI half of the same test is the genuine red.
  5. Add `test_registered_coordination_worktree_same_path_still_refused` (FR-014, US4-AS2). In the same fixture, register a real coordination worktree at `R/.worktrees/<slug>-coord` using `git -C R worktree add -b <coord-branch> R/.worktrees/<slug>-coord`. The name must end in `-coord` (`surface_resolver._COORD_SUFFIX`, `surface_resolver.py:101`). Then assert:
     - `read_event_log(EventLogReadContract.primary_checkout(<coord mission dir>))` and `read_event_stream_log(...)` raise `StatusContractError`, matching `"primary_checkout reads must not target coordination worktree paths"`;
     - `append_event_log(EventLogWriteContract.primary_checkout_append(<coord dir>), ev)` raises, matching `"primary_checkout_append must not target coordination worktree paths"`.
- **Files**: `tests/specify_cli/coordination/test_owned_status_read_contract.py` (created by the cherry-pick).
- **Parallel?**: no. It is the first commit of the WP.
- **Validation checklist**:
  - [ ] `git log -2 --format='%an %s%n%b'` shows Samuel Goff as the author of the carried commit and a `(cherry picked from commit 4ff6ff0c0…)` line.
  - [ ] The adaptation commit carries the `Co-authored-by` trailer.
  - [ ] After the adaptation commit, the finalize test is still red for the O6 reason, not a fixture error. Record the failure line.
  - [ ] No import from any `tests/**/test_*.py` module remains.
  - [ ] Markers stay `integration` + `git_repo`.
- **Edge cases**:
  - The WP02 factory `make_owned_checkouts(placement="under_worktrees")` builds P at `R/.worktrees/owned-a` directly (WP02 T011). Prefer it over the carried `git worktree move`. If you keep the move, it needs a cwd outside the moved tree; the carried test already `chdir`s to R first.
  - R must ignore `.worktrees/`; the carried test writes `.git/info/exclude`. Keep it, so R's `status --porcelain` stays clean for the snapshot.
  - The same-path control must use a **registered** worktree. An unregistered `.worktrees/x-coord` husk is a different case (`WorktreeTopology.UNREGISTERED`) and is not what FR-014 pins.

### Subtask T028 – `surface_resolver.primary_read_targets_coord_worktree(path, *, owned)`

- **Purpose**: give the status contract layer one predicate, owned by the canonical coordination surface resolver (#4959, C-002). It answers "does this repository-root-labelled path target a coordination worktree?" and consults the validated fact before path shape (FR-013).
- **Steps**:
  1. Red first. In `tests/specify_cli/coordination/test_status_surface_owned.py` (markers `unit` + `fast` for the pure cases), write:
     - `owned is None` and a path under `.worktrees/` → `True` (today's shape answer; byte-identical to `is_under_worktrees_segment`).
     - `owned is None` and a path not under `.worktrees/` → `False`.
     - `owned` set and the path inside `owned.owned_root` → `False`, even though `owned.owned_root` is `R/.worktrees/owned-a`.
     - `owned` set and the path **outside** `owned.owned_root` but under `.worktrees/`, for example `R/.worktrees/<slug>-coord/kitty-specs/...` → `True`. The fact exempts only its own subtree.
     - `owned` set and a sibling-prefix path `R/.worktrees/owned-a-evil/...` → `True`. Containment is by path components, not string prefix.
     - A symlinked alias of P: resolve before comparing, and the result is `False`.
     - NFR-002: patch `subprocess.run` in `specify_cli.coordination.surface_resolver` to fail the test if called. No git is consulted in any case above.

     In tests, mint facts with `OwnedCheckout._mint(...)`, as WP01's `tests/mission_runtime/test_owned_checkout.py` does (contract §1 allows a `tests/` helper, and G3 scans `src/` only), or take them from the WP02 minter on a real fixture. Never call `OwnedCheckout(...)`, which raises `TypeError` by design.
  2. Implement in `src/specify_cli/coordination/surface_resolver.py`, next to `is_under_worktrees_segment` (`:482`):
     ```python
     def primary_read_targets_coord_worktree(path: Path, *, owned: OwnedCheckout | None) -> bool:
         """..."""
         if owned is not None and _is_within(path, owned.owned_root):
             return False
         return is_under_worktrees_segment(path)
     ```
     - Reuse the containment helper WP01 uses (`mission_runtime.checkout_identity._is_within`, per plan IC-01) only if it is part of the public `mission_runtime` surface. Otherwise write a local `Path.resolve(strict=False)` + `is_relative_to` check. Do **not** import a private `mission_runtime` submodule: gates MR-1/MR-2 in `tests/architectural/test_mission_runtime_surface.py` forbid it.
     - Import `OwnedCheckout` from `mission_runtime`, which the module already imports from (`surface_resolver.py:57`). There is no new layer edge.
     - The docstring states: the owned exemption is sound only because the fact was minted by the canonical validator, which proved registration, branch and topology; path shape is consulted only when no fact covers the path.
  3. Add the name to `__all__` (`surface_resolver.py:81-96`, alphabetical) per the charter's `__all__` convention (C-007).
- **Files**: `src/specify_cli/coordination/surface_resolver.py`, `tests/specify_cli/coordination/test_status_surface_owned.py`.
- **Parallel?**: no. T029 depends on it.
- **Validation checklist**:
  - [ ] The tests were committed red (`ImportError` on the new name), then green.
  - [ ] Same-fixture positive control: the `owned is None` row and the owned row use the **same** path, so the only variable is the fact.
  - [ ] `.venv/bin/mypy --strict src/specify_cli/coordination/surface_resolver.py` is clean.
  - [ ] `tests/coordination/test_surface_resolver_collapse.py` and `tests/specify_cli/coordination/test_surface_resolver.py` stay green.
- **Edge cases**:
  - On Windows, compare resolved, case-normalised paths. Reuse whatever WP01 decided for case folding (`kernel.paths.is_windows()`); do not invent a second rule.
  - A `path` that does not exist yet (a first write creates `feature_dir`) must still resolve (`strict=False`).
  - Do not call `classify_worktree_topology` / `read_worktree_registry` here. Registry reads are the non-owned routing authority, and adding one would violate NFR-002.

### Subtask T029 – Route all six `status_service` shape-guard sites; read and write contracts gain `owned`

- **Purpose**: close O6 at the contract layer. The owned checkout's own reads and appends are accepted by the canonical predicate, while every coordination-label protection stays byte-identical (FR-013, FR-014, R-10, R-16).
- **Steps**:
  1. Red first, in `test_status_surface_owned.py` (integration + git_repo, using the WP02 `owned_checkouts` fixture with P moved under `R/.worktrees/owned-a`):
     - `read_event_log(EventLogReadContract.primary_checkout(P_mission_dir, owned=fact))` returns events;
     - the same for `read_event_stream_log`;
     - `append_event_log(EventLogWriteContract.primary_checkout_append(P_mission_dir, owned=fact), ev)` appends;
     - the **same calls without `owned=`** still raise the existing messages (same-fixture control);
     - `EventLogReadContract.coordination_worktree(P_mission_dir, ...)`, a coordination label on an owned path, still requires a coordination path. See the edge cases for the chosen semantics.
  2. In `src/specify_cli/coordination/status_service.py`:
     - Add `owned: OwnedCheckout | None = None` as the **last** field of `EventLogReadContract` (`:77`) and `EventLogWriteContract` (`:119`), so positional construction stays compatible. Import it under `TYPE_CHECKING` (`status_service.py:30`), because the module is imported on cold paths.
     - Extend only the repository-root-labelled factories: `primary_checkout(cls, feature_dir, *, owned=None)` (`:93`) and `primary_checkout_append(cls, feature_dir, *, owned=None)` (`:126`). The coordination factories and the branch-ref factory do **not** take `owned`.
     - Replace `_is_coordination_worktree_path` (`:59-73`) with two small helpers, `_validate_read_labels(contract)` and `_validate_write_contract(contract)` (`:337`), each calling `surface_resolver.primary_read_targets_coord_worktree(contract.feature_dir, owned=contract.owned)`.
     - The six sites are `:160` and `:167` (`read_event_log`), `:222` and `:229` (`read_event_stream_log`), and `:340` and `:347` (`_validate_write_contract`). Fold the duplicated read-guard blocks at `:156-171` and `:218-233` into the one `_validate_read_labels` helper (campsite, behaviour-preserving). Keep every `StatusContractError` message string **byte-identical**: they are pinned by existing tests and are logs_telemetry.
  2a. Shape of the folded read guard. Keep the message constants verbatim, and hoist them to module constants if a string now appears three or more times (Sonar S1192):
     ```python
     def _validate_read_labels(contract: EventLogReadContract) -> None:
         from specify_cli.coordination.surface_resolver import primary_read_targets_coord_worktree  # noqa: PLC0415 - cold path
         targets_coord = primary_read_targets_coord_worktree(contract.feature_dir, owned=contract.owned)
         if contract.source == StatusReadSource.PRIMARY_CHECKOUT and targets_coord:
             raise StatusContractError(_PRIMARY_READ_REFUSED)
         if contract.source == StatusReadSource.COORDINATION_WORKTREE and not targets_coord:
             raise StatusContractError(_COORD_READ_REQUIRES_COORD_PATH)
     ```
     `_validate_write_contract` mirrors this for `PRIMARY_CHECKOUT_APPEND` and `COORDINATION_TRANSACTION_APPEND`. `LEGACY_LANE_APPEND` stays unguarded, exactly as today.
  3. Keep `StatusReadSource` (`:39-44`) and `EventLogWriteTarget` (`:47-52`) unchanged. No `OWNED_CHECKOUT` member (C-002). Update the module docstring (`:1-19`): an owned repository-root-labelled contract carries the validated fact, and the classification is delegated to `surface_resolver`.
- **Files**: `src/specify_cli/coordination/status_service.py`, `tests/specify_cli/coordination/test_status_surface_owned.py`.
- **Parallel?**: no. It follows T028.
- **Validation checklist**:
  - [ ] `grep -n "_is_coordination_worktree_path\|is_under_worktrees_segment" src/specify_cli/coordination/status_service.py` returns nothing; all six sites go through `surface_resolver`.
  - [ ] `tests/specify_cli/coordination/test_wp05_status_read_contract.py`, `test_status_facade_adoption_wp02.py`, `test_plain_door_semantics.py` and `tests/architectural/test_status_unsafe_allowlist.py` stay green unchanged.
  - [ ] The `test_primary_contract_still_rejects_coordination_shaped_path` cases carried in T027 stay green.
  - [ ] mypy is clean on `status_service.py` and `surface_resolver.py`.
- **Edge cases**:
  - **A coordination label on an owned path.** A `COORDINATION_WORKTREE` contract has no `owned` field, so the predicate sees `owned=None` and a path under `.worktrees/`, and the coordination read is accepted by shape exactly as today. This is intentional: the coordination label is not an owned read, and its behaviour must not change (FR-014). Do not add an `owned` parameter to the coordination factories.
  - **Frozen dataclass equality.** Adding `owned` changes `__eq__`/`__hash__` of the contracts. `grep -rn "EventLogReadContract\|EventLogWriteContract" tests/` for equality assertions and confirm they pass `owned=None` implicitly.
  - **Positional construction.** `EventLogReadContract(source, feature_dir, ...)` in tests must keep working, which is why `owned` goes last.

### Subtask T030 – `transaction.py`: the `.worktrees` check becomes `is_under_worktrees_segment`; owned read contract at the transaction target

- **Purpose**:
  - Remove the last raw `".worktrees" in parts` idiom outside the topology authority (C-SEAM-1, R-16).
  - Make the status read of an owned transaction target use the fact-carrying `primary_checkout` contract. That is the change that closes O6 for reads.
- **Scope split with WP07 (read this).** The transaction's own bare owned root (`BookkeepingTransaction.acquire(effective_root=)`, `_primary_root`, the owned append label) is **not** converted here. Its sole caller, `_acquire_status_transaction` (`status_transition.py:1017-1037`), and the tests that pin the acquire kwargs (`tests/specify_cli/coordination/test_status_transition.py::test_batch_door_acquires_transaction_with_the_single_door_shape`, which asserts `single["effective_root"]`) both belong to WP07. Converting the signature here would break a WP07-owned test mid-sequence. WP07 T033 performs the acquire conversion as a declared out-of-map edit of this WP's `transaction.py`, once `TransitionRequest.owned` exists. Leave `acquire`, `_acquire_locked`, `_primary_root` and `commit()` untouched.
- **Steps**:
  1. Make the behaviour-preserving swap in its own commit. At `src/specify_cli/coordination/transaction.py:644`, replace `self._legacy_mode and ".worktrees" not in self.feature_dir.parts` with `self._legacy_mode and not is_under_worktrees_segment(self.feature_dir)`, importing from `specify_cli.coordination.surface_resolver`. Import it lazily inside `append_events`, as `status_service._is_coordination_worktree_path` does today (`status_service.py:59-73`); a module-level import risks a cycle through `mission_runtime`. Run `tests/specify_cli/coordination/test_transaction*.py` and confirm nothing changes.
     - Today an owned P under `.worktrees` appends with the coordination label. After T029, `_validate_write_contract` still accepts that label by shape, so owned writes keep working.
     - WP07 makes the label honest.
     - Do not change the append label in this WP.
  2. Make the out-of-map hunks in `src/specify_cli/coordination/status_transition.py`. That file is WP07-owned, so declare each hunk in the commit body. These three hunks are the whole list:
     - (a) `_TransactionIdentity` (`:92-101`): add `owned: OwnedCheckout | None = None` as the last field. Keep `primary_root`; WP07 collapses it.
     - (b) `_identity_for_request` (`:884-988`): the local `owned` is already the WP02 fact, but it is only bound inside the `if request.effective_root is not None:` arm (`:897`). Initialise `owned = None` before that `if`, then pass `owned=owned` into the `_TransactionIdentity(...)` constructor (`:978-988`). Leave the re-validation block alone; WP07 removes it.
     - (c) `_read_contract_from_transaction_target` (`:1294`): make the first statement `if identity.owned is not None: return EventLogReadContract.primary_checkout(identity.feature_dir, owned=identity.owned)`.
       - This is the site that produces O6 today, via `status/bootstrap.py:151` → `read_events_transactional` → a `primary_checkout` contract on a `.worktrees` path.
       - The branch goes first so an owned identity never falls into the `_is_under_worktree` shape arm at `:1300-1307`.
  3. Run the carried T027 finalize test. It must now be **green** (O6 closed for status), with `r_snapshot` unchanged.
- **Files**: `src/specify_cli/coordination/transaction.py`, plus the declared hunks in `src/specify_cli/coordination/status_transition.py`.
- **Parallel?**:
  - Step 1 can land right after T028.
  - Steps 2 and 3 need T029.
- **Validation checklist**:
  - [ ] `grep -n '".worktrees"' src/specify_cli/coordination/transaction.py` finds only comments.
  - [ ] `git diff <base> -- src/specify_cli/coordination/status_transition.py` shows exactly hunks (a)-(c).
  - [ ] These pass unchanged:
    - `tests/specify_cli/coordination/test_transaction.py`
    - `test_transaction_segment_validation.py`
    - `test_transaction_legacy_topology_routing.py`
    - `test_status_transition*.py`
    - `tests/integration/test_explicit_checkout_commands.py` (FR-022 owned finalize outside `.worktrees/`)
  - [ ] `grep -rn "worktrees" tests/architectural/*.py tests/architectural/_baselines.yaml | grep -i transaction` finds any allowlist entry for the old idiom; remove it (baselines only shrink).
- **Edge cases**:
  - A non-owned `LANES`/flat legacy-mode mission whose `feature_dir` sits inside a lane worktree must keep the coordination label. Step 1 keeps it.
  - An owned identity whose `feature_dir` is **outside** `.worktrees` must also take the owned contract: hunk (c) is unconditional on `identity.owned`. The FR-022 test guards the outcome.
  - Do not add an `owned` parameter to `acquire` "in passing". It is WP07's conversion, and adding it here would create an unplanned dual keyword.

### Subtask T031 – FR-013 / FR-014 same-path tests

- **Purpose**: prove FR-013 and FR-014 on the **same path**, so a green owned read can never come from a weakened coordination guard (spec FR-014 "No-op passable? yes — paired with FR-013 on the same path").
- **Steps**:
  1. In `test_status_surface_owned.py`, add a parametrised matrix over `reader ∈ {read_event_log, read_event_stream_log}` plus the write path, and over `path_kind`:

     | path_kind | label | owned | expected |
     |---|---|---|---|
     | owned P at `R/.worktrees/owned-a` | repository-root | fact(P) | accepted (FR-013) |
     | owned P at `R/.worktrees/owned-a` | repository-root | None | refused, existing message |
     | registered coordination worktree `R/.worktrees/<slug>-coord` | repository-root | None | refused (FR-014) |
     | registered coordination worktree | repository-root | fact(P) (a fact for a **different** checkout) | refused: the fact exempts only its own subtree |
     | registered coordination worktree | coordination | n/a | accepted (unchanged) |
     | P outside `.worktrees` | repository-root | fact(P) | accepted (FR-022 guard) |

  2. **Paired identity.** Build the owned-a row and the coordination row from one fixture instance, so the `.worktrees/<name>` path *shape* is the same kind and only registration plus the fact differ.
  3. **NFR-002 count.** Wrap `subprocess.run` / `subprocess.Popen` in `status_service` and `surface_resolver`, and assert the owned-accepted rows make **0** git calls. The non-owned rows make 0 as well (shape guard only).
  3a. Skeleton for the matrix (adapt the names to the WP02 fixture API):
     ```python
     @pytest.mark.parametrize("row", MATRIX_ROWS, ids=lambda r: r.id)
     @pytest.mark.parametrize("op", ["read", "stream", "append"])
     def test_same_path_matrix(owned_under_worktrees, registered_coord, row, op):
         contract = row.build(owned_under_worktrees, registered_coord, op)
         if row.expected_ok:
             _run(op, contract)
         else:
             with pytest.raises(StatusContractError, match=row.message):
                 _run(op, contract)
     ```
  4. **Non-vacuity.** Before committing, temporarily make `primary_read_targets_coord_worktree` always return `False` and confirm the FR-014 rows go red; revert. Record that in the Activity Log as the mutation check (no code is committed for it).
- **Files**: `tests/specify_cli/coordination/test_status_surface_owned.py`.
- **Parallel?**: yes, alongside T030 step 1.
- **Validation checklist**:
  - [ ] Every accepted row has a refused sibling on the same fixture.
  - [ ] The owned-accepted **read** rows were red before T029, and the finalize row was red before T030. Commit them with the T028 test commit. The owned **append** row is accepted through the fact-carrying `primary_checkout_append` contract, which WP07 wires into the transaction; this WP tests it at the contract level only.
  - [ ] Markers: git-backed rows are `integration` + `git_repo`; pure rows are `unit` + `fast`.
- **Edge cases**:
  - `git worktree add` inside `tmp_path` on Windows needs short paths; keep names short.
  - Make sure the coordination worktree's `kitty-specs/<slug>/` exists before reading (create an empty `status.events.jsonl`), so a refusal is the guard, not `FileNotFoundError`.

## Test Strategy

**Red-first map** (C-007: every `[build]` requirement reproduced through its pre-existing entry point before the fix):

| Requirement | Red-first test | Entry point | Why it is non-vacuous |
|---|---|---|---|
| FR-013 | `test_finalize_and_read_owned_mission_below_worktrees` (carried `4ff6ff0c0`, adapted) | real `agent mission finalize-tasks --owned-checkout` via `CliRunner` | genuine O6 red on base; same-fixture control: finalize of P **outside** `.worktrees` (existing `tests/integration/test_explicit_checkout_commands.py::test_finalize_seeds_owned_status_only`) stays green |
| FR-013 (unit) | owned-accepted rows in `test_status_surface_owned.py` | `read_event_log` / `append_event_log` | paired with refused rows on the same path |
| FR-014 `[ratchet]` | `test_registered_coordination_worktree_same_path_still_refused` plus the T031 coordination rows | status contracts | green before and after; the mutation check in T031 step 4 proves it can fail |
| NFR-002 | subprocess-count assertions (T028, T031) | predicate and contracts | a counting wrapper, not a mock of the behaviour |

**Commands** (record exact commands and pass/fail counts in the Activity Log and the PR's *Tests run*):

```bash
.venv/bin/python -m pytest tests/specify_cli/coordination/test_owned_status_read_contract.py tests/specify_cli/coordination/test_status_surface_owned.py -q
.venv/bin/python -m pytest tests/specify_cli/coordination/ tests/coordination/ -q          # owning subsystem dirs
.venv/bin/python -m pytest tests/integration/test_explicit_checkout_commands.py tests/status/test_bootstrap.py -q   # FR-022 + O6 read path
.venv/bin/python -m pytest tests/architectural/test_status_unsafe_allowlist.py tests/architectural/test_layer_rules.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_mission_runtime_surface.py -q   # specific implicated gates only
make test-fast
.venv/bin/ruff check src/specify_cli/coordination/status_service.py src/specify_cli/coordination/surface_resolver.py src/specify_cli/coordination/transaction.py src/specify_cli/coordination/status_transition.py tests/specify_cli/coordination/test_owned_status_read_contract.py tests/specify_cli/coordination/test_status_surface_owned.py
.venv/bin/ruff format --check <same files>
.venv/bin/mypy --strict src/specify_cli/coordination/status_service.py src/specify_cli/coordination/surface_resolver.py src/specify_cli/coordination/transaction.py src/specify_cli/coordination/status_transition.py src/specify_cli/core/owned_mission.py src/mission_runtime/owned_checkout.py src/mission_runtime/resolution.py
```

mypy discipline (plan: Staging Strategy): never drop `--strict`; list callers **and callees** in the same invocation (`follow_imports = "skip"` for `specify_cli.*`). If `--strict` reports pre-existing errors in these files, run the identical command on the planning base, record that count, and show it did not grow; never narrow the file list to hide them.

Do **not** run `make test-full` or the bare `tests/architectural/` directory (`NO_FULL_HEAVY_SUITES_IN_MISSION`). Classify any unrelated red with the baseline-red gotcha in `CLAUDE.md` before touching it.

## Risks & Mitigations

- **Risk: weakening the coordination guard.** The exemption applies only under `owned.owned_root`, and T031's paired rows plus the mutation check pin that.
- **Risk: out-of-map drift into `status_transition.py`.** Keep to hunks (a)-(c) exactly. WP07's reviewer diffs `status_transition.py` against this WP's merge commit.
- **Risk: `EventLogReadContract` equality changes.** `owned` is appended last with a default of `None`; grep the tests for equality usage (T029 edge cases).
- **Risk: cold-import regression (#1461).** Import `OwnedCheckout` under `TYPE_CHECKING` in `status_service.py` and `status_transition.py`, with `from __future__ import annotations` already present.
- **Risk: the owned append label stays the coordination label until WP07.** The label is accepted by shape, and T031's owned append row calls the contract directly, so nothing regresses. WP07 T033 switches the transaction to `primary_checkout_append(owned=...)`.

## Review Guidance

- Confirm the cherry-pick provenance: author Samuel Goff, `cherry picked from commit 4ff6ff0c0`. The dropped test is removed in a separate, trailer-carrying commit.
- Confirm there is no new `StatusReadSource` / `EventLogWriteTarget` value (C-002) and that all six sites route through `surface_resolver.primary_read_targets_coord_worktree`.
- Confirm every `StatusContractError` string is byte-identical.
- Confirm the `status_transition.py` edits are exactly hunks (a)-(c), each declared in a commit body.
- Confirm no new use of the legacy `OwnedMission` attribute names.
- Confirm the implementer ran mypy (not only pytest) on the touched files, and that it passed.
- Transitional surfaces (the six shared seams plus every other function marked `TRANSITIONAL(WP18)`) are expected until WP18. Do not reject them.

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
- 2026-09-28T21:38:24Z – unknown – Acknowledged review-cycle-1 feedback (reviewer-renata): fixing NFR-001 oracle blocker (Issue 1), fixing hunk (c) now per orchestrator override (item 3), and folding nits N1-N3. Orchestrator ruled the NFR-001 wording tension: add a single named, canonical status-mutex tolerance to tests/_owned_fixtures.py (WP02's file) as a declared out-of-map edit, rather than leaving the exclusion narrow-but-local.
- 2026-09-28T22:03:41Z – unknown – Review-cycle-1 fixes complete. Issue 1 (NFR-001 oracle): added RSnapshotter.assert_unchanged(..., tolerate_status_mutex_for=<lock key>) in tests/_owned_fixtures.py (WP02's file, out-of-map, orchestrator-ruled) tolerating exactly one added+empty, canonically-named lock key; home_files now compared unconditionally; mutation-proof tests (accept + 3 reject cases) added to tests/integration/test_owned_fixtures_selftest.py. Item 3 (hunk c): gated the owned primary_checkout shortcut in status_transition._read_contract_from_transaction_target on 'not routes_through_coordination(identity.owned.topology)' (out-of-map hunk (d), WP07-owned file, fixed now per orchestrator override rather than left latent); red-first unit test constructs the fact/_TransactionIdentity directly since the pipeline refuses non-single_branch owned identities upstream. Nits N1-N3 folded: NFR-002 counter now wraps subprocess.run+Popen in both status_service and surface_resolver; three type:ignore[arg-type] removed via an EventLogReadContract|EventLogWriteContract union + isinstance narrowing; added the missing 'coordination worktree + coordination label -> accepted' matrix row. Mutation check for hunk (c) recorded: without the topology gate the new unit test fails (verified red before the fix). All 7 commits red-first where applicable; ruff check/format clean; mypy --strict unchanged at baseline (5 errors across the 3 production files; the 21 pre-existing test_owned_fixtures_selftest.py no-untyped-def errors did not grow, my 4 new tests are annotated).
