---
work_package_id: WP06
title: specify_cli readers, fail-open callers, mission-step executor, SPDD deny
dependencies:
- WP05
requirement_refs:
- FR-016
- FR-017
planning_base_branch: core-align-3-persistent-deactivation
merge_target_branch: core-align-3-persistent-deactivation
branch_strategy: Planning artifacts for this mission were generated on core-align-3-persistent-deactivation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into core-align-3-persistent-deactivation unless the human explicitly redirects the landing branch.
subtasks:
- T030
- T031
- T032
- T033
- T034
- T035
phase: Phase 3 - Readers honour the ledger
history:
- at: '2026-10-19T12:17:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/
create_intent:
- tests/architectural/test_no_raw_activation_membership.py
- tests/specify_cli/test_activation_fail_closed_callers.py
- tests/specify_cli/test_cli_readers_honour_deny.py
- tests/specify_cli/mission_step_contracts/test_executor_deny.py
- tests/charter_offering/test_spdd_probe_deny.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/review/gate_bindings.py
- src/specify_cli/mission_step_contracts/executor.py
- src/specify_cli/charter_runtime/preflight/runner.py
- src/specify_cli/invocation/registry.py
- src/specify_cli/invocation/empty_charter.py
- src/specify_cli/cli/commands/agent/workflow_executor.py
- src/specify_cli/cli/commands/agent/mission_finalize_bootstrap.py
- src/specify_cli/cli/commands/agent/tasks_status_cmd.py
- src/specify_cli/cli/commands/profiles_cmd.py
- src/specify_cli/cli/commands/charter/_synthesis.py
- src/specify_cli/cli/commands/charter/list_cmd.py
- src/charter/offering/spdd_reasons/activation.py
- tests/architectural/test_no_raw_activation_membership.py
- tests/specify_cli/test_activation_fail_closed_callers.py
- tests/specify_cli/test_cli_readers_honour_deny.py
- tests/specify_cli/mission_step_contracts/test_executor_deny.py
- tests/charter_offering/test_spdd_probe_deny.py
- src/specify_cli/cli/commands/charter/_resynthesis_preflight.py
- tests/conftest.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – specify_cli readers, fail-open callers, mission-step executor, SPDD deny

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro` (`packs/built-in/agent_profiles/python-pedro.agent.yaml`)
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` in the event log; address every item; record with `spec-kitty agent tasks add-history WP06 --note "..."`.

---

## Objective

The CLI-side consumers use the `PackContext` membership accessor (`admits` / `effective_ids`)
and stop swallowing activation-store errors, so a denied artifact is not served by the review
gate, implement preflight, the mission-step executor, the invocation registry, the profiles
command or the list command; the offering-side SPDD probe subtracts deny.

## Context

- Plan IC-06; research.md D-07, D-20, D-21; FR-016 reader list; FR-017 fail-closed.
- Builds on WP05 (`PackContext.admits`, `effective_ids`, `deactivated_urns`; `ActiveCharterConfigError` from `from_config`).
- `specify_cli` reaches activation only via `charter.activation.api` or existing baseline rows;
  the baseline must not grow. If a call site needs a new symbol, export it on the API.
- SPDD probe: offering layer, no `charter.activation` import (C-002); the required floor is a
  documented residual (D-07).
- Shared files (ordered): `charter/offering/spdd_reasons/activation.py` (from WP03), the raw-membership gate (from WP05), `cli/commands/charter/_resynthesis_preflight.py` (→WP07).
- Mission order: WP06 of 15 (strictly linear). Transition model D0: tolerant mode is the default. New deny and fail-closed tests are ledger-seeded and run strict through `SWEPT_PREFIXES`; a malformed **ledger** fails closed in either mode.

## Branch Strategy

- **Strategy**: single_branch; sequential in the repository root checkout on `core-align-3-persistent-deactivation`.
- **Planning base branch**: `core-align-3-persistent-deactivation`
- **Merge target branch**: `core-align-3-persistent-deactivation`

```bash
spec-kitty agent action implement WP06 --agent claude --mission persistent-deactivation-ledger-01M59YAA
```

## ATDD (red first)

T030 writes: (a) fail-closed tests — a malformed `activation.yaml` makes the review gate binding,
the mission-step executor and charter preflight raise `ActiveCharterConfigError` instead of
returning an unfiltered graph; (b) deny tests — a denied agent_profile is absent from
`spec-kitty profiles list` and the invocation registry, a denied mission-step contract is not
picked by the executor, `charter list` shows the deactivated column, the SPDD probe returns False
when its directive/tactic is denied. Commit before implementation; record the red summary.

