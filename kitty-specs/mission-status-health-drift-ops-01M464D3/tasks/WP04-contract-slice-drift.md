---
work_package_id: WP04
title: 'Contract slice D: the drift read'
dependencies:
- WP03
requirement_refs:
- FR-008
- FR-009
- FR-010
- FR-011
- FR-012
- FR-013
- FR-014
- FR-015
- FR-023
- NFR-006
- SC-003
planning_base_branch: issue-5776-mission-status-contract-health-drift-ops
merge_target_branch: issue-5776-mission-status-contract-health-drift-ops
branch_strategy: Planning artifacts for this mission were generated on issue-5776-mission-status-contract-health-drift-ops. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5776-mission-status-contract-health-drift-ops unless the human explicitly redirects the landing branch.
subtasks:
- T018
- T019
- T020
- T021
- T022
history: []
agent_profile: python-pedro
authoritative_surface: contracts/mission-status/
create_intent:
- contracts/mission-status/paths/drift.yaml
- contracts/mission-status/parameters/DriftMissionId.yaml
- contracts/mission-status/schemas/DriftReport.yaml
- contracts/mission-status/schemas/DriftFinding.yaml
- contracts/mission-status/schemas/LaneComparison.yaml
- contracts/mission-status/schemas/DriftKind.yaml
- contracts/mission-status/schemas/DriftSeverity.yaml
- contracts/mission-status/schemas/DriftAuthority.yaml
- contracts/mission-status/schemas/DriftSide.yaml
- contracts/mission-status/schemas/DriftRemedy.yaml
- contracts/mission-status/schemas/DriftRefusalCode.yaml
- contracts/mission-status/schemas/DriftRefusal.yaml
- contracts/mission-status/responses/DriftMissionNotFound.yaml
- contracts/mission-status/responses/DriftScanUnreadable.yaml
- contracts/mission-status/examples/DriftReport.clean.yaml
- contracts/mission-status/examples/DriftReport.populated.yaml
- contracts/mission-status/examples/DriftReport.corrupt-json.yaml
- contracts/mission-status/examples/DriftReport.truncated.yaml
- contracts/mission-status/examples/DriftRefusal.mission-not-found.yaml
- contracts/mission-status/examples/DriftRefusal.scan-unreadable.yaml
execution_mode: code_change
model: ''
owned_files:
- contracts/mission-status/paths/drift.yaml
- contracts/mission-status/parameters/DriftMissionId.yaml
- contracts/mission-status/schemas/DriftReport.yaml
- contracts/mission-status/schemas/DriftFinding.yaml
- contracts/mission-status/schemas/LaneComparison.yaml
- contracts/mission-status/schemas/DriftKind.yaml
- contracts/mission-status/schemas/DriftSeverity.yaml
- contracts/mission-status/schemas/DriftAuthority.yaml
- contracts/mission-status/schemas/DriftSide.yaml
- contracts/mission-status/schemas/DriftRemedy.yaml
- contracts/mission-status/schemas/DriftRefusalCode.yaml
- contracts/mission-status/schemas/DriftRefusal.yaml
- contracts/mission-status/responses/DriftMissionNotFound.yaml
- contracts/mission-status/responses/DriftScanUnreadable.yaml
- contracts/mission-status/examples/DriftReport.clean.yaml
- contracts/mission-status/examples/DriftReport.populated.yaml
- contracts/mission-status/examples/DriftReport.corrupt-json.yaml
- contracts/mission-status/examples/DriftReport.truncated.yaml
- contracts/mission-status/examples/DriftRefusal.mission-not-found.yaml
- contracts/mission-status/examples/DriftRefusal.scan-unreadable.yaml
- contracts/mission-status/openapi.yaml
- contracts/mission-status/schemas/_index.yaml
- contracts/mission-status/examples/_index.yaml
- contracts/mission-status/parameters/_index.yaml
- contracts/mission-status/responses/_index.yaml
- contracts/mission-status/CHANGELOG.md
- contracts/tools/enum_pins.json
- tests/contract/test_mission_status_examples.py
- tests/contract/test_enum_pin_check.py
role: implementer
tags: []
tracker_refs: []
---
# Work Package Prompt: WP04 - Contract slice D: the drift read

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Author `getDriftReport` and its schemas, enums, refusal, responses, parameter and examples in the contract tree, with the red-first required cases in the examples and pin tests.

