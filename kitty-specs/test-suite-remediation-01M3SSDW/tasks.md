---
description: "Work package task list for test-suite-remediation-01M3SSDW"
---

# Work Packages: Test-suite remediation: masked greens and pin honesty

**Inputs**: Design documents from `kitty-specs/test-suite-remediation-01M3SSDW/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md, data-model.md, contracts/dead-symbol-allowlist.md, quickstart.md, research/{masked-greens,pin-inventory,dead-symbol-rekey}.md

**Tests**: This mission's product under change *is* the test suite. Every WP edits tests, and every FIX/RETIRE carries a planted-break proof (FR-011). That test work is the deliverable itself, not optional extra work.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work package is independently deliverable and testable. The plan's Implementation Concern Map (IC-01..IC-12) maps to WPs as follows:

- IC-01 → WP01; IC-02 → WP02; IC-03 → WP03; IC-04 → WP04; IC-05 → WP05.
- IC-06 splits along the pin-inventory G2 line (WP06) and the G1+G3 line (WP07).
- IC-07 → WP08; IC-08 → WP09; IC-09 → WP10.
- IC-10 splits into loader + YAML + migration (WP11) and the gate rewrite + bite battery (WP12).
- IC-11 → WP13, with two re-cuts:
  - The refresh helper and its 17 tests are retired in **WP12**. `test_refresh_dead_symbol_hashes.py` imports `_compute_dangling` / `_compute_offenders` / `_compute_stale` from the gate, so it cannot outlive the gate rewrite. Retiring it in the same WP keeps every commit green.
  - `docs/development/reference/ci-gate-mechanics.md` moves to **WP15**, so one WP owns every `docs/` edit and the regenerated docs indexes.
- IC-12 splits into ratchet rows + keys floor (WP14) and ADR + docs (WP15).

**Prompt Files**: Each work package references a matching prompt file in `tasks/`. Treat this file as the high-level checklist; the deep implementation detail lives inside the prompt files.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done --mission test-suite-remediation-01M3SSDW`. The reduced event-log snapshot is the sole subtask-completion authority.

## Path Conventions

- **Single project**: `src/`, `tests/`, `docs/` at the repository root.
- The only **planned** product-source change is `src/specify_cli/doctrine/pack_validator.py` (WP01, FR-005 fix commit only; C-005).
- Any other `src/` edit is allowed only as a sanctioned FR-005 fix under mission-wide rule A below: a red-first, separate `fix(...)` commit, with a one-line rationale in the WP notes (analysis C1).

## Mission-wide rules (every WP carries them in its prompt)

- **C-001 / NO_FULL_HEAVY_SUITES_IN_MISSION**: named test files and named gate files only. Never `tests/architectural/` as a directory, never `make test-full`, and no stress, timing, e2e or performance suite run. A named e2e or integration **file** run by name counts as a named test file, not a suite (plan reading; analysis B2). `make test-fast` is the shared baseline.
- **C-011, ATDD-first (D1 reading, `traces/design-decisions.md`)**:
  - product-code changes take a failing-first test commit, red on base and green at the WP's final commit;
  - test-only WPs carry the planted-break red→green proof;
  - WP10 commits strict-xfail ATDD tests;
  - WP11 commits its loader tests failing-first, before the loader;
  - WP12 flips the WP10 tests green.

  Every WP states this in its "Definition of Done (C-011)".
- **A. New product defect (FR-005, DM-01M3SSV4; analysis C1)**: if an unmasked or converted test exposes a new product defect, never re-mask it.
  - If the fix fits the WP: a red-first, separate `fix(...)` commit, as a sanctioned out-of-map `src/` edit, with a one-line rationale in the WP notes, a new issue and an issue-matrix row.
  - Otherwise: a strict xfail citing a newly filed open issue, and a report to the orchestrator.
- **B. Evidence completeness (FR-011; analysis C2)**: the evidence in the review note and final report is the **full** per-item record (`path::function::mutation`, old result, new result on the break, result after revert, command), never a summary.
- **C. Lint and type gates (NFR-005; analysis C3)**: ruff check and format-check on every touched `.py` file; `mypy` on touched `src/` files and on new or rewritten typed test modules (WP05, WP10, WP11, WP12). Compare against the base where findings pre-exist, and add 0 new ones.
- **C-007**: planted breaks are scratch edits, reverted and never committed. Run `git diff --stat src/` (and `git diff --stat` overall) before **every** commit.
- **Evidence (FR-011)**: records use the data-model.md §4 shape. They go into the WP's hand-off note and final report. The orchestrator materializes them under `kitty-specs/.../evidence/` at closeout (see "Closeout (orchestrator)" below). **Never** write them into a `kitty-specs/` path from a code WP.
- **Format-excluded files** (`pyproject.toml [tool.ruff.format].exclude`) are edited **without** running `ruff format` on them.
- **CHANGELOG entries are not written by WPs**; the orchestrator writes them at closeout.
- **Commit trailers**: `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` (sonnet WPs) or `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (opus WPs), then `Claude-Session: https://claude.ai/code/session_016Yu85b3RXSx3QzQphAUzpf`.

---

## Work Package WP01: Doctrine probe unmask and fragment-intent product fix (Priority: P1) 🎯 MVP

**Goal**: The 9 doctrine-probe tests execute instead of skipping, and the defect that unmasking surfaced is fixed red-first: `_collect_fragment_edge_intent` ignores `drg/fragment.yaml` intent and emits a spurious `same_id_collision` advisory.
**Independent Test**: `uv run --frozen pytest tests/specify_cli/doctrine/test_pack_validator.py tests/integration/test_quickstart_end_to_end.py -n0 -q -rs` shows 0 SKIPPED for the 9 former probe tests (was 9), and the fragment-intent regression test was red on the red commit and is green on the fix commit.
**Prompt**: `tasks/WP01-doctrine-probe-unmask-and-fragment-intent-fix.md`
**Requirement Refs**: FR-001, FR-005, FR-011, NFR-001, NFR-004, NFR-005, C-001, C-005, C-007, SC-001, SC-005

### Included Subtasks

T001 Record the 9-SKIP baseline; delete the class probe in `tests/specify_cli/doctrine/test_pack_validator.py` and add the `built_in_dir` precondition assert (WP01)
T002 [P] Delete the module probe in `tests/integration/test_quickstart_end_to_end.py` (4 tests) and add the same precondition assert (WP01)
T003 Re-author the intent fixture to `drg/fragment.yaml`, add the `validate_pack` regression test, keep one `*.graph.yaml` case with `check_drg_root=False`, and file the defect issue: the RED commit (WP01)
T004 Product fix in `src/specify_cli/doctrine/pack_validator.py::_collect_fragment_edge_intent`, in its own `fix(...)` commit (WP01)
T005 Planted-break proofs, NFR-001 counts, skip hygiene, issue-matrix row and evidence hand-off (WP01)

