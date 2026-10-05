---
work_package_id: WP02
title: 'Pure invariant: started predicate, frozen membership, lane computation and writer check'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-008
- FR-010
- NFR-002
- NFR-004
- C-002
- C-006
- SC-002
planning_base_branch: issue-5573-frozen-started-lanes
merge_target_branch: issue-5573-frozen-started-lanes
branch_strategy: Planning artifacts for this mission were generated on issue-5573-frozen-started-lanes. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5573-frozen-started-lanes unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-frozen-started-lanes-01M444FM
base_commit: 56c3ef9b8eb7b0f0aaca0ca85fa5ca0451ef57f2
created_at: '2026-10-04T19:40:37.813176+00:00'
subtasks:
- T005
- T006
- T007
- T008
- T009
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- src/specify_cli/lanes/frozen_membership.py
- tests/lanes/test_frozen_lane_membership.py
- tests/lanes/test_frozen_lane_membership_sweep.py
- tests/lanes/test_lane_tip_listing.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/lanes/frozen_membership.py
- src/specify_cli/lanes/compute.py
- src/specify_cli/lanes/compute_and_persist.py
- src/specify_cli/lanes/lane_tip.py
- src/specify_cli/lanes/models.py
- tests/lanes/test_frozen_lane_membership.py
- tests/lanes/test_frozen_lane_membership_sweep.py
- tests/lanes/test_lane_identity.py
- tests/lanes/test_lane_tip_listing.py
- tests/status/test_compute_and_persist_core.py
role: implementer
tags: []
tracker_refs: []
---

# WP02 — Pure invariant: started predicate, frozen membership, lane computation and writer check

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to
its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's
`task_type` and `authoritative_surface`.

---

Implementation command: `spec-kitty agent action implement WP02 --agent claude`

## Post-tasks squad folds (binding — these override any conflicting text below)

- **The dead-symbol gate is `tests/architectural/test_no_dead_symbols.py`** (`test_no_public_symbol_in_all_is_unimported`,
  ~L1507). `test_dead_symbol_allowlist_contract.py` cannot fail, so ignore it.
  - Keep `__all__` in `frozen_membership.py` to what WP03 and `compute.py` actually import:
    `FrozenLaneMembership`, `MembershipConflict`, `build_frozen_membership`, `started_wp_ids`, `remedy_for`,
    `assert_frozen_membership_honoured`.
  - Remedy constants and the `STARTED_LANES` set are **private** (`_REMEDY_*`). `MembershipConflictReason` is either
    imported by `compute.py` or kept out of `__all__`.
  - Add `recorded_tip_branches` to `lane_tip.__all__` if that module declares one.
  - Run the gate on the WP02 lane. `started_wp_ids`, `build_frozen_membership` and `recorded_tip_branches` have no
    `src/` caller until WP03 and **may be red on this lane**. Report exactly which names are red to the reviewer.
    WP03 must turn it green. Do **not** add allowlist entries (C-004).
- **Complexity.** `ruff.toml` baselines C901 off for `compute.py`, so a plain `ruff check` cannot fail there. Measure
  with `ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=15' <file>`. `compute_lanes` is
  already 35: it **must not grow**. Put all new logic, including conflict collection and the raise, in helpers that
  are each ≤ 15. Report before/after numbers for `compute_lanes` and `_assign_stable_lane_ids`.
- **Early returns** (`compute.py:~722`, `~753-770`): the empty-graph and planning-only paths return before
  union-find. Run removal and kind-change conflict collection **right after the planning/code split, before those
  returns**, so removing every code WP or a kind change still refuses. Add tests for both:
  - every code WP removed while started;
  - a planning-only resulting graph with a started code WP now a planning artifact.
- **Frozen union after Rules 1 and 2** (corrected in T006 step 4). Exclude `frozen_lane_membership` events from
  `_count_independent_collapses`, or document why they count. Either way, add a test that pins the choice.
- **The sweep must not be satisfiable by "always refuse"** (T009). Compute the **expected** outcome independently in the
  test, with a tiny union-find over the amended ownership:
  - expect a refusal iff a group holds two or more distinct bound lanes, a bound WP is absent and not retired, or a
    bound WP changed kind;
  - assert `raised == expected`;
  - when not raising, every bound WP keeps its lane **and** every freshly minted id is outside `reserved_lane_ids`;
  - also assert determinism over two shuffled input orders (dict insertion order), not just two identical calls.