## Context

Contract only: no reader code (that is WP07). The shapes are the planning contract `kitty-specs/mission-status-health-drift-ops-01M464D3/contracts/operations-and-schemas.md` and the data model (`data-model.md`): keep every property, name and rule listed there, or report a refinement in the hand-off. This WP edits chokepoint files after WP03 (`openapi.yaml`, the four `_index.yaml`, `enum_pins.json`, `CHANGELOG.md`, the two enum/example test modules): serialised by the dependency chain. `DriftRefusal` follows `ArtifactRefusal` (a `Problem` plus `code` and one `if`/`then` per code pinning the status). `provisional_check` is word-satisfied by the previous slice's `kind`, `code` and `truncated`, so the qualified names are asserted by WP06, but the tokens must be present here.

Plan concern: IC-04 of `kitty-specs/mission-status-health-drift-ops-01M464D3/plan.md`. Read, in this order, before writing anything: `.kittify/charter/charter.md`, `AGENTS.md` (for conventions only), the Mission's `spec.md` (the requirement ids in the frontmatter), `plan.md` sections named below, `research.md`, `data-model.md`, `quickstart.md` and `contracts/*.md` in `kitty-specs/mission-status-health-drift-ops-01M464D3/`.

**Dependencies and order.** Depends on WP03; the lane workspace already holds their approved commits. No work package is dispatched before the orchestrator's Step 0 record exists in `tracer-approach.md`. **Pre-dispatch (orchestrator Step PD in `tasks.md`, operator ruling 13):** before this dispatch the orchestrator fast-forwards the mission-lane branch `kitty/mission-<slug>` and, once the orchestrator's run of `spec-kitty agent action implement WP04 --agent claude` (the command of your Implementation command section; it creates or resumes the lane workspace) has created this lane workspace and before you are started, merges the planning branch into it and greps inside it for every record this prompt reads: the Step 0 record (heading `## Record: Step 0`) and the hand-off record of WP03 (heading `## Record: Hand-off WP03 (`), both in `tracer-approach.md`; read them from the lane workspace root. If a line the prompt tells you to read is not there, stop and report it; never run `--refresh-planning-commit` and never copy a record in by hand.

## Owned files (write scope; final, explicit, no directory-wide glob)

- `contracts/mission-status/paths/drift.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/parameters/DriftMissionId.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/schemas/DriftReport.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/schemas/DriftFinding.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/schemas/LaneComparison.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/schemas/DriftKind.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/schemas/DriftSeverity.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/schemas/DriftAuthority.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/schemas/DriftSide.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/schemas/DriftRemedy.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/schemas/DriftRefusalCode.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/schemas/DriftRefusal.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/responses/DriftMissionNotFound.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/responses/DriftScanUnreadable.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/examples/DriftReport.clean.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/examples/DriftReport.populated.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/examples/DriftReport.corrupt-json.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/examples/DriftReport.truncated.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/examples/DriftRefusal.mission-not-found.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/examples/DriftRefusal.scan-unreadable.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/openapi.yaml`
- `contracts/mission-status/schemas/_index.yaml`
- `contracts/mission-status/examples/_index.yaml`
- `contracts/mission-status/parameters/_index.yaml`
- `contracts/mission-status/responses/_index.yaml`
- `contracts/mission-status/CHANGELOG.md`
- `contracts/tools/enum_pins.json`
- `tests/contract/test_mission_status_examples.py`
- `tests/contract/test_enum_pin_check.py`

No file under `kitty-specs/` is in this write scope: record what you learn in the hand-off; the orchestrator appends it to the tracer files. An out-of-map edit is acceptable only when small, well-justified and recorded with a one-line rationale in the hand-off. Shared files in this list are declared chokepoints serialised by the dependency chain (plan 'Declared shared-file exceptions'); edit only your own entries in them.

## Implementation concern (plan section IC-04, verbatim)

