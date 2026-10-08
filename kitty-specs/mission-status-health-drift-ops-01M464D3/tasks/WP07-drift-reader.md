---
work_package_id: WP07
title: Drift reader and its tests
dependencies:
- WP06
requirement_refs:
- FR-008
- FR-009
- FR-010
- FR-011
- FR-012
- FR-013
- FR-014
- FR-015
- FR-024
- FR-026
- NFR-002
- NFR-003
- NFR-005
- NFR-006
- NFR-007
- C-009
- SC-003
- SC-010
planning_base_branch: issue-5776-mission-status-contract-health-drift-ops
merge_target_branch: issue-5776-mission-status-contract-health-drift-ops
branch_strategy: Planning artifacts for this mission were generated on issue-5776-mission-status-contract-health-drift-ops. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5776-mission-status-contract-health-drift-ops unless the human explicitly redirects the landing branch.
subtasks:
- T034
- T035
- T036
- T037
- T038
- T039
- T040
- T056
history: []
agent_profile: python-pedro
authoritative_surface: tests/contract/
create_intent:
- tests/contract/_mission_status_drift.py
- tests/contract/test_mission_status_drift.py
execution_mode: code_change
model: ''
owned_files:
- tests/contract/_mission_status_drift.py
- tests/contract/test_mission_status_drift.py
- .github/workflows/packs.yml
- tests/architectural/test_ci_corpus_trigger_completeness.py
- .github/workflows/ci-router.yml
role: implementer
tags: []
tracker_refs: []
---
# Work Package Prompt: WP07 - Drift reader and its tests

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Build the drift reader (the strict sibling of the v1 read-directory helper, the fallback list, kinds 1 to 3, the fixed summaries, order and cap) and every fixture of FR-026 that concerns drift, with a mutation catalogue.

## Context

Not dispatched before the J-1 record exists in `tracer-design-decisions.md` (or the operator accepted the open risk P-9): the reader is built on contract shapes that must be final. The module is fixture-built only: a temporary repository per case, each plant with its control; corpus-reading cases live in the reality module (WP09). May be split by the orchestrator into kinds 1 and 2 with the read-directory logic, then kind 3 and the listing (same files, sequential, the registration pair in the first part). The resolver: assumptions only (spec R-9); nothing here reasons about its internals beyond the outcomes the spec fixes. The first test run happens with the real resolver against real-git fixtures (0.02 s a repository); the network case uses the offline fixture with the one private import `_reset_remote_branch_lookup_cache` (FR-026).

Plan concern: IC-07 of `kitty-specs/mission-status-health-drift-ops-01M464D3/plan.md`. Read, in this order, before writing anything: `.kittify/charter/charter.md`, `AGENTS.md` (for conventions only), the Mission's `spec.md` (the requirement ids in the frontmatter), `plan.md` sections named below, `research.md`, `data-model.md`, `quickstart.md` and `contracts/*.md` in `kitty-specs/mission-status-health-drift-ops-01M464D3/`.

**Dependencies and order.** Depends on WP06; the lane workspace already holds their approved commits. No work package is dispatched before the orchestrator's Step 0 record exists in `tracer-approach.md`. **Pre-dispatch (orchestrator Step PD in `tasks.md`, operator ruling 13):** before this dispatch the orchestrator fast-forwards the mission-lane branch `kitty/mission-<slug>` and, once the orchestrator's run of `spec-kitty agent action implement WP07 --agent claude` (the command of your Implementation command section; it creates or resumes the lane workspace) has created this lane workspace and before you are started, merges the planning branch into it and greps inside it for every record this prompt reads: the Step 0 record (heading `## Record: Step 0`) and the hand-off record of WP06 (heading `## Record: Hand-off WP06 (`) in `tracer-approach.md`, and the J-1 record (heading `## Record: J-1 (`) in `tracer-design-decisions.md`, the last `contracts-commit: <hash>` line of the J-1 record being the same hash as the last `contracts-commit: <hash>` line of the WP06 hand-off record (`a=$(grep "^contracts-commit: " tracer-approach.md | tail -n 1); b=$(grep "^contracts-commit: " tracer-design-decisions.md | tail -n 1); [ -n "$a" ] && [ "$a" = "$b" ] && echo OK` prints OK, run from the mission directory `kitty-specs/<mission-slug>/` of the lane workspace (both last lines non-empty and equal)); read them from the lane workspace root. If a line the prompt tells you to read is not there, stop and report it; never run `--refresh-planning-commit` and never copy a record in by hand.

## Owned files (write scope; final, explicit, no directory-wide glob)

- `tests/contract/_mission_status_drift.py` (new: created by this WP, listed in `create_intent`)
- `tests/contract/test_mission_status_drift.py` (new: created by this WP, listed in `create_intent`)
- `.github/workflows/packs.yml`
- `tests/architectural/test_ci_corpus_trigger_completeness.py`
- `.github/workflows/ci-router.yml`

No file under `kitty-specs/` is in this write scope: record what you learn in the hand-off; the orchestrator appends it to the tracer files. An out-of-map edit is acceptable only when small, well-justified and recorded with a one-line rationale in the hand-off. Shared files in this list are declared chokepoints serialised by the dependency chain (plan 'Declared shared-file exceptions'); edit only your own entries in them.

## Implementation concern (plan section IC-07, verbatim)

