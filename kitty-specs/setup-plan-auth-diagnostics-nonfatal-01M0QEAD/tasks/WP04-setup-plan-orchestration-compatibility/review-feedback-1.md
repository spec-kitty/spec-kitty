> Hostname cleanup: `retired-host.example` redacts the former Team Kitty hostname in historical evidence; the current endpoint is `https://team.spec-kitty.ai`.

# WP04 review feedback — rejected

## Blocking findings

### 1. The required combined quickstart suite is order-dependent because WP04 leaks the authenticated TokenManager singleton

`tests/runtime/test_setup_plan_sync_evidence.py::_install_real_storage` resets the process singleton before patching `SecureStorage.from_environment`, but it never resets that singleton after the test. Once `test_real_encrypted_refresh_session_never_reads_queue_scope` initializes the manager from its authenticated encrypted store, later tests inherit that manager after the monkeypatch itself has been undone.

Reproduction:

```text
SPEC_KITTY_ENABLE_SAAS_SYNC=0 uv run pytest -q \
  tests/runtime/test_setup_plan_sync_evidence.py::test_real_encrypted_refresh_session_never_reads_queue_scope \
  tests/sync/test_sync_boundary_preflight.py::test_collect_foreground_identity_none_when_unauthenticated

1 passed, 1 failed
AssertionError: identity.server_url == 'https://retired-host.example' (expected None)
```

The preflight test passes alone. The full required quickstart union produced `260 passed, 1 skipped, 1 failed` for the same reason. Add teardown/finalizer isolation that resets the canonical token manager after every real-storage test, then rerun the combined quickstart command in its documented order.

Affected file: `tests/runtime/test_setup_plan_sync_evidence.py:151-162`.

### 2. T013/T017/NFR-001 do not freeze or exercise the binding compatibility matrix

`test_local_outcome_reporter_preserves_complete_baseline_payload_and_exit` constructs six literal payload dictionaries and calls only the new reporter. It neither captures payloads/exits from the real pre-existing `setup_plan` entry point nor runs the required readiness cross-product. It omits distinct committed-pristine/insufficient, non-substantive/uncommitted-spec, and project/context/git-resolution rows, and it does not exercise real-command auth-acquisition failure, route null/denied/raised, or SaaS-disabled fatal-probe cases. This is a synthetic-fixture test: deleting the orchestration paths would leave its payload assertions green.

The missing matrix also conceals a production-path gap. `setup_plan()` collects `hosted_decision` at `mission_setup_plan.py:1077`, then delegates git failure reporting to `_enforce_git_preflight` at lines 1079-1083. That helper emits its own payload and raises `typer.Exit` (`mission.py:375-382`); the outer `except typer.Exit` re-raises without passing the already-collected diagnostics through `_report_setup_plan_outcome`. Thus an applicable git-preflight row cannot receive the contract's additive warnings through the sole reporter.

Remediation:

1. Capture exact payload and exit baselines from the dependency-resolved pre-production entry point for every binding matrix row.
2. Drive the real command across every applicable auth/boundary/route variant and compare the complete payload after removing only `warnings`, plus exact exit equality.
3. Include parser-level exactly-one-JSON-object checks and representative real-command human parity.
4. Cover auth acquisition/evaluation raise, route null/denied/raise, and SaaS-disabled fatal auth/boundary/route probes through the real command.
5. Route git-preflight failure reporting through the authoritative outcome reporter once evidence exists, preserving the legacy payload and exit.
6. Prove all enumerated refused sinks (not only lifecycle fan-out and dossier) remain at zero while local lifecycle JSONL exists.

Affected files: `tests/specify_cli/cli/commands/agent/test_mission_setup_plan_phases.py:89-146`, `tests/runtime/test_setup_plan_sync_evidence.py:165-223`, `src/specify_cli/cli/commands/agent/mission_setup_plan.py:1065-1089`, and `src/specify_cli/cli/commands/agent/mission.py:361-382`.

## Verification summary

- ATDD red-first chronology: PASS. Commit `9c586bf05` changes tests only and is red against the dependency-resolved pre-production code (`7 failed` for the newly added cases). The red test is nevertheless synthetic/incomplete as described above.
- Ruff: PASS.
- strict mypy over all five changed mission source files: PASS.
- terminology gate: PASS.
- extra setup-plan branch-match suite: PASS (`4 passed`).
- issue evidence: PASS. `issue-matrix.json` records #2695 and #3621 as `fixed`, and #3127 as `deferred-with-followup` and an external release-readiness gate.
- architecture gate and negative control: PASS in isolation, but they do not replace the missing production-chain matrix.

## Eight anti-pattern checks

1. Dead code: PASS — every new WP04 helper/class has a production caller in `mission_setup_plan.py`.
2. Synthetic-fixture test: FAIL — the claimed compatibility matrix is literal reporter input, not real command/baseline behavior.
3. Silent empty return: PASS — new no-op compatibility seams are explicitly documented; no unexplained new empty failure return was found.
4. FR coverage: FAIL — FR-001/FR-011/FR-014 full matrix and several T017 real-command variants are not asserted.
5. Frozen surface: PASS — no net WP04 production/test change lands outside the declared implementation surfaces after lane cleanup.
6. Locked decision: PASS — no forbidden strict-sync, queue-auth, or hosted-only weakening pattern was introduced.
7. Shared-file ownership: PASS — lane-d owns the net implementation/doc/test surfaces; transient planning-artifact changes were removed by the lane cleanup/rebase.
8. Production fragility: PASS — no new transient-race raise was introduced; the new explicit exit follows existing local error behavior.