- **Purpose**: `getDriftReport`, its schemas, enums, refusal, responses, parameter and examples.
- **Relevant requirements**: FR-008 to FR-014 (shape, summaries, remedy, `sourceCode`), FR-015 (descriptions: no-store, fallback rule, network behaviour), FR-023 (Drift part, provisional table), OR-2, OR-3, OR-4, OR-7, OR-9, ARCH-002, FRESH-014; AC-DRIFT 22, 24 and 28 (contract halves).
- **Affected surfaces**: new `paths/drift.yaml`, `parameters/DriftMissionId.yaml`, schemas `DriftReport`, `DriftFinding`, `LaneComparison`, `DriftKind`, `DriftSeverity`, `DriftAuthority`, `DriftSide`, `DriftRemedy`, `DriftRefusal`, `DriftRefusalCode`, responses `DriftMissionNotFound`, `DriftScanUnreadable`, and the Drift examples; edited `openapi.yaml` (the `/drift` key, the `Drift` tag), the four `_index.yaml`, `CHANGELOG.md` (Added, Provisional tokens, the not-shipped decision, `info` not carried, non-null), `enum_pins.json` (six pins), `test_mission_status_examples.py` (path keys, `MIN_EXAMPLES`, required cases), `test_enum_pin_check.py` (the `counts:` line).
- **Red-first**: `EXPECTED_PATH_KEYS` gains `/drift`, the required-case manifest gains each Drift example and the case that an example with a null `missionId` or `artifactPath` is refused, the pin test gains the six pins and the `counts:` line, and the CHANGELOG token test gains the Drift tokens; all red until the contract files exist.
- **Sequencing**: after IC-03 (chokepoint files). **Acceptance (named)**: `leak_scan.py`, `example_check.py`, `provisional_check.py`, `enum_pin_check.py`, `citation_check.py`, `layout_check.py` and `run_negative_cases.py` (JVM, vacuum and oasdiff tags excluded) green over the tree; the lowered-major spike keeps `breaking=4` with the new path and tag.
- **Risks**: **chokepoint** `openapi.yaml`, indexes, `enum_pins.json`, `CHANGELOG.md`; the `if`/`then` status pinning of `DriftRefusal`; `provisional_check` word-satisfaction (D-P11).

## Design decisions that bind this work package (plan, verbatim)

**D-P9 Contract authoring decisions.** All new enums are snake_case and pinned (PR-2; the vacuum `enum-case` rule is outside every Python gate, hence J-1). Every new property carries exactly one `x-source` or `x-derived` (field catalogue of the spec); every new schema is closed; every new operation keeps the shared `Problem` for `default`. Refusal schemas follow `ArtifactRefusal` (a `Problem` plus `code` and one `if`/`then` per code pinning the status). `DriftFinding.sourceCode` is a string matching `^[A-Z][A-Z0-9_]*$` or null; `OpsEvidence.value` has `maxLength: 512`; `OpsInvocation.profileId` and `action` use `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`. The two query parameter files are new (`DriftMissionId`, `OpsProfile`); `PageSize` and `PageCursor` are the shared ones. The unicode-escape hazard applies to every pattern with a NUL or backslash (write `\x00`, build `chr(0)` and `chr(92)` in tests).