- **Purpose**: The drift reader, the strict sibling, the fallback list, kinds 1 to 3, the fixed summaries, order and cap, and every fixture of FR-026 that concerns drift.
- **Relevant requirements**: FR-008 to FR-015, FR-024 (drift rows), FR-026 (drift fixtures), NFR-002, NFR-003, NFR-005, NFR-007, ARCH-001, GOV-001, GOV-007, COMPLETE-001, COMPLETE-013's drift counterpart (AD-10), FRESH-001, FRESH-007, FRESH2-001 to FRESH2-007, FRESH3-001; AC-DRIFT 1 to 15, 17, 18 and 20 to 28 (row 19's fixture half stays here; its corpus half is IC-09's), AC-CROSS 1, 4, 5 (drift parts: the counting opener and the subprocess total on fixtures; the corpus-sized cases of row 4 are IC-09's).
- **Affected surfaces**: new `_mission_status_drift.py`, new `test_mission_status_drift.py` (markers `contract`, `corpus`, `git_repo`; module `pytestmark`), `.github/workflows/packs.yml`, `tests/architectural/test_ci_corpus_trigger_completeness.py`, `.github/workflows/ci-router.yml`.
- **Red-first**: the AC-DRIFT rows of the Test strategy, each with its control, against a stub `scan_drift` that raises; the mutation catalogue of the drift reader.
- **Sequencing**: after IC-06 (J-1 done). **Acceptance (named)**: the first commit holds the red tests and a raising stub; every mutation of the catalogue is killed; the named census files and the registration gates run green; the named gate files of the quickstart.
- **Risks**: the resolver (assumptions only, spec R-9), real-git fixtures (0.02 s a repository), network (the offline fixture), the 500 line (D-P7), the size of the module (a possible split into IC-07a kinds 1 and 2 and IC-07b kind 3 is allowed, same files, sequential).

## Design decisions that bind this work package (plan, verbatim)

**D-P1 Reader architecture.** Five helper modules (PD-1). Entry points return an outcome object (an HTTP status and a body, or a typed refusal), never raise for a refusal, so each of the two operations is testable as the service answers it. An injectable file-system seam (`scandir`, `lstat`, `open_binary`) with counting and fault-injecting wrappers serves the bounded-read assertions (NFR-002); the reader's own code opens only the files the spec lists. No private import except the one `_reset_remote_branch_lookup_cache` of the offline fixture (FR-026) and none in the oracles.

**D-P2 The resolver memo (FR-015, FRESH2-003, FRESH3-004).** One neutral helper module, `_mission_status_memo.py`: an object `memo` created per run (a reality run or a fixture build), keyed by (resolved repository root, Mission directory name), holding the raw resolver outcome (the directory or the exception) and the number of subprocesses the call started. Consumers: the strict drift sibling (D-P3), the new Project builder (D-P4) and the oracles. A test builds two repositories with the same Mission name and different outcomes and asserts each gets its own result; a control reads one repository twice and asserts one resolver run. **Counting:** the subprocess count wraps `subprocess.Popen.__init__` through a pytest `MonkeyPatch` context (never a manual global mutation, which the architectural scans flag); IC-03's first task runs the two named scan files against a stub module holding this wrapper before the helper is written (risk P-14). The FR-007 stub of `subprocess.run` that raises unless the memo helper's resolver call is on the stack composes with it.

**D-P3 The strict drift sibling (FRESH2-004).** In `_mission_status_drift.py`: catches `CoordinationBranchDeleted` only and returns the Mission's own directory with the reason `coordination_branch_deleted`; every other resolver exception propagates as a typed unreadable outcome (500 `drift_scan_unreadable`); a read directory outside the repository root raises. v1's `resolve_read_dir` is not edited (a ratchet file) and is the control of the plant: one test asserts, on the same three fixtures (`CoordAuthorityUnavailable`, `MissionMetadataUnavailable`, outside the root), that the strict sibling raises while the v1 helper returns the own directory with a reason, and that for `CoordinationBranchDeleted` both return the own directory.

**D-P6 Kind 3 is provisional and honest-rule gated, not floored (FR-012, R-1).** The reader implements the rule exactly as written (completion first; three-way `lanes.json` classification for a non-completed Mission; expected lane and expected Mission-level branch; one local-ref listing, once; one finding per Mission, no branch name). The oracle shares the product's `is_mission_completed` and `materialize_snapshot` for a Mission whose read directory is its own directory and reads the two arms directly otherwise (COMPLETE-012), reads `meta.json` and the manifest as raw JSON, and tests each expected name with its own `git rev-parse --verify --quiet`. **No corpus floor and no assertion rests on the old 93**: the corpus is asserted equal to the oracle, and the synthetic fixtures carry the named plants (a merged marker, an all-terminal Mission, a reopened Mission, an expected and a planned-only lane, the coordination pair). IC-01's first task re-measures the counts under the final rule (research R-3); if the finding population is dominated by a class the oracle shares with the reader by construction, the honest-rule criterion cannot be met and the point goes to the operator, not to a self-ruled change.

**D-P7 The `lanes.json` classification and the 500 line.** One raw JSON pre-read before `read_lanes_json`, only after the completion test says not completed; legacy shape (`feature_slug` and no `mission_slug`) is counted on the named list for kind 3 only; every other shape is 500 `drift_scan_unreadable`. The literal `feature_slug` appears once, in the reader's legacy-shape test, and the reader-literal pin test of T056 pins it (AC-VERSION, bullet 5 of the spec; the terminology scan itself reads only the contract YAML and the CHANGELOG entry). The principle of the round-2 rulings is the test: a broken derived file is a finding, a broken authority a 500, an older valid shape "not evaluated" and counted.