### Implementation Notes

- Sequence: test edits (T001/T002) → red commit (T003, regression test RED on the spurious advisory) → fix commit (T004, product file only) → proofs (T005).
- The precondition assert uses `charter.offering.pack_paths.built_in_dir(ArtifactKind.TACTIC) / f"{_BUILT_IN_TACTIC_ID}.tactic.yaml"`.

### Parallel Opportunities

- T001 and T002 touch different files and can proceed in parallel.

### Dependencies

- None (starting package).

### Risks & Mitigations

- The fix must not alter the `drg_root_graph_missing` path from #3387. Run `tests/doctrine/drg/test_org_fragment_validation.py` by name.
- The fix commit must stay product-only (C-005). Check the commit's `--stat`.

**Estimated prompt size**: ~361 lines (dense; written prompt).

---

## Work Package WP02: Closed-issue markers: re-point, retire, re-cite (Priority: P1)

**Goal**: No skip, xfail or guard in the FR-002 inventory rests on a closed issue.
- #3113 is re-pointed to a newly filed open issue, still strict, and the landmine guard changes in the same edit.
- The #932 and EXPERIMENTAL#828 dead guards are retired, and a version-monkeypatch test replaces the unreachable branch.
- The sync gate is kept and re-cited.

**Independent Test**: The quickstart FR-002 commands pass. Under `--runxfail`, both limit-8 cases FAIL with "scanner went blind to transport-call". `rg -n "_has_events_5|clean_install_acceptance_deferred|shared_package_deferral" tests` returns nothing.
**Prompt**: `tasks/WP02-closed-issue-markers.md`
**Requirement Refs**: FR-002, FR-005, FR-011, NFR-001, NFR-004, NFR-005, C-001, C-002, C-007, SC-002, SC-005

### Included Subtasks

T006 File the "egress guard limit 8" open issue. Re-point both strict xfails, the landmine guard and the limit-8 docstring cross-reference to it in one edit (WP02)
T007 [P] Delete `_has_events_5` and its 6 guard sites in the 3 migration test files (WP02)
T008 Replace the unreachable branch at `tests/migration/test_mission_state_repair.py:161` with a version-monkeypatch refusal test (WP02)
T009 [P] Retire both `clean_install_acceptance_deferred()` skipifs, delete `tests/_support/shared_package_deferral.py`, and prove the covering guards (WP02)
T010 Re-cite the sync-gate docstring. Record the row-8 false positive, the skip hygiene and the evidence hand-off (WP02)

### Implementation Notes

- The new issue number must exist before any xfail reason is edited.
- The version test monkeypatches `spec_kitty_events.__version__` below `REQUIRED_EVENTS_PACKAGE` (5.0.0) and asserts `MissionStateDryRunError` matching `requires spec-kitty-events >=`.

### Parallel Opportunities

- T007 and T009 touch disjoint files.

### Dependencies

- None.

### Risks & Mitigations

- The spec-kitty#828 vs EXPERIMENTAL#828 ambiguity is stated in the evidence.
- The wheel/venv tests in `test_packaging_parity.py` and `test_clean_install_next.py` are run **by node**, never as a suite.

**Estimated prompt size**: ~352 lines (dense; written prompt).

---

## Work Package WP03: Quarantine removal and lane relocation (Priority: P1)

**Goal**: The five quarantined accept-diagnose tests, and the 18 other tests in their file, run in a real CI lane. The file is relocated to `tests/specify_cli/acceptance/`, which the nightly `specify-cli-out-of-matrix` job collects under `-n auto --dist loadfile`. The JSON parses use `result.stdout`.
**Independent Test**: `--collect-only` under the nightly selection lists the 5 node ids. The registry check shows that `tests/specify_cli/acceptance` is claimed by no `modules[]` row. The file passes under `-n 2 --dist loadfile`.
**Prompt**: `tasks/WP03-quarantine-removal-and-lane-relocation.md`
**Requirement Refs**: FR-002, FR-003, FR-011, NFR-001, NFR-004, NFR-005, C-001, C-007, SC-002, SC-005

### Included Subtasks

T011 `git mv` the file to `tests/specify_cli/acceptance/test_acceptance_support.py`, rename the `ruff.toml` per-file-ignore key, and fix the docstring path in `test_issue_4891_accept_missing_lanes.py` (WP03)
T012 Remove `_ACCEPT_COMMAND_XDIST_QUARANTINE` and its 5 uses; switch every accept-CLI `json.loads(result.output)` to `result.stdout` (WP03)
T013 Lane proof: `--collect-only` under the nightly selection, plus the registry check (RK-2) and the named architectural gates (WP03)
T014 Per-test planted break, single-file xdist run and evidence hand-off (WP03)

### Implementation Notes

- Keep `pytestmark = [pytest.mark.integration]`. Keep history with `git mv`.
- Do not touch `tests/conftest.py`'s quarantine chokepoint (WP04 owns `tests/conftest.py`).

### Parallel Opportunities

- None inside the WP (a single file chain).

### Dependencies

- None.

### Risks & Mitigations

- RK-2: a demotion to `--ignore` without a registry row would orphan the file again. The registry check is recorded in the evidence.
- Out of scope, and not touched (RK-5): the `quarantine-visibility` residue and the three open-issue quarantines.

**Estimated prompt size**: ~293 lines (dense; written prompt).

---

## Work Package WP04: Errors fail instead of skipping (Priority: P2)

**Goal**: Build, packaging-metadata, time-budget, home-isolation and declared-dependency errors fail instead of skipping (masked-greens rows 10–15, 17, 18). Declared platform/tool guards stay exempt.
**Independent Test**: The quickstart FR-004 named-file run is green. The `--collect-only -m timing` and `-m stress` runs each collect their test. `rg -n "_build_wheel_fallback|_SKIP_PRE_WP04|importorskip\(\"jsonschema\"\)" tests` returns nothing.
**Prompt**: `tasks/WP04-errors-fail-instead-of-skipping.md`
**Requirement Refs**: FR-004, FR-011, NFR-001, NFR-004, NFR-005, C-001, C-007, SC-005

### Included Subtasks

