---
work_package_id: WP15
title: Acceptance package conversion
dependencies:
- WP04
- WP07
- WP13
- WP14
requirement_refs:
- FR-001
- FR-022
planning_base_branch: claude/sleepy-hamilton-5lelee
merge_target_branch: claude/sleepy-hamilton-5lelee
branch_strategy: Planning artifacts for this mission were generated on claude/sleepy-hamilton-5lelee. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/sleepy-hamilton-5lelee unless the human explicitly redirects the landing branch.
subtasks:
- T080
- T081
- T082
- T083
phase: Phase 4 - Conversion sweep
history:
- at: '2026-09-28T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/acceptance/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/acceptance/__init__.py
- src/specify_cli/acceptance/execution_context.py
- src/specify_cli/acceptance/gates_core.py
- src/specify_cli/acceptance/matrix.py
- tests/acceptance/test_gate_execution_context.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP15 – Acceptance package conversion

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Then load the action-scoped governance: `spec-kitty charter context --action implement --json`. The charter (`.kittify/charter/charter.md`) is binding.

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
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

This is the `acceptance/*` half of IC-10a. It is a **behaviour-preserving signature migration**: every bare owned-root parameter in the acceptance package becomes `owned: OwnedCheckout | None`, and nothing else changes.

Done means:

1. The four owned modules contain **zero** occurrences of the identifier `effective_root` (parameter, keyword, local read, `"effective_root"` key), zero `effective_root_kwargs` imports or calls, and zero `OwnedMission` references. Each converted function takes `owned: OwnedCheckout | None = None` (keyword-only, default `None`) in the position the old `effective_root` had.
2. Every existing test of the acceptance package passes **unchanged** (FR-022), and `tests/architectural/test_read_surface_placement_guard.py::test_declared_home_surface_delegates_not_reimplements` still sees exactly one delegated call.
3. The owned arm of each converted function is covered by at least one focused test in `tests/acceptance/test_gate_execution_context.py` (diff coverage ≥ 90%, NFR-005).
4. `mypy --strict`, ruff check and ruff format are clean on the touched files; `make test-fast` passes.

**Mission-wide DoD (post-tasks squad):**
- `grep -rn "bridging: WP15 converts" src` is empty: every bridging call site marked for this WP is converted, including sites in other WPs' files (declared out-of-map edits).
- Every bridging call site this WP adds carries `# bridging: WP<n> converts`, naming the WP that converts it (never a free-form comment, never no marker).
- `TRANSITIONAL(WP18)` markers added by this WP (exact list; any deviation is amended here in the same PR, and WP18 T096 fails on unlisted markers): **0** markers.
- Red-first proofs are **commits**: the red test commit precedes its fix commit, and the reviewer verifies the order in `git log`.
- Error codes are imported from `OwnedRefusalCode` (WP01); no `OWNED_*` string literal is repeated in `src/` or new tests (Sonar S1192).

## Context & Constraints

- **Mission docs**: `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/` → `spec.md` (FR-001, FR-022), `plan.md` (Staging Strategy; IC-10a; Scale/Scope), `research.md` R-03 (bare owned-root parameter census now deferred to plan Scale/Scope, not R-03; "convert all bare owned-root parameters … G4/G5 empty allowlist"), `data-model.md` (OwnedCheckout fields), `contracts/owned-checkout-carrier.md` §3 and §7, `contracts/architectural-gate.md` (G4/G5 are what this WP is burning down), `occurrence_map.yaml`.
- **Landed prerequisites** (verify their actual shapes on your lane base before editing):
  - WP01: `from mission_runtime import OwnedCheckout` (public import only — MR-1/MR-2 forbid `mission_runtime.owned_checkout` submodule imports). Canonical fields: `owned_root`, `repository_root`, `mission_dir`, `mission_slug`, `topology`, `target_branch`. The legacy properties (`root`, `primary`, `directory`, `slug`, `target`) are transitional and deleted by WP18 — do not read them.
  - WP04: `placement_seam(..., owned=)` (dual keyword until WP18), and whatever WP04/T021 did to `mission_runtime.resolve_artifact_surface` (`resolution.py:2320` on the planning base) and `mission_runtime.declared_read_surface` (`resolution.py:2125`).
  - WP07: `specify_cli.coordination.write_seam.write_artifact` converted to the fact (called from `matrix.py:524`).
