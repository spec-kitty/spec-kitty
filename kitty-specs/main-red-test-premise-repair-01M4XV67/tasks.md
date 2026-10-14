# Tasks: Restore green main: stale test premises

**Mission**: main-red-test-premise-repair-01M4XV67 · **Topology**: single_branch (WPs run sequentially in the write checkout)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Record red-first proof for both failing tests at base | WP01 | |
| T002 | Re-pin `test_is_well_formed_declaration` over `(token, mission_type, expected)` | WP01 | |
| T003 | Add research-kind and placeholder cases | WP01 | |
| T004 | Apply the sanctioned corrections to `build_recovery_repo(full=True)` as a second fixture commit | WP01 | |
| T005 | Run the recovery, byte-identity and lint targeted suites | WP01 | |
| T006 | Add the `uv.lock`-only non-src filter group and output to ci-router | WP02 | [P] |
| T007 | Fan the group out to `upgrade` and `status` through a separate non-census `DEPENDENCY_MODULE_FANOUT` map | WP02 | |
| T008 | Lockstep pins: workflow coherence, gate-selection authority, fan-out census/allowlist | WP02 | |
| T009 | Focused selection test: lock-only selects upgrade+status; manifest-only adds no upgrade | WP02 | |

## WP01 – Re-pin the two stale test premises (#6240, #6238)

**Prompt**: [tasks/WP01-repin-stale-test-premises.md](tasks/WP01-repin-stale-test-premises.md) · **Priority**: P1 · **Dependencies**: none

Goal: both red tests pass on the pinned events version, with the audit as strict as before.

T001 Record red-first proof (WP01)
T002 Re-pin the well-formedness test signature (WP01)
T003 Research-kind and placeholder cases (WP01)
T004 Sanctioned-correction overlay in the full-corpus fixture (WP01)
T005 Targeted test runs (WP01)

Risk: the overlay could perturb other assertions that compare against the original bytes. Mitigation: run the whole recovery and byte-identity files.

## WP02 – Lock-file reducer bump selects upgrade and status shards

**Prompt**: [tasks/WP02-lockfile-fanout-routing.md](tasks/WP02-lockfile-fanout-routing.md) · **Priority**: P2 · **Dependencies**: none

Goal: a `uv.lock` change selects the `upgrade` and `status` module shards; `pyproject.toml` is excluded (operator ruling).

T006 ci-router filter group + output (WP02)
T007 DEPENDENCY_MODULE_FANOUT map (non-census) (WP02)
T008 Lockstep pins (WP02)
T009 Focused selection test (WP02)

Risk: the transcription and census guards red if any lockstep site is missed. Mitigation: a separate non-census map keeps the pack census untouched; a mutation proof shows the test is not vacuous.
