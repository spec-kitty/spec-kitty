---
work_package_id: WP04
title: PlacementSeam.write_dir and the loud post-fix EMPTY surface (IC-03 part 2)
dependencies:
- WP01
- WP03
requirement_refs:
- FR-003
- FR-003a
- C-001
- C-002
- C-008
- FR-017
planning_base_branch: issue-5440-coord-artifact-single-home
merge_target_branch: issue-5440-coord-artifact-single-home
branch_strategy: Planning artifacts for this mission were generated on issue-5440-coord-artifact-single-home. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5440-coord-artifact-single-home unless the human explicitly redirects the landing branch.
subtasks:
- T018
- T019
- T020
- T021
- T022
phase: Phase 1 - Write-location accessor
history:
- at: '2026-10-01T08:36:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/mission_runtime/resolution.py
create_intent:
- tests/mission_runtime/test_placement_seam_write_dir.py
- tests/coordination/test_surface_resolver_post_fix_empty_loud.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/mission_runtime/resolution.py
- src/specify_cli/coordination/surface_resolver.py
- src/specify_cli/missions/_read_path_resolver.py
- tests/mission_runtime/test_placement_seam_write_dir.py
- tests/coordination/test_surface_resolver_post_fix_empty_loud.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
agent: claude
assignee: ''
shell_pid: ''
---

# Work Package Prompt: WP04 – PlacementSeam.write_dir and the loud post-fix EMPTY surface (IC-03 part 2)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

Add **the one sanctioned seam extension** (C-001): `PlacementSeam.write_dir(kind) -> WriteLocation`, on the existing placement seam in `src/mission_runtime/resolution.py`, beside `write_target` and `read_dir`. Every COORD-partition writer migrated in WP06-WP18 calls it. Along the way, make the read side's EMPTY state **loud for post-fix Missions in both coordination topologies**, while keeping the read fallback (C-002). Also correct the stale in-code contract text that still claims UNMATERIALIZED resolves to primary.

Success means:

- `placement_seam(repo_root, slug, owned=...).write_dir(kind)` behaves as follows:
  - **PRIMARY kinds, or `lanes`/`single_branch` topologies**: returns the declared PRIMARY dir, byte-identical to today's `read_dir` short-circuit, with no side effects (C-008).
  - **COORD kinds of coordination-routed Missions**: delegates to WP03's `establish_coord_write_location` (materialize, seed, restore or refuse).
- The owned-checkout coordination arm works through the owned workspace.
- A property test pins `write_dir(kind).surface` ⇔ `write_target(kind).ref` agreement for every kind × topology. It also pins that `resolve_placement_only`, `write_target` and `read_dir` remain side-effect free.
- A post-fix Mission (its coordination branch history carries the `Spec-Kitty-Coordination-Seed: <mission_id>` trailer; round 4) whose worktree Mission dir is missing logs the EMPTY warning for **both** `coord` and `lanes_with_coord`. Pre-fix behaviour is unchanged, and reads still fall back to the repository root checkout.
- The docstrings and the `CoordState.EMPTY` contract text say what the code does.
- The `mission_runtime` outbound ledger does **not** grow (cap 10, `tests/architectural/_baselines.yaml` key `test_layer_rules.mission_runtime_allowed_specify_cli`).

## Context & Constraints

- **Load the charter**: `.kittify/charter/charter.md` and `spec-kitty charter context --action implement --json`.
- **Spec**:
  - FR-003 (one accessor for every COORD writer);
  - FR-003a (establish or refuse loudly; post-fix EMPTY warns);
  - US2.7 (post-fix EMPTY loud for both topologies, reads keep the fallback);
  - C-001, C-002, C-008.
- **Plan**: IC-03, "How it reconciles with existing seams":
  - `resolve_placement_only` / `write_target` stay ref-only and side-effect free;
  - `read_dir` keeps the read fallback;
  - `resolve_status_surface_with_anchor(for_write=True)` stays pure. It is reached from `resolve_placement_only` (`resolution.py:1974-1982`, `_assemble_core_fragments(..., for_write=True)`).