- **Named unit tests to add:**
  - US3 AS2: a planned lane-mate split out of a started lane gets a fresh id that is not reserved, and the started WP
    keeps its lane;
  - retired reservation: a retired started WP's id is never minted for a new group.
- `SINGLE_BRANCH`: both `compute_lanes` and `assert_frozen_membership_honoured` ignore `frozen` (test it).
- `recorded_tip_branches` catches `OSError` too (git missing) and returns an empty frozenset.
- Do **not** re-export the new names from `specify_cli/lanes/__init__.py` (an import-cycle risk with status).

## Objective

Close the #5573 defect class by construction in the **pure** lane computation. Started work packages' recorded lanes
become a constraint input that `compute_lanes` honours:
- a lane holding started work keeps its id;
- started lane-mates stay together;
- lane ids that held started work are never re-minted;
- unsatisfiable cases raise one typed error, `LANE_MEMBERSHIP_FROZEN`.

The write chokepoint re-checks the result.

## Context

- **Spec:** FR-001–FR-005, FR-008, FR-010.
- **Plan:** "Design → The constraint inside `compute_lanes`", and IC-02.
- **Data model:** `data-model.md` (types and invariants).
- **Contract:** `contracts/lane-membership-frozen.md` (reasons, remedies, message shape).
- **Root cause** (grounding §2): `_assign_stable_lane_ids` (`src/specify_cli/lanes/compute.py:505-560`) reads lane
  ids back by membership overlap only. It can rebind a started WP three ways: a tie (strict `>` over
  `sorted(existing.items())`, L537-544), greedy group order, and re-minting an orphaned id (`_next_free_lane_id`,
  L489/551).
- **Purity (C-002):** `compute.py` and `compute_and_persist.py` must stay git-free and meta-free. This WP only adds
  pure code, plus one git helper in `lane_tip.py`, which is already a git module.
- **Default preserves behaviour:** every new parameter defaults to `None`/empty. With no frozen input, output must be
  **byte-identical** to the base for every existing test (`tests/lanes`, `tests/status/test_compute_and_persist_core.py`,
  `tests/specify_cli/lanes`).
- **Dependents:** WP03 consumes `build_frozen_membership`, `started_wp_ids`, `recorded_tip_branches`, the `frozen=`
  keyword on `compute_lanes` / `compute_and_write_lanes`, and `LaneMembershipFrozenError`. WP04 documents them.
  Keep the public names exactly as specified here.
- **Red-first inside this WP:** write the T005/T006 unit tests first and commit them failing, or as one commit per
  red/green pair if you prefer. Then implement.

### Subtask T005: `lanes/frozen_membership.py` — evidence model, started predicate, builder (pure)

**Purpose**: one pure home for "which WPs are started" and "what membership is frozen".

**Steps**:
1. Create `src/specify_cli/lanes/frozen_membership.py` with `__all__` listing:
   - `MembershipConflictReason`: a `Literal` of `started_lanes_collapsed`, `started_wp_removed`,
     `started_wp_kind_changed`, `status_unreadable`.
   - `MembershipConflict`: a frozen dataclass with `reason`, `wp_ids: tuple[str, ...]` (sorted),
     `recorded_lanes: tuple[str, ...]` (sorted, distinct), `remedy: str`. Add
     `to_dict() -> dict[str, object]` for the JSON envelope.
   - `FrozenLaneMembership`: a frozen dataclass with `bindings: Mapping[str, str]` (store it as a read-only
     `MappingProxyType`, or a tuple of pairs exposed as a mapping, so it is hashable/immutable) and
     `retired_wp_ids: frozenset[str]`. Add:
     - a `reserved_lane_ids` property (the set of binding values);
     - an `empty()` classmethod;
     - `is_empty`.
   - `started_wp_ids(events: Iterable[StatusEvent]) -> frozenset[str]`: a WP is included iff some event has `to_lane`
     in the **positive** set `STARTED_LANES = {CLAIMED, IN_PROGRESS, FOR_REVIEW, IN_REVIEW, APPROVED, DONE}`. Make it
     a private module constant; this excludes the planned/blocked/canceled lanes and the genesis/uninitialized
     sentinels by construction. Import `Lane` and `StatusEvent` **through the
     `specify_cli.status` facade** (`from specify_cli.status import Lane, StatusEvent`;
     `tests/architectural/test_status_module_boundary.py` pins this). Treat genesis/uninitialized sentinels
     (`NON_DISPLAY_LANES`, if they appear as `to_lane`) as not started. Explain the history-based rule in the
     docstring: resets to planned and cancel-after-work keep a WP started (FR-008).
   - `build_frozen_membership(previous: LanesManifest | None, *, started: frozenset[str], tipped_branches: frozenset[str], present_wp_ids: frozenset[str], eligible_wp_ids: frozenset[str]) -> FrozenLaneMembership`:
     - `previous is None` → `empty()`.
     - Otherwise, for each lane in `previous.lanes`, the lane's started members are `set(lane.wp_ids) & started`.
     - If that set is empty, and the lane is a **code** lane whose created branch
       (`lane_created_branch(previous, lane.lane_id)` from `lanes.compute`) is in `tipped_branches`, then **all** of
       the lane's members count as started (the lane-work-tip fallback; over-freezing is the safe direction, spec Edge
       Cases).
     - `bindings[wp] = lane.lane_id` for every started member.
     - `retired_wp_ids = present_wp_ids - eligible_wp_ids`.
   - Remedy text constants (module-level, one per reason, matching the contract table), plus
     `remedy_for(reason, wp_ids) -> str`, which formats the WP ids in.
   - `assert_frozen_membership_honoured(manifest: LanesManifest, frozen: FrozenLaneMembership | None) -> None`:
     - for every binding whose WP appears in `manifest`, its lane id must equal the binding;
     - otherwise raise `LaneMembershipFrozenError` with reason `started_lanes_collapsed` naming the WP and its
       recorded lane. Document it as defence in depth: it should be unreachable after `compute_lanes`.