T015 Rows 10–11: `build_artifacts` / `installed_wheel_venv` fail instead of skip; `SharedBuildError` docstring; stale #3595 citation campsite in `tests/conftest.py` (WP04)
T016 [P] Row 12: delete the dead `_build_wheel_fallback` and its stale comment block in `tests/doctrine/test_wheel_packaging.py` (WP04)
T017 [P] Row 13: convert the 11 metadata skip sites in `tests/cross_cutting/versioning/test_version_detection.py` to failures (WP04)
T018 [P] Row 14: hoist `_SC12_BUDGET_SECONDS`, split the budget into a `timing` test that also carries `stress`, and prove it with `--collect-only` (RK-3) (WP04)
T019 [P] Row 15: the home-isolation skip becomes an assert; delete `_SKIP_PRE_WP04` and the stale pragmas (WP04)
T020 [P] Rows 17–18: plain imports for `spec_kitty_events` / `jsonschema`; exemption-list check and evidence hand-off (WP04)

### Implementation Notes

- `tests/conftest.py` is cross-cutting: run `tests/architectural/test_home_owner_behaviour.py` by name.
- The stress file's functional assertion texts are pinned verbatim by `test_timing_coverage_invariant.py:327-337`. They stay in the non-timing test.

### Parallel Opportunities

- T016–T020 are single-file edits and can proceed in parallel. T015 touches the two build files.

### Dependencies

- None.

### Risks & Mitigations

- RK-3: the `timing` marker has no live CI job. The split test carries `stress` through the module `pytestmark`, so the nightly stress job runs it. The proof is `--collect-only`, with no exception to C-001.

**Estimated prompt size**: ~348 lines (dense; written prompt).

---

## Work Package WP05: Contract round-trip relocation map (Priority: P2)

**Goal**: The 10 contract round-trip cases that skip forever run through a test-side historical→canonical module relocation map. A module absent under both names fails.
**Independent Test**: `uv run --frozen pytest tests/contract/test_example_round_trip.py -n0 -q -rs` shows 32 passed (29 round-trip cases plus 3 map self-tests), 0 skipped (was 19 passed, 10 skipped).
**Prompt**: `tasks/WP05-contract-round-trip-relocation-map.md`
**Requirement Refs**: FR-004, FR-011, NFR-001, NFR-004, NFR-005, C-001, C-006, C-007, SC-005

### Included Subtasks

T021 Create `tests/contract/_module_relocations.py` with a longest-prefix-first `HISTORICAL_TO_CANONICAL` map and a resolver (WP05)
T022 Route `tests/contract/test_example_round_trip.py` imports through the map; replace `except ImportError: pytest.skip` with a failure naming both module names (WP05)
T023 Map self-test (no dead rows, every target importable), planted breaks and evidence hand-off (WP05)

### Implementation Notes

- Archived contracts under `kitty-specs/` are immutable (C-006). The map lives test-side.

### Parallel Opportunities

- None (a single chain).

### Dependencies

- None.

### Risks & Mitigations

- A nested module must resolve deterministically: longest prefix first.

**Estimated prompt size**: ~292 lines (dense; written prompt).

---

## Work Package WP06: #5346 pins: consolidation trio (Priority: P1)

**Goal**: Convert or retire #5346 rows 3, 4 and 6 (pin-inventory G2):
- retire the hand-built allocator-path tests;
- rename and re-scope the mission-number bake test;
- stop pinning the private refusal-helper signatures.

**Independent Test**: The named consolidation files plus their covering guards are green. The neutral plants stay green with 0 test edits, and the violation plants go red (NFR-003).
**Prompt**: `tasks/WP06-5346-consolidation-trio.md`
**Requirement Refs**: FR-006, FR-008, FR-011, NFR-003, NFR-004, NFR-005, C-001, C-002, C-007, SC-004, SC-005

### Included Subtasks

T024 [P] Row 3: retire `TestWorktreeTeardownSeamRouting` in `tests/consolidation/test_mid8_embedded_preflight.py`, with covering-guard proof (WP06)
T025 [P] Row 4: rename and re-scope the unreachable-primary test in `tests/consolidation/test_issue_4474_topology_aware_bake.py`, and name the executor refusal guard (WP06)
T026 [P] Row 6: replace full-signature `assert_called_once_with` pins with `assert_called_once()` + `call_args.args[0] is exc`, keeping one `base_sha` threading assert (WP06)
T027 Neutral and violation plants per row, and the evidence hand-off (WP06)

### Implementation Notes

- The covering guards are read-only: `tests/consolidation/test_executor_lane_naming.py`, `tests/consolidation/test_mission_number_truthful_4900.py` and `tests/lanes/test_branch_naming_seam.py`.

### Parallel Opportunities

- T024, T025 and T026 are on three different files.

### Dependencies

- None.

### Risks & Mitigations

- RK-1: row 3 reduces the executed-test count. C-002 governs it, and the covering guard is proven red on the same break.

**Estimated prompt size**: ~300 lines (dense; written prompt).

---

## Work Package WP07: #5346 pins: compat surface and copied literals (Priority: P1)

**Goal**: Convert or retire #5346 rows 2, 5 and 7 (pin-inventory G1 + G3):
- the 18-times re-pinned `len(SYMBOL_TO_MODULE) == 196`;
- the verbatim-copy recapture constants;
- the literal-scan teardown routing test, which becomes behavioural.

**Independent Test**: The named files plus `tests/specify_cli/cli/commands/test_mission_close_teardown_message.py` are green. The neutral plants stay green with 0 test edits, and the violation plants go red.
**Prompt**: `tasks/WP07-5346-compat-surface-and-copied-literals.md`
**Requirement Refs**: FR-006, FR-008, FR-011, NFR-003, NFR-004, NFR-005, C-001, C-002, C-007, SC-004, SC-005

### Included Subtasks

T028 [P] Row 2: retire `test_guard_covers_full_167_symbol_surface` and its changelog docstring; add the relational floor `all(_SEAM_GROUPS.values())` (WP07)
T029 [P] Row 5a: `:481` asserts the rendered substitutions; retire `:490` behind the `:336/:341` guard (WP07)
T030 Row 5b: `:494` records the `argv` passed to the stubbed `capture_shard_timings.main` and asserts `argv[:2] == ["--module", "charter"]` (WP07)
T031 [P] Row 7: a behavioural seam recorder test replaces the per-file literal scan in `tests/specify_cli/coordination/test_teardown_single_seam_routing.py` (WP07)
T032 Neutral and violation plants per row, and the evidence hand-off (WP07)

### Implementation Notes

- `test_teardown_single_seam_routing.py` is format-excluded; do not reformat it.

### Parallel Opportunities

- The three files are disjoint, so T028, T029–T030 and T031 are parallel.