## Subtasks

### Subtask T030: Failing acceptance tests

**Steps**:
1. `tests/specify_cli/test_activation_fail_closed_callers.py`: one test per site in T031 using a ledger containing `activated_directives: notalist` (malformed) and, separately, `activated_tactics: [x]` plus `unknown_key: 1`. **Positive control (F15)**: each fail-closed test runs the same caller on the same fixture with a valid ledger first and asserts success.
2. `tests/specify_cli/test_cli_readers_honour_deny.py`: profiles list / registry / workflow-executor implement precondition / finalize bootstrap / tasks status / list command, each with a deny entry seeded via `tests/_factories/activation_ledger.py`, each first asserting the id is listed/served before the deny (F15).
3. `tests/specify_cli/mission_step_contracts/test_executor_deny.py`: deny the contract the executor would pick for an action; assert it is reported not runnable and never picked.
4. `tests/charter_offering/test_spdd_probe_deny.py`: probe True with allow, False with deny (directive id spelled like `_is_directive_038` expects and in stem form), unchanged early False without `config.yaml`.

### Subtask T031: Fail-open → fail-closed (P2)

**Steps**: let `ActiveCharterConfigError` propagate (as `OrgPackEnvVarUnsetError` already does) at:
- `review/gate_bindings._resolve_pack_context` (`gate_bindings.py:238-251`);
- `mission_step_contracts/executor._resolve_pack_context` (`executor.py:593-608`);
- `charter_runtime/preflight/runner.py:221-224`: its docstring contract becomes "never raises except activation-store errors".
Keep other exception handling unchanged; add a one-line rationale comment at each site.

### Subtask T032: Mission-step executor deny (P6)

**Steps**: `executor.py:184` filters `_contracts.get_by_action(...)` through `pack_context.admits(ArtifactKind.MISSION_STEP_CONTRACT, contract_id)`; a denied contract is reported as not runnable with a message naming `charter activate mission-step-contract <id>`.

### Subtask T033: CLI readers onto the accessor (M2)