2. Avoid an import cycle: `compute.py` will import from `frozen_membership`. Put `LaneMembershipFrozenError` in
   `compute.py` (beside `LaneDependencyCycleError`) and import it lazily inside `assert_frozen_membership_honoured`,
   or define the error in `frozen_membership.py` and re-export it from `compute.py`. Choose the cycle-free option and
   record why in the docstring. **Either way, `from specify_cli.lanes.compute import LaneMembershipFrozenError` must
   work.**
3. Tests in `tests/lanes/test_frozen_lane_membership.py` (`fast`), table-driven:
   - `started_wp_ids` over:
     - `planned → claimed`;
     - `planned → blocked` (not started);
     - `planned → canceled` (not started);
     - `claimed → in_progress → planned` (still started);
     - a forced `planned → in_progress`;
     - `blocked → in_progress`;
     - `done`;
     - an empty list.
   - `build_frozen_membership` cases:
     - `None` previous;
     - history-started binding;
     - tip fallback freezes all members of an unstarted tipped lane;
     - the tip fallback is ignored when the lane already has a history-started member;
     - the planning lane is never tip-frozen;
     - `retired` computation.

**Files**: the new module (~180 lines); the new test file (~200 lines).

### Subtask T006: `LaneMembershipFrozenError` and the `frozen=` constraint in `compute_lanes`

**Purpose**: honour frozen membership by construction; refuse only unsatisfiable cases.

**Steps**:
1. In `compute.py`, add
   `class LaneMembershipFrozenError(LaneComputationError)` with
   `error_code: ClassVar[str] = "LANE_MEMBERSHIP_FROZEN"`. Constructor:
   `__init__(self, conflicts: tuple[MembershipConflict, ...])`, non-empty. Attributes:
   - `conflicts`;
   - `reason`: the first by precedence `started_lanes_collapsed` > `started_wp_removed` > `started_wp_kind_changed` >
     `status_unreadable`;
   - `next_step`: distinct remedies joined by newlines, ordered by precedence.

   Message: `"Cannot re-finalize: started work packages would change lane. "` followed by one clause per conflict,
   e.g. `"WP01 (lane-a) and WP02 (lane-b) would be merged into one lane"`. Keep C-003 in mind: no existing message
   changes.
2. `compute_lanes(..., *, frozen: FrozenLaneMembership | None = None)`, keyword-only after the existing parameters.
   `SINGLE_BRANCH` ignores it.
3. **Conflict collection** (a helper, e.g. `_frozen_membership_conflicts(frozen, code_wp_ids, planning_wp_ids)`):
   - a binding WP absent from both id lists and **not** in `frozen.retired_wp_ids` → `started_wp_removed`;
   - a binding to `PLANNING_LANE_ID` for a WP now in `code_wp_ids`, or a binding to a code lane for a WP now in
     `planning_artifact_wp_ids` → `started_wp_kind_changed`.