### Dependencies

- None.

### Risks & Mitigations

- "cardinality-is-contract" is residue of the retired golden-count gate (R3). Remove the marker; do not re-add it.

**Estimated prompt size**: ~310 lines (dense; written prompt).

---

## Work Package WP08: FR-007 class: architectural and live-source call-site counts (Priority: P1)

**Goal**: Convert the exact counts of live structure in F3, F6, F8, F9, F11 and F12 (pin-inventory G4 + G5) to invariant forms or retire them behind covering guards. `EXPECTED_CALL_EXPRESSION_COUNT` is kept as an audited contract cardinality, with its disposition recorded.
**Independent Test**: The IC-07 named-file run is green, and every row's neutral and violation plants behave as recorded.
**Prompt**: `tasks/WP08-fr007-architectural-and-call-site-counts.md`
**Requirement Refs**: FR-007, FR-008, FR-011, NFR-003, NFR-004, NFR-005, C-001, C-002, C-003, C-007, SC-004, SC-005

### Included Subtasks

T033 [P] F9: retire `test_recorded_denominator_matches_docstring_claim` and strip the counts from the docstring (WP08)
T034 [P] F11: a **per-site** partition (`has_remediation or state in _PASS_STATES or (f, s) in _EXEMPT_STATES`) in `tests/architectural/test_remediation_effectiveness.py`. The floors become `>=`, counted over sites (WP08)
T035 [P] F12: retire `EXPECTED_ENCLOSING_COUNT` (set equality covers it); keep `EXPECTED_CALL_EXPRESSION_COUNT` as keep-contract (WP08)
T036 [P] F3: floor `>= 1` on `materialize_calls`; delete the per-site changelog docstring (WP08)
T037 [P] F6: drop `expected_sites` from the parametrize table; add a `>= 1` floor (WP08)
T038 [P] F8: retire `test_member_count` behind `:31` / `:48` (WP08)
T039 Neutral and violation plants per row, and the evidence hand-off (WP08)

### Implementation Notes

- Four of the six files are format-excluded (see the prompt).

### Parallel Opportunities

- Every conversion is on its own file.

### Dependencies

- None.

### Risks & Mitigations

- F11 needs a **per-site** partition. A pair-level one is RED on day one (5 pass-state pairs) and misses the split-site exploit (B2). The documented exploit (`:348-360`) and the split-site plant must both stay red.
- RK-1 applies to F8, F9 and F12a.

**Estimated prompt size**: ~327 lines (dense; written prompt).

---

## Work Package WP09: FR-007 class: corpus, data-artefact and agent-registry counts (Priority: P1)

**Goal**: Replace the counts in F4, F5, F7 and F10 (pin-inventory G6 + G7) over the shipped corpus, committed data artefacts and agent registries with shape or relational invariants.
**Independent Test**: The IC-08 named-file run is green. The neutral plants stay green with 0 edits, and the violation plants go red.
**Prompt**: `tasks/WP09-fr007-corpus-and-registry-counts.md`
**Requirement Refs**: FR-007, FR-008, FR-011, NFR-003, NFR-004, NFR-005, C-001, C-002, C-006, C-007, SC-004, SC-005

### Included Subtasks

T040 [P] F4: shape invariants in `tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py`; correct the "SC-011 cardinality contract" claim in place (WP09)
T041 [P] F5: relational anchor invariant in `tests/docs/test_glossary_linker.py`; rename the `_104_` test (WP09)
T042 [P] F7: retire the absolute counts in `tests/unit/convergence/test_census_status.py`; floor `>= 1` (WP09)
T043 [P] F10: cross-registry set equality in `tests/agent/test_agent_config_migration.py` and `tests/specify_cli/regression/test_twelve_agent_parity.py` (WP09)
T044 Neutral and violation plants per row, and the evidence hand-off (WP09)

### Implementation Notes

- F10 imports the canonical `specify_cli.agent_utils.directories.AGENT_DIRS`. `m_0_9_1_complete_lane_migration` exposes it only as a class attribute, so it is not the import source. The prompt explains how to avoid the tautological `NON_MIGRATED_AGENTS == AGENT_COMMAND_CONFIG` form.

### Parallel Opportunities

- All four conversions are on disjoint files.

### Dependencies

- None.

### Risks & Mitigations

- F4 has the largest docstring. Keep the per-triple contract test untouched.

**Estimated prompt size**: ~307 lines (dense; written prompt).

---

## Work Package WP10: Dead-symbol ATDD contract pins and parity snapshot (Priority: P1)

**Goal**: Commit the acceptance contract of the re-key **before** the re-key lands: M1, M7, M8 and M11 against the new seam, each red on its own. Freeze the exact exempted `(module, name, category)` set as a parity snapshot, and record the real-tree SC-003 red observation.
**Independent Test**: `tests/architectural/test_dead_symbol_allowlist_contract.py` collects cleanly. Every test is strict-XFAIL with `raises=(ImportError, AttributeError)`, and each is red on the missing seam under `--runxfail`. `test_no_dead_symbols.py` is GREEN before the plant and RED under the **code-token** body-edit plant: rename the local `envelope` to `persisted_envelope` in `src/specify_cli/status/lifecycle_events.py::append_lifecycle_event` (`:608-645`). A docstring edit does **not** change the content-tier hash, so it must not be used.
**Prompt**: `tasks/WP10-dead-symbol-atdd-contract-pins.md`
**Requirement Refs**: FR-009, FR-011, NFR-003, NFR-004, NFR-005, C-001, C-007, SC-003, SC-005

### Included Subtasks

T045 Create `tests/architectural/test_dead_symbol_allowlist_contract.py`: in-body seam import helper and synthetic-corpus builder (WP10)
T046 M1: an allowlisted dead symbol's code-token body edit leaves offenders `[]` and stale `[]`, with a same-fixture positive control (WP10)
T047 M7 (a rename is reported) and M8 (a move is reported with a "probably moved to" hint) (WP10)
T048 M11: an authority-parse flip over a scratch YAML; M11(a) pops from a category with ≥ 2 entries (WP10)
T049 Parity snapshot script and `before.json` (scratchpad), the real-tree SC-003 red observation, and the evidence hand-off (WP10)

### Implementation Notes

- The seam import goes inside each test body, never at module scope (contract §3, ATDD rule).
- The red is committed as `xfail(strict=True, raises=(ImportError, AttributeError))` (orchestrator ruling). WP12 removes the markers.
- `before.json` stays **outside** the repository. Its sha256, counts (293 / 91) and the script text go into the evidence hand-off, so WP12 can regenerate and verify it.

