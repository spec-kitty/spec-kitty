---
work_package_id: WP01
title: Baseline and campsite (tidy-first)
dependencies: []
requirement_refs:
- NFR-006
- C-004
planning_base_branch: issue-5625-mission-status-contract-1-1
merge_target_branch: issue-5625-mission-status-contract-1-1
branch_strategy: Planning artifacts for this mission were generated on issue-5625-mission-status-contract-1-1. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5625-mission-status-contract-1-1 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-status-contract-1-1-01M42XJC
base_commit: aef7cc96777272e8d85c1608345ee56d1bbe8ce7
created_at: '2026-10-04T12:43:53.753282+00:00'
subtasks:
- T001
- T002
- T003
- T004
history: []
agent_profile: python-pedro
authoritative_surface: tests/contract/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/contract/_mission_status_payloads.py
- tests/contract/test_mission_status_reality.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP01 – Baseline and campsite (tidy-first)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Take the implement-start baseline for the whole Mission (gate commands, architectural files, latest `main` CI conclusions) and land the one distinct, behaviour-preserving opening commit: name the git repository setup once in the reality check (plan section Campsite-clean (g)), or record that no domain-matched debt was found.

## Context

Charter Standing Order 2 (campsite first, tidy-first): the surfaces a Mission will change are cleaned in a distinct preceding commit. `tests/contract/test_mission_status_reality.py` is edited again by WP05, WP06 and WP08 and `_mission_status_payloads.py` by WP05 and WP08, so this WP finishes before any of them starts. It is the one real parallel window of the Mission: WP01 runs beside WP02 (no shared file). The baseline record is the Pre-existing Failure Reporting input for the whole Mission (plan section Baseline (f), research R-11, R-13). Nothing under `kitty-specs/` is written by this WP: the baseline record goes into the hand-off report and the orchestrator appends it add-only to `tracer-approach.md`.

Decisions honoured: none of the spec's CL, AD, AC, OQ or OD rows is mapped to this work package (spec.md remains reference material).

Plan concern: IC-01 (plan section Implementation Concern Map). Requirement refs: NFR-006, C-004. Dependencies: none. Branch contract: planning base and merge target are `issue-5625-mission-status-contract-1-1`; work runs in the lane workspace `spec-kitty agent action implement` resolves for you (never reconstruct a path by hand).

## Owned files (write scope)

Edit only these paths (declared shared-file exceptions are dependency chains, never concurrent; plan section Lanes):

- `tests/contract/_mission_status_payloads.py`
- `tests/contract/test_mission_status_reality.py`

Nothing under `kitty-specs/` is written by this work package: records you must make (a contract-note refinement, a decision, a friction observation, the baseline) go into your hand-off report; the orchestrator appends them add-only to the tracer files. A small, well-justified out-of-map edit is acceptable only with a one-line rationale in the hand-off report; the no-overlap rule is the real guard against collisions.

### Subtask T001: Take the implement-start baseline and record it for the orchestrator

**Purpose**: Record what is green and what is red on the unchanged base before any edit, so every later red is binned against it.

**Steps**:

1. Re-sync with the planning base branch, record the base commit hash (`git rev-parse HEAD`).
2. Run, unchanged, every command of the plan's gate set (plan section The gate set (e); quickstart sections Named gate files and Architectural files that read `tests/`): the nine router and registry gate files, the eight architectural-fast files, the two layer-rules files, `ruff check .`, `ruff format --check .`, `ruff check --select TID251 .`, `spec-kitty cutover-guard --base-ref origin/main`, the tool-job selection (command in the validation section below, labelled Tool-job selection) and the reality and payload modules (commands in the validation section below).
3. Record the latest `main` runs of the `architectural-fast` and `architectural-heavy` jobs of `ci-router.yml` (job conclusions and durations, as research R-13 did) with `gh run list` and `gh run view` (read-only calls only; no comment, no write).
4. Count the campsite literal again: occurrences of the scratch-repository init statement in `tests/contract/test_mission_status_reality.py` and call sites of `_commit_all`.
5. Bin every red you meet (pre-existing known-P0, CI environment, stale install, stale venv, or introduced; see the baseline rule below). Pre-existing red: stop and report it, do not continue past it unreported.
6. Record the planning-base commit and the counts as the Mission baseline table of the hand-off report. The orchestrator appends that table add-only to `tracer-approach.md` (the one source later work packages compare against) before it dispatches WP03; WP02 runs beside WP01 on a lane that forks from the same planning-base commit and records its own pre-change counts for the same command list.

