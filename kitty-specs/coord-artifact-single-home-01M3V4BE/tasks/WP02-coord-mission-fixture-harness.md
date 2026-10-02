---
work_package_id: WP02
title: Shared coordination-routed Mission fixture harness (IC-02)
dependencies: []
requirement_refs:
- FR-016
- C-005
- NFR-002
planning_base_branch: issue-5440-coord-artifact-single-home
merge_target_branch: issue-5440-coord-artifact-single-home
branch_strategy: Planning artifacts for this mission were generated on issue-5440-coord-artifact-single-home. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5440-coord-artifact-single-home unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-artifact-single-home-01M3V4BE
base_commit: c833721eb3c4ac284f1c32443a292e81969d99ae
created_at: '2026-10-01T10:12:33.617888+00:00'
subtasks:
- T008
- T009
- T010
- T011
phase: Phase 0 - Campsite and harness
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-01T08:36:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/_factories/
create_intent:
- tests/_factories/coord_mission.py
- tests/coordination/conftest.py
- tests/coordination/test_coord_mission_factory.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/_factories/coord_mission.py
- tests/coordination/conftest.py
- tests/coordination/test_coord_mission_factory.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Shared coordination-routed Mission fixture harness (IC-02)

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

Deliver the **one shared fixture harness** that every red-first reproduction in this Mission uses (FR-016, C-005, research "Red-first reproduction list"). It must construct each shape listed below, through the **production create path** or explicitly by hand.

**Production create path**:
- `create_mission_core`;
- the CLI `spec-kitty agent mission create --pr-bound --start-branch <topic>`;
- the CLI `spec-kitty agent mission create --topology coord|lanes_with_coord`.

**Shapes**:
- a coordination-routed Mission, parametrized over `coord` and `lanes_with_coord`;
- a **pre-fix shape**: root-checkout status log, coordination branch without the Mission dir, worktree absent or empty. It is built explicitly, so it stays valid after WP06 changes create;
- the four **NFR-002 fork fixtures**;
- probes for event ids, logical clocks, commit-range path history and coordination-branch trees.

**Success means**:
- `from tests._factories.coord_mission import make_coord_mission, make_prefix_coord_mission, make_fork_fixture, event_ids, lamports, commits_touching, coord_tree_has` works from any test module.
- `tests/coordination/conftest.py` exposes pytest fixtures wrapping them.
- `tests/coordination/test_coord_mission_factory.py` proves each builder produces its documented shape **at the current base**. These are green tests: this WP is the harness, not a fix.
- Later WPs (WP03-WP21) import from it rather than hand-rolling coordination fixtures.

## Context & Constraints