- **Plan IC-17**: the code-comment half of FR-017 (stale docstrings in `resolution.py`, the `_read_path_resolver.py` contract text) lands here, because this WP owns those files. The `docs/` half is WP22.
- **Research**: D1 (accessor shape and rejected alternatives), D4 (post-fix discriminator: the `Spec-Kitty-Coordination-Seed: <mission_id>` trailer, constant `COORD_SEED_TRAILER` owned by WP03; no meta flag; ~~`git ls-tree` non-empty~~ struck in round 4).
- **Contract**: `contracts/write-location-accessor.md` (postcondition table, errors, "Relationship to existing seams").
- **Data model**: §2 (the CoordState handling table and the read-side note).
- **Code anchors** (verified at `ecb5dd914a`):
  - `class PlacementSeam`: `resolution.py:2261`. `def write_target`: L2304. `def read_dir`: L2318 (RETROSPECTIVE delegates lazily to `specify_cli.retrospective.writer.resolve_retrospective_home`, ≈L2356; that is the precedent for a lazy cross-layer delegate). The declared-PRIMARY short-circuit is at ≈L2523-2525 (`declared_read_surface(...) is TopologySurface.PRIMARY`). `def placement_seam(repo_root, mission_slug, *, owned=None)`: L2835.
  - `_owned_read_dir_for_kind`: `resolution.py:1272` (raises on EMPTY for owned coordination Missions today).
  - Owned coordination workspace precedent: `runtime/next/runtime_bridge.py:359-366` (`_resolve_owned_coordination_workspace(...)`).
  - EMPTY branch of `resolve_status_surface_with_anchor`: `surface_resolver.py` ≈L1430-1450. WP01 extracted it into a helper, `_empty_coord_surface` or similar; use that helper. Today it warns only `if effective_topology is MissionTopology.LANES_WITH_COORD`, with `_COORD_EMPTY_FALLBACK_WARNING` defined at L132.
  - `CoordState` docstring: `missions/_read_path_resolver.py:250-275`. L259-260 reads "EMPTY … a fail-closed condition, never a silent primary fallback". That contradicts the kept non-owned read fallback.
  - Layer ledger: `tests/architectural/test_layer_rules.py:116` (`_MISSION_RUNTIME_ALLOWED_SPECIFY_CLI` includes `"coordination"`); cap in `tests/architectural/_baselines.yaml` (`mission_runtime_allowed_specify_cli: 10`).
- **`resolution.py` stays undecomposed** (3006 lines). Add only the method plus a small private helper or two. The types come from WP03's `src/mission_runtime/write_location.py`.
- **Model discipline**: implement = sonnet (`claude-sonnet-5`); review = opus.
- **Terminology**: Mission, never feature. "PRIMARY partition" for the partition sense; "repository root checkout" for the read fallback's location.
- **No heavy suites** (C-006).
- **Brownfield scout (binding read)**: before coding, read `## WP04` in `kitty-specs/coord-artifact-single-home-01M3V4BE/research/brownfield-scout-wp01-11.md` (plus its "Cross-cutting" section where present). Its corrections are folded into the "Binding corrections" section below, which overrides conflicting text above.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5440-coord-artifact-single-home; completed changes must merge back into issue-5440-coord-artifact-single-home.
- **Planning base branch**: `issue-5440-coord-artifact-single-home`
- **Merge target branch**: `issue-5440-coord-artifact-single-home`
- `finalize-tasks` allocates execution worktrees per computed lane from `lanes.json`.
- Start with `spec-kitty agent action implement WP04 --agent claude` and use the printed workspace path.
- **Lane-relevant shared files**: this WP runs in **lane A**, after WP01. It shares `src/specify_cli/coordination/surface_resolver.py` with WP01, which extracted the EMPTY-branch helper you modify. WP03 (another lane) is a dependency, so its `coord_seed.py` / `write_location.py` are in your base. WP05 follows you in lane A.

## Subtasks & Detailed Guidance

### Subtask T018 – Red-first tests and `PlacementSeam.write_dir`

