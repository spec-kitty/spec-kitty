# WP06 review cycle 1: changes requested

Reviewer: claude:opus:reviewer-renata:reviewer. Implementer of record: claude:opus:python-pedro.

## What holds

The removal itself is sound.

- **ADR 2026-10-29-1 Confirmation holds.**
  - `services/` and the three workflows are absent.
  - The pin gate, the release-asset owner gate and the packaging guards are green.
  - `test_shared_package_boundary` passes.
- **`contracts/` contents.** It holds exactly the five `fixtures/fixture_0*.json` files.
- **Absence gate.**
  - It is non-vacuous: seven planted positives, five planted negatives, a planted file in a tmp tree, and a check of which places are scanned.
  - It is not over-broad: `tests/`, `docs/` and Markdown are left out, and paths below an unpacked extra pass.
  - The `fast_gate` entry and the shard-timings row were swapped one-for-one.
- **No allowlist grew.** The duplicate-suite allowlist shrank by one entry and one `pinning_rule_inventory.json` row was removed.
- **Fleet change (deferred from WP04).** It is correct, and the tag-push cases still test what they tested: they plant a `tags` filter in a temp copy of the workflow directory, and the revert case needs that planted root to go red.
- **Router job.** `tests-contract-tools` now uses the composite action before the tests.
- **pyproject.** It keeps `contracts/**` excluded from the sdist; only `services/**` was dropped.

Run: 569 passed, 1 skipped over the gate files listed in the WP plus `tests/cross_cutting/packaging/` and the CI and release files. The skip (`test_no_duplicate_suite_execution.py:1021`) was already there before this WP.

## 1. MEDIUM: a live guard on `tests (contract tools)` was lost with `test_contracts_workflows.py`

`tests/ci/test_contracts_routing.py:148-249` ports the "exactly one home" rule, but not `test_the_tool_test_job_is_a_router_job_that_runs_the_corpus_marker_over_tests_contract_with_the_prelude` (old `test_contracts_workflows.py:1210-1222`).

The ported rule probes collection with the hard-coded `TOOL_TEST_MARKER` (`:214`) but never checks that either job's pytest command uses that marker. If the job's `-m` expression is edited, the one-home rule still passes while the job runs a different set.

Router-gate membership is still covered by `test_dual_mode_contract` and the `contract_tools` gating by `test_gate_selection_authority`. The marker and the job's `if` are not covered anywhere else.

Ask: in `test_contracts_routing.py`, assert the following for `tests-contract-tools`:
- its single pytest command carries `-m "corpus and not windows_ci"` (i.e. `TOOL_TEST_MARKER`) and runs through `uv run --frozen --no-sync pytest`;
- `needs == ["changes"]`;
- its `if` is `corpus || contract_tools` (normalised);
- the corpus-blocking job's command carries the same marker, since the rule assumes both jobs share it.

## 2. LOW-MEDIUM: `packs.yml` still deselects 27 deleted `tests/contract` modules

`.github/workflows/packs.yml:314` (`built-in-corpus-suite`) still carries `--deselect` for the 25 tool tests, `test_mission_status_examples.py` and `test_mission_status_contract_1_1.py`, all deleted here.

pytest ignores a `--deselect` that matches nothing, so this is dead configuration, not a failure. The guard that kept the list honest ("every deselected contract module exists", in `test_mission_status_routing.py`) was deleted in WP04, so nothing will flag this again. T026 asked to fix every live reference to the deleted tests.

Ask:
- Drop the 27 stale `--deselect` tokens. This is an out-of-map edit; give a one-line rationale.
- Add an existence check next to the one-home rule: every `tests/contract/...` deselected by the Packs corpus job is a live module. `tests/architectural/_gate_coverage.parse_workflow` already gives the ignores.

I checked that every live corpus-marked `tests/contract` module is still deselected by Packs, so nothing runs twice today.

## 3. LOW: the indirect-mark collection self-test was not ported

`test_a_module_with_an_unmarked_source_and_a_real_corpus_collection_is_still_judged` (old `:1441-1456`) proved that the collection probe under `collected_corpus_modules()` sees a corpus mark applied indirectly (through a shared `pytestmark` list from another module). The ported one-home rule depends on that property, and the self-test is about 15 lines with no dependency on the deleted workflows. Please port it into `test_contracts_routing.py`.

## Informational (no action needed for approval; WP08 or follow-up)

- `src/specify_cli/status/write_service_protocol.py:4`: the docstring still says the contract is `contracts/mission-write/openapi.yaml`.
- `tests/ci/test_lock_interop_peer.py:3-4`: the docstring names `services/mission-status-api/event-log` and the `lock-interop` job of `mission-status-api.yml`, both gone.
- `scripts/ci/lock_interop_peer.py` and its test no longer have a driver in core, because the `lock-interop` job left with the workflow. Either record how spec-kitty-events invokes it, or file a follow-up to move or retire it.

## Removed tests, accounted for

| Removed | Judgement |
|---|---|
| `test_events_import_frozen.py` | ADR D-9 exit clause: removed with `services/`; replaced by the absence gate. OK |
| `mission_status_gate_checks.py` + test, `test_mission_status_api_build.py` | build and workflow pins of removed subjects; events owns them. OK |
| `test_contracts_workflows.py` (70 tests) | contracts.yml / contracts-release.yml / lint / breaking-check pins: subjects removed. OK. The one-home rule and the src-routing rule were moved. The tool-job shape test was **lost** (finding 1), and so was the indirect-mark self-test (finding 3). The contracts.yml trigger-parity test is obsolete. |
| 25 tool tests, `test_mission_status_examples.py`, `test_mission_status_contract_1_1.py`, `fixtures/mission_status_pre_slice/` | D-6: events-owned code and source layout. OK, residual to port to events |
