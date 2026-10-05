---
work_package_id: WP02
title: 'Track A: directory alias authority and partition classification'
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-003
- FR-004
- FR-005
planning_base_branch: issue-5611-5419-nightly-green
merge_target_branch: issue-5611-5419-nightly-green
branch_strategy: Planning artifacts for this mission were generated on issue-5611-5419-nightly-green. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5611-5419-nightly-green unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-suites-green-01M44FEP
base_commit: b7142503eb9591f47e743bd92625919781e365bd
created_at: '2026-10-05T05:58:48.086486+00:00'
subtasks:
- T005
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - Track A (bare-slug consolidation)
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-05T04:58:23Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/coordination/
create_intent:
- tests/specify_cli/missions/test_mission_dir_aliases.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/missions/_read_path_resolver.py
- src/specify_cli/coordination/coherence.py
- src/specify_cli/coordination/commit_router.py
- tests/coordination/test_commit_router.py
- tests/specify_cli/coordination/test_commit_router_partition.py
- tests/specify_cli/coordination/test_commit_router_partition_authority.py
- tests/specify_cli/coordination/test_partition_authority_characterization.py
- tests/mission_runtime/test_artifact_partition_mapping.py
- tests/specify_cli/missions/test_mission_dir_aliases.py
role: implementer
task_type: implement
---

# Work Package Prompt: WP02 – Track A: directory alias authority and partition classification

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Then read `.kittify/charter/charter.md` (sections "Quality & Tech-Debt Standing Orders" and "ATDD-First Discipline") and run `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission nightly-suites-green-01M44FEP` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

Layer 1 of the red: the seed commit for a bare-slug coordination Mission must group its composed-directory status files to the COORD partition and commit them on the coordination branch (FR-002).

- One authority answers "which directory names belong to this Mission": `mission_dir_aliases(repo_root, mission_slug) -> frozenset[str]` in `src/specify_cli/missions/_read_path_resolver.py`, exported in `__all__` (FR-003).
- The set is exact: the primary directory name plus the composed coordination directory name derived from recorded identity. No prefix or suffix matching, no inference from the slug's shape (FR-004).
- The pure classifiers in `coordination/coherence.py` accept an optional collection of directory names; the commit router resolves the set once per commit and threads it through its partition grouping.
- A Mission whose primary directory already carries the composed name behaves exactly as before, and its bare stem is not an alias (FR-005).
- `src/mission_runtime/artifacts.py` is not edited.

After this work package the reproduction gets past the seed and fails at the reconciliation gate instead. That is the expected intermediate state; WP03 finishes it.

## Context & Constraints

Read first, in this order: `kitty-specs/nightly-suites-green-01M44FEP/spec.md` (User Story 1, FR-001 to FR-006, FR-018, FR-019, C-001, C-002, C-005), `plan.md` (section "Design notes / Track A" and the Implementation Concern Map), `research.md` (D1 to D3), `research/code-grounding.md` (sections 3, 6 and 9.1 to 9.4).