**Steps**:
1. `invocation/registry.py:59-142`, `invocation/empty_charter.py:84`.
2. `cli/commands/agent/workflow_executor.py:715` (implement precondition), `mission_finalize_bootstrap.py:82`, `tasks_status_cmd.py:75`.
3. `cli/commands/profiles_cmd.py:25-37, :173, :332`.
Also `cli/commands/charter/_resynthesis_preflight.py:40` (raw `getattr(pack_context, activated_*)`, flagged by WP05's gate). Replace raw `activated_<plural> is None` / `getattr` logic with `admits`/`effective_ids`; remove any temporary allowlist entries WP05 left in `tests/architectural/test_no_raw_activation_membership.py` (this WP co-owns that gate file, ordered after WP05; edit it only to delete those entries).

### Subtask T034: SPDD probe deny (D-07, M3)

**Steps**:
1. In `charter/offering/spdd_reasons/activation.py:150-167`, read allow **and** deny from whatever the one kernel resolver selects:
   - tolerant: the legacy surface (including deny keys carried there) or the ledger;
   - strict: the ledger.
2. Apply `allow and not deny`. The directive comparison reuses `_is_directive_038` normalisation (m3).
3. Under strict `UNMIGRATED`, raise the probe's own `_SpddActivationConfigError` naming `spec-kitty upgrade`. The offering never imports `charter.activation`.
4. No required floor (a residual the ADR records).
5. Pin in `tests/charter_offering/test_spdd_probe_deny.py`, which runs strict through `SWEPT_PREFIXES`:
   - deny on the ledger → False;
   - an `UNMIGRATED` fixture → `_SpddActivationConfigError` naming `spec-kitty upgrade`;
   - the same fixture after seeding a ledger → True (positive control).
6. Tolerant legacy-surface reading stays pinned by the existing `tests/charter/test_spdd_reasons_activation_parity.py`, unchanged. Do not add a tolerant-only case (test-mode rules).

### Subtask T035: Synthesis signal and list command

**Steps**:
1. `cli/commands/charter/_synthesis.py:606-625, 741-752`: delete `_ACTIVATION_SIGNAL_KEYS`; the "activation established" probe reads `load_activation_ledger` via the API; a non-empty deny list also counts as established.
2. `cli/commands/charter/list_cmd.py:270`: the deactivated column comes from `ActivationLedger.deny_for(kind)` via the API (no `list_deactivated`, R12).

## Validation / targeted test surface

```bash
cd /home/user/spec-kitty
.venv/bin/python -m pytest -q tests/specify_cli/test_activation_fail_closed_callers.py tests/specify_cli/test_cli_readers_honour_deny.py tests/specify_cli/mission_step_contracts/test_executor_deny.py tests/charter_offering/test_spdd_probe_deny.py
.venv/bin/python -m pytest -q tests/review/test_gate_bindings.py tests/specify_cli/review tests/specify_cli/mission_step_contracts tests/specify_cli/charter_runtime tests/charter/test_spdd_reasons_activation_parity.py tests/charter/test_charter_context_spdd_reasons.py tests/charter_offering/test_spdd_reasons_skill.py
.venv/bin/python -m pytest -q -n auto --dist loadfile -m "not timing and not stress" tests/specify_cli/cli/commands tests/specify_cli/invocation tests/charter_offering
.venv/bin/python -m pytest -q -n auto --dist loadfile -m "not timing and not stress" tests/review/test_pre_review_gate_integration.py tests/runtime/test_bridge_composition.py tests/unit/mission_loader tests/agent tests/status tests/lanes tests/git tests/specify_cli/status
.venv/bin/python -m pytest -q -n0 -m timing tests/perf/test_tasks_status_baseline.py
.venv/bin/python -m pytest -q tests/architectural/test_no_raw_activation_membership.py tests/architectural/test_org_activation_seam.py tests/architectural/test_charter_sole_door_agent_profile_repository.py tests/architectural/test_no_read_side_bypass.py tests/architectural/test_charter_sole_door_resolver_imports.py tests/architectural/test_runtime_charter_activation_boundary.py tests/architectural/test_charter_offering_does_not_import_activation.py tests/architectural/test_charter_activation_api_reexport.py tests/architectural/test_layer_rules.py tests/architectural/test_no_dead_symbols.py
make test-fast
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen mypy <touched src files>
```

## Standing orders

- python-pedro; complexity ≤ 15; ruff/format(`--force-exclude`)/mypy clean; no suppressions.
- Append dated entries to the Mission's `traces/*.md` (fail-closed contract change of preflight goes in `design-decisions.md`).
- Do not edit shipped migrations.

## Definition of Done

- The three fail-open callers propagate activation-store errors, each with a test.
- Every FR-016 CLI-side reader uses the accessor; raw-membership gate allowlist empty.
- SPDD probe subtracts deny; residual documented.
- Gates green; subtasks marked done.

## Risks

- `preflight/runner.py` gains a raising path: callers that relied on "never raise" must surface the error cleanly (exit 1 with the body), not a traceback.
- Boundary baseline growth: route via API.

## Reviewer Guidance

- Malformed-ledger runs of `charter context`, implement preflight, review gate and executor must all fail closed.
- Check no new baseline rows.

## Test-mode rules (analyze pass 2, binding)

- **New test files run strict through `SWEPT_PREFIXES`.** Every new test file this WP adds is
  appended, by exact path, to `SWEPT_PREFIXES` in `tests/conftest.py`, in the same commit as the
  file. The edit is append-only; this WP co-owns `tests/conftest.py`, dependency-ordered.
- **How strict mode is set (M1).** A `pytest_runtest_setup(item)` hookimpl (`tryfirst=True`) in
  `tests/conftest.py` sets or clears `os.environ["SPEC_KITTY_ACTIVATION_STRICT"]` from the
  item's path **before any fixture of that item is set up**, so function- and module-scoped
  fixtures see the item's mode. `test` means strict, and a stray legacy key raises. A matching
  `pytest_runtest_teardown` restores the previous value.
- **Session-scoped activation-seeding fixtures must be mode-independent (L1).** A session fixture
  is set up once, by its first user, in that item's mode. No such fixture exists today (grep).
  Any future one must be function-scoped, or go through the
  WP11 step-0 helpers or `tests/_factories/activation_ledger.py`, which work in both modes.
- **No test file references `SPEC_KITTY_ACTIVATION_STRICT`.** That covers `setenv`, `delenv`
  and string mentions. There are two exceptions: the kernel resolver test
  `tests/kernel/test_activation_ledger_store.py` (WP02 creates it, WP14 rewrites it), and the
  swept-prefix fixture in `tests/conftest.py` itself (WP02 creates it, WP14 deletes it).
- **No new tolerant-mode-only test.** Tolerant behaviour is pinned only by the existing tests,
  which stay unchanged until their sweep WP, and by the kernel resolver test. An existing test
  file this WP modifies must stay correct in tolerant mode. Tests for new behaviour go in new,
  ledger-seeded files.