### Parallel Opportunities

- T046–T048 can be drafted in parallel after T045.

### Dependencies

- None.

### Risks & Mitigations

- The tests must target the contract (contracts/dead-symbol-allowlist.md), never today's `SymbolKey` internals, or WP12 must rewrite them.

**Estimated prompt size**: ~361 lines (dense; written prompt).

---

## Work Package WP11: Dead-symbol allowlist loader and YAML migration (Priority: P1)

**Goal**: Add the schema-enforcing loader `tests/architectural/_dead_symbol_allowlist.py` (L1–L10) and the migrated data file `tests/architectural/dead_symbol_allowlist.yaml`, including the folded #470 widened list. Prove data-level parity against today's gate constants. The gate is **not** switched here; WP12 does that.
**Independent Test**: `tests/architectural/test_dead_symbol_allowlist_loader.py` is green (M12 schema battery plus real-file load). The YAML carries 293 entries and 91 widened entries. Its key set equals the old allowlist's `(module_path or source_module, bare_name)` set.
**Prompt**: `tasks/WP11-dead-symbol-allowlist-loader-and-yaml.md`
**Requirement Refs**: FR-009, FR-011, NFR-005, C-001, C-003, C-007

### Included Subtasks

T050 Loader module: `DeadSymbolKey`, `AllowlistCategory`, `AllowlistEntry`, `WidenedEntry`, `DeadSymbolAllowlist`, the duplicate-key-rejecting `SafeLoader`, rules L1–L10, `ALLOWLIST` (the single parse) with its views `SYMBOL_ALLOWLIST` and `WIDENED_SCOPE_GRANDFATHERED_470` (WP11)
T051 Scratchpad-only converter emitting `tests/architectural/dead_symbol_allowlist.yaml`: `module_path` wins, `category_*` ids, rationales, widened split, `check_push_safety` collapsed, tombstones dropped (WP11)
T052 `tests/architectural/test_dead_symbol_allowlist_loader.py`: the M12 schema battery plus data-level parity against the old gate constants (WP11)
T053 Quality gates (ruff, mypy, positional-anchor ban) and the evidence hand-off (WP11)

### Implementation Notes

- **Commit order (C-011)**: the T052 loader test file is committed first, failing, before the T050 loader.
- M12 lives in a new loader test file rather than the gate file. It exercises only the loader, and this keeps WP11 and WP12 file-disjoint.

### Parallel Opportunities

- T050 and T051 can be drafted in parallel. T052 needs both.

### Dependencies

- Depends on WP10 (ATDD-first: the contract pins land before any re-key artefact).

### Risks & Mitigations

- The `merge_three_layers` trap: `module_path="charter.drg"` must win over `source_module="charter.offering.drg.merge"`.
- PyYAML silently merges duplicate keys, so L3 needs the custom loader.

**Estimated prompt size**: ~356 lines (dense; written prompt).

---

## Work Package WP12: Dead-symbol gate re-key and bite battery (Priority: P1)

**Goal**: Switch `tests/architectural/test_no_dead_symbols.py` to the `(module, name)` identity loaded from YAML:
- apply the G1–G8 contract, with stale verdicts INVALID → GONE → REVIVED → SUPERSEDED → MOOT;
- delete the persisted-hash data and its guards;
- rebase the bite battery onto M2–M10 and M13;
- migrate `test_p1_planted_regression.py`;
- retire the refresh helper and its 17 tests, which are coupled to the gate internals being removed;
- prove lossless `before.json == after.json` parity.

WP10's contract tests PASS once WP12 removes their strict-xfail markers, a sanctioned out-of-map edit that makes no other change to `test_dead_symbol_allowlist_contract.py`. The widened #470 section is evaluated from the same parsed instance through `_evaluate_widened`, with an M11(c) bite (F-05).
**Independent Test**: The IC-10 named-file run is green, and the parity diff is empty. The SC-003 code-token plant (`envelope` → `persisted_envelope` in `append_lifecycle_event`) stays GREEN with 0 edits. A planted new dead symbol reds the gate (the C-002 covering guard for the helper retirement), and `test_p1_planted_regression` stays live.
**Prompt**: `tasks/WP12-dead-symbol-gate-rekey.md`
**Requirement Refs**: FR-008, FR-009, FR-011, NFR-003, NFR-005, C-001, C-002, C-003, C-007, SC-003, SC-005

### Included Subtasks

T054 Before any edit, re-generate `before.json` with WP10's recorded script and verify its sha256 (WP12)
T055 Wire the gate to the loader: `_SYMBOL_ALLOWLIST` / `_WIDENED_SCOPE_GRANDFATHERED_470` aliases (G8), `DeadSymbolKey` exemption plus keyability (G1), allowlist injection (G7); keep auto-exempt condition (1) (G5) (WP12)
T056 Stale verdicts (G3) with the move hint and the corpus floor. Delete the T016 suppression, dangling logic, provenance guards, cross-category duplicate guards and every `_CATEGORY_*` literal (G6) (WP12)
T057 Rebase the bite battery: M2–M6, M9, M10 and M13. Keep `bite_e`, `bite_k`, the widened and dynamic-accessor tests; fold the disjointness check into SUPERSEDED. Retire `bite_b`, `bite_g`'s body arm and `bite_j`'s relocation arm (WP12)
T058 Migrate `tests/architectural/test_p1_planted_regression.py` to `DeadSymbolKey` (WP12)
T059 Retire `tests/architectural/_refresh_dead_symbol_hashes.py` and `tests/architectural/test_refresh_dead_symbol_hashes.py` (17 tests), with the C-002 covering-guard proof (WP12)
T060 `after.json` parity, the real-tree SC-003 plant, the REVIVED plant, the contract suite green and the evidence hand-off (WP12)

### Implementation Notes

- The gate file keeps its name, its `architectural` marker and its real asserts (C-007 canon, pinned in 3 places). The real-tree test keeps its own literal `assert` statements (F-11).
- `RealTreeInputs` is read-only. M13 never monkeypatches the walker before calling the cache (F-06).
- **Sanctioned out-of-map edits, which are not added to `owned_files` to avoid ownership overlap**:
  - removing the strict-xfail markers from WP10's `test_dead_symbol_allowlist_contract.py`;
  - regenerating WP11's `dead_symbol_allowlist.yaml` **only** on base drift, with WP11's recorded converter (F-02a).
- `test_no_dead_symbols.py` takes about 4 minutes. It is a named gate file, not a sweep.

### Parallel Opportunities

- T058 can proceed alongside T056–T057 once T055 lands.

