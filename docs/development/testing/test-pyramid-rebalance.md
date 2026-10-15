---
title: Test-pyramid rebalance plan
description: Which layer a Spec Kitty test belongs in, and the measured, wave-by-wave plan for moving end-to-end coverage from tests/integration and tests/e2e into the acceptance scenarios.
doc_status: active
updated: '2026-10-15'
audience: docs/context/audience/internal/lead-developer.md
type: explanation
related:
- docs/adr/4.x/2026-10-15-1-qa-and-core-share-the-acceptance-scenarios-and-absorb-engineering-tests-through-a-ledger.md
- docs/development/testing/integration-e2e-inventory.md
- docs/development/testing/acceptance-scenarios.md
- docs/development/testing/index.md
---

# Test-pyramid rebalance plan

**Status:** proposed with [ADR 2026-10-15-1](../../adr/4.x/2026-10-15-1-qa-and-core-share-the-acceptance-scenarios-and-absorb-engineering-tests-through-a-ledger.md); QA and core agree it there. Epic [#6101](https://github.com/spec-kitty/spec-kitty/issues/6101).

**Reader:** anyone adding, moving or deleting a test, who needs to know which layer it belongs in and what has to happen before an end-to-end test may be deleted.

## The layers

| Layer | Where | Runs | Checks | Owner |
|---|---|---|---|---|
| Unit | `tests/unit/`, a module's own tree (`tests/status/`, `tests/charter/`, ...) | every pull request (`make test-fast`, module matrix) | one function or class, no git, no CLI process | core |
| Architectural gates | `tests/architectural/` | every pull request (battery) | rules over the source and CI config | core |
| Contract | `tests/contract/`, `contracts/` | every pull request | published interfaces and their tools | core |
| Integration | `tests/integration/` | nightly only (`integration-next`) | several real components together, often with internals patched, faults injected or internal state built by hand | core |
| End-to-end (engineering) | `tests/e2e/` | per pull request only when `tests/e2e/**` changes; nightly (`e2e`) | a CLI workflow from source (`python -m specify_cli`) on Linux | core |
| Acceptance scenarios | `tests/scenarios/**.feature` + `acceptance-jvm/` | per pull request: contract check only; nightly: run on Linux, macOS and Windows | what a user sees from the built wheel: exit code, output, files, git state | QA and core (scenarios), core (runner) |

The shape to aim for: many unit tests, fewer integration tests, and a thin end-to-end layer, where a test that checks a promise to users is an acceptance scenario rather than a Python e2e or integration test.

## Where a test belongs

Ask in order and stop at the first yes.

1. **Does it check one function, class or file transformation, with no git and no CLI process?** Unit test, in the module's tree.
2. **Does it check a rule about the code base or CI config?** Architectural gate.
3. **Does it need internals:** a monkeypatch or fake collaborator, an injected fault, a race, an internal module called directly, a private environment flag, or state files written by hand (`meta.json`, `status.events.jsonl`, `lanes.json`, anything under `.kittify/`)? Integration test. It stays pytest.
4. **Can a user reach the arrange with the CLI and plain git, and see the outcome as exit code, output, files or git state?** Acceptance scenario. If it restates a promise, QA can tag it `@promise:<id>`.
5. **Otherwise** (it needs the source tree, an older wheel, a concurrency barrier, timing): engineering e2e test.

Two rules from the ADRs bound step 4:

* A scenario's builders reach state only by running the CLI ([ADR 2026-10-13-1](../../adr/4.x/2026-10-13-1-acceptance-scenarios-link-to-promises-by-identifier-only.md), decision 5). Plain git, and files a user edits by hand in git (a tracked file, `.git/info/sparse-checkout`), are allowed.
* A test is a scenario or an engineering test, never both ([ADR 2026-10-11-3](../../adr/4.x/2026-10-11-3-acceptance-testing-and-bdd-support.md)).

## Moving a test into a scenario

1. Write the scenario with at least the assertions of the test, on an equal or stronger arrange (a real `spec-kitty init` instead of a copied `.kittify`, a real non-terminal stdin instead of a patched probe). Leave it untagged so it gates the nightly.
2. Run it: `gradle -p acceptance-jvm test --no-daemon -Pacceptance.pass=gating` (see [CLI acceptance scenarios](acceptance-scenarios.md)).
3. Prove it can fail: put the defect the test guards back in the source, run the scenario, and see it go red, and only it. Then restore the source. The runner's test task never resolves UP-TO-DATE, so a re-run after a change under `src/` really runs against a freshly built wheel.
4. Delete the test, or the test function, in the same pull request.
5. Add a row to `tests/scenarios/absorption-ledger.json`: `retired` (file, or `file::Class::test`), `replaced_by` (the `feature::scenario name`, or a surviving pytest node id), `issue`, and a `note` that says what changed in the arrange and what is not covered.
6. Remove what pointed at the deleted file: the `[tool.ruff.format].exclude` list in `pyproject.toml`, `ruff.toml` per-file ignores, `tests/architectural/global_state_allowlist/*.yaml`.

`tests/architectural/test_scenario_contract.py` fails the pull request if a retired test still exists, a replacement is missing or not gating, or a file of the 2026-10-15 baseline disappeared without a whole-file row.

Only tests whose feedback already arrives nightly may move: all of `tests/integration`, and `tests/e2e`. A test that runs on every pull request keeps running there.

## Baseline and progress

Measured with the files' own text: files named `test_*.py`, all `.py` lines in the tree, and `def test_*` functions.

| Tree | 2026-10-15 baseline (`f87ecb8a21`) | After waves 1, 1b, R and D | Change |
|---|---|---|---|
| `tests/integration` | 177 files, 64,552 lines, 1,141 tests | 151 files, 59,294 lines, 970 tests | -26 files (-15%), -5,258 lines (-8%) |
| `tests/e2e` | 7 files, 3,264 lines, 22 tests | 5 files, 2,868 lines, 12 tests | -2 files, -396 lines (-12%) |
| `tests/scenarios` (gating) | 2 files, 5 scenarios | 8 files, 24 scenarios | +19 scenarios |

Of the 28 files that left the two trees, 3 were absorbed whole into scenarios, 6 were duplicates
retired after their unique assertions were folded into the surviving tests, and 19 were unit tests
moved to their module's tree (where they now run on every pull request). A further 17 test
functions moved into scenarios from files that stay. `tests/scenarios/absorption-ledger.json`
holds one row for each (42 rows).

The [inventory](integration-e2e-inventory.md) classifies every baseline file:

| Bucket | `tests/integration` | `tests/e2e` |
|---|---|---|
| Scenario (whole file can move) | 10 | 2 |
| Scenario, partly (some tests can move) | 22 | 3 |
| Stays integration (needs internals) | 119 | 1 |
| Belongs in unit tests | 18 | 1 |
| Duplicate of another test | 6 | 0 |
| P0 reproduction (nightly `p0-repro` lane) | 2 | 0 |

Most of `tests/integration` correctly stays pytest. The realistic target is the 32 movable integration files, the 18 misplaced unit files and the 6 duplicates: 56 files, about a third of the tree.

## Waves

Each wave has an exit target, measured with the same counts.

| Wave | Content | Needs | Status | Exit target |
|---|---|---|---|---|
| 1 | Sparse-checkout doctor, `consolidate --abort` with a user's merge, Mission create and its refusals, the retired alias option refused; two duplicates retired | none | done | 13 ledger rows, 11 new gating scenarios |
| 1b | Black-box cases that need only the CLI and plain git: `implement` and `consolidate` refused under sparse-checkout, `consolidate --abort` on a Mission with no merge state, `mission close --discard`, a fresh `init` ready for `next`; new coverage for `specify` outside a project | new steps: commit everything, branches unchanged, clean tree, a Mission's file content | done | 6 more ledger rows, 8 more gating scenarios |
| 1c | The rest of the black-box candidates: charter synthesize and status freshness on a fresh project, the charter quickstart checks, the custom Mission error envelopes | new Arrange steps (charter interview with defaults); the custom Mission definition lives under `.kittify/missions/`, which needs a ruling like decision 6 | open | 4 integration files partly absorbed |
| 2 | Mission lifecycle: implement, review, reject, approve, consolidate, `single_branch` write checkout, re-finalize frozen lanes, review cycles, the e2e full workflow and coordination status placement | a decision on authored content in Arrange (ADR 2026-10-15-1, decision 6), then a "Mission with finalized work packages" builder | blocked on the decision | 15 integration files and 3 e2e files absorbed |
| 3 | Org charter packs in lint, status and context | a CLI command that registers an org pack (no command does today, so the arrange would write `.kittify/config.yaml`); file the gap upstream first | blocked on the CLI gap | 3 integration files absorbed |
| D | Unit tests misplaced in `tests/integration` and `tests/e2e` moved to their module's tree | none | done | 19 files moved; one test that could not fail deleted |
| R | Duplicate claims verified; unique assertions folded into the surviving tests, then the duplicate retired: `test_policy_source_attribution.py`, `test_reject_without_force.py`, `test_session_warning_once.py`, `test_mission_close.py` (plus `test_legacy_feature_alias.py` and `test_hic_terminus_e2e.py` in wave 1) | none | done | 6 files |

The two P0 reproductions (`test_p0_repro_5932_*`, `test_p0_repro_5939_*`) already drive only the CLI. When their defects are fixed, they can become scenarios tagged `@defect:<issue>`.

## Risks

* **Windows and macOS.** A scenario proven on Linux gates three operating systems. Run the nightly by `workflow_dispatch` on the branch before merging a wave that adds path or git-state assertions.
* **Assertions lost in translation.** The ledger proves a replacement exists, not that it asserts as much. The reviewer compares the retired test with its scenario; the row's `note` must name any difference.
* **Function-level deletions.** Removing a test function from a kept file without a row is not detected; reviewers check it.
* **Feedback timing.** Absorbed coverage runs nightly, as it did before. A red night files one P0 through `acceptance-bdd-escalation`.

## Related

* [Integration and e2e inventory](integration-e2e-inventory.md)
* [CLI acceptance scenarios](acceptance-scenarios.md)
* [ADR 2026-10-15-1](../../adr/4.x/2026-10-15-1-qa-and-core-share-the-acceptance-scenarios-and-absorb-engineering-tests-through-a-ledger.md)
