# Phase 0 Research — #7073 move-task fixture charter provisioning

All findings below were verified against `main` @ `d18c4f1d58` in this clone and with a scratch probe script run
through `uv run --frozen python`, plus a full run of the target module.

## R1. Where the mission-type activation set comes from

`charter.activation.mission_type_profiles.existing_mission_types(repo_root)` is the single source of truth
(FR-018). It builds a `PackContext` and returns `sorted(pack_context.activated_mission_types)`.
`PackContext.from_config` reads the activation source through `load_activation_ledger(repo_root)` and
`_read_activated_mission_types`, which is **total**: a genuinely absent `mission_type_activations` key resolves to
`frozenset()` with no all-four backfill (#2657 — "absent is not backfilled"), by design, because `PackContext` is
built on hot read paths that must not crash.

Consequence: an unprovisioned project reads as "no mission types activated", which is correct, and the
fail-closed for *creating* a mission lives at the mission-create boundary, not in the reader.

## R2. Where the fixture's exception comes from

`resolve_mission_type_context(repo_root, mission_type=...)` is the FR-006 activation gate: it checks the
candidate id against `existing_mission_types()` and raises

```
charter.activation.mission_type_profiles.UnknownMissionTypeError:
Unknown mission type 'software-dev'. No registered mission types are available.
```

(the exact text in issue #7073) when the id is not registered. Confirmed on the fixture: `existing_mission_types`
returns `[]` before any provisioning.

## R3. Why the 15 nodes reach that resolver, and why the failure is swallowed

`tests/tasks/test_move_task_git_validation_unit.py` drives the real `move-task` CLI
(`specify_cli.cli.commands.agent.tasks.app`) with `CliRunner`. A review-ward move runs
`_validate_ready_for_review` → `_is_code_producing` (`src/specify_cli/cli/commands/agent/tasks_parsing_validation.py:956`)
→ `charter.activation.api.code_producing_for` (`mission_type_profiles.py:1135`), which does:

```python
try:
    return bool(resolve_mission_type_context(repo_root, mission_type=mission_type).code_producing)
except Exception:  # noqa: BLE001 - gate must not crash; fall back to built-in default
    logging.getLogger(__name__).warning(
        "code_producing resolution failed for mission type %r; using the built-in default",
        mission_type, exc_info=True,
    )
    return bool(BUILTIN_CODE_PRODUCING.get(mission_type, False))
```

So the `UnknownMissionTypeError` in the issue is a **logged-with-traceback, caught** exception: every node reads
the built-in fallback (`software-dev` → `True`) rather than the project's resolved profile. That is the defect —
the guard's capability input is a degraded value that no assertion in the module covers.

## R4. What a provisioned project actually looks like

`spec-kitty init` calls
`specify_cli.provisioning.default_charter.provision_default_mission_type_activations(project_path)`, whose write
routes through `charter.activation.compiler.provision_mission_type_activations` →
`prepare_activation_write` / `resolve_activation_write_target` (the single activation writer). For a fresh
project (no ledger, no legacy activation keys) the target is the **activation ledger**,
`.kittify/charter/activation.yaml` (ADR `2026-10-19-1`), not `config.yaml`.

Scratch probe on a fixture-shaped repo (git init, `.kittify/config.yaml` containing `# Config\n`, one commit):

| State | `existing_mission_types` | `resolve_mission_type_context` | `code_producing_for` |
| --- | --- | --- | --- |
| before provisioning | `[]` | raises `UnknownMissionTypeError` | `True` via fallback + WARNING with `exc_info` |
| after `provision_default_mission_type_activations` | `['documentation', 'plan', 'research', 'software-dev']` | `software-dev`, `provenance=built-in`, 5 curated action steps | `True` from the resolved profile, no log record |

The ledger it wrote:

```yaml
mission_type_activations:
- software-dev
- documentation
- research
- plan
```

## R5. Why the fix is the fixture and not the assertion

Three candidate fixes, weighed against `DIRECTIVE_041` (judge the test, not git-blame):

1. **Provision the fixture** (chosen). The fixture claims to be a project; a real project has an activated
   mission type. Provisioning uses the production provisioner, so the fixture cannot drift from `init`, and the
   guard under test reads the same input shape it reads in production.
2. *Assert on the fallback path deliberately.* Rejected: it would pin the degraded branch as the contract, and
   the module is not a test of `code_producing_for`'s fallback — it is a test of `move-task`'s git validation.
3. *Make `_validate_ready_for_review` not require the capability.* Rejected: the capability is load-bearing
   (`software-dev` is code-producing, `research` is not), and removing it would weaken the guard — forbidden by
   C-001.

## R6. The blessed test helper already exists

`tests/_factories/__init__.py::provision_test_charter` is a thin wrapper over the production provisioner,
explicitly documented as "NOT a second, test-only seeder", and already used by fixtures that need a provisioned
charter. Reusing it satisfies C-003 and needs no new helper.

## R7. What the module looks like today, and what must not move

- 15 node ids in two classes (`TestMoveTaskGitValidation`, `TestMoveTaskCommitsLaneDeliverables`).
- Base run on `d18c4f1d58`: **8 failed, 7 passed**; the 8 stop at `IMPLEMENTATION_MISSING` (no change to the
  WP's `owned_files` in the evidence window) — the subject of #7057 / PR #7100, not of this mission.
- With PR #7100's fixture re-pin applied on top of `d18c4f1d58`: **15 passed**, and the
  `UnknownMissionTypeError` fallback warning still fires on every node — i.e. #7100 and this mission are
  independent, and this mission is the one that removes the swallowed exception.
- The fixture's commit shape is asserted by nodes (`Add implementation` is the lane branch's head subject), so
  provisioning must happen before the fixture's `Initial commit`.

## R8. CI coverage of the module

`tests/tasks` is listed under `out_of_matrix` in `.github/ci-module-registry.yml`, so no per-PR job runs this
module; local runs are the evidence and the nightly shard is the automated backstop. This is a pre-existing
coverage gap, owned by the module registry (it is also recorded in #7057's PR as deferred), not something this
test-only fix changes.