- **Load the charter**: `.kittify/charter/charter.md` and `spec-kitty charter context --action implement --json`.
- **Plan**: IC-02 ("Red-first reproduction harness"), including the risk that every reproduction lands with the WP that turns it green, and never as `xfail`. That is why this WP contains **no reproductions**; it only builds shapes.
- **Spec**:
  - FR-016 (red-first reproductions);
  - NFR-002 (the four fork fixtures: root uncommitted + coordination untracked, the #5519 shape; root committed on target + coordination committed; fresh clone; ledger only on the coordination branch);
  - US1 "Independent Test" (production create path, both coordination topologies);
  - C-005.
- **Data model**: §4, fork-report value objects (what the fork fixtures must make detectable); §6, coordination surface lifecycle (the UNMATERIALIZED / EMPTY / MATERIALIZED / DELETED states the builders must reach).
- **Existing factory**: `tests/_factories/__init__.py::make_mission` wraps `create_mission_core` and calls `provision_test_charter`. `create_mission_core` hard-requires an activated mission type and raises `CharterPackConfigError` without provisioning, so reuse `provision_test_charter`.
  - Signature: `create_mission_core(repo_root, mission_slug, *, topology=MissionTopology.COORD, pr_bound=False, target_branch=None, ...)` at `src/specify_cli/core/mission_creation.py:760`.
- **Topology caveat (CLAUDE.md "Create-time topology")**: in a repo with no `origin/HEAD`, primary-branch detection falls back to the current branch. Always pass the topology explicitly, and set up a remote with `origin/HEAD` for the `--pr-bound --start-branch` path.
- **Git template**: `tests/_support/git_template` provides a fast template. Reuse it, and the repo's `git_repo` marker (pytest.ini), where practical.
- **Model discipline**: implement = sonnet (`claude-sonnet-5`); review = opus.
- **Terminology**: Mission, never feature. Say "repository root checkout" or "target branch"; never bare "primary".
- **No heavy suites** (C-006).
- **Fixture semantics across lanes (post-tasks squad P-m5):** pre-fix assertions use WP02's `make_prefix_coord_mission`; `make_coord_mission` carries only shape-agnostic invariants (its shape changes when WP06 lands); use `make_coord_mission(..., materialized=True)` when a test needs a deterministic MATERIALIZED coordination surface in every lane.
- **Brownfield scout (binding read)**: before coding, read `## WP02` in `kitty-specs/coord-artifact-single-home-01M3V4BE/research/brownfield-scout-wp01-11.md` (plus its "Cross-cutting" section where present). Its corrections are folded into the "Binding corrections" section below, which overrides conflicting text above.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5440-coord-artifact-single-home; completed changes must merge back into issue-5440-coord-artifact-single-home.
- **Planning base branch**: `issue-5440-coord-artifact-single-home`
- **Merge target branch**: `issue-5440-coord-artifact-single-home`
- `finalize-tasks` allocates execution worktrees per computed lane from `lanes.json`.
- Start with `spec-kitty agent action implement WP02 --agent claude` and use the printed workspace path.
- **Lane-relevant shared files**: none. This WP owns only new test files, runs in its own lane, and can run in parallel with WP01 and WP11 from the start.

## Subtasks & Detailed Guidance

### Subtask T008 – Production-path factory `make_coord_mission`

- **Purpose**: One call yields a coordination-routed Mission created exactly the way an operator creates it, so a reproduction exercises the real create path (spec R10 / US1 Independent Test).
- **Steps**:
  1. Create `tests/_factories/coord_mission.py`, with a module docstring that cites this Mission and FR-016.
  2. Define a frozen dataclass `CoordMission`:
     ```python
     @dataclass(frozen=True)
     class CoordMission:
         repo_root: Path
         mission_slug: str
         mid8: str
         mission_dir_name: str          # kitty-specs/<dir> name as created
         topology: MissionTopology
         target_branch: str
         coordination_branch: str       # from meta.json
         coord_worktree_path: Path      # CoordinationWorkspace.worktree_path(...)
         creation_base_sha: str         # target tip BEFORE create ran
         @property
         def root_mission_dir(self) -> Path: ...
         @property
         def coord_mission_dir(self) -> Path: ...
     ```
  3. `make_coord_mission(tmp_path, topology, *, via="core", slug="demo", protected_primary=False) -> CoordMission`:
     - **Repo setup**: init a repo (template if available), `git config user.email/name`, initial commit, provision the charter (`provision_test_charter`), commit. For `via != "core"`, run `spec-kitty init . --ai claude --non-interactive` if the CLI path needs it; mirror the quickstart.md §0 fixture.
     - **`via="core"`**: create topic branch `topic`, record `creation_base_sha = git rev-parse topic`, then call `create_mission_core(repo_root, slug, topology=topology, target_branch="topic")`.
     - **`via="cli_topology"`**: on `topic`, run `spec-kitty agent mission create <slug> --topology <t> --branch-strategy already-confirmed --json` through the project's CLI test helper (find the established invoker: `CliRunner` over the Typer app, or a `subprocess` helper in `tests/_support`), then parse `mission_slug` / `coordination_branch` from the JSON.
     - **`via="cli_pr_bound"`**: from `main` (with a bare remote and `origin/HEAD` set), run `... --topology <t> --pr-bound --start-branch topic --branch-strategy already-confirmed --json`. Always pass `--topology` explicitly: `--pr-bound` alone resolves `lanes` on an unprotected primary branch (`_resolve_default_topology_phase`, `cli/commands/agent/mission_create.py:372`). Assert `meta.json` `topology` equals `<t>` after create so a factory call can never silently hand back a `lanes` Mission.
     - **`protected_primary=True`**: configure the primary branch as protected the way `ProtectionPolicy.resolve` reads it. Locate the config knob via `grep -rn "protected" src/specify_cli/policy/`. It is used by WP06's US1.4 test.
     - Read `meta.json` from the root Mission dir to fill `mid8`, `coordination_branch` and `target_branch`. Compute `coord_worktree_path` with `CoordinationWorkspace.worktree_path(repo_root, mission_slug, mid8)` (`src/specify_cli/coordination/workspace.py:270`).
  4. Export a helper `COORD_TOPOLOGIES = (MissionTopology.COORD, MissionTopology.LANES_WITH_COORD)` for `pytest.mark.parametrize`.
- **Files**: `tests/_factories/coord_mission.py`.
- **Validation**: T011 tests assert `meta.json["topology"]` equals the requested topology and that the coordination branch exists, for every `via` × topology combination.
- **Edge cases**:
  - The factory must not assume create's **current** placement of `status.events.jsonl`. After WP06 lands, the log is on the coordination branch and the root has none. Fields and probes must work for both.
  - Return values must be plain values; do not keep CLI runners open.

### Subtask T009 – Pre-fix shape builder `make_prefix_coord_mission`

- **Purpose**: Several reproductions need a Mission "created before this fix": status log in the repository root checkout (committed on the target branch), coordination branch cut **without** the Mission dir. Examples:
  - seed tests (WP03);
  - writer migrations (WP07, WP09, WP10);
  - consolidation R22 (WP18);
  - R6's legacy control (WP06).

  After WP06, create no longer produces that shape, so the builder must construct it **explicitly**.
- **Steps**:
  1. `make_prefix_coord_mission(tmp_path, topology, *, worktree="absent"|"empty", remote_only=False, branch_deleted=False, extra_events=0) -> CoordMission`.
  2. Construction:
     - create the repo and charter as in T008, plus a topic branch;
     - write `meta.json` through the production meta builder if reachable (preferred: call `create_mission_core`, then **rewrite** the outcome into the pre-fix shape);
     - ensure `kitty-specs/<dir>/status.events.jsonl` with `MissionCreated` and `SpecifyStarted` events, produced by the production emitter, exists in the root checkout and is committed on the target branch;
     - ensure the coordination branch tip does **not** contain `kitty-specs/<dir>/`; reset it to the pre-create commit if create seeded it;
     - remove the coordination worktree (`worktree="absent"`, state UNMATERIALIZED), or leave the worktree root without the Mission dir (`worktree="empty"`, state EMPTY).
  3. Variants:
     - `remote_only=True`: push the coordination branch to a bare `origin` and delete the local branch (the #4970 remote-only case);
     - `branch_deleted=True`: delete the branch everywhere (DELETED);
     - `extra_events=N`: append N status events in the root checkout, uncommitted.
  4. Assert the resulting state with the production probe `probe_coord_state` (`src/specify_cli/missions/_read_path_resolver.py`, `CoordState` at L250-275) inside the builder. A mis-built fixture then fails loudly at construction, never silently.
- **Files**: `tests/_factories/coord_mission.py`.
- **Validation**: T011 asserts `probe_coord_state(...)` returns `UNMATERIALIZED`, `EMPTY` or `DELETED` per variant, and that `git ls-tree -r <coord> -- kitty-specs/<dir>` is empty.
- **Edge cases**:
  - Rewriting create's output must not leave a stale coordination worktree registration. Run `git worktree prune` after removal.
  - On a remote-only branch, the probe may need the remote fetched. Follow the existing remote-probe tests (`tests/specify_cli/coordination/test_coord_branch_remote_probe_4979.py`).
- **`materialized=True` option (post-tasks squad R-M4)**: `make_coord_mission(..., materialized=True)` returns a seeded, **MATERIALIZED** coordination surface in every lane, independent of whether WP06 has landed. WP02 cannot depend on WP04 (`write_dir`), because that would be a cycle WP02 → WP04 → WP03 → WP02. Build it explicitly with git:
  1. Ensure the coordination worktree exists at `coord_worktree_path`, using `git worktree add` on the coordination branch, or `CoordinationWorkspace.resolve` if that is pure enough.
  2. If the coordination branch tree lacks `kitty-specs/<dir>/`, copy the creation events (MissionCreated/SpecifyStarted) into `<coord wt>/kitty-specs/<dir>/status.events.jsonl` and commit them on the coordination branch (`chore(<mission>): fixture seed`). Copy COORD records only, never `meta.json` (US1.3).
  3. Assert the production coordination-state probe reports MATERIALIZED (the `CoordState` classifier in `missions/_read_path_resolver.py`; find the exact probe function, e.g. `probe_coord_state`) before returning. The builder fails loudly otherwise.
  WP13/WP14/WP15 use this so their red-first fixtures hold at their lane base (WP01–WP05), where create does not yet seed.
- **Shape caveat (round 5, X2)**: `materialized=True` produces a **pre-fix-shaped** MATERIALIZED surface. Its fixture commit carries **no** `Spec-Kitty-Coordination-Seed` trailer; WP02 runs first and cannot import WP03's `COORD_SEED_TRAILER`. It is the right fixture for "MATERIALIZED, coordination copy dirty" preconditions (WP13/WP14/WP15/WP19), but it is **not** a post-fix Mission.
- **Helper note: post-fix fixtures come from WP03's real seed.** Build them from a pre-fix EMPTY Mission (`make_prefix_coord_mission(worktree="empty")`), then call `placement_seam(...).write_dir(STATUS_STATE)` → SEEDED with the trailer committed, then delete the coordination Mission dir if an EMPTY post-fix state is needed. WP04, WP07 and later WPs do this in their own tests; WP02 only documents it.

### Subtask T010 – NFR-002 fork fixtures and probes

- **Purpose**: These fixtures are shared by WP03 (seed fork refusal), WP17 (doctor fork detection, repair, verify) and WP21. They let tests count "0 entries lost, 0 events lost, no id twice" (NFR-002, SC-004).
- **Steps**:
  1. `make_fork_fixture(tmp_path, shape, topology=COORD) -> ForkFixture`, where `ForkFixture` extends `CoordMission` with `decision_ids_root`, `decision_ids_coord` and `clone_root: Path | None`. Shapes:
     - **(a) `"root_uncommitted_coord_untracked"`** (the #5519 shape): pre-fix Mission; the first decision is opened in the root checkout (uncommitted); a coordination Mission dir then exists with a second, diverging decision event (untracked in the coordination worktree). The two status logs are non-empty and neither event-id sequence is a prefix of the other.
     - **(b) `"both_committed"`**: like (a), but the root copy is committed on the target branch and the coordination copy is committed on the coordination branch.
     - **(c) `"fresh_clone"`**: `git clone` of (b) into `clone_root`, fetching both branches as local branches, with no coordination worktree. Fork detection must work from refs.
     - **(d) `"ledger_only_on_coordination"`**: `decisions/DM-<ulid>.md` plus `decisions/index.json` committed **only** on the coordination branch (the pre-fix #3928 placement), absent from the root checkout and the target branch.
  2. Produce decision events with the production emitters where possible: `specify_cli.decisions.service` open/resolve, writing into a chosen dir. If the service now routes elsewhere (later WPs change it), fall back to the event model plus `append_event` from `specify_cli.status.store` or the decisions event writer. Keep event JSON production-shaped (`event_id`, `event_lamport`, `event_type`, ...).
  3. Probes (pure helpers):
     - `event_ids(source: Path | tuple[Path, str, str]) -> tuple[str, ...]`: from a file, or from `(repo, ref, relpath)` via `git show`;
     - `lamports(...)`: same sources, returning the logical clocks;
     - `commits_touching(repo, rev_range, relpath) -> list[str]`: `git log --format=%H <range> -- <path>`;
     - `coord_tree_has(repo, branch, relpath) -> bool`: `git ls-tree`;
     - `index_entry_ids(path_or_blob) -> set[str]`: reads `decisions/index.json`.
- **Files**: `tests/_factories/coord_mission.py`.
- **Validation**: T011 asserts, for each shape:
  - (a)/(b): the two sequences are non-empty and non-prefix; for (a) the decision ids differ per surface.
  - (c): no worktree, but `event_ids((clone, coord_branch, path))` is non-empty.
  - (d): the ledger is present on the coordination ref only.
- **Edge cases**:
  - Event ids are ULIDs. Generate them with the production id minting, not hard-coded strings that might collide.
  - `lamports` must parse the field name the status model actually uses. Check `src/specify_cli/status/models.py` for `event_lamport` or its equivalent before coding it.

### Subtask T011 – Pytest fixtures and factory self-tests

- **Purpose**: Make the harness ergonomic for pytest, and pin that each builder keeps producing its documented shape. A broken fixture would make every later red-first test vacuous.
- **Steps**:
  1. `tests/coordination/conftest.py` (new; `tests/coordination/` currently has no conftest and no `__init__.py`). Define:
     - `coord_mission` (parametrized over both topologies via `params=`);
     - `prefix_coord_mission` (default `worktree="empty"`);
     - `fork_fixture` (indirect-parametrizable by shape).

     Fixtures delegate to `tests._factories.coord_mission`, which is the importable helper other test directories use. Check that the root `tests/conftest.py` already puts the repository root on `sys.path`, so `tests._factories` imports; `tests/_factories/__init__.py` exists.
  2. `tests/coordination/test_coord_mission_factory.py` holds one test per builder and variant (green at the current base):
     - every `via` × topology: topology recorded, coordination branch exists, `creation_base_sha` is an ancestor of the target tip;
     - pre-fix variants: probe state as documented; the root log has `MissionCreated`;
     - each fork shape: the assertions listed in T010;
     - probes on a tiny hand-made repo (`commits_touching` empty versus non-empty).
  3. Markers:
     - mark git-heavy tests with `git_repo` (pytest.ini);
     - pure probe tests with `fast`/`unit`;
     - none of these may need `slow` (target < 30 s per test).
  4. In the module docstring, add a short "How later WPs use this" section listing the R-ids that rely on each builder (research red-first list): R1/R1b/R6/R20 (WP06), R2 (WP05), R3/R14/R15/R16 (WP17), R4 (WP09), R22/R23/R24 (WP18).
- **Files**: `tests/coordination/conftest.py`, `tests/coordination/test_coord_mission_factory.py`.
- **Validation**: `uv run --frozen pytest tests/coordination/test_coord_mission_factory.py -q` is green. Run the whole `tests/coordination/` directory once, to prove the new conftest breaks no existing test there (name clashes with existing fixtures).
- **Edge cases**: fixture names must not shadow existing fixtures in `tests/conftest.py`. Grep for `def coord_mission` / `prefix_` before naming.

## Binding corrections — analyze + brownfield scout (round 3)

> These corrections are binding and **override any conflicting text earlier in this prompt**. Source: `analysis-report.md` and the brownfield scout notes (pointer in Context & Constraints). Operator decisions are quoted where they apply.

- **DELETED variant**: `probe_coord_state(..., coordination_branch=None)` (`_read_path_resolver.py:278`) returns DELETED **only when `coordination_branch=` is passed**. `_coord_branch_exists` (surface_resolver.py:688) checks the local head, then `refs/remotes/`, then a network `remote_branch_lookup` (HIT or ERROR count as present). So `branch_deleted=True` must remove the local head, the remote-tracking ref and the bare-remote branch, or use no remote at all. Keep fixtures remote-less unless `remote_only=True`; an unreachable remote is a flake vector.
- **`lamports` probe**:
  - status rows carry `lamport_clock` (lifecycle envelope) or nothing (`MissionCreated`);
  - decision rows carry no Lamport field; the CLI's `event_lamport` is a line-count proxy (`decisions/emit.py:97,140`).
  - The probe must tolerate a missing field per row.
- **Two decision streams**: DecisionPoint* rows go into `status.events.jsonl` (via `decisions/emit.py:88`), and `DecisionGitLog` writes `decisions.events.jsonl` (`events/decision_log.py:119`). Fork fixtures (a) and (b) must say which stream diverges; provide per-stream variants, because WP03's prefix rule runs per stream.
- **Fork fixture (d)**, the ledger only on the coordination branch, is built with git plumbing; WP17's R16 needs it.
- **`materialized=True` must use a real `git worktree add`**. MATERIALIZED vs EMPTY is decided by `Path.exists()` on the worktree root, so a plain `mkdir` reads EMPTY.
- Fixture name `coord_mission` also exists in other directory-scoped conftests (`tests/terminus/conftest.py:1351`, …). That is fine, but never import two `CoordMission` classes into one module.
- `hypothesis` is not a dependency; property tests use a seeded RNG.
- **I4**: WP19 is **not** a parallel root. It depends on this WP; the roots are WP01, WP02 and WP11.
- **Red evidence (analyze C2)**: exempt. This WP is the harness and its self-tests are green by design.

## Targeted test surface

- Baseline: `make test-fast`.
- This WP:
  ```bash
  uv run --frozen pytest tests/coordination/test_coord_mission_factory.py -q
  uv run --frozen pytest tests/coordination/ -q                 # no fixture clash in the directory the conftest governs
  uv run --frozen pytest tests/_factories/test_make_mission_parity.py -q
  ```
- Named architectural gate files only: none required (test-only change). If you add any `src/` import shim, stop: this WP owns no `src/` file.
- Never run the bare `tests/architectural/`, any e2e/integration directory, performance/stress suites or `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION, C-006).
- Record commands and counts in the Activity Log. Classify unrelated reds with the CLAUDE.md baseline-red gotcha.

## Quality gates

- C901 ≤ 15 for every function (NFR-004). Builders are naturally long, so split them into private step helpers.
- `ruff check`, `ruff format --check` and `mypy --strict` are clean on the three new files (NFR-005). Tests are typed too: annotate fixtures and helpers.
- ≥ 90% coverage of the new helper module from the self-tests (NFR-003).
- **Mission tracer files (analyze C4; charter Standing Order 3)**: at every decision point and every friction, append a dated entry through the canonical CLI, e.g. `spec-kitty agent tracer-append --mission coord-artifact-single-home-01M3V4BE --category design-decisions|approach|tooling-friction --entry "<YYYY-MM-DD WPxx: …>" --actor <you>`. The files are `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md`.
- **Pre-existing Failure Reporting Rule (analyze C4; charter)**: a red you did not cause and that is red on your base MUST be reported. Record the test id, the exact command and the evidence (output, base SHA) in the activity log and notify the orchestrator, who files the GitHub issue. Never fix it silently, never green-wash it, never xfail it.

## Issues

Issues: none owed directly (harness for the FR-016 reproductions).

## Definition of Done

- `tests/_factories/coord_mission.py` exposes:
  - `make_coord_mission`, `make_prefix_coord_mission`, `make_fork_fixture`;
  - the probes `event_ids`, `lamports`, `commits_touching`, `coord_tree_has`, `index_entry_ids`;
  - `COORD_TOPOLOGIES`.
- `tests/coordination/conftest.py` fixtures exist, and the whole `tests/coordination/` directory still passes.
- Self-tests are green at the current base for every builder and variant.
- The pre-fix builder constructs its shape explicitly and validates it with the production probe.
- ruff, format and mypy --strict are clean.

## Risks & Mitigations

- **Fixture drifts when create changes (WP06).** Mitigation: the pre-fix builder rewrites create's output into an explicit shape and validates it with `probe_coord_state`.
- **Slow fixtures** multiply across many tests. Mitigation: the git template, minimal commits, and avoiding the CLI path except when `via` asks for it.
- **Production-emitter routing changes in later WPs** (decision writers move in WP09). Mitigation: the fork builders write events into an explicit dir through low-level append helpers, so they never depend on the routing under test.
- **Fixture-name collisions.** Mitigation: grep first, and use distinctive names.

## Review Guidance

- Reviewer: opus, distinct from the implementer.
- This WP has no product red test, because it is the harness. Verify instead:
  1. the self-tests pass on the WP's final commit;
  2. each builder's docstring matches its asserted shape;
  3. the pre-fix builder does not depend on create's current status-log placement;
  4. probes use git plumbing (`git show`, `git ls-tree`, `git log --format=%H`) rather than parsing porcelain;
  5. no `src/` file changed.

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