4. **Frozen union** (run it **after Rules 1 and 2**, so Rule 1 still logs its `write_scope_overlap` evidence; the
   resulting groups are identical): group present code WPs by bound lane id. For each
   lane id with two or more members, `uf.union` them, and append
   `CollapseEvent(wp_a, wp_b, rule="frozen_lane_membership", evidence=f"both started on {lane_id}")` when not already
   unioned. Update the `CollapseEvent.rule` docstring in `lanes/models.py` to list the new rule value. Check how
   `independent_wps_collapsed` is computed (`compute.py:~960-985`) and make sure a frozen-membership union is
   classified consistently. A collapse between WPs with no dependency is "independent"; that is acceptable, so
   document it.
5. **`_assign_stable_lane_ids(sorted_groups, previous_lanes, frozen=None)`**. Split it into small helpers to keep
   complexity ≤ 15 (e.g. `_pin_frozen_groups`, `_read_back_by_overlap`, `_mint_fresh_ids`):
   - **Pass 0:** for each group, pins = the distinct bound lane ids of its members (code lanes only). One pin → the
     group takes it. Two or more pins → a `started_lanes_collapsed` conflict naming every bound member and their
     lanes.
   - **Pass 1:** today's overlap read-back, unchanged, over ids not yet used. Document the deterministic tie-break
     (most shared members, then the lowest prior lane id) in the docstring.
   - **Pass 2:** mint fresh ids while skipping `used ∪ frozen.reserved_lane_ids` (FR-004).
   - Return the ids plus any conflicts, or raise. Collect **all** conflicts (step 3 + pass 0) and raise a single
     `LaneMembershipFrozenError` before building lanes.