**D-P8 Router globs for the new imports.** The `contract_tools` group of `ci-router.yml` names the `src/` files the helpers import, spelled `**/<path>` so the group stays non-src. Each reader work package adds its own entries in sorted position in the commit that first imports the file (Registration item 4 says which); `test_the_contract_tools_filter_group_names_every_src_file_the_mission_status_reader_and_its_tests_import` derives the required list from the imports and goes red until they are present. The expected new entries (to be recomputed by that test, never by hand): `status/lifecycle.py`, `lanes/models.py`, `status/validate.py` (one-way drift check only), `upgrade/metadata.py`, `migration/schema_version.py`, `core/paths.py`, `invocation/record.py`, `invocation/writer.py`, `invocation/errors.py`, `git/remote_probes.py` and the `__init__` files the import scan adds. No edit of `docs/development/reference/ci-gate-mechanics.md` is needed: its paragraph on the group already says "the `src/` modules the mission-status reference reader imports".

**D-P12 Read-only proof.** `tree_fingerprint` (it already takes a sub-path and hashes bytes and directory names) runs over `kitty-specs` and over `kitty-ops` before and after the run; writers are replaced by ones that raise; a control that writes shows the probe sees writes; the reader's seam records no write mode; the existing autouse fingerprint fixture of the reality module covers the new cases.

## Acceptance rows of this work package (plan 'Test strategy per acceptance criterion', verbatim)