**Files**: No file is written by this subtask.

**Validation**: The hand-off report holds the base commit, each command with its pass or fail counts, the two CI job records and the literal count.

### Subtask T002: Hoist git_init and commit_all into the payload helper, replace the eight call sites

**Purpose**: Remove the counted duplicate in the file about to change, as a distinct tidy-first commit.

**Steps**:

1. Only if the re-count of T001 is three or more (the drop rule below applies otherwise).
2. Add `git_init(repo)` and `commit_all(repo)` to `tests/contract/_mission_status_payloads.py` (the shared helper the new reader tests import). `git_init` replaces the literal pair `"init"`, `"-q"`; `commit_all` is the existing `_commit_all` definition moved, unchanged in behaviour.
3. Replace the six init statements (five tests and the shared fixture; they differ in form: a `git -C <path>` prefix list, the same prefix spelled inline with `tmp_path`, and one with a `root` variable) and the two `_commit_all` call sites in `tests/contract/test_mission_status_reality.py`. Nothing else is tidied.
4. One commit, message `refactor(tests): name the git repository setup once in the reality check (#5625)`. This commit is behaviour-preserving and is the declared exception to the red-first rule (plan Charter Check, ATDD row).

**Files**: `tests/contract/_mission_status_payloads.py` (about 15 lines added), `tests/contract/test_mission_status_reality.py` (eight call sites).

**Validation**: T003.

### Subtask T003: Prove the commit is behaviour-preserving, or record the drop rule

**Purpose**: Prove the refactor changes no behaviour.

**Steps**:

1. Run `tests/contract/test_mission_status_reality.py` (marker expression `corpus and not windows_ci`) and `tests/contract/test_mission_status_payloads.py` before and after: the same test ids pass with identical counts (577 passed and 157 passed at the plan fix; the T001 run is the comparison).
2. Check that no assertion changed: `git diff` of the commit shows only the hoisted helpers and the replaced call sites.
3. Drop rule: when the T001 re-count is below three, make no commit; say so in the hand-off report as "no domain-matched debt found in the edit surface".
4. Run the architectural-fast files named below (the helper now holds `git` subprocess calls in one place; the global-state and home-pin scans must stay green) and ruff on the two files.

**Files**: None.

**Validation**: Identical counts before and after; named gates green; ruff clean for both files.

### Subtask T004: Campsite verdict in the hand-off report (no separate deliverable)

**Purpose**: Carry the campsite verdict in the common hand-off report. T004 has no deliverable of its own beyond that report (the report section below already requires everything it lists); the id is kept because the work package's subtask list names it, and it is marked done together with T003.

**Steps**:

1. In the hand-off report (section Hand-off report below) state the campsite verdict: the commit hash, or the drop sentence.

**Files**: None (the report is your final message, not a file).

**Validation**: The orchestrator can append the baseline table and the verdict to `tracer-approach.md` without further questions.

## Validation: gates and targeted test surface

Charter: no full `tests/architectural/`, end-to-end, performance or `make test-full` sweep in mission work (`NO_FULL_HEAVY_SUITES_IN_MISSION`); run exactly the commands below, record each command and its passed/failed counts in the hand-off report. Use the checkout's own environment (`.venv/bin/...`), never a bare `uv run`. `<scratch>` means a scratch directory outside the repository.

**Targeted test surface of this work package**:

- `PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider -m "corpus and not windows_ci" tests/contract/test_mission_status_reality.py tests/contract/test_mission_status_payloads.py` (identical counts before and after the commit).

**Tool-job selection (the whole `tests/contract` corpus selection; the router job `tests (contract tools)`, step `Run the contract tool unit tests` of `.github/workflows/ci-router.yml`).** This is the job that runs the new test modules and every neighbour of the contract files this Mission changes, so it is part of the targeted surface (a directory-scoped contract run, not an architectural sweep). Verbatim from the workflow (CI-owned form):

```text
uv run --frozen --no-sync pytest -m "corpus and not windows_ci" tests/contract \
  --ignore=tests/contract/test_example_round_trip.py \
  --ignore=tests/contract/test_mission_status_payloads.py \
  --ignore=tests/contract/test_mission_status_reality.py \
  -n 4 --dist loadfile
```