6. Update the `compute_lanes` docstring `Args` for `frozen`, and the `_assign_stable_lane_ids` docstring (#5573).
7. Tests (red first) in `tests/lanes/test_frozen_lane_membership.py`, using the existing `_manifest` helper style from
   `test_lane_identity.py`:
   - **the #5573 tie:** prior lane-a=[WP01] and lane-b=[WP02]; WP01 now owns `b.py`; frozen {WP02: lane-b} → one lane
     `lane-b` holding WP01 and WP02;
   - **mirror:** frozen {WP01: lane-a} → lane-a;
   - **greedy steal:** an earlier group with no started WP would take a started WP's id under the old algorithm; the
     started group keeps it;
   - **re-mint:** an orphaned id reserved by a retired started WP is not re-minted for a new group;
   - **split:** started lane-mates WP01 and WP02 (both on lane-a), with the overlap removed → still one lane-a;
   - **two pins** → `LaneMembershipFrozenError`, with `.reason == "started_lanes_collapsed"`, `.error_code`, both WPs
     and both lanes in the conflict;
   - **removed started WP** → `started_wp_removed`; **removed but retired** → no error, and the id stays reserved;
   - **kind change** → `started_wp_kind_changed`;
   - `frozen=None` and `frozen=FrozenLaneMembership.empty()` give the same output as no argument (the same fixture
     run three ways).

**Files**: `compute.py` (~+120/−20 lines); `models.py` (docstring); tests (~+250 lines).

### Subtask T007: The `frozen=` keyword on `compute_and_write_lanes` + chokepoint post-check

**Purpose**: the single persistence core passes the constraint through and re-asserts it before writing.

**Steps**:
1. `compute_and_write_lanes(..., *, frozen: FrozenLaneMembership | None = None)`:
   - pass it to `compute_lanes(frozen=frozen)`;
   - after the existing `assert_topology_matches_manifest` block and before `write_lanes_json`, call
     `assert_frozen_membership_honoured(lanes_manifest, frozen)`;
   - update the docstring (`Args`, `Raises`: `LaneMembershipFrozenError`, with no `lanes.json` written).
2. Keep the module's purity note true (no typer, json, console, policy or git).
3. Extend `tests/status/test_compute_and_persist_core.py`:
   - (a) a frozen membership that is honoured writes normally;
   - (b) a conflicting frozen membership raises and leaves the pre-existing `lanes.json` byte-identical;
   - (c) the post-check alone raises when given a manifest that violates bindings (call
     `assert_frozen_membership_honoured` directly, so the defence-in-depth branch is covered).

### Subtask T008: `lane_tip.recorded_tip_branches(repo_root)` — one git call for all tips

**Purpose**: the lane-work-tip fallback without one git call per lane (NFR-001).

**Steps**:
1. Add `recorded_tip_branches(repo_root: Path) -> frozenset[str]` to `src/specify_cli/lanes/lane_tip.py`:
   - run `git for-each-ref --format=%(refname) refs/spec-kitty/lane-tip/`;
   - strip `LANE_TIP_REF_PREFIX` from each line;
   - return the branch names;
   - on a non-zero exit, return an empty frozenset. Document that this is read-only evidence, and that a git failure
     means no fallback evidence; the status log remains the primary authority.
2. Tests in `tests/lanes/test_lane_tip_listing.py` (`integration` + `git_repo`, real git in `tmp_path`):
   - no refs → empty;
   - `record_tip` two branches (one with a slash-y name such as `kitty/mission-x-lane-a`) → both returned;
   - a non-git dir → empty.

### Subtask T009: Permutation sweep + merge/split/tie cases (property-style, stdlib only)

**Purpose**: SC-002 / NFR-002 — no started WP ever silently changes lane, across permutations. Unstarted regrouping
stays deterministic (FR-010).

**Steps**:
1. Create `tests/lanes/test_frozen_lane_membership_sweep.py` (`fast`). Build a small universe of WP01–WP04, each owning
   one file.
   - **Prior manifests:** 2 or 3 lanes (enumerate partitions with `itertools`). Compute them with `compute_lanes`
     from disjoint ownership, so they are realistic.
   - **Amendments:** merge two lanes (an owned-file overlap), merge three, split (remove an overlap from a
     co-lane pair whose prior ownership overlapped), add a WP05, remove a WP.
   - **Started set:** every subset of the prior WPs.
   - Parametrize with `pytest.mark.parametrize` over `itertools.product`. Keep the case count ≲ 500 and the runtime
     < 2 s (NFR-004).
2. **Invariant per case:** either `compute_lanes(..., previous_lanes=prior, frozen=build_frozen_membership(...))`
   returns a manifest where every started WP still present has its prior lane id, or it raises
   `LaneMembershipFrozenError`. A removed started WP must raise.
3. **Determinism:** compute twice and compare `to_dict()` minus `computed_at` (NFR-002).
4. **Same-fixture positive control:** with `started=frozenset()` and no tips, the result equals today's algorithm
   (`frozen=None`), byte for byte, minus `computed_at`.
5. Boy-scout in `tests/lanes/test_lane_identity.py`:
   - add explicit **merge (tie)** and **split** cases for unstarted WPs, documenting the tie-break rule;
   - fold the redundant `test_read_back_never_overwrites_a_bound_id` uniqueness assertion into the new merge test
     (delete the duplicate only if its scenario is fully covered; state that in the commit message).

## Definition of Done

- All new and changed tests pass. Existing `tests/lanes`, `tests/specify_cli/lanes` and
  `tests/status/test_compute_and_persist_core.py` pass with **no expectation changes**.
- `compute.py` / `compute_and_persist.py` import no git, `meta.json`, typer or console code.
- Every touched function has complexity ≤ 15 (`ruff check --select C901`).
- `mypy` and `ruff check` are clean; `ruff format --check --force-exclude <files>` is clean.
- Architectural gate files are green: `tests/architectural/test_status_module_boundary.py`,
  `tests/architectural/test_layer_rules.py`, `tests/architectural/test_dead_symbol_allowlist_contract.py`. A new
  public symbol without a `src/` caller is expected until WP03 wires it. If the dead-symbol gate flags it, note it
  for the reviewer rather than suppressing it; WP03 adds the callers.
- Each subtask is recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.
- Every commit carries `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`.

## Risks

- **Byte-identical default:** any accidental change to unpinned read-back breaks #4945 tests. Run `tests/lanes`
  before and after.
- **Complexity creep in `_assign_stable_lane_ids`:** extract helpers.
- **Import cycle** between `compute.py` and `frozen_membership.py`: resolve it deliberately (see T005 step 2).

## Reviewer Guidance

- Check pass 0 runs before read-back and that reserved ids are excluded from minting only.
- Check the sweep's invariant really is "keep or raise", and that the positive control compares against `frozen=None`.
- Check `started_wp_ids` treats `blocked`/`canceled`-from-planned as not started and resets as started.
- Check `compute.py` purity and that `SINGLE_BRANCH` ignores `frozen`.