**D-P11 CHANGELOG and provisional tests are section-scoped.** One test reads the existing `## 1.0.0-SNAPSHOT` section only: its headings, the three remaining deferred gaps (and the planted entry that lacks "lane weights" fails), the not-shipped decision of `derived_view_stale` with its reason, that `info` is not carried, that `missionId` and `artifactPath` of `DriftFinding` are non-null, the cap of 1000, and every FR-023 token inside the section's own `### Provisional` heading. The four **qualified** names (`DriftFinding.kind`, `DriftReport.truncated`, `DriftRefusal.code`, `OpsRefusal.code`) are asserted literally, each with a plant that removes it, because `provisional_check` is word-satisfied by the previous slice's `kind`, `code` and `truncated` (the previous slice's tracer friction F-4).

**D-P8 Router globs for the new imports.** The `contract_tools` group of `ci-router.yml` names the `src/` files the helpers import, spelled `**/<path>` so the group stays non-src. Each reader work package adds its own entries in sorted position in the commit that first imports the file (the helper commit; the red-first commit only if its stub or test module imports `src/`; a stub that merely raises needs none); `test_the_contract_tools_filter_group_names_every_src_file_the_mission_status_reader_and_its_tests_import` derives the required list from the imports and goes red until they are present. The expected new entries (to be recomputed by that test, never by hand): `status/lifecycle.py`, `lanes/models.py`, `status/validate.py` (one-way drift check only), `upgrade/metadata.py`, `migration/schema_version.py`, `core/paths.py`, `invocation/record.py`, `invocation/writer.py`, `invocation/errors.py`, `git/remote_probes.py` and the `__init__` files the import scan adds. No edit of `docs/development/reference/ci-gate-mechanics.md` is needed: its paragraph on the group already says "the `src/` modules the mission-status reference reader imports".

## Contract halves of the acceptance rows (plan, verbatim)

The reader proofs are WP07's; this WP proves the contract halves of these AC-DRIFT rows:

| 22 the fourth kind is absent | stale `.kittify/derived/` beside a clean and a mismatching Mission; `DriftKind` pinned to three (B, P) |
| 23 order and cap; nothing to report | 1001 findings in shuffled order give 1000 and `truncated`; exactly 1000 give false; a clean repository gives 200 with `findings: []` (the FR-024 "nothing to report" line) (B, P, M: sort off) |
| 24 fixed summaries, closed pair table, no leak | slug shaped like a host path and an event log holding an address; a reader producing a pair outside the table fails; leak scan clean (B, P) |
| 25 `scannedAt` and `no-store` | injected clock advanced between reads; a bundle without the header fails the example/operation test (B, P) |
| 28 no dead value | each `DriftKind`, `DriftSeverity`, `DriftAuthority`, `DriftSide`, `DriftRemedy` value produced by a fixture through the production entry point; `info` absent from the pin; an example with a null `missionId` or `artifactPath` fails validation (B, P) |

### Subtask T018: Red-first: required cases, path keys, pins and tokens

**Purpose**: Commit 1: `EXPECTED_PATH_KEYS` gains `/drift`; `MIN_EXAMPLES` moves; the required-case manifest gains each Drift example and the case that an example with a null `missionId` or `artifactPath` is refused; `test_enum_pin_check.py` gains the six pins and the `counts:` line; the CHANGELOG token test gains the Drift tokens. All red until the contract files exist.

**Steps**:
1. Write the assertions against names that do not exist yet; the red must be behaviour failures (missing example, missing pin), not collection errors.
2. Verify the red on the base without `git stash`.
3. **Camel-case plant (AC-VERSION, bullet 5, operator ruling 12):** in `tests/contract/test_enum_pin_check.py`, following the existing `module_copy` pattern (a copy of `contracts/mission-status` and `contracts/_shared` in the scratch directory), one test rewrites the value `snapshot_or_event_log_missing` of `schemas/DriftKind.yaml` in the copy to its camel-case spelling `snapshotOrEventLogMissing` and runs `enum_pin_check.py --root <copy> --module mission-status`: it must exit 1 with `ENUM_VALUE_ADDED: mission-status:DriftKind` naming `snapshotOrEventLogMissing` and `ENUM_VALUE_REMOVED: mission-status:DriftKind` naming `snapshot_or_event_log_missing` (the pin fails a changed enum value, so a camel-case value cannot ship); the unmodified copy is the control and exits 0. This is committed test code of WP04, red until the `DriftKind` pin and schema exist; the JVM lint half of the plant stays the orchestrator's J-1 replay.

**Files**: tests/contract/test_mission_status_examples.py, test_enum_pin_check.py (edit)

**Validation**: Red run recorded.

### Subtask T019: Schemas and enums

**Purpose**: Add the ten Drift schemas (`DriftReport`, `DriftFinding`, `LaneComparison`, `DriftKind`, `DriftSeverity`, `DriftAuthority`, `DriftSide`, `DriftRemedy`, `DriftRefusalCode`, `DriftRefusal`), each closed, `title` equal to the file stem, every property with exactly one `x-source` or `x-derived`, snake_case enums; `DriftFinding.missionId` and `artifactPath` non-null; `sourceCode` a string matching `^[A-Z][A-Z0-9_]*$` or null; `DriftReport.findings` `maxItems: 1000`.

**Steps**:
1. The `DriftFinding.summary` description carries the six fixed sentences of the data model, written verbatim (the reference reader compares them literally).
2. `DriftKind` has THREE values; the description states the two checks behind `lane_branch_missing`, that a manifest predating `mission_slug` is not evaluated for it, 'no local branch', and the considered-and-not-shipped decision on `derived_view_stale`.
3. `DriftRemedy` maps `materialize_status` once to `spec-kitty agent status materialize --mission <slug>` (not `spec-kitty materialize`), says the client builds the text and takes the slug from `MissionHead.slug`.

**Files**: ten files under schemas/

**Validation**: `citation_check.py`, `layout_check.py` exit 0.

### Subtask T020: Path, parameter, responses, openapi, tags

**Purpose**: Add `paths/drift.yaml` (operation `getDriftReport`, tag `Drift`, optional query `missionId` via `parameters/DriftMissionId.yaml`, 200 `DriftReport` with the documented `Cache-Control: no-store`, 404 `DriftMissionNotFound`, 500 `DriftScanUnreadable`, `default` shared `Problem`), the two responses (`application/problem+json`, schema `DriftRefusal`), the `/drift` key and the `Drift` root tag in `openapi.yaml`.

**Steps**:
1. The `getDriftReport` description states: a scan reads, never repairs; Rescan is a second call; `scannedAt` is the time of this scan; a Mission whose declared coordination branch no longer exists is scanned from its own directory which can lag the coordination surface; the stock coordination resolver may query remotes so the outcome depends on the network: an unreachable remote leaves the Mission's own directory as the read directory (200, no fallback entry), a reachable remote lacking the branch gives the fallback, and any other resolver error is a 500 (operator ruling at WP07, 2026-10-06); `findings: []` means the scan ran and found none.
2. `info.version` stays `1.0.0-SNAPSHOT`.

**Files**: paths/drift.yaml, parameters/DriftMissionId.yaml, two responses, openapi.yaml

**Validation**: `layout_check.py`, `example_check.py` exit 0.

### Subtask T021: Examples

**Purpose**: Add the six Drift examples (`DriftReport.clean`, `.populated`, `.corrupt-json`, `.truncated`, `DriftRefusal.mission-not-found`, `DriftRefusal.scan-unreadable`) per the planning contract; leaf schemas carry short inline `examples`.

**Steps**:
1. Every example leak-free (no host path, address, credential); a path in an example satisfies the artifact-path rule.
2. `DriftReport.truncated` is a short list with a comment (a real truncated report holds exactly 1000 findings).

**Files**: six files under examples/

**Validation**: `example_check.py` validated count equals the example count.

### Subtask T022: Indexes, CHANGELOG, pins; acceptance

**Purpose**: New entries in the four `_index.yaml` files; CHANGELOG additions merged into the `1.0.0-SNAPSHOT` section (Added; Provisional tokens `DriftKind`, `kind`, `remedy`, `DriftRemedy`, `laneComparison`, `truncated`, `DriftRefusalCode`, `code`; the not-shipped decision of `derived_view_stale` with its reason; `info` of the audit `Severity` not carried; `missionId` and `artifactPath` non-null; the cap of 1000; the read behaviour 'a manifest predating `mission_slug` is not evaluated for kind 3'); six pins in `enum_pins.json` (`DriftKind`, `DriftSeverity`, `DriftAuthority`, `DriftSide`, `DriftRemedy`, `DriftRefusalCode`; `info` absent from the severity pin). Run the acceptance set.

**Steps**:
1. Run `provisional_check.py` on the finished tree: its output is the final list, never a guess.
2. Run the lowered-major spike: `breaking=4` must hold with the new path and tag.

**Files**: four indexes, CHANGELOG.md, enum_pins.json

**Validation**: All named acceptance green.

## Validation: gates and targeted test surface (concrete; run from the lane workspace root)

Targeted files only, never a directory sweep. Use `PWHEADLESS=1` and the interpreter of the synced environment recorded at Step 0.

### Python checks over the contract tree and the negative-case runner

```text
.venv/bin/python contracts/tools/layout_check.py --root contracts
.venv/bin/python contracts/tools/citation_check.py --root contracts
.venv/bin/python contracts/tools/provisional_check.py --root contracts
.venv/bin/python contracts/tools/example_check.py --root contracts
.venv/bin/python contracts/tools/event_mapping_check.py --root contracts
.venv/bin/python contracts/tools/enum_pin_check.py --root contracts
.venv/bin/python contracts/tools/leak_scan.py --root contracts
.venv/bin/python contracts/tools/structure_check.py --root contracts
.venv/bin/python contracts/tools/codeowners_check.py
.venv/bin/python contracts/tools/no_pytest_scan.py
.venv/bin/python contracts/tools/run_negative_cases.py --manifest contracts/tools/negative_cases.json --work <scratch>/negative-work --exclude-tag jvm --exclude-tag vacuum --exclude-tag oasdiff
```

Exit codes: 0 pass, 1 violation, 2 the check could not do its job. Each prints a final `counts:` line; record them in the hand-off (plan-time lines: `layout_check` `path_files=8 index_files=7`; `citation_check` `properties=191 x_source=140 x_derived=51 inputs_resolved=93`; `provisional_check` `provisional_elements=22`; `example_check` `examples=75 validated=75`; `enum_pin_check` `enums=7 values=43`; `leak_scan` `files=1062 values_strict=682 values_human=8792 values_all=26219 values_artifact_path=37`; `structure_check` `readme_headings=20 changelog_headings=7`; these move as files are added). `citation_check` and `event_mapping_check` read git and the sources: run them from a checkout.

### Tool tests, example and proof modules

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/contract/test_leak_scan.py tests/contract/test_fixture_builder.py tests/contract/test_enum_pin_check.py tests/contract/test_run_negative_cases.py tests/contract/test_mission_status_examples.py tests/contract/test_mission_status_contract_1_1.py
```

### Additive-proof spike

The lowered-major breaking-check spike on the real files (research R-5), run from the checkout with the pinned `oasdiff` fetched into a scratch directory:

```text
.venv/bin/python contracts/tools/install_tools.py --pins contracts/tools/pins.json --dest <scratch>/tools --only oasdiff
mkdir -p <scratch>/base && git archive <baseline sha> contracts/mission-status contracts/_shared | tar -x -C <scratch>/base
# move the two directories up one level so <scratch>/base/mission-status and <scratch>/base/_shared exist;
# copy that directory to <scratch>/lowered and rewrite info.version in its mission-status/openapi.yaml to 0.9.0 (scratch only)
PATH=<scratch>/tools/oasdiff-1.32.1:$PATH .venv/bin/python contracts/tools/breaking_check.py --root contracts --baseline-root <scratch>/lowered
```

`<baseline sha>` is the merge-base of `HEAD` with upstream `main` (`git merge-base HEAD <main>`), recorded by the orchestrator's Step 0. Expected: exit 0 and a final line `counts: modules=1 baselines=1 breaking=4 provisional_changes=<N> no_baseline_initial=0 preview_ref=skipped` (the four breaking entries name `currentBranch`, `lastActivityAt`, `schemaVersion` and `specKittyVersion`; `<N>` is measured on the tree and reported). Adding the new path and tag must not change `breaking=4`.

### Named gate files (router, registry, corpus-trigger, terminology, archive-freeze, ruff pair, cutover guard)

Run after every rebase and before hand-off:

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/ci/test_contracts_workflows.py tests/ci/test_contracts_routing.py tests/ci/test_corpus_blocking_home.py \
  tests/architectural/test_ci_corpus_trigger_completeness.py tests/architectural/test_same_tier_uniqueness.py \
  tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_module_shard_registry.py \
  tests/architectural/test_workflow_coherence.py tests/architectural/test_no_legacy_terminology.py
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/architectural/test_archive_root_byte_identical.py
.venv/bin/ruff check .
.venv/bin/ruff format --check .
<synced-spec-kitty> cutover-guard --base-ref origin/main
```

Environment note: the checkout `.venv` is hand-built and lacks ruff, mypy and respx (a stale-venv red, bin 4). Use the synced environment the orchestrator recorded at Step 0 (its ruff and test extras; never `uv run` in the checkout `.venv`). **Substitution rule for every command of this prompt: each `.venv/bin/python` and `.venv/bin/ruff` written below reads `<synced-python>` and `<synced-ruff>`** (the `<scratch>/venv/bin/python` and `<scratch>/venv/bin/ruff` of the Step 0 record, defined once in item 2 of the Step 0 block of `tasks.md`); the hand-built `.venv/bin/python` is not used for any gate command of this work package (every `.venv/bin/spec-kitty` written below, the `cutover-guard` gate, reads `<synced-spec-kitty>` = `<scratch>/venv/bin/spec-kitty`, the CLI of the same synced environment, because a lane workspace does not carry the checkout `.venv`; orchestrator note 18 of `reviews/tasks.ruling.md`, defined once in item 2 of the Step 0 block of `tasks.md`, same import check and `PYTHONPATH` rule). Per-file format check: `ruff format --check --force-exclude <files>`.

### Census files that read `tests/` (run at implement start, after every new or edited test module, and at hand-off)

The list is derived at Step 0 from the `fast_gate` roster plus the heavy-battery census files, and every path was checked to exist:

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/architectural/test_no_manual_global_state_mutation.py tests/architectural/test_no_tmp_paths_in_tests.py \
  tests/architectural/test_issue_named_test_census.py \
  tests/architectural/test_global_state_allowlist_sealed.py \
  tests/architectural/test_spec_kitty_home_pin_census.py tests/architectural/test_spec_kitty_home_pin_guard.py \
  tests/architectural/test_spec_kitty_home_pin_budget.py tests/architectural/test_home_pin_gate_verdict.py \
  tests/architectural/test_clock_import_ban.py tests/architectural/test_clock_call_ban.py
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/architectural/test_layer_rules.py tests/architectural/test_pyproject_shape.py
.venv/bin/ruff check --select TID251 .
```

Named files only, never the directory, never `tests/architectural` as a sweep (charter rule `NO_FULL_HEAVY_SUITES_IN_MISSION`). The scans inspect real-git fixtures, a `subprocess` stub, a counting wrapper, git identity setup, any manual `os.chdir`, `os.environ` or `sys.path` change, a shared-temp literal and a wall-clock call in a test module: use `monkeypatch` and a scratch `HOME`, an injected clock, and build host-path-shaped plants from fragments. **No allowlist or baseline entry may be added to make a new module pass.** The two dead-symbol files walk `src/` (no `src/` change here) and run only in the Step 0 baseline.

## Red-first rule (C-011, charter ATDD-First Discipline)

The FIRST commit of this work package is its failing tests, with a raising stub for each production entry point the tests call, red on the lane base and committed BEFORE any implementation commit (registration pair included where this WP creates a module). The stub raises (for example `NotImplementedError`), so the red run shows **behaviour failures, not collection or import errors**; the reviewer checks that, and that the **control tests are red too** (a control that is green against the stub is not exercising the entry point). Verify the red without `git stash`: extract the base into a scratch directory (`git archive <base-commit> | tar -x -C <scratch>/base`), copy the new test file(s) and stub in, and run pytest from that directory with the checkout's interpreter; record the failing test ids and the reason in the hand-off. The reviewer verifies red then green: red on the base, green on the tip. Tests call the production entry point, never only a helper. Never weaken, skip or retry-to-green a test.

## Dispatch hygiene (binding for this work package)

- **No sub-agents.** You work alone: do not start, fork, brief or message other agents.
- **A denied command means STOP and report it** in the hand-off; never retry a denied command in another form.
- **No pattern kills** (`pkill`, `killall`), **no `git stash`**, **no `rm` with a variable or wildcard glob**, no checkout, switch, restore, reset, clean or rebase of the shared checkout. Work in the lane workspace the orchestrator assigns; do not move HEAD of any other workspace.
- **Repository-relative paths only** in every file, commit message and report; placeholders such as `<repo>`, `<scratch>`, `<tmp>`, `<user>` elsewhere. This repository is PUBLIC: no absolute path under a home directory, no drive path, no user name, e-mail address, private identifier, chat mention or credential in any file, test, fixture, commit message or report. Leaking values a test needs (host paths, addresses, tokens, an at-sign file name) are assembled from fragments at run time and never typed as literals; no shared-temp literal in any plant.
- **Unicode-escape hazard:** editing tools decode a backslash-u sequence typed into a file into the raw character. Write a NUL as `\x00` in a contract pattern, build NUL with `chr(0)` and a backslash with `chr(92)` in tests, and check every new file for raw NUL bytes after writing.
- **Commit locally. NEVER push, never open a pull request, never comment on an issue, never merge.** Conventional commit subjects ending with `(#5776)`; end each commit message with the attribution trailers the dispatch brief supplies. Commit through `spec-kitty safe-commit` where a guarded branch requires it; never bypass a guard.
- **Never hand-edit** `status.events.jsonl`, `meta.json`, `status.json`, `lanes.json`, issue-matrix files or work package frontmatter; never call `materialize`.
- **Baseline-red binning against the Step 0 record.** Before your first change run this work package's targeted commands once on the unchanged lane base and reconcile with the orchestrator's Step 0 record in `tracer-approach.md` (read it; the orchestrator appends it before any dispatch). Bin every red: (1) pre-existing known-P0 (nightly lane only), (2) CI-environment, (3) stale install, (4) stale venv (resync, then retry), (5) introduced. Only a failure red on your branch and green on the base is yours. A pre-existing red: STOP and report it (command, failure summary, why you believe it is pre-existing); the orchestrator owns the tracker issue (Pre-existing Failure Reporting Rule). Do not absorb it, never retry until green. A red on your lane base but green at the Mission baseline came from an earlier work package of this Mission: report it against that work package, do not bin it as pre-existing.
- Terminology: Mission, never feature; say which sense of lane (status lane versus code lane). New code passes `ruff check` and `ruff format --check` with no suppression added; complexity ceiling 15; a literal used three or more times in a module becomes a constant; new code is annotated to pass `mypy --strict` as local discipline.

## Hand-off report (your final message)

Commits (hash and subject in order, the first marked as the red-first commit); the red evidence (failing test ids, why they are behaviour failures, that the controls are red, how it was verified on the base); every command run with passed/failed/skipped counts and exit codes; baseline bins against the Step 0 record; **measured minima, margins and re-measurements** (every timed bound: the minimum of the repeats and the margin below the bound; every re-measured count; every floor against its re-measure); any refinement of a contract note or design decision; any friction observation (tooling hazards met); anything not done and why. **Code work packages never write under `kitty-specs/`**: the orchestrator appends decisions, measurements and friction add-only to `tracer-approach.md`, `tracer-design-decisions.md` and `tracer-tooling-friction.md` between dispatches.

## Definition of Done

- `leak_scan.py`, `example_check.py`, `provisional_check.py`, `enum_pin_check.py`, `citation_check.py`, `layout_check.py` and `run_negative_cases.py` (JVM, vacuum and oasdiff tags excluded) green over the tree.
- The lowered-major spike keeps `breaking=4` with the new path and tag.
- AC-DRIFT 22, 24 and 28 contract halves (the pin of three kinds; the fixed-summary description; null `missionId` or `artifactPath` refused by validation).
- The named census files and registration gates run green.
- First commit is the red tests with a raising stub (behaviour failures, controls red), verified on the base; green on the tip.
- Named gate files and census files green or binned against the Step 0 record; ruff check, ruff format --check and TID251 clean with no suppression added.
- Hand-off carries measured minima, margins and re-measurements; nothing written under `kitty-specs/`.
- Per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.
- Nothing pushed; no pull request; no tracker write.

## Risks

- Chokepoint files: `openapi.yaml`, indexes, `enum_pins.json`, `CHANGELOG.md`.
- The `if`/`then` status pinning of `DriftRefusal`.
- `provisional_check` word-satisfaction (D-P11).

## Reviewer Guidance

The reviewer is a separate role from the implementer. Review the diff of this work package against its owned files and its full targeted test surface, plus the named gate files and census files above; never a full sweep.
- Verify red then green: the first commit is the red-first commit with a raising stub; the red run shows BEHAVIOUR failures, not collection errors; the control tests are red too; green on the tip.
- Re-run the named gate files and the census files; check baseline bins against the Step 0 record in `tracer-approach.md`; check the hand-off carries measured minima, margins and re-measurements.
- Check public hygiene: no absolute path, user name, address, credential or private detail in any added line or commit message; no leaking literal; no raw NUL byte.
- Check nothing under `kitty-specs/` was written and no file outside the owned list changed without a recorded rationale.
- Re-run the Python checks and the spike; check every new property carries exactly one `x-source` or `x-derived`, all enums are snake_case and pinned, every example is leak-free and the Provisional list equals `provisional_check.py` output.

## Wrap-up reference (orchestrator-owned, NOT part of this work package)

After every work package is approved the orchestrator runs W-1 (accept, local lane consolidation, registration and scope check over the real diff), W-2 (J-1 confirmation), W-3 (dev-assist cleanup), W-4 (issue-verdict evidence, aggregate adversarial squad, terminal #5776 verdict), W-5 (history compaction), W-6 (rebase onto upstream `main`) and W-7 (final evidence); then the draft pull request. You do none of this.

## Implementation command

`spec-kitty agent action implement WP04 --agent claude`