Runnable as written here (the checkout's interpreter, no `uv run`; the same arguments):

```text
PWHEADLESS=1 .venv/bin/python -m pytest -p no:cacheprovider -m "corpus and not windows_ci" tests/contract \
  --ignore=tests/contract/test_example_round_trip.py \
  --ignore=tests/contract/test_mission_status_payloads.py \
  --ignore=tests/contract/test_mission_status_reality.py \
  -n 4 --dist loadfile -q
```

Record the passed and skipped counts in the hand-off report and compare them with the Mission baseline (1,016 passed and 37 skipped at the plan fix; the WP01 T001 table in `tracer-approach.md` is the authoritative comparison, and the counts rise by the tests this Mission adds).

**Gates every code work package passes before hand-off** (baselines at the plan fix: 368 passed and 1 skipped; 171 passed; 83 passed; ruff clean; TID251 clean):

1. Router, registry and hygiene gate files, ruff and cutover guard:

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/ci/test_contracts_workflows.py tests/ci/test_contracts_routing.py tests/ci/test_corpus_blocking_home.py \
  tests/architectural/test_ci_corpus_trigger_completeness.py tests/architectural/test_same_tier_uniqueness.py \
  tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_module_shard_registry.py \
  tests/architectural/test_workflow_coherence.py tests/architectural/test_no_legacy_terminology.py
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/spec-kitty cutover-guard --base-ref origin/main
```

2. Architectural files that census `tests/` (real-git fixtures, worktrees, git identity setup, `os.chdir`/`os.environ`/`sys.path` changes in a new test module are what they inspect; no allowlist or baseline entry may be added to make a module pass: use `monkeypatch` and a scratch HOME). Run after every new or edited test module:

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/architectural/test_no_manual_global_state_mutation.py tests/architectural/test_global_state_allowlist_sealed.py \
  tests/architectural/test_spec_kitty_home_pin_census.py tests/architectural/test_spec_kitty_home_pin_guard.py \
  tests/architectural/test_spec_kitty_home_pin_budget.py tests/architectural/test_home_pin_gate_verdict.py \
  tests/architectural/test_no_dead_symbols.py tests/architectural/test_dead_symbol_allowlist_contract.py
```

3. Layer rules and import boundaries:

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/architectural/test_layer_rules.py tests/architectural/test_pyproject_shape.py
.venv/bin/ruff check --select TID251 .
```

4. Per-file format check where useful: `.venv/bin/ruff format --check --force-exclude <files>`.

## Red-first rule (C-011, charter ATDD-First Discipline)

**This work package is exempt from the red-first rule** (a behaviour-preserving campsite commit, the declared exception; the drop rule applies when the re-count is below three). The rule below applies to every other work package and is kept so the exemption is read against it. The FIRST commit of a work package is its failing test or planted fixture, red on the planning base (the lane's base before your first commit), committed BEFORE any implementation commit. Verify the red and record the failing test ids and the reason in the hand-off report: run the test file against the base by extracting the base into a scratch directory (`git archive <base-commit> | tar -x -C <scratch>/base`, copy the new test file in, run pytest from that directory with the checkout's interpreter); do not use `git stash`. The reviewer verifies red then green: red on the planning base AND green on the final commit. Declared exceptions are named in the subtasks (the behaviour-preserving campsite commit, the three regression-control leak kinds, the old-kind digest test). Never weaken, skip or retry-to-green a test to pass.

## Baseline rule: pre-existing red versus introduced red

Before your first change, run this work package's targeted commands once on the unchanged lane base. Any red is binned before work continues: (1) pre-existing known-P0 red on `main` (leave it red, never green-wash), (2) CI-environment failure (auth, opt-out variables; passes locally), (3) stale install, (4) stale venv (re-run `uv sync --frozen --all-extras`, then retry), or (5) introduced by you. Only a red that is red on your branch AND green on the base is yours to fix. A pre-existing red: STOP and report to the orchestrator in your hand-off (command, failure summary, why you believe it is pre-existing); the orchestrator owns the tracker issue (Pre-existing Failure Reporting Rule). Do not open an issue or post a comment yourself, do not absorb it, do not retry until green.

## Git, commits and public-repo hygiene

- **Commit locally. NEVER push, never open a pull request, never comment on an issue, never merge.** One pull request per Mission is opened by the orchestrator after the wrap-up sequence.
- Conventional commit subjects ending with `(#5625)`; end each commit message with the attribution trailers the orchestrator supplies. Commit through `spec-kitty safe-commit` where a guarded branch requires it; never bypass a guard with raw git or an environment override.
- **This repository is PUBLIC**: everything you write ships visibly and permanently. No absolute path under a home directory and no drive path, no user name, no e-mail address, no private reference, no credential in any file, test, fixture, commit message or report. Use repo-relative paths and placeholders such as `<repo>`, `<scratch>`, `<user>`. A username-leak is folded before anything leaves the machine; report any you find.
- Leaking values a test needs (host paths, addresses, tokens, an at-sign file name) are assembled from fragments at run time and never typed as literals. Editing tools decode a unicode escape typed into a file into the raw character: write NUL as `chr(0)` and backslash as `chr(92)` in tests, use the hex escape in contract patterns, and check every new file for raw NUL bytes.
- Terminology: Mission, never feature; say which sense of lane (status lane versus code lane); no `--feature` flag text. New code passes `ruff check` and `ruff format --check` with no suppression added; complexity ceiling 15; literals used three or more times in a module become constants.
- `kitty-specs/` is archive-frozen on `main`: this Mission's own files are add-only on the branch. Never hand-edit `meta.json`, `status.events.jsonl`, `lanes.json` or work package frontmatter; never call `materialize`. Never run a pattern kill (`pkill`/`killall`), `git stash`, or `rm` with a variable glob.
- **Subagents dispatch nothing**: you work alone; do not start, fork or brief other agents. A denied command means STOP and report it; never retry a denied command.

## Hand-off report (your final message)

Commits (hash and subject; at most the one campsite commit, which is exempt from red-first, or the drop sentence), the Mission baseline table (planning-base commit, every command with passed/failed counts, the tool-job counts, the two CI job records, the literal re-count), every command run with passed/failed counts, baseline bins, any refinement of a contract note or design decision, any friction observation (for `tracer-tooling-friction.md`), anything not done and why. The orchestrator records decisions and friction add-only; you do not write them under `kitty-specs/`.

## Definition of Done

- T001 baseline recorded in the hand-off report (base commit, every gate command with counts, the two CI job records, the re-count).
- Either exactly one commit `refactor(tests): ... (#5625)` that is behaviour-preserving, or the drop sentence.
- Identical test ids and counts before and after; named gates and ruff green.
- Write scope respected: two files, nothing under `kitty-specs/`.
- Per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.
- Dispatch gate (orchestrator): WP03 is not dispatched until the T001 baseline table is appended add-only to `tracer-approach.md`; every later work package compares against it.
- Nothing pushed; no pull request; no tracker write.

## Risks

- The hoisted helper changes a `git` argument by accident: compare argument lists before and after.
- A pre-existing red is absorbed silently: bin and report it first.

## Reviewer Guidance

The reviewer is a separate role from the implementer. Review the diff of this work package against its owned files and its full targeted test surface (every file the change touches), plus the specific named architectural gate files it implicates; never a full sweep.

- Confirm the diff is only the hoist and the eight replaced call sites (no new assertion, no new test).
- Confirm the counts equal the T001 baseline and the commit is a separate commit (not folded into a later WP).
- Red-first does not apply to this WP (behaviour-preserving, declared exception); verify the drop rule if no commit exists.
- Verify that the single commit is behaviour-preserving (same test ids, same counts as the T001 baseline) or that the drop sentence is justified; check the baseline bins in the hand-off.
- Check public hygiene: no absolute path, user name, address, credential or private detail in any added line or commit message; no leaking literal.

## Wrap-up reference (orchestrator-owned, NOT part of this work package)

After every work package is approved the orchestrator runs plan steps W-1 to W-7 in this order: W-1 accept, then lane consolidation (`spec-kitty consolidate`, strategy `rebase` recommended), then registration and wiring check, scripted scope check and issue-matrix rows; W-2 JVM shake-out; W-3 dev-assist cleanup; W-4 aggregate adversarial squad (report-only, pre-rebase tree); W-5 history compaction; W-6 rebase onto upstream including the 1.0.0 release commit; W-7 final evidence. Only then is the draft pull request opened, and it needs the `contract-mission-status-v1.0.0` tag. Evidence recorded earlier is labelled pre-tag or pre-rebase. You do none of this.

## Implementation command

`spec-kitty agent action implement WP01 --agent claude`