- **Purpose**: Expose the single write-location accessor on the existing seam (research D1). Writers stop deriving write locations from read resolvers.
- **Steps**:
  1. **Red-first commit (separate, first)**: `tests/mission_runtime/test_placement_seam_write_dir.py`, using `tests._factories.coord_mission` (WP02):
     - `test_write_dir_coord_kind_on_prefix_empty_mission_is_coordination_surface`: on `make_prefix_coord_mission(worktree="empty")`, `placement_seam(repo_root, slug).write_dir(MissionArtifactKind.STATUS_STATE)` returns `surface == "coordination"` and `path` is the coordination Mission dir holding the seeded log. Red at the base: `AttributeError`, no method.
     - `test_read_dir_keeps_root_fallback_on_empty` (C-002 control): `read_dir(STATUS_STATE)` on the same fixture returns the repository-root Mission dir. It is green at the base and must stay green.
     - `test_write_dir_primary_kind_is_side_effect_free`: `write_dir(MissionArtifactKind.SPEC)` equals `read_dir(SPEC)`, and creates no worktree.
  2. Implement in `PlacementSeam`, directly after `read_dir`:
     ```python
     def write_dir(self, kind: MissionArtifactKind) -> WriteLocation:
         """Where a write of ``kind`` for this Mission goes (the ONE write-location accessor)."""
         declared = <the same declared-surface decision read_dir uses>
         if declared is TopologySurface.PRIMARY:   # PRIMARY kind, or non-coord topology (C-008)
             return WriteLocation(path=self.read_dir(kind), surface="primary",
                                  coord_state_before=None, establishment=Establishment.NONE)
         from specify_cli.coordination.coord_seed import establish_coord_write_location  # noqa: PLC0415 — lazy cross-layer delegate over the existing ``coordination`` ledger edge (same pattern as RETROSPECTIVE's resolve_retrospective_home)
         return establish_coord_write_location(self.repo_root, self.mission_slug, kind, owned=self.owned)
     ```
     - Reuse the existing private helper that computes `declared_read_surface` (≈L2518-2525). Do not duplicate the decision. If it is only reachable inside `read_dir`'s call chain, extract a tiny private helper `_declared_surface(kind)` that both use.
     - RETROSPECTIVE stays on its own home (PRIMARY partition). Confirm `write_dir(RETROSPECTIVE)` equals `read_dir(RETROSPECTIVE)`.
     - The existing `# noqa: PLC0415` comments in the file show the accepted lazy-import convention. Mirror it, with a rationale.
  3. Check `self.repo_root` / `self.mission_slug` / `self.owned` attribute names on `PlacementSeam`, and adapt.
- **Files**: `src/mission_runtime/resolution.py`, `tests/mission_runtime/test_placement_seam_write_dir.py`.
- **Validation**: the red tests turn green; `tests/architectural/test_layer_rules.py` is green with the ledger unchanged (the import is from `specify_cli.coordination`, already allowed).
- **Edge cases**:
  - `write_dir` must never be called from a read path inside `resolution.py` itself. Grep for accidental use.
  - Exceptions from the delegate propagate unchanged (`CoordinationBranchDeleted`, `CoordinationWorktreeUnmaterialized`, `CoordSeedForkRefused`, `FeatureStatusLockTimeoutError`).
- **`checkout_root` (post-tasks squad P-M3)**: PRIMARY-kind and non-coordination results set `checkout_root` to the repository root checkout. COORD results come from WP03's establish, which sets the coordination worktree root. Cover both in the T020 property test.

### Subtask T019 – Owned-checkout coordination arm

- **Purpose**: Owned checkouts with a coordination topology follow the same rules (spec Edge Cases). `_owned_read_dir_for_kind` (`resolution.py:1272`) raises on EMPTY today, so the owned write path must establish through the owned coordination workspace instead.
- **Steps**:
  1. Read `_owned_read_dir_for_kind` and its `tolerate_unmaterialized_coord` flag. Read the owned workspace selection in `runtime_bridge.py:359-366` (`_resolve_owned_coordination_workspace(CoordinationWorkspace, repo_root, mission_slug, ...)`).
  2. When `self.owned is not None` and the kind is COORD on a coordination topology, `write_dir` still delegates to `establish_coord_write_location(..., owned=self.owned)`. WP03 implemented the owned variant there; this subtask verifies the seam passes `owned` correctly and that the PRIMARY short-circuit for owned Missions resolves to the owned checkout's PRIMARY dir (as `read_dir` does today).
  3. If WP03's owned branch needs a hook only the seam knows (for example the owned PRIMARY root), pass it as an explicit argument. Do not re-derive it inside `coord_seed.py`.
  4. Tests:
     - an owned coordination Mission in the MATERIALIZED state → `write_dir(STATUS_STATE).path` is inside the owned coordination workspace;
     - an owned Mission whose coordination workspace cannot be established → `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` (existing `OwnedRefusalCode`).
     Use the owned-checkout fixtures from `tests/core/test_adopt_owned_checkout.py` / `tests/specify_cli/coordination/test_status_surface_owned.py` as patterns.