- **Callee rule (plan: Staging Strategy).** For each call you make **out of** the acceptance package, read the callee's current signature first:
  - takes `owned` → pass `owned=owned`;
  - is one of the six shared dual-keyword seams, or any other function whose legacy keyword is marked `TRANSITIONAL(WP18)` → pass `owned=owned` (never the legacy keyword);
  - still takes only `effective_root` → pass the bridging expression `effective_root=owned.owned_root if owned else None` as a plain keyword, marked `# bridging: WP<n> converts` (the WP that owns the callee), and log the site in the Activity Log.
- **Caller rule (cross-WP call sites).** Converting a public function breaks every caller that passes `effective_root=` to it. On the planning base those callers are **in other WPs' files**:
  - `src/specify_cli/cli/commands/accept.py` (WP14) → `collect_feature_summary` (`accept.py:679, 703` via `**scope`) and `normalize_feature_encoding` (`accept.py:695`);
  - `src/specify_cli/cli/commands/agent/mission_finalize.py:2636` (WP13) → `scaffold_acceptance_matrix(..., **({"effective_root": owned.root} if owned else {}))`.
  WP13 and WP14 are dependencies of this WP (operator sequencing), so both callers are merged on your lane base. Confirm with `git log --oneline`; since the caller WP has merged, change that one call expression to `owned=owned` as a **one-line out-of-map edit**, with the rationale "WP15 converted the callee signature; caller already holds the fact" in the commit message and Activity Log. If it has not merged, do **not** edit the caller file (a parallel lane owns it): convert every private function and leave the public function's parameter for the last commit, then ask the orchestrator to sequence it after the caller WP (and say so in the Activity Log). Callers that do not pass the keyword (`orchestrator_api/commands.py:2135`, `consolidation/executor.py`, `cli/commands/agent/acceptance_verdict.py`, `acceptance/post_consolidation.py`) are unaffected because the new keyword defaults to `None`.
- **Occurrence map**: `code_symbols` rename; `serialized_keys` do_not_change (the acceptance summary JSON and `acceptance-matrix.json` keys stay byte-identical); `logs_telemetry` do_not_change.
- **Terminology (C-008)**: new docstrings say "owned checkout" / "repository root checkout". Do not rewrite unrelated legacy docstrings; do update any docstring sentence that names the parameter you removed (for example `matrix.py:495-500`, `__init__.py:1204`).
- **No suppressions**, complexity ≤ 15 for every touched function (none of the touched acceptance functions is ≥ 12 on the planning base; keep it that way).

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `claude/sleepy-hamilton-5lelee`; completed changes must merge back into `claude/sleepy-hamilton-5lelee`.
- **Planning base branch**: `claude/sleepy-hamilton-5lelee`
- **Merge target branch**: `claude/sleepy-hamilton-5lelee`
- **Execution lane**: assigned in `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/lanes.json` by `spec-kitty agent mission finalize-tasks`. Start with `spec-kitty implement WP15` and use only the workspace path it prints.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Occurrence census (planning base `df1588860`)

Re-run at the end; it must print nothing except logged bridges:

```bash
grep -nw "effective_root\|effective_root_kwargs\|OwnedMission" \
  src/specify_cli/acceptance/__init__.py src/specify_cli/acceptance/execution_context.py \
  src/specify_cli/acceptance/gates_core.py src/specify_cli/acceptance/matrix.py
```

Totals on the planning base: 27 + 5 + 9 + 6 identifier lines; 19 parameters (11 + 2 + 4 + 2), 15 `effective_root_kwargs(...)` calls, 5 plain `effective_root=` keywords, 24 local reads, 0 `"effective_root"` dict keys, 0 `OwnedMission` references. The per-file tables are in each subtask.

## Subtasks & Detailed Guidance

### Subtask T080 – Convert `acceptance/__init__.py`

