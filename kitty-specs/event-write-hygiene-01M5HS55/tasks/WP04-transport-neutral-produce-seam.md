---
work_package_id: WP04
title: Transport-neutral produce seam (#6607, part 2)
dependencies:
- WP03
requirement_refs:
- FR-008
- FR-009
- SC-003
- C-003
subtasks:
- T013
- T014
- T015
- T016
- T017
phase: 'Phase 3 - #6607'
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-22T13:30:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- tests/status/test_adapters_contract.py
- tests/conftest_fanout_sink.py
- tests/status/test_fanout_timeout.py
- tests/specify_cli/status/test_resolved_binding_fanout.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/adapters.py
- src/specify_cli/status/emit.py
- src/specify_cli/status/models.py
- src/specify_cli/status/wp_status_metadata.py
- src/specify_cli/coordination/outbound.py
- src/specify_cli/coordination/status_transition.py
- src/specify_cli/decisions/emit.py
- src/specify_cli/core/mission_creation_commit.py
- src/specify_cli/cli/commands/init.py
- pyproject.toml
- tests/status/test_adapters_contract.py
- tests/conftest_fanout_sink.py
- tests/status/test_fanout_timeout.py
- tests/specify_cli/status/test_resolved_binding_fanout.py
- tests/agent/cli/commands/test_status_cli.py
- tests/agent/test_create_feature_branch_unit.py
- tests/agent/test_orchestrator_commands_integration.py
- tests/architectural/test_ledger_floor.py
- tests/architectural/test_timing_coverage_invariant.py
- tests/conftest_saas_sink.py
- tests/core/test_mission_creation_fanout_commit_boundary.py
- tests/integration/migration/test_wp03_advance_to_approval.py
- tests/integration/review/test_verdict_save_topologies.py
- tests/lanes/test_lane_tip_record_points.py
- tests/release/coverage_breadth_baseline.json
- tests/release/coverage_breadth_evidence.md
- tests/specify_cli/acceptance/test_acceptance_support.py
- tests/specify_cli/cli/commands/agent/test_finalize_atomicity.py
- tests/specify_cli/cli/commands/agent/test_finalize_clobber_e2e.py
- tests/specify_cli/cli/commands/agent/test_issue_3466_finalize_target_branch_override.py
- tests/specify_cli/cli/commands/agent/test_sc6_planning_placement_e2e.py
- tests/specify_cli/cli/commands/test_finalize_tasks_validate_only_readonly.py
- tests/specify_cli/cli/commands/test_wp06_sc2_paused_mission_blockers.py
- tests/specify_cli/coordination/test_outbound.py
- tests/specify_cli/core/test_mission_creation_fire_once.py
- tests/specify_cli/decisions/test_emit.py
- tests/specify_cli/orchestrator_api/test_transition_subtask_gate.py
- tests/specify_cli/status/test_cutover_byte_stability.py
- tests/specify_cli/status/test_execution_mode_stamp_paths.py
- tests/specify_cli/status/test_infer_subtasks_primary.py
- tests/specify_cli/status/test_resolved_binding_linkage.py
- tests/specify_cli/status/test_saas_resolved_binding_fanout.py
- tests/specify_cli/status/test_wp_metadata.py
- tests/status/test_actor_boundary_normalize.py
- tests/status/test_actor_identity_reconciliation_4665.py
- tests/status/test_agent_status_emit_aggregate_wiring.py
- tests/status/test_agent_status_emit_cli.py
- tests/status/test_bootstrap.py
- tests/status/test_emit_backward_transition.py
- tests/status/test_emit_fanout_after_adapter.py
- tests/status/test_event_mission_id.py
- tests/status/test_saas_fanout_timeout.py
- tests/status/test_sync_lane_mapping.py
- tests/status/test_transition_pipeline.py
role: implementer
task_type: implement
---

# Work Package Prompt: WP04 – Transport-neutral produce seam (#6607, part 2)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile named in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status --mission event-write-hygiene-01M5HS55` for a `review_ref`. Address every item, and record what you changed with `spec-kitty agent tasks add-history WP04 --note "..."`.

---

## Objectives & Success Criteria

- Give the status produce seam and its direct residue transport-neutral names. **Keep no deprecated aliases.** The operator ruled that `spec-kitty/event-router` is frozen and dead, so nothing is kept for its sake. That includes the env var `SPEC_KITTY_SAAS_FANOUT_TIMEOUT`.
- **Behaviour is unchanged**:
  - there is no default handler;
  - every `fire_*` is a non-raising no-op until a handler is registered;
  - registration is idempotent by qualified name;
  - each handler call is bounded by the timeout, and a non-positive value runs it inline.
- Done means:
  - `grep -ni saas src/specify_cli/status/adapters.py` is empty (SC-003);
  - a stub-handler contract test pins the behaviour through the new names (FR-009);
  - the old env var has no effect, which a test asserts;
  - every test that used the old names passes against the new ones, and none passes vacuously (see T016);
  - requirements covered: FR-008, FR-009, SC-003.

## Rename table (exact; governed by `occurrence_map.yaml`)

| Old | New | Where |
|---|---|---|
| `_DEFAULT_SAAS_FANOUT_TIMEOUT_S` | `_DEFAULT_FANOUT_TIMEOUT_S` | `status/adapters.py` |
| `_SAAS_FANOUT_TIMEOUT_ENV` = `"SPEC_KITTY_SAAS_FANOUT_TIMEOUT"` | `_FANOUT_TIMEOUT_ENV` = `"SPEC_KITTY_STATUS_FANOUT_TIMEOUT"` | `adapters.py` |
| `_saas_fanout_timeout_s` | `_fanout_timeout_s` | `adapters.py` |
| `SaasFanOutHandler` / `LifecycleSaasFanOutHandler` | `StatusFanOutHandler` / `LifecycleFanOutHandler` | `adapters.py` |
| `_saas_handlers` / `_lifecycle_saas_handlers` | `_status_handlers` / `_lifecycle_handlers` | `adapters.py` |
| `register_saas_fanout_handler` | `register_status_fanout_handler` | `adapters.py` + callers |
| `register_lifecycle_saas_fanout_handler` | `register_lifecycle_fanout_handler` | `adapters.py` + callers |
| `fire_saas_fanout` | `fire_status_fanout` | `adapters.py`, `status/emit.py`, `coordination/outbound.py`, `status/__init__.py` |
| `fire_lifecycle_saas_fanout` | `fire_lifecycle_fanout` | `adapters.py`, `decisions/emit.py`, `status/lifecycle_events.py`, `status/__init__.py` |
| log labels `"SaaS fan-out"`, `"Lifecycle SaaS fan-out"`, breadcrumb `"fire_saas_fanout: ..."` | `"Status fan-out"`, `"Lifecycle fan-out"`, `"fire_status_fanout: ..."` | `adapters.py` |
| `emit._saas_fan_out` (and any `_saas_*` helper in `emit.py`) | `_status_fan_out` | `status/emit.py`, `coordination/status_transition.py:472`, `status/models.py:454` comment |
| `"Skipping SaaS fan-out for genesis..."` (emit.py:1538) | `"Skipping status fan-out for genesis..."` | `status/emit.py` |
| `queue_saas_emission` / `_send_to_saas` | `queue_fanout_emission` / `_send_to_fanout` | `coordination/outbound.py`, `coordination/status_transition.py` |
| `fanout_lifecycle_event_hosted` | `fanout_lifecycle_event` | `status/lifecycle_events.py`, `status/__init__.py`, `core/mission_creation_commit.py` |
| `tests/conftest_saas_sink.py` (`mock_saas_sink` fixture) | `tests/conftest_fanout_sink.py` (`mock_fanout_sink`) | `tests/` + `pytest_plugins` users |
| `tests/status/test_saas_fanout_timeout.py` | `tests/status/test_fanout_timeout.py` | + `tests/release/coverage_breadth_baseline.json:36-37`, `coverage_breadth_evidence.md`, `test_timing_coverage_invariant.py:290` |
| `tests/specify_cli/status/test_saas_resolved_binding_fanout.py` | `tests/specify_cli/status/test_resolved_binding_fanout.py` | + `pyproject.toml:2058` |

Docstrings and comments that describe **the seam** as "SaaS" get neutral wording ("transport", "status fan-out"). Do this in `adapters.py`, `emit.py` (module docstring :5, :894-930, :1367, :1449, :1520-1567), `outbound.py`, `status_transition.py:4`, `models.py:151/:203`, `wp_status_metadata.py:4`, `decisions/emit.py:296` and `cli/commands/init.py:1236`. Also replace the stale `drain_posture` docstrings in `adapters.py`.

**Out of scope** (Locality of Change). These are not seam names: `_saas_client_factory`, `get_saas_client`, `register_saas_client_factory`, `_get_saas_client_from_seam`, `saas_reachable`, `saas_gated`, `is_saas_sync_enabled`, `tests/architectural/test_saas_sync_gate_selection_invariance.py` and the `S310` comment in `pyproject.toml`. Leave them, and list them in history as a follow-up candidate.

## Context & Constraints

- **Read first**: `plan.md` IC-05, `research.md` R-4, `research-census.md` sections 4 and "riskiest findings" 3–5, and `occurrence_map.yaml`. Rename only within these categories.
- **Ownership-map leeway**: the 18 files listed under *Leeway files* at the end of this prompt belong to WP01, WP02 or WP03. Edit them here as mechanical rename edits (occurrence-map governed) and add one history line naming the leeway. Also use leeway for `status/__init__.py` and `status/lifecycle_events.py` (owned by WP03).
- **Behaviour constraint**: logic, ordering, thread bounds and exception handling stay byte-for-byte the same apart from names. Do not "improve" the seam.
- **Constraints**: no new suppressions, complexity ≤ 15, and `ruff format --check --force-exclude` on changed files.

## Branch Strategy

- **Strategy**: `single_branch`, working in the repository root checkout on `feat/event-write-hygiene`.
- **Planning base branch**: `feat/event-write-hygiene`. **Merge target branch**: `feat/event-write-hygiene`.
- Implement with `spec-kitty agent action implement WP04 --agent claude --mission event-write-hygiene-01M5HS55`.

## Subtasks & Detailed Guidance

### Subtask T013 – Red-first: contract test and extended timeout test

- **Steps**:
  1. Create `tests/status/test_adapters_contract.py`, written against the **new** names:
     - (a) After `reset_handlers()`, `fire_status_fanout(repo_root=None, wp_id="WP01")`, `fire_lifecycle_fanout(repo_root=None, envelope={}, log_path=None)` and `fire_resolved_binding_fanout(...)` invoke nothing and do not raise (empty-registry control).
     - (b) A stub registered via `register_status_fanout_handler` receives the kwargs exactly once, with `repo_root` re-joined, as the current `fire_saas_fanout` does. Do the same for the lifecycle stub (which does not receive `repo_root`) and the resolved-binding stub.
     - (c) Registering the same qualified function twice delivers once.
     - (d) A raising stub is swallowed and logged, and a later stub still runs.
     - (e) `adapters.py`'s source contains no `saas` (case-insensitive). Read it with `Path(adapters.__file__).read_text()`.
     - (f) No module-level handler is registered after import. The registries are empty in a fresh interpreter: use `subprocess` with `sys.executable -c "from specify_cli.status import adapters as a; assert not a._status_handlers ..."`. Use the new private names; this is a contract test of the module.
  2. Retarget `tests/status/test_saas_fanout_timeout.py`'s env usage to `SPEC_KITTY_STATUS_FANOUT_TIMEOUT` (still in the old file; T016 renames it), and add a case:
     - setting only the **old** variable to `0` keeps the 10 s default bound (`_fanout_timeout_s() == 10.0`);
     - setting the new one to `0` runs the handler inline.

     The census warns that a test still setting the old var would silently fall back to the default, so this pins the no-alias ruling.
  3. Run both files. They must fail on the current tree with import or name errors. Commit them with message `test(status): pin the transport-neutral produce-seam contract (red)`.

### Subtask T014 – Rename `status/adapters.py`

- Apply the table above to `adapters.py`, then update its module and function docstrings to neutral wording, removing the `drain_posture` history text (one factual sentence is enough: "`repo_root` is accepted for API stability and not forwarded to handlers").
- Update `status/__init__.py` re-exports and `__all__` (leeway).
- **Validation**: `grep -ni saas src/specify_cli/status/adapters.py` is empty, and `.venv/bin/python -m pytest tests/status/test_adapters_contract.py -q` passes except where a caller is still unrenamed.

### Subtask T015 – Rename `emit.py`, `outbound.py`, `lifecycle_events.py` and `decisions/emit.py` callers

- Apply the table to every `src/` caller. Use `rg -n "saas_fan|SAAS_FAN|SaasFan|lifecycle_saas|queue_saas_emission|_send_to_saas|fanout_lifecycle_event_hosted" src` until only out-of-scope names remain.
- `coordination/status_transition.py:472` reaches into `emit._saas_fan_out`. Rename the call. Do not refactor the private reach-in; just note it in history as existing.
- **Validation**: `.venv/bin/mypy` on every changed `src` module, and `ruff check`.

### Subtask T016 – Rename the test sink (fail-loud), test files and path-keyed ledgers

- **Steps**:
  1. `git mv tests/conftest_saas_sink.py tests/conftest_fanout_sink.py`, then rename the fixture `mock_saas_sink` → `mock_fanout_sink` and every `pytest_plugins = ("tests.conftest_saas_sink",)` reference (test_status_transition.py:48, test_wp05_status_emit_seam_feature_dir.py:29, test_outbound.py:37 and comments in test_phantom_fanout.py:83).
  2. **Make the sink fail loud** (census finding 3). `conftest_saas_sink.py:102` patches emit's import only `if hasattr(...)`, so after a rename it would silently skip, and the `call_count == 0` assertions (test_status_transition.py:527/:560/:580) would pass vacuously. Replace the conditional with an unconditional `monkeypatch.setattr(target_module, "fire_status_fanout", mock)`, which raises `AttributeError` when the target is missing. Add one planted test proving that a missing target raises.
  3. `git mv tests/status/test_saas_fanout_timeout.py tests/status/test_fanout_timeout.py` and `git mv tests/specify_cli/status/test_saas_resolved_binding_fanout.py tests/specify_cli/status/test_resolved_binding_fanout.py`. Update the path-keyed ledgers:
     - `tests/release/coverage_breadth_baseline.json` (node ids, :36-37) and `tests/release/coverage_breadth_evidence.md`;
     - `tests/architectural/test_timing_coverage_invariant.py:290`;
     - `pyproject.toml:2058` (whatever list it is in; keep the list sorted if it is sorted).

     Then run `tests/release/test_coverage_breadth.py` (it checks :302) and `tests/architectural/test_timing_coverage_invariant.py` on their own.
  4. If a renamed test function name contains `saas`, rename it too (node ids change), and update the coverage baseline consistently.

### Subtask T017 – Retarget test references and run the blast radius

- **Steps**:
  1. Rewrite every test reference in the `owned_files` and `leeway_files` lists:
     - string patch targets (`"specify_cli.status.emit.fire_saas_fanout"`, `"...adapters._saas_handlers"`, and so on; the census lists 13);
     - caplog exact-text assertions (`test_emit_fanout_after_adapter.py:102` breadcrumb, `test_emit.py:1862` genesis skip);
     - `monkeypatch.setenv("SPEC_KITTY_SAAS_FANOUT_TIMEOUT", ...)`;
     - fixture names.
  2. Final sweep: `rg -n "saas_fan|SAAS_FAN|SaasFan|lifecycle_saas|queue_saas_emission|_send_to_saas|fanout_lifecycle_event_hosted|conftest_saas_sink|mock_saas_sink|SaaS fan-out" src tests docs/api docs/architecture`. Only `docs/` lines (WP05's) and out-of-scope names may remain.
  3. Run:
     ```bash
     PWHEADLESS=1 .venv/bin/python -m pytest tests/status tests/specify_cli/status tests/specify_cli/coordination tests/specify_cli/decisions tests/core tests/specify_cli/core -q -n auto --dist loadfile
     PWHEADLESS=1 .venv/bin/python -m pytest <every other file in owned_files + leeway_files> -q -n auto --dist loadfile
     PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_timing_coverage_invariant.py tests/architectural/test_ledger_floor.py tests/release/test_coverage_breadth.py tests/architectural/test_no_legacy_terminology.py -q
     make test-fast
     ```
     Then run mypy on changed src modules, and ruff check plus `ruff format --check --force-exclude` on all changed files. Classify any red against the merge base before acting on it.

## Risks & Mitigations

- **Vacuous green after the rename**: covered by the fail-loud sink (T016.2) and the old-env-var test (T013.2).
- **Path-keyed ledgers**: rename and ledger update land in the same commit.
- **Hidden string references**: the final sweep in T017.

## Review Guidance

- The red commit precedes the renames.
- No alias of any old name exists (`rg` for every old identifier in `src` is empty).
- Seam logic diff is names and docstrings only. Check with `git diff -w` on `adapters.py` and `emit.py`.
- The sink is fail-loud, and the planted missing-target test exists.

## Progress & Status

Use `add-history`, `mark-status T013..T017 --status done`, then `move-task WP04 --to for_review`.

## Leeway files (out-of-map, mechanical rename edits; record one history line)

- `tests/agent/test_orchestrator_lane_allocation.py`
- `tests/agent/test_orchestrator_lane_context_refresh.py`
- `tests/architectural/test_status_module_boundary.py`
- `tests/integration/test_owned_lifecycle_acceptance_finalize.py`
- `tests/integration/test_review_durability_matrix.py`
- `tests/specify_cli/cli/commands/agent/test_emit_review_result.py`
- `tests/specify_cli/coordination/test_phantom_fanout.py`
- `tests/specify_cli/coordination/test_plain_door_semantics.py`
- `tests/specify_cli/coordination/test_status_transition.py`
- `tests/specify_cli/coordination/test_wp05_status_emit_seam_feature_dir.py`
- `tests/specify_cli/lanes/test_for_review_gate_parity.py`
- `tests/status/conftest.py`
- `tests/status/test_dependency_guard.py`
- `tests/status/test_emit.py`
- `tests/status/test_lifecycle_events.py`
- `tests/status/test_review_claim_role_aware.py`
- `tests/status/test_work_package_lifecycle.py`
- `tests/tasks/test_move_task_git_validation_unit.py`
- `src/specify_cli/status/__init__.py`
- `src/specify_cli/status/lifecycle_events.py`