- **Files**: `src/mission_runtime/resolution.py`, `tests/mission_runtime/test_placement_seam_write_dir.py`.
- **Validation**: owned tests are green; `tests/specify_cli/coordination/test_status_surface_owned.py` and `test_owned_status_read_contract.py` are unchanged and green.
- **Edge cases**: do not change `_owned_read_dir_for_kind`'s raising behaviour for **reads**. Only the write path gains establishment.

### Subtask T020 – Property tests: agreement and purity

- **Purpose**: `write_dir` agrees with `write_target` by construction (contract: the coordination worktree's branch is `write_target(kind).ref`). The pure seams stay pure, so `resolve_placement_only` can never materialize or seed.
- **Steps**:
  1. Parametrize over every `MissionArtifactKind` × topology (`lanes`, `single_branch`, `coord`, `lanes_with_coord`) on MATERIALIZED fixtures:
     - `loc = seam.write_dir(kind)`; `ref = seam.write_target(kind).ref`.
     - If `loc.surface == "coordination"`: `git -C <worktree root of loc.path> rev-parse --abbrev-ref HEAD == ref`.
     - Else `ref` is the target branch, or the declared PRIMARY ref for that kind.
     - For `lanes` / `single_branch`: `loc.path == seam.read_dir(kind)` (byte-identical, C-008).
  2. **Purity**: on an UNMATERIALIZED / EMPTY fixture, call `resolve_placement_only(...)`, `seam.write_target(kind)` and `seam.read_dir(kind)` for every kind. Then assert that no worktree was created, no Mission dir appeared on the coordination surface, and no ref moved (snapshot `git for-each-ref` before and after; `git worktree list --porcelain` before and after).
  3. Assert the `WriteLocation` returned for COORD kinds has an existing `path` (contract postcondition).
- **Files**: `tests/mission_runtime/test_placement_seam_write_dir.py`.
- **Validation**: green, and fast enough to stay in the fast tier where possible. Mark git-heavy cases with `git_repo`.
- **Edge cases**: kinds whose PRIMARY ref is not the target branch (owned or verbatim refs). Compare against `write_target`, not a hard-coded branch.

### Subtask T021 – Loud EMPTY for post-fix Missions (read side)

- **Purpose**: US2.7 / FR-003a. After this Mission, every create seeds the coordination surface (WP06), so an EMPTY coordination worktree on a **post-fix** Mission signals a regression and must be loud, for both topologies.
  - Today only `lanes_with_coord` warns; solo `coord` is quiet by design (#2533, WP08 T029 comment).
  - Pre-fix Missions keep today's behaviour.
  - Reads keep the fallback to the repository root checkout (C-002).
- **Steps**:
  1. In the EMPTY-branch helper WP01 extracted from `resolve_status_surface_with_anchor` (`surface_resolver.py`, the block at ≈L1430-1450), add the post-fix discriminator, research D4:
     ```python
     post_fix = coord_branch_is_post_fix(repo_root, coordination_branch, mission_id)  # WP03's trailer discriminator (COORD_SEED_TRAILER); round 4
     if post_fix or effective_topology is MissionTopology.LANES_WITH_COORD:
         logger.warning(_COORD_EMPTY_FALLBACK_WARNING, {...})
     return ResolvedStatusSurface(surface_path=feature_dir / _STATUS_EVENTS_FILENAME, primary_anchor=feature_dir)
     ```
  2. The probe is a **read-only** git call (a trailer lookup in the coordination branch history; ~~`git ls-tree`~~ struck in round 4). Import WP03's single discriminator lazily; never redefine it. That keeps the function pure (no writes, no materialization); it is reached from `resolve_placement_only`. WP03 defines it (with `COORD_SEED_TRAILER`) in `coord_seed.py`; import it lazily (single authority). ~~Otherwise define it here~~ is struck in round 5: WP03 always provides it.
  3. Optionally extend the warning text with "post-fix Mission: the coordination Mission dir was removed from the worktree; writes will restore it from the branch tip". Keep the existing placeholders, and keep the existing tests' message match green.
  4. Tests in `tests/coordination/test_surface_resolver_post_fix_empty_loud.py`:
     - post-fix `coord` → warns (`caplog`);
     - post-fix `lanes_with_coord` → warns;
     - pre-fix `coord` → quiet (today's #2533 behaviour);
     - pre-fix `lanes_with_coord` → warns (today);
     - all four → the returned surface is the root dir (C-002).

     Build the post-fix fixture through **WP03's real seed** (round 5, X2; WP03 is in your base): a pre-fix EMPTY Mission (`make_prefix_coord_mission(worktree="empty")`), then `write_dir(STATUS_STATE)` → SEEDED with the trailer, then delete the dir in the worktree. ~~A manual commit of the Mission dir~~ is struck: it carries no trailer and so is not post-fix.
- **Files**: `src/specify_cli/coordination/surface_resolver.py`, `tests/coordination/test_surface_resolver_post_fix_empty_loud.py`.
- **Validation**: existing `tests/coordination/test_surface_resolver_coord_empty_warning.py`, `test_surface_resolver_solo_coord_primary.py` and `tests/specify_cli/coordination/test_legacy_warning_classifier.py` stay green unchanged. If one pins "solo coord never warns" for a fixture that is actually post-fix-shaped, stop: report it rather than re-pin it, because it means the fixture is mislabelled.
- **Edge cases**:
  - The extra trailer lookup costs one subprocess on the EMPTY branch only, which is the rare path. Do not run it on MATERIALIZED.
  - A missing coordination branch is DELETED, a separate branch of the resolver. Leave it unchanged.

### Subtask T022 – Correct stale in-code contract text

- **Purpose**: The code-comment half of FR-017. The docstrings must state shipped behaviour: writes never substitute the repository root checkout; reads keep the declared, loud PRIMARY fallback.
- **Steps**:
  1. `resolution.py`:
     - Docstrings around ≈L2338-2343 (read_dir's "EMPTY/UNMATERIALIZED (the create-window) … resolves identically" paragraph): add that writers must use `write_dir`, which never substitutes the root checkout.
     - ≈L2442-2443 (`ResolvedSurface`, "a PRIMARY stamp on a substituted surface (the EMPTY / UNMATERIALIZED create window)").
     - ≈L2672-2673 (`resolve_artifact_surface`, "EMPTY / UNMATERIALIZED resolve the primary dir, stamped PRIMARY").
     - In each: state "read side only; the write side is `PlacementSeam.write_dir`, which materializes/seeds/refuses".
     - Re-derive the exact lines with grep; they may have shifted after T018.
  2. In `surface_resolver.py`, document that `resolve_status_surface_with_anchor(for_write=True)` is "commit-ref oriented, not a write location; must stay pure (reached from `resolve_placement_only`)".
  3. In `missions/_read_path_resolver.py:259-260`, reword the `CoordState.EMPTY` bullet to: "coord worktree root exists but its Mission dir is absent. Read: loud declared PRIMARY fallback (C-002); write: seed or restore via `PlacementSeam.write_dir`." Keep the rest of the docstring.
  4. No behaviour change in this subtask. If a test asserts on docstring text (rare; grep), keep it green.
- **Files**: `src/mission_runtime/resolution.py`, `src/specify_cli/coordination/surface_resolver.py`, `src/specify_cli/missions/_read_path_resolver.py`.
- **Validation**: `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q` (terminology guard), and ruff on the files.
- **Edge cases**: avoid the retired terms the terminology guard rejects. Say Mission (never feature) and name each sense of "primary".

## Binding corrections — analyze + brownfield scout (round 3)

> These corrections are binding and **override any conflicting text earlier in this prompt**. Source: `analysis-report.md` and the brownfield scout notes (pointer in Context & Constraints). Operator decisions are quoted where they apply.

- **Single write authority**: WP03 made `assert_coord_write_materialized` a delegate of `establish_coord_write_location`. `write_dir` uses the same accessor; there must be no second write-side decision.
- **PUBLISHED / E2 case (operator decision; scout X2)**: after consolidation, `REVIEW_CYCLE`, `TRACER_FILE`, `ISSUE_MATRIX` and `ACCEPTANCE_MATRIX` resolve to the **target branch** (`_E2_CONSOLIDATED_ELIGIBLE_KINDS`, `resolution.py:191-199`).
  - `write_dir` follows that existing resolution **before** any coordination-state probe. It returns the PRIMARY dir with `checkout_root` = the main repo root, never raises `CoordinationBranchDeleted` and never writes into a torn-down worktree.
  - Add this to T018 with tests: a consolidated Mission fixture (coordination branch deleted) where `write_dir(REVIEW_CYCLE|TRACER_FILE|ISSUE_MATRIX|ACCEPTANCE_MATRIX)` gives a PRIMARY location with no raise; `STATUS_STATE` follows whatever `write_target` resolves today.
- **No `# noqa: PLC0415`**: the rule is not selected (pyproject.toml:2446-2468), so the suppression is unused (NFR-005). The precedent lazy import at `resolution.py:2356` carries none.
- **Declared surface**: call the public, owned-aware `declared_read_surface(repo_root, slug, kind, owned=self.owned)` (`resolution.py:2451`). Do not extract a new `_declared_surface`.
- **`checkout_root` for PRIMARY** must be the main repo root via `get_main_repo_root` (the re-anchor in `read_dir`, L2346-2355), or `owned.owned_root`, never `self.repo_root` verbatim. Pin this in T020 by calling from a lane worktree.
- **Exceptions**: `CoordinationBranchDeleted` and `CoordinationWorktreeUnmaterialized` are `StatusReadPathNotFound` subclasses (surface_resolver.py:191, :292), not `ActionContextError`. `write_dir` propagates them; say so in the docstring for WP07+ writers.
- **D4 / naming fix (operator decision)**:
  - fix `coord_branch_has_committed_artifact` (surface_resolver.py:786) to compose the Mission dir via `coord_mission_dir_name` / `_compose_mission_dir(slug, mid8)` instead of `kitty-specs/{mission_slug}/`;
  - make the git-error arm explicit rather than a silent fail-closed `True`;
  - drive the loud post-fix warning from WP03's discriminator (one definition);
  - widen `_empty_coord_surface`'s private signature here (`repo_root`, `coord_branch`; WP01 could not, because of ruff ARG).
  - Negative test: the `test_surface_resolver_solo_coord_primary.py:107-146` pre-fix shape does not get the post-fix loud warning.
- **Duplicate warnings**: the EMPTY warning is reachable from `resolve_placement_only` (`_assemble_core_fragments(for_write=True)`). Gate it on `not for_write` (or dedupe) so that `write_target`/commit-ref queries do not warn repeatedly; `establish` warns once.
- **Purity probe**: `probe_coord_state`'s DELETED arm may hit the network, so the T020 snapshot fixtures are remote-less.
- `write_dir` must not construct a `CommitTarget` (`test_no_write_side_rederivation.py` scans constructions).
- **G2**: FR-017 is now in requirement_refs (T022 delivers its code-comment half).
- Valid guards: `test_surface_resolver_coord_empty_warning.py` :127 and :179 (the latter is pre-fix under the corrected discriminator).
- **I10 (round 4)**: the PUBLISHED/E2 arm implements **research D23**. The single write authority it agrees with is **D22** (WP03).

## Targeted test surface

- Baseline: `make test-fast`.
- This WP:
  ```bash
  uv run --frozen pytest tests/mission_runtime/test_placement_seam_write_dir.py tests/coordination/test_surface_resolver_post_fix_empty_loud.py -q
  uv run --frozen pytest tests/mission_runtime/ -q
  uv run --frozen pytest tests/coordination/test_surface_resolver_coord_empty_warning.py tests/coordination/test_surface_resolver_collapse.py tests/coordination/test_surface_resolver_solo_coord_primary.py tests/coordination/test_coord_seed.py tests/coordination/test_materialize_coord_surface.py -q
  uv run --frozen pytest tests/specify_cli/coordination/test_coord_topology_states.py tests/specify_cli/coordination/test_status_surface_owned.py tests/specify_cli/coordination/test_owned_status_read_contract.py tests/specify_cli/coordination/test_legacy_warning_classifier.py tests/status/test_aggregate_surface_resolution.py -q
  ```
- Named architectural gate files only:
  - `tests/architectural/test_layer_rules.py`
  - `tests/architectural/test_status_state_read_dir_single_authority.py`
  - `tests/architectural/test_no_write_side_rederivation.py` (unchanged here; must stay green)
  - `tests/architectural/test_no_legacy_terminology.py`
  - `tests/architectural/test_no_dead_symbols.py` (`establish_coord_write_location` now has a caller)
- Never run the bare `tests/architectural/`, any e2e/integration directory, performance/stress suites or `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION, C-006).
- Record commands and counts in the Activity Log. Classify unrelated reds with the CLAUDE.md baseline-red gotcha.

## Quality gates

- C901 ≤ 15 for every touched function (NFR-004). The EMPTY helper from WP01 has headroom; keep `write_dir` trivial.
- `ruff check`, `ruff format --check` and `mypy --strict` are clean on changed files (NFR-005). The lazy import carries the file's existing `# noqa: PLC0415` convention with a rationale; no other suppression.
- ≥ 90% coverage of new lines (NFR-003): every `write_dir` branch, both topologies and the owned arm are tested.
- **Mission tracer files (analyze C4; charter Standing Order 3)**: at every decision point and every friction, append a dated entry through the canonical CLI, e.g. `spec-kitty agent tracer-append --mission coord-artifact-single-home-01M3V4BE --category design-decisions|approach|tooling-friction --entry "<YYYY-MM-DD WPxx: …>" --actor <you>`. The files are `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md`.
- **Pre-existing Failure Reporting Rule (analyze C4; charter)**: a red you did not cause and that is red on your base MUST be reported. Record the test id, the exact command and the evidence (output, base SHA) in the activity log and notify the orchestrator, who files the GitHub issue. Never fix it silently, never green-wash it, never xfail it.

## Issues

Issues: #5519 #2533

## Definition of Done

- `PlacementSeam.write_dir` exists. It returns `WriteLocation`, short-circuits PRIMARY and non-coordination cases with no side effects, and delegates COORD kinds lazily.
- Owned coordination arm tested.
- Agreement and purity properties pinned for every kind × topology.
- Post-fix EMPTY warns for both topologies; pre-fix behaviour unchanged; read fallback kept.
- Stale docstrings and the `CoordState.EMPTY` contract text corrected.
- The layer ledger has not grown; static gates are clean; the red-first commit precedes the implementation.

## Risks & Mitigations

- **Import cycle** (`resolution.py` ↔ `coord_seed.py` ↔ `write_location.py`). Mitigation: a types-only `write_location.py` and a lazy import inside `write_dir`.
- **Purity regression**: a read path accidentally calling `write_dir`. Mitigation: the T020 purity test plus grep review.
- **Over-loud warning** on genuinely pre-fix solo `coord` Missions. Mitigation: the D4 discriminator, and explicit pre-fix controls.
- **Owned-checkout divergence.** Mitigation: route through the same owned workspace resolver the runtime bridge uses.

## Review Guidance

- Reviewer: opus, distinct from the implementer.
- Verify red→green: the T018 red tests are RED on the WP's base (lane-A base before the fix commits: `write_dir` missing) and GREEN on the final commit. The C-002 read-fallback control is green on both.
- Confirm:
  - there is no second write-location entry point (DIRECTIVE_044);
  - `resolve_placement_only` / `write_target` / `read_dir` are unchanged in behaviour;
  - the ledger cap is unchanged;
  - the EMPTY warning logic uses WP03's trailer discriminator (no meta flag; ~~branch-tree discriminator~~ struck);
  - the docstring changes match shipped behaviour.

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

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Why this matters**: The acceptance system reads the LAST activity log entry as the current state. If entries are out of order, acceptance will fail even when the work is complete.

**Initial entry**:

- 2026-10-01T08:36:27Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