- **Purpose**: `acceptance/__init__.py` holds the accept read path (`collect_feature_summary`) and all of its private readers. It carries 11 bare owned-root parameters, the largest single cluster in the package (R-03).
- **Steps**:
  1. Replace `from specify_cli.core.owned_mission import effective_root_kwargs` (`:18`) with `from mission_runtime import OwnedCheckout` (under `TYPE_CHECKING` if the module keeps runtime imports lazy; follow the file's existing import style).
  2. Convert each function below; for each, the parameter becomes `owned: OwnedCheckout | None = None` and every forward becomes `owned=owned`:

     | Line | Function | Owned-root uses inside |
     |---|---|---|
     | 229 | `_encoding_backup_scope_prefix` | `:252` `_planning_read_dir(..., effective_root=effective_root)` |
     | 298 | `_mission_routes_through_coordination` | `:324` `if effective_root is None:` branch; `:330-334` `declared_home_surface(..., effective_root=effective_root)` |
     | 345 | `_accept_dirty_gate` | `:392` keyword; `:401-405` `_filter_coordination_residue(**effective_root_kwargs(...))` |
     | 414 | `_filter_coordination_residue` | `:432-435` `_mission_routes_through_coordination(**effective_root_kwargs(...))` |
     | 741 | `_iter_work_packages` | `:752-755` `_wp_tasks_read_dir(**effective_root_kwargs(...))` |
     | 1031 | `normalize_feature_encoding` (public) | `:1051-1054` `_planning_read_dir(**effective_root_kwargs(...))` |
     | 1138 | `_status_read_feature_dir` | `:1157` `if effective_root is not None:`; `:1160` `placement_seam(..., effective_root=effective_root)` |
     | 1185 | `_planning_read_dir` | `:1226-1229` `placement_seam(**effective_root_kwargs(...))` |
     | 1234 | `_wp_tasks_read_dir` | `:1271-1274` `placement_seam(**effective_root_kwargs(...))` |
     | 1284 | `_primary_anchor_feature_dir` | `:1319-1322` `placement_seam(**...)`; **`:1334` `resolve_mission(feature, effective_root or repo_root)`** |
     | 1388 | `collect_feature_summary` (public) | `:1396` `scope = effective_root_kwargs(effective_root)`; splats at `:1397, 1398, 1414, 1415, 1442, 1484, 1538` |

  3. Replace the `None`-checks with `owned`-checks: `if effective_root is None:` → `if owned is None:`; `if effective_root is not None:` → `if owned is not None:`. Keep the branch bodies identical apart from the keyword.
  4. `:1334` is the only site that uses the owned root as a **value**: `resolve_mission(feature, effective_root or repo_root)` becomes `resolve_mission(feature, owned.owned_root if owned is not None else repo_root)`. Do not introduce a local named `effective_root` or `owned_root: Path` to hold it (gate G4/G5 scan locals and annotations).
  5. In `collect_feature_summary`, delete the `scope` local and pass `owned=owned` explicitly at each of the seven former splat sites; `_check_lane_gates` (`:1538`) is converted in T081 — convert both in the same commit or the call breaks.
  6. Apply the **caller rule** from Context for `collect_feature_summary` and `normalize_feature_encoding` (callers in `accept.py`).
- **Files**: `src/specify_cli/acceptance/__init__.py`.
- **Parallel?**: T081 and T082 are independent files, but `collect_feature_summary` → `_check_lane_gates` crosses into `gates_core.py`, so land T080 and T081 in one commit, or T081 first.
- **Validation checklist**:
  - [ ] `grep -nw "effective_root\|effective_root_kwargs" src/specify_cli/acceptance/__init__.py` prints nothing (or only logged bridges).
  - [ ] `tests/specify_cli/acceptance/test_status_read_feature_dir_canonical_mid8.py`, `test_accept_gate_read_surface.py`, `test_accept_dirty_kitty_ops.py`, `test_trio_read_seam_migration.py` pass unchanged.
  - [ ] `tests/integration/test_explicit_checkout_commands.py -k accept` passes unchanged (owned accept reads the owned checkout's documents without writes).
- **Edge cases**: `_mission_routes_through_coordination` deliberately uses a different predicate for the owned arm (declared home surface of `ACCEPTANCE_MATRIX`) than for the non-owned arm (`resolve_topology` + `routes_through_coordination`). Keep that asymmetry; it is not a bug to "unify" here. `_status_read_feature_dir`'s owned arm returns the seam dir unconditionally, while the non-owned arm falls back to `feature_dir` when the status dir is absent — preserve both.

### Subtask T081 – Convert `acceptance/execution_context.py` and `gates_core.py`

- **Purpose**: The gate-execution context (GEC) and the lane gates are the acceptance gate's single surface authority. They must receive the fact rather than a path, so the gate judges the owned checkout it was handed (GEC-1, C1) and never re-derives a root.
- **Steps**:
  1. `execution_context.py`: replace the `effective_root_kwargs` import at `:59` with `OwnedCheckout` from `mission_runtime`.
  2. Convert `declared_home_surface` (`:231-269`): the parameter at `:237` becomes `owned: OwnedCheckout | None = None`; the forward at `:266-268` into `mission_runtime.declared_read_surface(repo_root, mission_slug, kind, resolver=resolver, **effective_root_kwargs(effective_root))` becomes `owned=owned`.
  3. Convert `build_gate_execution_context` (`:312-345`): the parameter at `:318` becomes `owned`; the forward at `:336-338` into `mission_runtime.resolve_artifact_surface(..., **effective_root_kwargs(effective_root))` becomes `owned=owned`.
  4. Both callees live in `src/mission_runtime/resolution.py` (`declared_read_surface` `:2125`, `resolve_artifact_surface` `:2320` on the planning base; WP04 owns the file). Apply the callee rule: if WP04 converted them, pass `owned=owned`; if they still take only `effective_root`, pass the bridging keyword and log it.
  5. `gates_core.py`: replace the import at `:37`, then convert:

     | Line | Function | Owned-root uses inside |
     |---|---|---|
     | 311 | `_acceptance_gate_context` | `:345` `scope = effective_root_kwargs(...)`; `:346` `build_gate_execution_context(**scope)` |
     | 453 | `_matrix_surface_cannot_hold` | `:479` `scope = ...`; `:480` `declared_home_surface(**scope)` |
     | 640 | `_evaluate_acceptance_matrix` | `:671` `scope = ...`; splats at `:672`, `:678` |
     | 743 | `_check_lane_gates` | `:774-782` `_evaluate_acceptance_matrix(**effective_root_kwargs(...))` |

     Delete every `scope` local and pass `owned=owned` explicitly.
  6. Remove `from typing import Any` only if nothing else uses it once the `scope: dict[str, Any]` annotations are gone (ruff F401 tells you).
  7. Do not widen `build_gate_execution_context`'s contract: it stays "the ONE construction door" and stays pure (no HEAD read). `owned` only selects the surface.
  8. Commit together with T080 (the `_check_lane_gates` call from `collect_feature_summary` crosses the two files): `refactor(acceptance): gate context and lane gates take the OwnedCheckout fact (WP15/T080-T081)`.
- **Files**:
  - `src/specify_cli/acceptance/execution_context.py`
  - `src/specify_cli/acceptance/gates_core.py`
- **Parallel?**: Yes with T082; coupled with T080 through `_check_lane_gates`.
- **Validation checklist**:
  - [ ] `tests/architectural/test_read_surface_placement_guard.py::test_declared_home_surface_delegates_not_reimplements` passes unchanged. Its spy (`:358-360`) forwards `**kwargs` to the real `declared_read_surface`, so the keyword you pass must be one the real function accepts.
  - [ ] `tests/acceptance/test_gate_execution_context.py` (all 30 tests) passes before you add anything in T083.
  - [ ] `tests/specify_cli/acceptance/test_acceptance_cores.py`, `test_issue_1834.py`, `test_issue_4974_accept_concurrent_verdict.py`, `test_negative_invariant_authoring.py`, `test_find_unchecked_tasks_canon.py` pass unchanged.
  - [ ] `tests/characterization/test_trio_pure_cores.py` and `tests/status/test_wp01_terminus_authority_parity.py` pass unchanged (they import `gates_core`).
- **Edge cases**:
  - `resolve_artifact_surface` raises `CoordinationBranchDeleted` for a deleted coordination branch (C3 fail-loud). With `owned` set on a single_branch mission that path is unreachable, but do not add a `try/except` that would swallow it for the non-owned case.
  - `_matrix_surface_cannot_hold` must keep returning the same GEC-5 outcome type for flat and coordination missions.
  - `_check_lane_gates` forwards the git context branch (`test_resolve_git_context_branch_forwards_through_check_lane_gates`); keep the keyword order irrelevant by passing everything by keyword.

### Subtask T082 – Convert `acceptance/matrix.py`

- **Purpose**: The acceptance-matrix writer is the only **write** path in the package. Its owned arm decides where the matrix is committed (the owned checkout) and whether a failed write is fatal (it is, for owned missions).
- **Steps**:
  1. Replace the `effective_root_kwargs` import at `:24` with `OwnedCheckout` from `mission_runtime`.
  2. `write_and_commit_acceptance_matrix` (`:470-535`): the parameter at `:478` becomes `owned: OwnedCheckout | None = None`.
  3. Its forward at `:524-533` into `specify_cli.coordination.write_seam.write_artifact(..., effective_root=effective_root)` becomes `owned=owned` if WP07 converted `write_artifact` (it should have; `write_seam.py` is WP07-owned). Otherwise pass the bridging keyword and log it.
  4. `scaffold_acceptance_matrix` (`:795-925`): the parameter at `:802` becomes `owned`.
  5. `:910-918`: `write_and_commit_acceptance_matrix(..., **effective_root_kwargs(effective_root))` becomes `owned=owned`.
  6. `:922`: `if effective_root is not None: raise RuntimeError(result.diagnostic or "Owned acceptance matrix write failed.")` becomes `if owned is not None:` with the same message (the message is `logs_telemetry: do_not_change`).
  7. Update the docstrings that describe the removed parameter (around `:495-500` and in the scaffold docstring) to describe `owned`, using "owned checkout".
  8. Apply the caller rule to `scaffold_acceptance_matrix`: its only keyword-passing caller is `cli/commands/agent/mission_finalize.py:2629-2637` (WP13). That caller also passes `repo_root=owned.primary` and `policy=ProtectionPolicy.resolve(owned.primary ...)`; those legacy attribute reads are WP13's to convert, not yours. Only the owned-root keyword on that call is in scope for your one-line edit, and only if WP13 has merged.
  9. Commit: `refactor(acceptance): matrix writer takes the OwnedCheckout fact (WP15/T082)`.
- **Files**:
  - `src/specify_cli/acceptance/matrix.py`
  - Possibly one line of `src/specify_cli/cli/commands/agent/mission_finalize.py` (out-of-map, only after WP13 merged).
- **Parallel?**: Yes with T081.
- **Validation checklist**:
  - [ ] `tests/architectural/test_acceptance_matrix_write_seam.py`, `tests/specify_cli/acceptance/test_matrix_write_seam.py`, `tests/specify_cli/acceptance/test_matrix_marker_reject.py` pass unchanged.
  - [ ] `tests/acceptance/test_overall_verdict_scaffold.py`, `tests/acceptance/test_issue_3231_scaffold_pending_poisons_acceptance.py`, `tests/acceptance/test_post_consolidation.py` pass unchanged.
  - [ ] `tests/integration/test_issue_2404_acceptance_matrix_write_surface.py`, `tests/lanes/test_acceptance_matrix.py` pass unchanged.
  - [ ] `tests/integration/test_explicit_checkout_commands.py::test_finalize_seeds_owned_status_only` and `::test_accept_no_commit_updates_only_owned_matrix` pass unchanged.
  - [ ] `grep -nw "effective_root\|effective_root_kwargs" src/specify_cli/acceptance/matrix.py` prints nothing (or only a logged bridge).
- **Edge cases**:
  - The non-owned zero-write refusal path (FR-011) must still never fall back to a bare repository-root write; only the owned arm raises `RuntimeError`.
  - `write_and_commit_acceptance_matrix` has non-owned callers (`cli/commands/agent/acceptance_verdict.py`, `acceptance/post_consolidation.py`) that pass no keyword; their behaviour must not change.
  - `scaffold_acceptance_matrix` can be called with `repo_root=None` (no commit); keep that branch untouched.
  - An owned write that the seam reports as `unchanged` is success, exactly like `committed`; do not narrow the success set.
  - `write_artifact` receives `stage=` callables; the owned arm must stage only paths under `owned.mission_dir`, which the write seam (WP07) enforces — do not add a second containment check here.
  - Keep the function's return type (`Path`) and its early return for an existing matrix; idempotent re-runs are a hard requirement.

### Subtask T083 – Acceptance-package test updates plus the FR-022 ratchet

- **Purpose**: Diff coverage ≥ 90% (NFR-005) needs the owned arms exercised directly, and FR-022 needs proof that nothing existing changed. The only acceptance test file this WP owns is `tests/acceptance/test_gate_execution_context.py`, so the new focused tests go there.
- **Steps**:
  1. Get a real fact. The WP02 fixtures (`owned_checkouts`, `r_snapshot`, `stale_root_copy`) live in `tests/integration/conftest.py`, which pytest applies only under `tests/integration/`. From `tests/acceptance/` import them explicitly and re-export them through `__all__` (the pattern `tests/integration/test_owned_checkout_mark_status.py:13-22` uses), or use the sanctioned test helper WP02 documents for minting a fact in tests. Never call `OwnedCheckout._mint` directly (gate G3).
  2. Add a section `# --- owned checkout (WP15) ---` with focused tests:
     - `build_gate_execution_context(..., owned=fact)` stamps the surface under `fact.owned_root`, never under the repository root checkout, even when R holds a stale copy of the same mission slug (`stale_root_copy`).
     - `declared_home_surface(..., owned=fact)` for a single_branch mission answers `TopologySurface.PRIMARY`.
     - `collect_feature_summary(repo_root, slug, owned=fact, mutate_matrix=False)` reads WPs from `fact.mission_dir / "tasks"`.
     - `_status_read_feature_dir(..., owned=fact)` returns the owned status dir even when it does not exist yet (the owned arm has no fallback).
     - `scaffold_acceptance_matrix(..., owned=fact)` raises `RuntimeError("... Owned acceptance matrix write failed.")` when the write seam reports a non-committed status (monkeypatch `write_and_commit_acceptance_matrix` in the `matrix` module to return a refused result).
     - `normalize_feature_encoding(..., owned=fact)` only touches files under `fact.mission_dir`.
  3. Markers: `integration` + `git_repo` on tests that build repositories, `unit` + `fast` on pure ones. Do not change the file's existing markers on existing tests.
  4. In each owned test, assert the repository root checkout snapshot is unchanged (`r_snapshot`, NFR-001).
  5. Run the full FR-022 ratchet list (Test Strategy). No existing test file may change. If one must, that is a behaviour change: stop and record it.
  6. Commit: `test(acceptance): cover the owned arms of the acceptance package (WP15/T083)`.
- **Files**:
  - `tests/acceptance/test_gate_execution_context.py` (append only).
  - Read-only: `tests/integration/conftest.py`, `tests/acceptance/conftest.py` (check it does not already define a conflicting fixture name).
- **Parallel?**: No; after T080–T082.
- **Validation checklist**:
  - [ ] `uv run --frozen pytest tests/acceptance/test_gate_execution_context.py --cov=specify_cli.acceptance --cov-report=term-missing` shows every new owned branch covered.
  - [ ] `git diff --stat -- tests/ ':!tests/acceptance/test_gate_execution_context.py'` is empty.
  - [ ] Every new test fails if its owned arm is reverted to the non-owned arm (spot-check two by mutation; do not commit).
  - [ ] Record the full ratchet command and counts in the Activity Log.
- **Edge cases**:
  - The file's existing fixture `flat_topology_mission` (`ctf.FlatTopologyContext`) is not an owned fixture; do not repurpose it.
  - `test_fixture_smoke_no_resolver_patched` (`:793`) asserts nothing is patched globally; keep your monkeypatches function-scoped.
  - The `tests/acceptance/conftest.py` fixtures and the imported WP02 fixtures must not share names; rename on import if they clash.
  - `tests/acceptance/conftest.py` already re-exports integration fixtures (from `tests.integration.coord_topology_fixture`, `:11`); follow the same local pattern for the WP02 fixtures in the test module rather than editing that conftest (not owned).

## Test Strategy

Targeted (existing files must pass unchanged; the owned test file gains tests):

```bash
uv run --frozen pytest -q \
  tests/acceptance/ \
  tests/specify_cli/acceptance/ \
  tests/specify_cli/test_acceptance.py tests/specify_cli/test_canonical_acceptance.py \
  tests/specify_cli/test_accept_gate_convergence.py tests/specify_cli/test_acceptable_ending.py \
  tests/specify_cli/test_terminal_state_gate_integrity.py tests/specify_cli/test_acceptance_regressions.py \
  tests/specify_cli/test_accept_no_commit_readonly.py \
  tests/agent/test_orchestrator_commands_integration.py \
  tests/integration/test_accept_matrix_coord_partition.py \
  tests/integration/test_issue_2404_acceptance_matrix_write_surface.py \
  tests/integration/test_deferral_enforcement_and_disclosure.py \
  tests/integration/test_explicit_checkout_commands.py \
  tests/lanes/test_acceptance_matrix.py \
  tests/characterization/test_trio_pure_cores.py \
  tests/mission_runtime/test_coord_read_seam.py \
  tests/status/test_wp01_terminus_authority_parity.py \
  tests/consolidation/test_issue_2804_merge_resets_gate_artifacts.py \
  tests/specify_cli/cli/commands/test_accept_normalize_encoding.py \
  tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py
```

Specific architectural gates implicated (files, not the directory):

```bash
uv run --frozen pytest -q \
  tests/architectural/test_read_surface_placement_guard.py \
  tests/architectural/test_acceptance_matrix_write_seam.py \
  tests/architectural/test_single_mission_surface_resolver.py \
  tests/architectural/test_owned_checkout_gate_selftest.py
```

Baseline and quality gates:

```bash
make test-fast
uv run --frozen ruff check src/specify_cli/acceptance/ tests/acceptance/test_gate_execution_context.py
uv run --frozen ruff format --check src/specify_cli/acceptance/ tests/acceptance/test_gate_execution_context.py
uv run --frozen mypy --strict src/specify_cli/acceptance/__init__.py src/specify_cli/acceptance/execution_context.py \
  src/specify_cli/acceptance/gates_core.py src/specify_cli/acceptance/matrix.py \
  src/specify_cli/coordination/write_seam.py src/specify_cli/cli/commands/accept.py \
  src/specify_cli/cli/commands/agent/mission_finalize.py
```

Run mypy on the callee and caller files **in one invocation**: `pyproject.toml` sets `follow_imports = "skip"` for `specify_cli.*`, so a mismatched keyword between two `specify_cli` modules is invisible unless both are on the command line. Record the exact commands and pass/fail counts in the Activity Log and the PR's *Tests run* section.

## Risks & Mitigations

- **Cross-WP caller breakage.** `accept.py` (WP14) and `mission_finalize.py` (WP13) pass the old keyword to public functions here. Both are dependencies, so they are merged; mitigation: the caller rule in Context (one-line declared out-of-map flips).
- **Seam asymmetries mistaken for bugs.** Several readers treat the owned arm differently from the non-owned arm on purpose (see T080 edge cases). Mitigation: behaviour-preserving means both arms keep their current logic; only the parameter type changes.
- **Spy/monkeypatch compatibility.** Architectural tests spy on `declared_read_surface` and forward `**kwargs`. Mitigation: pass only keywords the real callee accepts.
- **mypy blind spot** (`follow_imports = "skip"`). Mitigation: multi-file invocation above.

## Review Guidance

- Re-run the occurrence census; anything left must be a logged bridge with a named callee.
- Check that every converted parameter is keyword-only with default `None` and typed `OwnedCheckout | None` (gate G6 pins signatures only for the §7 consumers, but consistency here is what lets WP18 go green).
- Check that any edit to `accept.py` or `mission_finalize.py` is one line, carries the rationale, and happened only after that WP merged.
- Confirm `git diff --stat -- tests/` touches only `tests/acceptance/test_gate_execution_context.py`.
- Confirm the multi-file mypy command ran clean.

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
- 2026-09-29T11:47:41Z – claude – shell_pid=24451 – Red-first: fe8040406 (7 owned tests, all TypeError on lane base 8a21949c5) precedes fixes 8aa026d17 (T080-T081) and 8b8e6bc22 (T082). Markers: 'bridging: WP15 converts' grep now empty (was 4: accept.py x3, mission_finalize.py x1); 0 TRANSITIONAL(WP18) added; 0 bridges added. Out-of-map: accept.py (3 call exprs -> owned=owned), mission_finalize.py (1 call expr -> owned=owned), tests/specify_cli/cli/commands/test_accept_decomposition.py (2 bridge tests now assert owned is fact). _RESOLVER_READ_LEDGER unchanged (no post-mint get_main_repo_root read removed; test_finalize_atomicity green). Pre-existing reds on base: test_gate_execution_context::test_build_context_unmaterialized_stamps_primary_without_raising, ::test_gec5_create_window_gate_refuses_instead_of_passing (CoordinationWorktreeUnmaterialized), test_issue_2404 census x2 (source counts identical to base). mypy --strict 7 errors base = 7 head (identical). Census grep of effective_root in acceptance package empty.
- 2026-09-29T12:12:36Z – claude – Review cycle 1 (MEDIUM) addressed in 7a5fdbd3d: added test_owned_check_lane_gates_forwards_the_fact_to_every_gate_seam; mutation-proved red on each of the 4 dropped gates_core forwards (scratch worktrees, nothing committed). Source unchanged; ruff check/format clean on the test file; mypy unaffected (base==head 7). 2404 census and GEC reds untouched; execution_context ruff format drift left.