### Dependencies

- Depends on WP11.

### Risks & Mitigations

- Parity drift if the base moves: re-take `before.json` from the new base and record both hashes.
- Complexity ≤ 15 per function (NFR-005). Extract the verdict classifier into small helpers.
- The size is at the upper bound (7 subtasks). All four owned files are coupled through the gate's internal API, so the WP cannot be split without shared ownership.

**Estimated prompt size**: ~395 lines (dense; written prompt).

---

## Work Package WP13: Retire the hash-toll surfaces (Priority: P2)

**Goal**: Delete `SymbolKey.source_module` and its G1–G6 guard tests, which exist only for the persisted-hash identity. Correct the stale `_symbol_key.py` docstrings and the `tests/architectural/README.md` scope claim. Keep `tests/unit/test_symbol_key.py`'s `len(index) == 400`.
**Independent Test**: The IC-11 named-file run is green. `rg -n "\.source_module\b|source_module=" src tests scripts` and `rg -n "import .*_refresh_dead_symbol_hashes|from tests\.architectural\._refresh_dead_symbol_hashes" tests scripts` return nothing. The grep targets field and import usage; WP11's forbidden-key literals are expected (F-01). `test_timing_coverage_invariant.py` stays green.
**Prompt**: `tasks/WP13-retire-hash-toll-surfaces.md`
**Requirement Refs**: FR-009, FR-011, NFR-005, C-001, C-002, C-007, SC-005

### Included Subtasks

T061 Grep gate, plus the C-002 covering-guard proof: WP11's loader rule L5 rejects a `source_module` key (WP13)
T062 `tests/architectural/_symbol_key.py`: remove `SymbolKey.source_module` and correct the header, body-sensitivity and G1–G6 docstrings (WP13)
T063 `tests/unit/test_symbol_key.py`: remove the G1–G6 section (25 `source_module` references) and keep `len(index) == 400` (WP13)
T064 `tests/architectural/README.md` stale scope claim; evidence hand-off (WP13)

### Implementation Notes

- `_symbol_key.py` is format-excluded; do not reformat it. `SymbolKey` itself stays, as runtime-only keyability and auto-exempt condition (1).

### Parallel Opportunities

- T062 and T063 are parallel after T061.

### Dependencies

- Depends on WP12.

### Risks & Mitigations

- RK-1: the deleted G-tests. Their subject (the field) is deleted, and the L5 plant is the covering guard.

**Estimated prompt size**: ~271 lines (dense; written prompt).

---

## Work Package WP14: Size ratchet rows and top-level-keys floor (Priority: P1)

**Goal**: Cap the new dead-symbol exemption authority in `_baselines.yaml` (Burn-down (a)):
- the `allowlist_entries` row and leaf;
- the RK-6 `widened_grandfathered_470` row and leaf, in the same section.