Rule for every row: the test fails when the change is reverted. **Three kinds of revert proof**, named in each row: **B** base-red (the test is red on the work package's base and green on its tip; the first commit carries the test and a stub entry point that raises, so a red is a behaviour failure); **P** planted pair (a control that passes and a plant that fails on the same fixture, so the probe can see the thing); **M** named mutation (a table of reader mutations applied by the test, each of which must turn its rows red: `the mutation was not killed: <name>`; the catalogue is in contracts/tool-extension-and-reader.md). Tests call the reference reader's production entry point, never only a helper. Row numbers are the order of the spec's tables.

| Row | Red-first test (proof kind) |
|---|---|
| 1 differing snapshot; variant and order | `WP01` planned versus approved; provenance-only; all-done; unmodified control (B, P, M: confuse variants) |
| 2 corrupt snapshot a finding; unreadable and raising reducer 500 | not JSON; a list; `OSError`; corrupt event log; control before corruption (B, P) |
| 3 `laneComparison` rows and nulls | one-sided work package; `genesis` lane; plain difference control (B, P) |
| 4 exactly one file missing; path; remedy | log without snapshot (remedy), snapshot without log (null), neither (none), both (control) (B, P) |
| 5 remedy null on a merged Mission | `merged_at` in the own `meta.json` versus an unmerged twin (B, P) |
| 6 expected lane branch absent | active Mission, `in_progress` lane, no branch; control with the branch (B, P) |
| 7 coordination expects its coordination branch only | absent gives a finding, present gives none although `mission_branch` is absent; a non-coordination control expects `mission_branch` (B, P, M: expect both) |
| 8 local branches only | remote-tracking ref only; control local (B, P) |
| 9 not expected | planned-only lane; completed Mission; absent manifest, each beside a flagged Mission (B, P) |
| 10 `lanes.json` three-way; completion first | non-completed: legacy-shaped (no finding, listed), not UTF-8, not JSON, not an object, neither key, current-shaped missing a key (each 500); completed: the same files are never read; control current manifest (B, P, M: read before completion) |
| 11 `meta.json` fail-closed | `[]` and invalid JSON are 500; absent `meta.json` is no coordination branch (B, P) |
| 12 git failure is never kind 3 | no `.git` with an expected lane (500); scan with no expected lane not failed (B, P) |
| 13 at most one listing, once | many Missions with expected lanes: the reader's own subprocess count exactly one; none expected: zero (B, P, M: per-branch call) |
| 14 a remote that cannot be asked | real-git fixture, remote URL a non-existent local path, declared branch absent locally: 200 from the own directory, no fallback entry (operator ruling at WP07, 2026-10-06); control a reachable remote lacking the branch: 200 fallback; cache reset between (B, P) |
| 15 `missionId` lookup uses the v1 identity read | unreadable `meta.json` in B, `?missionId=` of A is 200; unknown ULID is 404 (B, P) |
| 16 memo keyed by root and directory | two repositories, same name, different outcomes; one repository read twice runs the resolver once (in the project module, IC-03) (B, P) |
| 17 read directory coordination-aware; fallback; other 500s | coordination copy consistent with stale primary (none) and the reverse (kind 1); deleted branch a 200 naming `coordination_branch_deleted`; the other resolver outcomes 500 (B, P) |
| 18 strict sibling does not fall back, v1 does | the three fixtures in one test (B, P) |
| 19 completion reads the own directory | **drift module (fixtures):** `merged_at` in the own copy only versus the coordination copy only (B, P). **Reality module (IC-09, corpus job):** equality with `is_mission_completed` over every corpus Mission declaring no coordination branch, with a discovered-count guard: the compared count equals an independent `meta.json` scan, is above zero and is at least the floor of D-P13 (490); a planted empty directory fails (B, P) |
| 20 generation gate | older-generation snapshot in step with its replay (none); same Mission at the current generation with a field differing (kind 1) (B, P) |
| 21 undecodable files | invalid UTF-8 in each of `status.json` (finding), `lanes.json` (500 non-completed, unread completed), `meta.json` (500), the event log (500); clean control (B, P) |
| 22 the fourth kind is absent | stale `.kittify/derived/` beside a clean and a mismatching Mission; `DriftKind` pinned to three (B, P) |
| 23 order and cap; nothing to report | 1001 findings in shuffled order give 1000 and `truncated`; exactly 1000 give false; a clean repository gives 200 with `findings: []` (the FR-024 "nothing to report" line) (B, P, M: sort off) |
| 24 fixed summaries, closed pair table, no leak | slug shaped like a host path and an event log holding an address; a reader producing a pair outside the table fails; leak scan clean (B, P) |
| 25 `scannedAt` and `no-store` | injected clock advanced between reads; a bundle without the header fails the example/operation test (B, P) |
| 26 404, 400, per-Mission equality | unknown ULID 404; non-ULID 400; per-Mission equals project-wide filtered (B, P) |
| 27 read-only | `materialize` and file creation raising; a control that writes (B, P) |
| 28 no dead value | each `DriftKind`, `DriftSeverity`, `DriftAuthority`, `DriftSide`, `DriftRemedy` value produced by a fixture through the production entry point; `info` absent from the pin; an example with a null `missionId` or `artifactPath` fails validation (B, P) |

Row 16 is proved in `test_mission_status_project.py` by WP03; row 19's corpus half is WP09's. AC-CROSS 1, 4 (fixture-built half) and 5 drift parts:

| AC-CROSS 1 determinism | two reads byte-equal; two bundle builds equal; a clock tick changes `scannedAt` only (B, P) | (the bundle half is carried by the existing `test_two_bundle_builds_of_this_tree_are_byte_identical`, see WP06; no test is written here for it)
| AC-CROSS 4 bounded reads and time | **fixture-built:** counting opener, and subprocess total equals the memo's count plus the listing (drift and ops modules; these are counts, not timings); the synthetic 10,000-file directory at most 30 s (minimum of at least 5 repeats, D-P16) is the Ops module's case only (WP08 T045, plan D-P16 and IC-08), and the drift module has no absolute timing assertion. **Corpus-sized (reality module, IC-09):** real directory at most 5 s (minimum of at least 5 repeats); one Project build and one scan at most 120 s each; one case timing the memoised pass, the Project build and the per-Mission reductions together at most 120 s; each with a discovered-count guard (served plus skipped equals discovered and is non-zero; Missions examined at least the floor); the planted cache-the-result mutation (a memoising listing, applied as a context manager in the reality module) must turn the real 5 s listing case red (B, P, M) |
| AC-CROSS 5 writers | covered by AC-DRIFT 27 and AC-OPS 14 |

### Subtask T034: Red-first commit: AC-DRIFT rows, raising stub, registration pair

**Purpose**: Commit 1: `tests/contract/test_mission_status_drift.py` with every AC-DRIFT row below, each with its control, against a stub `scan_drift` (in `_mission_status_drift.py`) that raises; the mutation catalogue of the drift reader (contracts/tool-extension-and-reader.md); the registration pair and `pytestmark` in the same commit; the reader-literal pin test of T056 also belongs in this commit.

**Steps**:
1. Reader entry points return an outcome object (HTTP status and body, or a typed refusal) and never raise for a refusal (D-P1).
2. Real-git fixtures, a `subprocess` stub and a counting wrapper are what the architectural scans inspect: use `monkeypatch`, a scratch `HOME`, no shared-temp literal; run the census files immediately after this commit.

**Files**: tests/contract/test_mission_status_drift.py (new), _mission_status_drift.py (stub), .github/workflows/packs.yml, tests/architectural/test_ci_corpus_trigger_completeness.py (the registration pair); .github/workflows/ci-router.yml only if the test module or the stub already imports a `src/` file the `contract_tools` group does not name (otherwise the globs land with the helper's real imports)

**Validation**: Red run: behaviour failures, controls red; registry gates green.

### Subtask T035: Strict sibling and fallback (D-P3, D-P7)

**Purpose**: Implement the read-directory step: catches `CoordinationBranchDeleted` only and returns the Mission's own directory with reason `coordination_branch_deleted`; every other resolver exception becomes a typed unreadable outcome (500 `drift_scan_unreadable`); a read directory outside the repository root raises. v1's `resolve_read_dir` is NOT edited and is the control of the plant.

**Steps**:
1. AC-DRIFT 17 and 18: the three fixtures (`CoordAuthorityUnavailable`, `MissionMetadataUnavailable`, outside the root) in one test; strict raises, v1 returns own directory with a reason; both agree for `CoordinationBranchDeleted`.
2. Resolver only through the memo helper of WP03.

**Files**: tests/contract/_mission_status_drift.py

**Validation**: AC-DRIFT 14-18, 21 green.

### Subtask T036: Kinds 1 and 2

**Purpose**: Kind 1 (`snapshot_disagrees_with_event_log`): compare the persisted snapshot with the reducer replay at the snapshot's own generation (generation gate); a corrupt snapshot is a `CORRUPT_JSON` finding, unreadable or raising reducer is a 500. Kind 2 (`snapshot_or_event_log_missing`): exactly one file missing, path, remedy (null on a merged Mission; `merged_at` read from the Mission's own `meta.json`). One finding per Mission with the six fixed summaries.

**Steps**:
1. `laneComparison` rows and nulls, `genesis` lane, one-sided work package.
2. Undecodable files: invalid UTF-8 in each file as the table says (finding for `status.json`; 500 for `meta.json`, the event log and, when non-completed, `lanes.json`).

**Files**: tests/contract/_mission_status_drift.py

**Validation**: AC-DRIFT 1-5, 20, 21 green.

### Subtask T037: Kind 3 and the single branch listing

**Purpose**: Completion first (`is_mission_completed` over the own directory); then the three-way `lanes.json` classification for a non-completed Mission (legacy shape counted and not evaluated; every other broken shape 500); expected lane branch and expected Mission-level branch (coordination Missions expect their coordination branch only); ONE local-ref listing for the whole scan (zero when none is expected); a listing failure is a 500, never kind-3 findings; local branches only.

**Steps**:
1. `feature_slug` appears exactly once in `_mission_status_drift.py`, in the legacy-shape test. It is pinned by the T056 test, NOT by the existing terminology scan: `terminology_problems` in `tests/contract/test_mission_status_contract_1_1.py` scans only the YAML files of `contracts/mission-status` and the CHANGELOG entry, never a Python reader, so without T056 a second use would pass unseen.
2. Mutation: per-branch git call must be killed (AC-DRIFT 13: subprocess count exactly one).

**Files**: tests/contract/_mission_status_drift.py

**Validation**: AC-DRIFT 6-13, 19 (fixture half) green.

### Subtask T038: Order, cap, summaries, scannedAt, per-Mission entry, read-only

**Purpose**: Order and cap of 1000 with `truncated`; nothing to report gives 200 with `findings: []`; fixed summaries with a closed pair table and no leak; `scannedAt` from an injected clock (no default wall-clock call); `no-store`; unknown ULID 404, non-ULID 400, per-Mission equals the project-wide report filtered; `missionId` lookup uses the v1 identity read; no write of any kind.

**Steps**:
1. No dead value: each `DriftKind`, `DriftSeverity`, `DriftAuthority`, `DriftSide`, `DriftRemedy` value is produced by a fixture through the production entry point.
2. `materialize` and file creation raise in the read-only test; a control that writes proves the probe sees writes.

**Files**: tests/contract/_mission_status_drift.py

**Validation**: AC-DRIFT 15, 22-28 green.

### Subtask T039: Mutation catalogue and bounded reads

**Purpose**: Every mutation of the catalogue is killed (`the mutation was not killed: <name>`); the counting opener and subprocess-total tests (AC-CROSS 1, 4, 5 drift parts, fixture-built).

**Steps**:
1. Confuse variants, expect both branches, read before completion, per-branch call, sort off: each turns its rows red.
2. The 10,000-file timed case is owned by WP08 (T045, the Ops module); this module has no absolute timing assertion. Bounded reads here are counted (opener and subprocess counts), not timed.

**Files**: tests/contract/test_mission_status_drift.py

**Validation**: All mutations killed.

### Subtask T040: Acceptance runs (router-glob derivation check)

**Purpose**: Confirm that the router-glob derivation test (`test_the_contract_tools_filter_group_names_every_src_file_the_mission_status_reader_and_its_tests_import`, in `tests/ci/test_contracts_workflows.py`) is green. The globs were already added, each in the commit that first imported its `src/` file (Registration item 4); this subtask edits nothing. Run the module under the router marker expression and the negative collection; run the census and registration gates and, last, the three battery legs (binding gate below).

**Steps**:
1. Record counts and the module's runtime under `-n 4 --dist loadfile`.

**Files**: none

**Validation**: Named acceptance green.

### Subtask T056: Pin the sole legacy-shape literal of the drift reader (AC-VERSION, bullet 5)

**Purpose**: The literal `feature_slug` (the legacy-shape test of D-P7) is the one accepted occurrence of a retired term outside the scope of the terminology scan, and it must be pinned by a test with a planted second use that fails. WP06 cannot carry this (the reader module does not exist when WP06 runs, and `terminology_problems` reads only the contract YAML and the CHANGELOG entry), so the pin belongs to this work package, which owns the reader and its test module (operator ruling 12, `kitty-specs/mission-status-health-drift-ops-01M464D3/reviews/tasks.ruling.md`).

**Steps**:
1. In `tests/contract/test_mission_status_drift.py` add one pure test over the SOURCE of `tests/contract/_mission_status_drift.py` (parsed with `ast`, never imported): collect every string constant (docstrings included) and every identifier or attribute name containing `feature` (case-insensitive); exactly one is allowed, its value is exactly `feature_slug`, and it sits inside the legacy-shape function (named in the failure message, with the line). Assemble any planted text from fragments; do not type a second spelling of the retired term into the test.
2. Plants (each must fail): the same source with a second `feature_slug` constant appended; with a docstring that mentions it; with a `feature`-prefixed identifier. Controls: the real source passes; the real source with its single use removed fails with a different message (count zero), so the test sees both directions.
3. Placement: commit 1, beside the AC-DRIFT rows. Against the raising stub the count is zero, so it is a behaviour failure (red) until T037 writes the one literal, then green. It needs no registration of its own.

**Files**: tests/contract/test_mission_status_drift.py

**Validation**: Red on the stub (count zero), green after T037; the three plants each fail; the control passes.

## Validation: gates and targeted test surface (concrete; run from the lane workspace root)

Targeted files only, never a directory sweep. Use `PWHEADLESS=1` and the interpreter of the synced environment recorded at Step 0.

### Tool tests, example and proof modules

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/contract/test_leak_scan.py tests/contract/test_fixture_builder.py tests/contract/test_enum_pin_check.py tests/contract/test_run_negative_cases.py tests/contract/test_mission_status_examples.py tests/contract/test_mission_status_contract_1_1.py
```

The new module of this work package, run on its own after the red commit and on the tip:

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/contract/test_mission_status_drift.py
```

### The tool job's whole selection

The tool job's whole selection, as the router runs it (plan-time: 1,778 passed, 37 skipped in 176 s locally; re-take against the Step 0 record):

```text
PWHEADLESS=1 .venv/bin/python -m pytest -p no:cacheprovider -m "corpus and not windows_ci" tests/contract --ignore=tests/contract/test_example_round_trip.py --ignore=tests/contract/test_mission_status_payloads.py --ignore=tests/contract/test_mission_status_reality.py -n 4 --dist loadfile -q
```

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

Named files only, never the directory, never `tests/architectural` as a sweep for these commands (charter rule `NO_FULL_HEAVY_SUITES_IN_MISSION`; the one exception is the binding three-leg battery gate below, by operator ruling). The scans inspect real-git fixtures, a `subprocess` stub, a counting wrapper, git identity setup, any manual `os.chdir`, `os.environ` or `sys.path` change, a shared-temp literal and a wall-clock call in a test module: use `monkeypatch` and a scratch `HOME`, an injected clock, and build host-path-shaped plants from fragments. **No allowlist or baseline entry may be added to make a new module pass.** The two dead-symbol files walk `src/` (no `src/` change here) and run only in the Step 0 baseline.

### Registration of `test_mission_status_drift.py` (NEW test module)

**Registration pair, in the SAME commit that creates the module (and in sorted position; the registry gates must be green on every commit):**

1. `.github/workflows/packs.yml`: one `--deselect tests/contract/test_mission_status_drift.py` entry in the one-line `built-in-corpus-suite` command (it is one physical line; edit it in place, keep it one line, keep alphabetical position among the existing `--deselect tests/contract/...` entries).
2. `tests/architectural/test_ci_corpus_trigger_completeness.py`: one row `"tests/contract/test_mission_status_drift.py",` in the `_CORPUS_MARKED_MODULES` frozenset, in sorted position (the neighbouring detail-reader module is the pattern).
3. `pytestmark` of the module: ONE single-line list holding `pytest.mark.corpus`, exactly the form of `tests/contract/test_mission_status_detail.py`: `pytestmark = [pytest.mark.contract, pytest.mark.corpus, pytest.mark.git_repo]`. The registry gate's `_CORPUS_MARK_APPLICATION_RE` matches `pytestmark = ... pytest.mark.corpus` within one line only; a mark spelled through a shared list or wrapped across lines is reported as in the registry but not marked.
4. Router globs (the `contract_tools` group of `.github/workflows/ci-router.yml`): add the `**/<path>` entries for the `src/` files the new helper(s) import, spelled `**/specify_cli/...` / `**/kernel/...` so the group stays non-src, in sorted position, in the commit that FIRST adds an import of that `src/` file, never in a separate closing commit (the derivation test is in `tests/ci/test_contracts_workflows.py` and scans every `tests/contract/*mission_status*.py` file, stubs included, so it goes red the moment any such file imports a `src/` file the group does not yet name, and the 'registry gates green on every commit' rule then fails). The red-first commit carries the globs only if its test module or its stub imports a `src/` file (a stub that merely raises imports nothing and needs none); otherwise they land in the commit that gives the helper its real body, together with that import. The test `test_the_contract_tools_filter_group_names_every_src_file_the_mission_status_reader_and_its_tests_import` derives the required list from the imports and stays red until they are present; never write the list by hand, recompute it from that test's output. Expected new entries (recomputed by the test, not typed): `**/specify_cli/status/lifecycle.py`, `**/specify_cli/lanes/models.py`, `**/specify_cli/status/validate.py` (one-way drift check only), `**/specify_cli/git/remote_probes.py`, `**/specify_cli/core/paths.py` and the `__init__` files the import scan adds
5. Proof of selection: `.venv/bin/python -m pytest --collect-only -q -m "corpus and not windows_ci" tests/contract/test_mission_status_drift.py` collects the module; `.venv/bin/python -m pytest --collect-only -q -m "fast or unit" tests/contract/test_mission_status_drift.py` collects nothing (exit 5 and no test ids is the pass condition).
6. Editing `packs.yml` and the registry test selects the `architectural-heavy` battery on this PR (plan PD-2). The operator's ruling 14 makes the three battery legs a BINDING local gate for this work package: see the next section.

### **Architectural battery: BINDING local gate (operator ruling 14, `kitty-specs/mission-status-health-drift-ops-01M464D3/reviews/tasks.ruling.md`, 2026-10-06).** This work package edits registration files (`.github/workflows/packs.yml`, `tests/architectural/test_ci_corpus_trigger_completeness.py`, `.github/workflows/ci-router.yml`), which selects the architectural battery on the pull request. The operator requires the FULL architectural battery to be run locally on this work package, as on #5625 (the previous slice, `kitty-specs/mission-status-contract-1-1-01M42XJC/tracer-design-decisions.md`, section 'Operator request: local architectural battery runs'). This is a binding gate, not a conditional one and not dependent on the dispatch brief. **It overrides, for WP03, WP07 and WP08 only (and, by orchestrator note 17 of `reviews/tasks.ruling.md` extending ruling 14, for the orchestrator's Step 0 baseline run of the same three legs on the unchanged D-0 tip and its note 16 fallback run of them on a lane tip; the ruling's own text names only WP03, WP07 and WP08), the charter rule `NO_FULL_HEAVY_SUITES_IN_MISSION` and the plan's 'CI-owned, not run locally' default** (the ruling replaces that bar); everywhere else in this Mission the rule stands, and the named-files-only rule above still governs every other command of this work package.

**The three legs** are the jobs of `.github/workflows/ci-router.yml` as it runs them: `architectural-fast` (display name `architectural fast gates (ratchet/census, always-on)`, CI timeout 10 minutes) and `architectural-heavy` (one job key, a two-leg matrix, display name `architectural battery (heavy, code-scoped) 1/2` and `2/2`, CI timeout 30 minutes each). Common selection: the directory `tests/architectural`, the marker expression `-m "not performance and not stress and not timing"`, `-n 4 --dist loadfile`, and four `--deselect` entries for files other jobs own (`test_no_legacy_terminology.py` in the `terminology` job, `test_layer_rules.py` and `test_pyproject_shape.py` in the `layer-rules` job, `test_archive_root_byte_identical.py` in the `archive-freeze` job; those four run in this work package's named gate commands above, not in the legs). The shard split is the partition plugin `scripts/ci/battery_partition_plugin.py` (`-p scripts.ci.battery_partition_plugin --battery-part fast`, `1/2` or `2/2`): file-disjoint parts that together cover the base selection, proved statically by `tests/architectural/test_battery_partition_proof.py`. `uv run --frozen python` of the CI commands is replaced here by `<synced-python>`, the interpreter of the synced environment defined once in orchestrator Step 0 (item 2 of `tasks.md`, the `<scratch>/venv/bin/python` recorded in the Step 0 record; never the hand-built checkout `.venv/bin/python`, which lacks respx, and never a bare `uv run`). **Before the first leg**, from this lane workspace root, run `<synced-python> -c "import specify_cli; print(specify_cli.__file__)"`: the path must lie inside this lane workspace's `src/`; if it does not, put `PYTHONPATH=<lane workspace>/src` in front of every leg command and repeat the check (a leg that imported another tree proves nothing), and the junit files go to `<scratch>`, never into the workspace. Collection was checked on the planning base with exactly these commands (`--collect-only`): fast 34 files, 787 tests; heavy 1/2 106 files, 1,651 tests; heavy 2/2 106 files, 1,363 tests; counts move with the tree, so compare against the Step 0 record, not against these figures.

Leg 1, `architectural-fast`:

```text
PWHEADLESS=1 <synced-python> -m pytest tests/architectural \
  -m "not performance and not stress and not timing" \
  -n 4 --dist loadfile \
  --deselect tests/architectural/test_no_legacy_terminology.py \
  --deselect tests/architectural/test_layer_rules.py \
  --deselect tests/architectural/test_pyproject_shape.py \
  --deselect tests/architectural/test_archive_root_byte_identical.py \
  -p scripts.ci.battery_partition_plugin --battery-part fast \
  --junitxml=<scratch>/xunit-architectural-fast.xml
```

Leg 2, `architectural-heavy` shard `1/2` (label `1-of-2`):

```text
PWHEADLESS=1 <synced-python> -m pytest tests/architectural \
  -m "not performance and not stress and not timing" \
  -n 4 --dist loadfile \
  --deselect tests/architectural/test_no_legacy_terminology.py \
  --deselect tests/architectural/test_layer_rules.py \
  --deselect tests/architectural/test_pyproject_shape.py \
  --deselect tests/architectural/test_archive_root_byte_identical.py \
  -p scripts.ci.battery_partition_plugin --battery-part 1/2 \
  --junitxml=<scratch>/xunit-architectural-heavy-1-of-2.xml
```

Leg 3, `architectural-heavy` shard `2/2` (label `2-of-2`):

```text
PWHEADLESS=1 <synced-python> -m pytest tests/architectural \
  -m "not performance and not stress and not timing" \
  -n 4 --dist loadfile \
  --deselect tests/architectural/test_no_legacy_terminology.py \
  --deselect tests/architectural/test_layer_rules.py \
  --deselect tests/architectural/test_pyproject_shape.py \
  --deselect tests/architectural/test_archive_root_byte_identical.py \
  -p scripts.ci.battery_partition_plugin --battery-part 2/2 \
  --junitxml=<scratch>/xunit-architectural-heavy-2-of-2.xml
```

**How to run.** From the lane workspace root (the `-p scripts.ci.battery_partition_plugin` import fails elsewhere), on the final commit of the work package after the named gate files are green and before the approval request. Each leg runs as a **background command** with its output and exit code written to scratch files (a heavy shard can run up to the 30-minute CI budget): `nohup sh -c '<the leg command>; echo $? > <scratch>/leg-N.exit' > <scratch>/leg-N.log 2>&1 &` (with the Bash tool: `run_in_background`). Await each leg with **the harness's permitted wait primitive: a background command awaited with an until-loop monitor** (for example a monitor on `until [ -f <scratch>/leg-N.exit ]; do sleep 20; done`), **never a foreground `sleep` loop** (the harness refuses a foreground sleep, and a denied command means stop). A missing exit-code file means not finished, never a pass; a tool timeout is neither a pass nor a fail. Do not hand off before all three exit-code files exist. **Probe and fallback (orchestrator note 16 of `reviews/tasks.ruling.md`):** the orchestrator probes the primitive once at Step 0 and records `wait-primitive: permitted` or `wait-primitive: not permitted` in the Step 0 record. If the record says `not permitted`, or your first attempt to use the primitive is denied, STOP, do not run the legs and do not retry in another form: state in your hand-off that the three legs are left to the orchestrator, which runs the same three commands itself on your final commit before the review, binned the same way, and appends the result to your hand-off record; the reviewer reads the three exit-code files from there.

**Binning.** Bin every red of a leg against the orchestrator's Step 0 record in `tracer-approach.md`, which carries a per-leg baseline for each of the three legs (the latest `main` run conclusion and duration of each job, and the Step 0 local run of each leg on the unchanged base: counts and exit status). Only a red that is red on your branch and green on the base is yours. The previous slice met two environmental reds in heavy 1/2 on every run (the graph regeneration byte-identity test, which shells out to the user-level installed CLI, and the accept-stamp idempotency test, which resolves the placement port to a stray repository at the system temporary root); treat that as a hint for where to look, never as a pre-binned answer: the Step 0 record of this Mission decides. **Durations:** report the wall time of each leg beside the Step 0 local wall time of the same leg (same commands, same interpreter, no CI `collect_universe_prestep`); the main-CI durations are informational and carry no pass rule (orchestrator note 15, `reviews/tasks.ruling.md`), so a longer or shorter time is reported, not binned. A pre-existing red is reported in the hand-off (command, failure summary, why), never absorbed, and the leg is not retried to green. The hand-off carries, per leg, the command, the passed, failed and skipped counts, the exit status from the exit-code file, the junit path and the bins.

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

- The first commit holds the red tests and a raising stub.
- Every mutation of the catalogue is killed.
- The named census files and the registration gates run green; the named gate files of the quickstart.
- All AC-DRIFT rows below (row 19's corpus half is WP09's); AC-CROSS 1, 4, 5 drift parts (counts only; the timed 10,000-file case is WP08's).
- The reader-literal pin test of T056 passes and each planted second use fails (AC-VERSION, bullet 5).
- First commit is the red tests with a raising stub (behaviour failures, controls red), verified on the base; green on the tip.
- `test_mission_status_drift.py`: registration pair and single-line `pytestmark` in the module-creating commit; the router globs in the commit that first imports each `src/` file (the helper commit; the red-first commit only if its stub or test module imports `src/`); registry gates green on every commit; the router-glob derivation test confirmed green in T40, with no separate closing glob commit.
- The three architectural battery legs (`architectural-fast`, `architectural-heavy` 1/2 and 2/2) ran locally on the final commit, as the binding gate of operator ruling 14 requires: three exit-code files read, counts and exit status in the hand-off, every red binned against the Step 0 per-leg baselines. Under the note 16 fallback (the orchestrator ran the legs because the wait primitive was denied to the worker), this is met when the orchestrator ran the three legs and appended the three exit-code results to the hand-off record before review; the worker's hand-off then states that the legs are left to the orchestrator.
- Named gate files and census files green or binned against the Step 0 record; ruff check, ruff format --check and TID251 clean with no suppression added.
- Hand-off carries measured minima, margins and re-measurements; nothing written under `kitty-specs/`.
- Per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.
- Nothing pushed; no pull request; no tracker write.

## Risks

- The resolver (assumptions only, spec R-9); real-git fixtures; network (the offline fixture); the 500 line (D-P7); the size of the module (a split is allowed: same files, sequential).

## Reviewer Guidance

The reviewer is a separate role from the implementer. Review the diff of this work package against its owned files and its full targeted test surface, plus the named gate files and census files above; never a full sweep, except the three battery legs of the binding gate below (operator ruling 14 makes them binding for WP03, WP07 and WP08 only; every other work package keeps named files only).
- Verify red then green: the first commit is the red-first commit with a raising stub; the red run shows BEHAVIOUR failures, not collection errors; the control tests are red too; green on the tip.
- Re-run the named gate files and the census files; check baseline bins against the Step 0 record in `tracer-approach.md`; check the hand-off carries measured minima, margins and re-measurements.
- Check public hygiene: no absolute path, user name, address, credential or private detail in any added line or commit message; no leaking literal; no raw NUL byte.
- Check nothing under `kitty-specs/` was written and no file outside the owned list changed without a recorded rationale.
- Verify every mutation of the catalogue is killed, the registration pair is in the module-creating commit, each router glob is in the commit that first imports its `src/` file, and the module is selected by the router marker expression and not by the nightly's. Verify the hand-off carries the three battery legs (binding gate, operator ruling 14): command, counts, exit status from the exit-code files and bins against the Step 0 per-leg baselines; re-run a leg when the hand-off is thin, and treat a missing leg as a reason to reject (under the note 16 fallback the rejection applies after the orchestrator has appended the three exit-code results to the hand-off record; before that append, a hand-off that says the legs are left to the orchestrator is not rejected for it). Compare each leg with the Step 0 local run of the same leg, not with main-CI durations (informational only, orchestrator note 15).

## Wrap-up reference (orchestrator-owned, NOT part of this work package)

After every work package is approved the orchestrator runs W-1 (accept, local lane consolidation, registration and scope check over the real diff), W-2 (J-1 confirmation), W-3 (dev-assist cleanup), W-4 (issue-verdict evidence, aggregate adversarial squad, terminal #5776 verdict), W-5 (history compaction), W-6 (rebase onto upstream `main`) and W-7 (final evidence); then the draft pull request. You do none of this.

## Implementation command

`spec-kitty agent action implement WP07 --agent claude`