**The defect (#5651, tracked by #5611).** A coordination Mission whose primary directory is the bare slug (`kitty-specs/<slug>`) while its coordination branch and coordination directory use the composed `<slug>-<mid8>` name cannot consolidate onto a protected target. It regressed with `5b5699e500`. The red has three layers, each proven by an in-memory probe:

1. The seed commit groups the composed-directory status files to the PRIMARY partition, is refused on the protected branch and leaves them untracked.
2. With layer 1 fixed, the reconciliation gate fails on `kitty-specs/<slug>-<mid8>/status.events.jsonl` because `_is_bookkeeping` anchors on the bare slug.
3. With layers 1 and 2 fixed, teardown reads `meta.json` from the status directory, which has none, so `mid8` is empty and the coordination worktree is never destroyed.

**Operator rulings (2026-10-05).** (a) Alias authority: keep the composed coordination directory and add one exact alias set `{primary directory name, composed <slug>-<mid8> name}`, with `mid8` read from recorded identity and never prefix-matched. (b) One directory on the target: the consolidated Mission leaves exactly one Mission directory on the target, the primary one, with the complete event log.

**Track A work packages.** WP01 enablers, WP02 alias authority and partition classification, WP03 consolidation consumers and the one-directory end state, WP04 refused-seed backstop. Tracks B and C share no file with Track A.

**Fix at the seam (C-002).** Fix on the callee side. Do not change a fixture to make a test pass; the sibling test `test_explicit_delete_override_still_reachable` is green today only because `c5f1280aeb` re-keyed its fixture.

**Verified code facts for this work package (base `9adc68803f`).**

- `src/specify_cli/coordination/commit_router.py`: `commit_for_mission` at `:253` calls `_group_files_by_partition` at `:328` (skipped when `owned is not None`; leave that bypass untouched). `_group_files_by_partition` is defined at `:971`; its per-file loop calls `partition_for_mission_path(repo_root, mission_slug, file)` at `:1036`. `partition_for_mission_path` is defined at `:934` and returns from `is_coord_residue_churn(path, mission_slug=mission_slug)` at `:968`, after `del repo_root, owned`. `_representative_kind_for_bucket` is defined at `:902` and calls `kind_for_mission_file(file, mission_slug=mission_slug)` at `:928`.
- `partition_for_mission_path` is public (`__all__`) and has one cross-module caller, `acceptance/__init__.py:451`. That caller is out of scope (spec C-007); any new parameter must be optional and keyword-only so it is unaffected.
- `src/specify_cli/coordination/coherence.py`: `is_coord_residue_churn` at `:161` (classification at `:251`), `is_status_state_path` at `:258` (`:275`). Both call `mission_runtime.kind_for_mission_file(path, mission_slug=...)`.
- `src/mission_runtime/artifacts.py:491` `_artifact_kind_for_path`: at `:508-509` it returns `None` when the path's `kitty-specs/<segment>` differs from `mission_slug`. This exact-name check is what you reuse once per alias name; you do not change it.
- `src/specify_cli/missions/_read_path_resolver.py`: `_compose_mission_dir` at `:194` (returns the slug verbatim for an empty `mid8`, delegates to `lanes/branch_naming.py:645 coord_mission_dir_name`, which never double-suffixes), `coord_feature_dir` at `:218`, `read_primary_meta` at `:825` (returns `(meta, declares_coordination)`; raises the typed `MissionMetaReadError` on a corrupt `meta.json`; canonicalises a non-composed handle on the raw-miss path), `__all__` at `:1809`.
- `mid8` derivations that already exist: `coordination/surface_resolver.py:1042 resolve_declared_mid8(meta, mission_slug)` (the shared cascade; its third tier falls back to `mid8_from_slug`, a guess from the slug's tail, which the alias must NOT use), and the router's own `commit_router.py:1263 _resolve_mid8(repo_root, mission_slug)` (callers at `:1231` and `:1838`). `_resolve_mid8` reads the primary metadata with `load_meta(..., allow_missing=True, on_malformed="none")`, derives from the declared `mission_id` only, returns `None` on absent or corrupt metadata and on any other exception, and re-raises only `MissionSelectorAmbiguous` (`:1276-1278`).
- `read_primary_meta` (`:825`) canonicalises a handle that is not a directory name and raises on corrupt metadata. Both behaviours are wrong for the alias: see T006.
- `_read_path_resolver.py:896 literal_primary_dir_has_meta(repo_root, mission_slug)` answers whether the literal `kitty-specs/<mission_slug>/` directory holds a `meta.json`.
- `coordination/__init__.py` imports `surface_resolver`, which imports `_read_path_resolver`; the resolver late-imports `coordination.workspace` inside `coord_feature_dir` to avoid a cycle. Follow that pattern for any new import in either direction.
- The seed call that must be fixed: `coordination/coord_seed.py:585 _commit_seed` passes the bare `request.mission_slug` and `kind=MissionArtifactKind.STATUS_STATE` to `commit_for_mission`. You do not edit `coord_seed.py` (owned by WP01).

### Paths owned by running missions (do not edit)

Copied from `research/code-grounding.md` section 6. Paths are relative to `src/specify_cli/` unless they start with `tests/` or are a root file.

| Running mission | Paths |
|---|---|
| #5635 | `cli/commands/implement*.py`, `agent/workflow_executor.py`, `coordination/planning_commit.py`, `core/dependency_graph.py`, `lanes/implement_support.py`, `status/emit.py`, `status/__init__.py`, `workspace/context.py`, `pyproject.toml`, `tests/architectural/test_layer_rules.py`, `tests/architectural/test_wp_integrity_partition_call_shape.py`, `tests/architectural/dead_symbol_allowlist.yaml` |
| #5634 | `core/mission_creation*.py`, `tests/core/test_mission_create_coord_status_*.py` |
| #5573 | `lanes/compute.py`, `lanes/compute_and_persist.py`, `lanes/frozen_membership.py`, `lanes/lane_tip.py`, `lanes/models.py`, `cli/commands/agent/mission_finalize*.py`, `tests/specify_cli/cli/commands/agent/**` |
| #5457 | `upgrade/runner.py`, `lanes/consolidation.py`, `lanes/auto_rebase.py`, `lanes/stale_check.py`, `lanes/worktree_allocator.py`, `state/contract.py`, `tests/architectural/test_destructive_op_routing.py` |
| #4925 (PR #5709) | `cli/commands/upgrade.py`, `upgrade/finalize.py`, `upgrade/outcome.py`, `skills/manifest_store.py`, `tool_surface/repair.py` |
| #5668 | `consolidation/reconciliation.py`: the approved-claim bound. Only the body of `_is_bookkeeping` may change, and only in WP03. |
| #3931 | `cli/commands/agent/tasks_move_task*.py`, `cli/commands/_git_remedies.py`, `cli/commands/agent/tasks_parsing_validation.py` |

Also off limits for every work package of this mission: `src/mission_runtime/artifacts.py`, any `.github/workflows/*.yml`, `.github/ci-module-registry.yml`, and `kitty-specs/**`.

**Rule.** An edit outside this work package's `owned_files` needs a one-line rationale in your hand-back. An edit in a path listed above is a STOP: make no such edit, and report to the orchestrator what you found and why the listed path seems to need a change.

### Commit order and commit hygiene (charter C-011, spec C-005)

1. Tidy-first enabler commit(s): behaviour-preserving, with their focused tests.
2. Failing-test commit: the test goes through the pre-existing entry point and is red on this work package's base for the reason named in the subtask. Record the red output (test id plus the failing assertion line) in your hand-back.
3. Fix commit(s): the failing test turns green; new branches are covered by tests in the same commit.

Marker convention (ADR `docs/adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md`, amendment at line 70): `p0_repro(issue=N)` is only for a reproduction of an OPEN P0 that must stay off the per-pull-request path; `regression` is the marker for an issue-pinned guard of a bug that is fixed, and it runs per pull request. Tests added here guard bugs fixed in the same pull request, so they never carry `p0_repro`.

Every commit message ends with the trailer `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`. No commit message, code comment, docstring or document names an AI tool or a model.

### Quality bar (spec NFR-005)

- Cyclomatic complexity at most 15 per function (`ruff` C901). Extract a helper before a function reaches 16.
- `mypy --strict` clean for every changed source file; no new `# type: ignore`, no new `# noqa`.
- A string literal used three or more times in one module becomes a named module constant.
- Every new branch and helper has a test in the same commit.
- No empty or effect-free `except` block.

### Tracer files

Do not edit anything under `kitty-specs/`, including `kitty-specs/nightly-suites-green-01M44FEP/traces/`. Put tooling friction, approach changes and design choices in your hand-back as three short lists; the orchestrator appends them to the tracer files.

## Branch Strategy

- **Strategy**: lane worktree per computed lane (`lanes.json`); this mission's topology is `lanes`.
- **Planning base branch**: `issue-5611-5419-nightly-green`
- **Merge target branch**: `issue-5611-5419-nightly-green`
- **Dependencies**: WP01

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Start with `spec-kitty agent action implement WP02 --agent claude --mission nightly-suites-green-01M44FEP`. It allocates or reuses the lane worktree and prints its path; work only there and never reconstruct the path yourself. Do not push, and do not open or merge a pull request: the orchestrator consolidates and the operator merges.

## Subtasks & Detailed Guidance

### Subtask T005 – Red test through `commit_for_mission`

- **Purpose**: Reproduce layer 1 at the smallest pre-existing entry point, before any fix.
- **Steps**:
  1. In `tests/coordination/test_commit_router.py`, add a test that builds a coordination Mission with a bare primary directory: `kitty-specs/<slug>/meta.json` on the primary checkout declaring `mission_id`, `mid8`, `coordination_branch` and `topology`, and a coordination worktree holding `kitty-specs/<slug>-<mid8>/status.events.jsonl` and `status.json` as untracked files. Reuse the file's existing fixtures and factories; do not hand-build what a helper already provides.
  2. Call `commit_for_mission(repo_root, <bare slug>, files=(the two composed-directory paths), kind=MissionArtifactKind.STATUS_STATE, policy=<a policy that protects the primary branch>, ...)`, the same call shape `_commit_seed` uses.
  3. Assert the result status is `committed`, the commit is on the coordination branch, and both files are tracked there. Today the result is `no_op_wrong_surface` (the type is declared at `commit_router.py:218`) because both files group to PRIMARY.
  4. Commit the red test alone. Record the failing assertion in your hand-back.
- **Files**: `tests/coordination/test_commit_router.py`.
- **Parallel?**: No; it comes first.
- **Notes**: The test carries the directory's usual markers and no `p0_repro` marker. It must not mock `_group_files_by_partition` or `partition_for_mission_path`.

### Subtask T006 – `mission_dir_aliases` authority

- **Purpose**: One place that derives a Mission's directory names from recorded identity (FR-003, FR-004).
- **Steps**:
  1. Add `mission_dir_aliases(repo_root: Path, mission_slug: str) -> frozenset[str]` to `_read_path_resolver.py` and to `__all__`.
  2. Contract:
     - The set always contains `mission_slug` as passed, so every existing exact-name verdict is preserved.
     - Read the metadata of the LITERAL primary directory `kitty-specs/<mission_slug>/` only. Do not canonicalise the handle: a `mission_slug` that is a bare handle for a Mission whose directory is `<slug>-<mid8>` has no literal directory and gains no alias, so its partition verdicts are unchanged from the base.
     - Derive `mid8` from declared identity only (`mid8` or `mission_id` in that `meta.json`). When it is non-empty, add `_compose_mission_dir(mission_slug, mid8)`. Never use the `mid8_from_slug` tier and never guess from the slug's last eight characters.
     - When identity is unproven (no `meta.json`, no `mission_id` or `mid8`), return the single-name set.
     - A slug that already ends in `-<mid8>` yields a one-element set, because the composer does not double-suffix. The bare stem is not added (FR-005).
     - No new raise: absent or corrupt metadata yields the single-name set, exactly as the router's `_resolve_mid8` treats them today. Whether an ambiguous selector can reach this read at all is settled by the characterization in T009 step 5; whatever `commit_for_mission` does on the base for that input, it does after this change.
     - ONE derivation in the commit-router module: either `mission_dir_aliases` and `_resolve_mid8` share one private derivation, or one is re-pointed at the other. Two independent `mid8` derivations in `commit_router.py` is a defect. State in the hand-back which of the two you did and why.
  3. Create `tests/specify_cli/missions/test_mission_dir_aliases.py` with one test per contract line above (including corrupt metadata returning the single-name set without raising, and a bare handle for a composed-directory Mission returning the single-name set), plus: a slug with a legacy `NNN-` prefix (composed verbatim, no strip), and a slug whose last eight characters look like an identifier while `meta.json` records a different `mid8` (the set holds the recorded composition, not the look-alike).
  4. Write the docstring so it states the exactness rule and that the function performs one metadata read.
- **Files**: `src/specify_cli/missions/_read_path_resolver.py` (about 40 lines), new `tests/specify_cli/missions/test_mission_dir_aliases.py` (about 150 lines).
- **Parallel?**: Yes, alongside T007.
- **Notes**: `tests/architectural/test_no_dead_symbols.py` requires a caller outside the declaring module for every `__all__` name; T008 provides it (`commit_router.py`). Do not edit `tests/architectural/dead_symbol_allowlist.yaml` (do-not-touch); if the gate is red after T008, stop and report. `tests/architectural/test_no_read_side_bypass.py` and `test_single_mission_surface_resolver.py` police who may compose `kitty-specs` paths: the new function returns names, never a joined path.

### Subtask T007 – Classifiers accept a collection of directory names

- **Purpose**: Let a caller that knows the alias set classify against all of it, while the classifiers stay pure.
- **Steps**:
  1. Add an optional keyword-only parameter (suggested name `mission_dir_names: Collection[str] | None = None`) to `is_coord_residue_churn` and `is_status_state_path` in `coherence.py`.
  2. When it is `None`, behaviour is byte-identical to today (one `kind_for_mission_file(path, mission_slug=mission_slug)` call). When it is given, apply the existing exact-name classification once per name and return the first non-`None` kind; then continue as today (topology projection in `is_coord_residue_churn`, the `STATUS_STATE` identity check in `is_status_state_path`).
  3. Extract the "classify against several names" step into one small private helper used by both functions; do not duplicate the loop.
  4. No filesystem access, no git, no import of the resolver in `coherence.py`.
  5. Add tests to `tests/mission_runtime/test_artifact_partition_mapping.py` (it already covers `is_status_state_path`): with names `{slug, slug-mid8}` a path under `kitty-specs/<slug>-<mid8>/status.json` is STATUS_STATE; with the parameter omitted the same path is not; `kitty-specs/<slug>-<mid8>/spec.md` is not coordination residue under either form; a path under a name that is not in the collection is unclassified.
- **Files**: `src/specify_cli/coordination/coherence.py` (about 25 lines), `tests/mission_runtime/test_artifact_partition_mapping.py`.
- **Parallel?**: Yes, alongside T006.
- **Notes**: `is_coord_residue_churn` has 46 callers; none may need an edit. `cli/commands/implement.py` and `implement_cores.py` are do-not-touch callers of these predicates: the optional parameter must leave them compiling and behaving as before.

### Subtask T008 – Resolve once in the commit router and thread the names

- **Purpose**: Turn T005 green with one metadata read per commit.
- **Steps**:
  1. In `_group_files_by_partition`, resolve `mission_dir_aliases(repo_root, mission_slug)` once, before the per-file loop.
  2. Give `partition_for_mission_path` and `_representative_kind_for_bucket` an optional keyword-only names parameter and pass the resolved set to both. When `partition_for_mission_path` is called without it (the acceptance caller), its verdict is byte-identical to today; update its docstring, which currently says `repo_root` is not consulted, to describe the new parameter truthfully.
  3. Keep the early return for empty `files` ahead of the metadata read, so an empty commit does no I/O.
  4. Leave the `owned is not None` bypass at `:328` and the ref-collapse logic (`:1051-1058`) untouched.
  5. T005 must now pass. Add a characterization next to it: the same call for a Mission whose primary directory is `<slug>-<mid8>` produces the same groups before and after this change.
  6. If `_resolve_mid8` (`:1263`) is re-pointed or shares a helper (T006 contract, last line), its two callers (`:1231`, `:1838`) must see byte-identical results; pin that with a test if none exists.
- **Files**: `src/specify_cli/coordination/commit_router.py` (about 20 lines).
- **Parallel?**: No; needs T006 and T007.
- **Notes**: Cost: one `meta.json` read per `commit_for_mission` call with non-empty files. State that in the docstring. The read adds no new failure mode to `commit_for_mission`: unreadable metadata means "no alias", which is the base behaviour.

### Subtask T009 – Negative controls and canonical-unchanged pins

- **Purpose**: Prove the alias is exact and that nothing else changed (FR-004, FR-005).
- **Steps**:
  1. In `tests/specify_cli/coordination/test_commit_router_partition.py` (or `test_commit_router_partition_authority.py` where the existing structure fits better), add a parametrised test on one bare-slug fixture. Each of these paths must still group to PRIMARY:
     - `kitty-specs/<slug>-<different mid8>/status.json`
     - `kitty-specs/<slug>-<mid8>-x/status.json`
     - `kitty-specs/<other>-<mid8>/status.json`
     - `kitty-specs/<slug>-<mid8>/spec.md`
     - `kitty-specs/<slug>-<mid8>/src/x.py`
     - `kitty-specs/<stem>-abcdefgh/status.json` for a Mission `<stem>-abcdefgh` with no recorded identity, queried as `<stem>`
  2. Positive pair on the same fixture: `kitty-specs/<slug>-<mid8>/status.json` and `status.events.jsonl` group to COORD.
  3. In `tests/specify_cli/coordination/test_partition_authority_characterization.py`, extend the characterization so a Mission whose primary directory is the composed name yields the identical grouping it yields on the base, and so its bare stem (`<slug>` without `-<mid8>`) is not treated as its directory.
  4. Run `tests/coordination/test_ledger_topology_less_callers.py` unchanged; it pins the six topology-less callers.
  5. Characterization, written and committed GREEN on the base before T006 to T008 (a tidy-first commit), and green unchanged afterwards. Each calls `commit_for_mission` with non-empty files and pins the base result (status, groups, and whether it raises):
     - the primary `meta.json` is corrupt (not JSON; and JSON that is not an object);
     - the primary `meta.json` is absent;
     - the handle is ambiguous (two Missions match it), if that input can reach the router at all: pin what the base does;
     - a bare handle `<slug>` passed for a Mission whose only directory is `kitty-specs/<slug>-<mid8>/`, with files under that composed directory: the partition is the base's partition.
- **Files**: the three partition test files named above.
- **Parallel?**: Yes, once T008 is in.

### Subtask T010 – Gates, lint and hand-back

- **Purpose**: Close the work package with evidence.
- **Steps**:
  1. Run every command in the Test Strategy section.
  2. Run the reproduction once and record where it now fails. Expected: past the seed, at the reconciliation gate, naming `kitty-specs/<slug>-<mid8>/status.events.jsonl`. If it still fails with `MERGE_UNSAFE_WORKTREE_DIRTY`, the seed is still misrouted: investigate before handing back.
  3. Hand-back: commits, counts, the reproduction's new failure text, tracer notes, any out-of-map edit with rationale.
- **Files**: none.
- **Parallel?**: No.

## Test Strategy

### Validation commands

Run from the root of your lane worktree. Use the repository root checkout's environment, never a bare `uv run` (it re-syncs the environment) and never the globally installed `spec-kitty` binary for product behaviour (it is a different build).

```bash
export PY=/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/python
export PYTHONPATH=$(pwd)/src

# behavioural tests (named files only)
$PY -m pytest \
  tests/specify_cli/missions/test_mission_dir_aliases.py \
  tests/coordination/test_commit_router.py \
  tests/specify_cli/coordination/test_commit_router_partition.py \
  tests/specify_cli/coordination/test_commit_router_partition_authority.py \
  tests/specify_cli/coordination/test_partition_authority_characterization.py \
  tests/mission_runtime/test_artifact_partition_mapping.py \
  tests/coordination/test_ledger_topology_less_callers.py \
  tests/coordination/test_coord_seed.py \
  -n 4 --dist loadfile -p no:cacheprovider -q

# architectural and CI gate files this change implicates (named files only)
$PY -m pytest \
  tests/architectural/test_no_dead_symbols.py \
  tests/architectural/test_trio_seam_only.py \
  tests/architectural/test_mission_runtime_surface.py \
  tests/architectural/test_write_surface_placement_guard.py \
  tests/architectural/test_no_write_side_rederivation.py \
  tests/architectural/test_status_events_writes_gate.py \
  tests/architectural/test_coord_read_residuals_closeout.py \
  tests/architectural/test_no_read_side_bypass.py \
  tests/architectural/test_single_mission_surface_resolver.py \
  tests/architectural/test_no_worktree_name_guess.py \
  tests/architectural/test_lifted_root_meta_fail_closed_census.py \
  tests/architectural/test_exemption_registry_ratchet.py \
  tests/architectural/test_git_path_listing_owner.py \
  tests/architectural/test_guard_capability_call_sites.py \
  -n 4 --dist loadfile -p no:cacheprovider -q

# lint and format
/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/ruff check src/specify_cli/missions/_read_path_resolver.py src/specify_cli/coordination/coherence.py src/specify_cli/coordination/commit_router.py tests/specify_cli/missions/test_mission_dir_aliases.py tests/coordination/test_commit_router.py tests/specify_cli/coordination/test_commit_router_partition.py tests/specify_cli/coordination/test_commit_router_partition_authority.py tests/specify_cli/coordination/test_partition_authority_characterization.py tests/mission_runtime/test_artifact_partition_mapping.py
/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/ruff format --check --force-exclude src/specify_cli/missions/_read_path_resolver.py src/specify_cli/coordination/coherence.py src/specify_cli/coordination/commit_router.py tests/specify_cli/missions/test_mission_dir_aliases.py tests/coordination/test_commit_router.py tests/specify_cli/coordination/test_commit_router_partition.py tests/specify_cli/coordination/test_commit_router_partition_authority.py tests/specify_cli/coordination/test_partition_authority_characterization.py tests/mission_runtime/test_artifact_partition_mapping.py
/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/mypy --strict src/specify_cli/missions/_read_path_resolver.py src/specify_cli/coordination/coherence.py src/specify_cli/coordination/commit_router.py
```

**Named files only.** No whole directory, no `make test-fast`, no `make test-full`, no bare `tests/architectural/`. Never more than `-n 4` pytest workers; use `-n0` when you need a readable single failure. If a named file is red on your base commit as well, classify it (pre-existing, environment, stale install) and report it; do not fix it here.

`tests/architectural/test_layer_rules.py` and `test_wp_integrity_partition_call_shape.py` are do-not-touch files; you may run them, never edit them. If either goes red because of your change, stop and report.

### Non-vacuity controls (as test cases)

The five gate files added last in the list (`test_no_worktree_name_guess.py`, `test_lifted_root_meta_fail_closed_census.py`, `test_exemption_registry_ratchet.py`, `test_git_path_listing_owner.py`, `test_guard_capability_call_sites.py`) are run-only: a new metadata read or name composition may trip a census. If one goes red, do not edit the gate or its census; stop and report.

The characterization of T009 step 5 (corrupt, absent, ambiguous metadata; bare handle on a composed-directory Mission) is green on the base and stays green: no new raise, no partition change.

The six negative paths of T009 step 1 and the positive pair of step 2, on one fixture. A prefix-matched alias fails the first three; an alias that exempts the whole composed directory fails the fourth and fifth; an alias inferred from the slug's shape fails the sixth. The canonical-Mission characterization of T009 step 3 fails if the bare stem becomes an alias.

## Definition of Done

- T005 was committed red and is green at the end; the red output is in the hand-back.
- `mission_dir_aliases` exists, is exported, has a caller in `commit_router.py`, and performs one metadata read of the literal primary directory.
- `commit_router.py` holds one `mid8` derivation; the hand-back says how.
- The T009 step 5 characterization was committed green on the base and is unchanged and green at the end.
- `coherence.py` stays pure; `mission_runtime/artifacts.py` is unchanged (`git diff --stat` shows no entry for it).
- All six negative controls and the canonical characterization pass.
- All Test Strategy commands pass; the reproduction's new failure point is recorded.
- Subtasks T005 to T010 recorded with `spec-kitty agent tasks mark-status`.

## Risks & Mitigations

- **Import cycle between `coordination` and `missions`.** Mirror `surface_resolver.py`'s existing import of the resolver; fall back to a function-local import with a comment if a cycle appears.
- **Dead-symbol gate.** The new `__all__` name needs its `commit_router.py` caller in the same work package; the allowlist file may not be edited.
- **A handle that is not a directory name.** `read_primary_meta` canonicalises non-composed handles; the alias must not. Read the literal directory only, keep the passed slug in the set, and add only the composition derived from that directory's declared identity.
- **A new raise on the commit path.** Every `commit_for_mission` call with files would inherit it. Unreadable metadata means no alias.
- **Two `mid8` derivations in one module.** Reconcile with `_resolve_mid8`.
- **Extra I/O on a hot path.** One read per commit, none for an empty file list; state it and test the empty case does no read.
- **Do-not-touch adjacency.** `cli/commands/implement.py::_partition_files_for_commit` consumes the same classifier. Fix on the callee side only; that file is not edited.

## Review Guidance

Reviewer: `reviewer-renata` on the strongest available model, never the implementing agent.

What a lazy implementation looks like here, and how to detect it:

- **Prefix-matched alias.** `startswith(slug + "-")` or a regex on eight trailing characters anywhere in the diff. The first three negative controls catch it; also grep the diff for `startswith`, `endswith`, `re.` near the new code.
- **Alias inferred from the name.** The sixth negative control (no recorded identity) must exist and must build a Mission with no `mission_id`/`mid8` in `meta.json`.
- **Fixture re-key.** The T005 fixture must keep a bare primary directory and a composed coordination directory. A fixture whose primary directory is `<slug>-<mid8>` proves nothing; compare it with the reproduction's shape.
- **Classifier made impure.** `coherence.py` must not import the resolver or touch the filesystem.
- **Resolution per file.** `mission_dir_aliases` must be called once per `_group_files_by_partition` call, outside the loop.
- **`artifacts.py` edited.** It must not appear in the diff.
- **Unconverted consumer.** `_representative_kind_for_bucket` must receive the names too; check it is not left on the bare slug.
- **A second `mid8` derivation, or a new raise.** `commit_router.py` must end with one derivation; the corrupt, absent and ambiguous characterization must have been green on the base commit (check it out there) and be unedited afterwards.
- **Handle canonicalisation.** `mission_dir_aliases` must not call `read_primary_meta` or any canonicaliser; the bare-handle characterization catches it.

Verify red then green for T005 by checking out the red-test commit. Confirm the trailer, the absence of AI or model identifiers, and that the reproduction now fails at the reconciliation gate.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

1. Append the new entry at the END of this section; never prepend or insert in the middle.
2. Use the format `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>`.
3. The timestamp is the current UTC time (`date -u "+%Y-%m-%dT%H:%M:%SZ"`), never a future one.

The acceptance system reads the LAST entry as the current state, so order matters.

**Initial entry**:

- 2026-10-05T04:58:23Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status, and `spec-kitty agent tasks mark-status <Txxx> --status done` to record a finished subtask.