In the same WP:
- convert `len(_REQUIRED_TOP_LEVEL_KEYS) == 15` (#5346-1 / F2) to a floor at the **live section count at landing** (`>= 16`). A delete-the-new-section plant must go red (F-03);
- re-plant the planted-leaf test;
- record the kept-ratchet dispositions (FR-008, SC-004).
**Independent Test**: `tests/architectural/test_ratchet_baselines.py` is green, and `test_lowering_an_enforced_leaf_below_live_fails` passes for both new rows. The violation plants go red.
**Prompt**: `tasks/WP14-size-ratchet-rows-and-keys-floor.md`
**Requirement Refs**: FR-006, FR-007, FR-008, FR-009, FR-010 (withdrawn; disposition record only), FR-011, NFR-003, NFR-005, C-001, C-003, C-007, C-008, SC-004, SC-005

### Included Subtasks

T065 Red-first: plant the new row and observe `:618` red. Convert `== 15` to `>= <live section count>` (16 today), delete the section changelog comment, and plant the section deletion, which must go red (WP14)
T066 Add `_SizeRatchet("test_no_dead_symbols", "allowlist_entries", "tests.architectural._dead_symbol_allowlist", "SYMBOL_ALLOWLIST")` and its leaf, taken from the live count (WP14)
T067 Add the RK-6 row `widened_grandfathered_470` → `WIDENED_SCOPE_GRANDFATHERED_470` and its leaf in the same section (WP14)
T068 Re-plant `test_leaf_drift_detects_planted_unenforced_leaf` (`:554-578`) on a section that has no enforced row (WP14)
T069 Violation plants, plus the keep-ratchet / keep-contract / resolved disposition records for SC-004 (FR-008 history check); evidence hand-off (WP14)

### Implementation Notes

- The leaf values are read from the live loader at landing, never from this plan.

### Parallel Opportunities

- None (one test file plus its YAML).

### Dependencies

- Depends on WP12.

### Risks & Mitigations

- C-008: no census gate is added. The rows are ordinary size ratchets.

**Estimated prompt size**: ~312 lines (dense; written prompt).

---

## Work Package WP15: ADR and gate-mechanics docs (Priority: P2)

**Goal**: Record the identity decision in ADR `docs/adr/4.x/<date>-1-dead-symbol-allowlist-module-name-identity.md`, which partially supersedes D-1 of `relocation-hardened-dead-code-scanners-01KX958P`. Rewrite the stale "Renaming a symbol whose body is allowlisted" section of `docs/development/reference/ci-gate-mechanics.md`. Register the ADR and regenerate the docs indexes.
**Independent Test**: `tests/docs/test_freshen_adr_inventory.py`, `test_inventory_lockfile.py`, `test_adr_content_invariance.py` and `tests/architectural/test_no_legacy_terminology.py` are green, and `scripts/docs/check_docs_freshness.py --ci` passes.
**Prompt**: `tasks/WP15-adr-and-gate-mechanics-docs.md`
**Requirement Refs**: FR-009, FR-011, NFR-005, C-001, C-006, C-008

### Included Subtasks

T070 Author the ADR: context, decision, consequences, supersedes / relates, non-goals (WP15)
T071 Rewrite the "Renaming a symbol whose body is allowlisted" section of `docs/development/reference/ci-gate-mechanics.md`, and add the dead-symbol YAML kind to `docs/development/how-to/add-architectural-gate-exemption.md` (F-13) (WP15)
T072 Register the ADR with `python -m scripts.docs.freshen_adr_inventory` (index row + page-inventory lockfile) (WP15)
T073 Regenerate the docs retrieval index and inventory lockfile, run the freshness check and the named docs tests, and hand off (WP15)

### Implementation Notes

- WP15 owns every `docs/` edit in this mission and the regenerated indexes. No other WP touches `docs/`.

### Parallel Opportunities

- T070 and T071 are parallel.

### Dependencies

- Depends on WP13 and WP14 (the ADR cites the retired helper and the size-ratchet rows as landed facts).

### Risks & Mitigations

- The ADR filename date is the landing date. `owned_files` uses a date-agnostic glob.

**Estimated prompt size**: ~298 lines (dense; written prompt).

---

## Dependency & Execution Summary

```
WP01  WP02  WP03  WP04  WP05  WP06  WP07  WP08  WP09     (independent, parallel lanes)
WP10 ──► WP11 ──► WP12 ──► WP13 ──┐
                      └──► WP14 ──┴──► WP15
```

- **Sequence**: WP01–WP09 have no dependencies and are file-disjoint. The dead-symbol chain is the only sequence: WP10 → WP11 → WP12 → {WP13, WP14} → WP15.
- **Parallelization**: Up to nine lanes for WP01–WP09, plus the dead-symbol chain in its own lane. WP13 and WP14 can run in parallel once WP12 is approved.
- **MVP Scope**: WP01 (the unmask plus the one real product defect) and WP10–WP12 (the dominant friction source, SC-003).
- **Model tiers**:
  - WP10, WP11, WP12 and WP15 run on `claude-opus-5-5` (the re-key and the ADR).
  - All others run on `claude-sonnet-5`.
  - Review runs on opus for every WP (plan).

---

## Closeout (orchestrator)

These steps belong to the orchestrator, not to any WP. They run after all WPs are approved, in this order.

1. **Materialize the evidence (M7).** Write every WP's reported evidence records into `kitty-specs/test-suite-remediation-01M3SSDW/evidence/IC-NN-<slug>.md` (data-model §4), and WP10's and WP12's parity JSONs and digests into `evidence/dead-symbol-parity/{before,after}.json`, on the planning branch (a planning artifact).
   - **Split concerns merge into one IC file** (analysis C5): IC-06 ← WP06 + WP07; IC-10 ← WP11 + WP12; IC-11 ← WP12 (refresh-helper retirement) + WP13; IC-12 ← WP14 + WP15. Every other IC maps to one WP.
   - **SC-005 owner (analysis C6)**: each per-WP reviewer re-runs its WP's Review-Guidance picks during review and reports which ones. At closeout the orchestrator tallies them (≥ 6 FIX and ≥ 2 RETIRE across the mission), and sets `reviewer_rerun: true` on those records.
   - Update the quickstart FR-009 parity `diff` so it points at the committed files. If they are not committed, compare the WP10 and WP12 recorded digests instead.
2. **Rebase re-port (F-02b).** After rebasing onto upstream `main`, check whether any upstream commit edited the (now deleted) `_CATEGORY_*` allowlist literals in `tests/architectural/test_no_dead_symbols.py`. If one did:
   - port its delta into `tests/architectural/dead_symbol_allowlist.yaml` (with WP11's converter rules: `module_path` wins, `category_*` ids);
   - re-read the live counts for the two `_baselines.yaml` `test_no_dead_symbols` leaves;
   - re-run the parity check.
3. **Consolidated-branch gate run (F-04, F-02b).** On the **consolidated** mission branch, run the named files `tests/architectural/test_no_dead_symbols.py`, `test_dead_symbol_allowlist_loader.py`, `test_dead_symbol_allowlist_contract.py` and `test_ratchet_baselines.py`. The chain's parity was measured on a lane without WP01's product change. These are named gate files, not a directory sweep.
4. **Follow-up issues plus issue-matrix rows (m13, RK-2, RK-5, D-14).** For each, run `spec-kitty agent issue-verdict --verdict deferred-with-followup`. First confirm that `issue-verdict` creates a row when the mission has no issue matrix yet, since WP01 T005 and WP02 T010 rely on it:
   - the `quarantine-visibility` lane residue;
   - the three open-issue quarantines (EXP#1021 ×2, EXP#901);
   - the tracker-slice `importorskip("spec_kitty_tracker.context")` dead guards;
   - the `inline_meta_read` three-authority count;
   - simplifying auto-exempt condition (1);
   - optionally, re-keying F12's `EXPECTED_CALL_EXPRESSION_COUNT` as `{qualname: n}`;
   - the RK-2 "collected by some lane" gate;
   - the stale product comment in `src/specify_cli/upgrade/migrations/m_unify_charter_activation_finalize.py:474-484` (F-15; C-005 forbids editing it here);
   - the project `CLAUDE.md` line "Canonical source: `m_0_9_1_complete_lane_migration` → `AGENT_DIRS`", which should name `specify_cli.agent_utils.directories` (analysis D3; outside the file set).
5. **Tracker hygiene (Standing Order 8; analysis C4).** #5346 and #5353 are already assigned and commented, and their issue-matrix rows exist. At closeout, **verify that their verdicts are terminal**: #5346 `fixed`, and the parent #5353 linked with its verdict. Correct them with `spec-kitty agent issue-verdict` if they are not.
6. **CHANGELOG** entries (the WPs write none).

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP02, WP03 |
| FR-003 | WP03 |
| FR-004 | WP04, WP05 |
| FR-005 | WP01, WP02 |
| FR-006 | WP06, WP07, WP14 |
| FR-007 | WP08, WP09, WP14 |
| FR-008 | WP06, WP07, WP08, WP09, WP12, WP14 |
| FR-009 | WP10, WP11, WP12, WP13, WP14, WP15 |
| FR-010 | Withdrawn (DM-01M3SVDP). Mapped to WP14 only because the finalize-tasks coverage check requires every FR to be mapped; WP14 records the withdrawn disposition and implements no gate (C-008) |
| FR-011 | WP01–WP15 |
| NFR-001 | WP01, WP02, WP03, WP04, WP05 (masked-green files only, RK-1) |
| NFR-002 | Withdrawn; no WP |
| NFR-003 | WP06, WP07, WP08, WP09, WP10, WP12, WP14 |
| NFR-004 | WP01–WP10 |
| NFR-005 | WP01–WP15 |
| C-001 | WP01–WP15 |
| C-002 | WP02, WP06, WP07, WP08, WP09, WP12, WP13 |
| C-003 | WP08, WP11, WP12, WP14 |
| C-005 | WP01 |
| C-006 | WP05, WP09, WP15 |
| C-007 | WP01–WP14 |
| C-008 | WP14, WP15 |
| SC-001 | WP01 |
| SC-002 | WP02, WP03 |
| SC-003 | WP10, WP12 |
| SC-004 | WP06, WP07, WP08, WP09, WP14 |
| SC-005 | WP01–WP10, WP12, WP13, WP14 |
| SC-006 | Withdrawn; no WP |

C-004 (the scope boundary, amended for analysis F2) is honoured. No WP runs a slice-level quality pass of the integration harness or of the `status`, `agent`, `tracker` or `auth` slices. Individually inventoried FR-006/FR-007 pins stay in scope wherever their files live, e.g. WP09's F10 edit in `tests/agent/test_agent_config_migration.py`.

**SC-004 tally note (analysis A1)**: F1 and F2 are the same pins as #5346-2 and #5346-1. Count each once, under its #5346 row.

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Pack-validator probe → precondition assert | WP01 | P1 | Yes |
| T002 | Quickstart e2e probe → precondition assert | WP01 | P1 | Yes |
| T003 | fragment.yaml fixture + regression test (RED commit) + new issue | WP01 | P1 | No |
| T004 | `_collect_fragment_edge_intent` product fix commit | WP01 | P1 | No |
| T005 | WP01 plants, counts, hygiene, evidence | WP01 | P1 | No |
| T006 | #3113 re-point + landmine guard + docstring | WP02 | P1 | No |
| T007 | Delete `_has_events_5` ×3 and 6 guard sites | WP02 | P1 | Yes |
| T008 | Version-monkeypatch refusal test | WP02 | P1 | No |
| T009 | Retire #828 skipifs + delete deferral helper | WP02 | P1 | Yes |
| T010 | Sync-gate re-cite, false positive, evidence | WP02 | P1 | No |
| T011 | `git mv` + ruff.toml key + docstring path | WP03 | P1 | No |
| T012 | Remove quarantine + `result.stdout` | WP03 | P1 | No |
| T013 | Lane proof + registry check | WP03 | P1 | No |
| T014 | WP03 plant + xdist + evidence | WP03 | P1 | No |
| T015 | Build fixtures fail instead of skip + #3595 campsite | WP04 | P2 | No |
| T016 | Delete `_build_wheel_fallback` | WP04 | P2 | Yes |
| T017 | Version-detection 11 skip sites → fail | WP04 | P2 | Yes |
| T018 | Stress budget → `timing`+`stress` test | WP04 | P2 | Yes |
| T019 | Home-isolation skip → assert | WP04 | P2 | Yes |
| T020 | Plain imports + evidence | WP04 | P2 | Yes |
| T021 | `_module_relocations.py` map + resolver | WP05 | P2 | No |
| T022 | Round-trip through the map; fail on absence | WP05 | P2 | No |
| T023 | Map self-test + plants + evidence | WP05 | P2 | No |
| T024 | #5346-3 retire allocator-path class | WP06 | P1 | Yes |
| T025 | #5346-4 rename + re-scope | WP06 | P1 | Yes |
| T026 | #5346-6 signature pins → identity asserts | WP06 | P1 | Yes |
| T027 | WP06 plants + evidence | WP06 | P1 | No |
| T028 | #5346-2 retire count + relational floor | WP07 | P1 | Yes |
| T029 | #5346-5 `:481` convert, `:490` retire | WP07 | P1 | Yes |
| T030 | #5346-5 `:494` argv through the real seam | WP07 | P1 | No |
| T031 | #5346-7 behavioural seam recorder | WP07 | P1 | Yes |
| T032 | WP07 plants + evidence | WP07 | P1 | No |
| T033 | F9 retire denominator test | WP08 | P1 | Yes |
| T034 | F11 partition invariant | WP08 | P1 | Yes |
| T035 | F12 retire ENCLOSING, keep CALL_EXPRESSION | WP08 | P1 | Yes |
| T036 | F3 floor ≥ 1 | WP08 | P1 | Yes |
| T037 | F6 drop `expected_sites` | WP08 | P1 | Yes |
| T038 | F8 retire member count | WP08 | P1 | Yes |
| T039 | WP08 plants + evidence | WP08 | P1 | No |
| T040 | F4 shape invariants | WP09 | P1 | Yes |
| T041 | F5 relational anchors + rename | WP09 | P1 | Yes |
| T042 | F7 retire absolute counts | WP09 | P1 | Yes |
| T043 | F10 registry set equality | WP09 | P1 | Yes |
| T044 | WP09 plants + evidence | WP09 | P1 | No |
| T045 | Contract test scaffold | WP10 | P1 | No |
| T046 | M1 body edit stays green | WP10 | P1 | Yes |
| T047 | M7 rename + M8 move reported | WP10 | P1 | Yes |
| T048 | M11 authority parse | WP10 | P1 | Yes |
| T049 | Parity snapshot + SC-003 red + evidence | WP10 | P1 | No |
| T050 | Loader module L1–L10 | WP11 | P1 | Yes |
| T051 | Scratch converter → YAML | WP11 | P1 | Yes |
| T052 | Loader tests (M12) + data parity | WP11 | P1 | No |
| T053 | WP11 quality gates + evidence | WP11 | P1 | No |
| T054 | Re-take `before.json` | WP12 | P1 | No |
| T055 | Wire gate to loader (G1/G5/G7/G8) | WP12 | P1 | No |
| T056 | Stale verdicts + deletions + corpus floor | WP12 | P1 | No |
| T057 | Bite battery rebase | WP12 | P1 | No |
| T058 | `test_p1_planted_regression.py` key migration | WP12 | P1 | Yes |
| T059 | Retire refresh helper + 17 tests (C-002 proof) | WP12 | P1 | No |
| T060 | `after.json` parity + plants + evidence | WP12 | P1 | No |
| T061 | Grep gate + C-002 proof (L5 plant) | WP13 | P2 | No |
| T062 | `SymbolKey.source_module` removal | WP13 | P2 | Yes |
| T063 | `test_symbol_key.py` refs (keep `== 400`) | WP13 | P2 | Yes |
| T064 | README scope claim + evidence | WP13 | P2 | No |
| T065 | `== 15` → floor, red-first | WP14 | P1 | No |
| T066 | `allowlist_entries` row + leaf | WP14 | P1 | No |
| T067 | `widened_grandfathered_470` row + leaf | WP14 | P1 | No |
| T068 | Re-plant the planted-leaf test | WP14 | P1 | No |
| T069 | Plants + kept-ratchet dispositions + evidence | WP14 | P1 | No |
| T070 | Author the ADR | WP15 | P2 | Yes |
| T071 | Rewrite the gate-mechanics section | WP15 | P2 | Yes |
| T072 | Register the ADR (freshener) | WP15 | P2 | No |
| T073 | Regenerate docs indexes + checks | WP15 | P2 | No |
