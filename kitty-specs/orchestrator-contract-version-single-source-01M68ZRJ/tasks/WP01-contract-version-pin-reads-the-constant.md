---
work_package_id: WP01
title: The contract-version pin reads the constant, and a guard keeps it that way
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Test remediation
history:
- at: '2026-10-31T12:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/orchestrator_api/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/orchestrator_api/test_origin_freshness_envelopes.py
- tests/specify_cli/orchestrator_api/test_contract_version.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – The contract-version pin reads the constant, and a guard keeps it that way

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or
any user-defined profile), and behave according to its guidance before parsing the rest of this
prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this
work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via
  `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your
  implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with
  `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

This is issue #6578. `tests/orchestrator_api/test_origin_freshness_envelopes.py` exists to prove that
`accept-mission` and `consolidate-mission` refuse on stale origin evidence. It also pinned the
envelope's `contract_version` to a **literal** (`_CONTRACT_VERSION = "1.21.0"`, line 29, compared at
lines 122 and 176). That literal has been hand-re-pinned eleven times (1.11.0 → 1.21.0); #6578 was
filed on the occasion it had been left one bump stale.

By the end of this work package:

1. The origin-freshness assertions compare the emitted envelope to
   `specify_cli.orchestrator_api.envelope.CONTRACT_VERSION` and the module declares no literal
   contract version (FR-001, SC-001).
2. A fast test in `tests/specify_cli/orchestrator_api/test_contract_version.py` fails, naming every
   `path:line`, when any test module outside that file spells a contract version; it is RED on the
   pre-fix tree and GREEN after (FR-002, FR-003, SC-002).
3. The canonical pin's module prose no longer claims a current version it does not assert (FR-004).
4. Both `assert envelope["contract_version"] == …` lines still exist (FR-005, C-002).
5. `src/` is untouched and `CONTRACT_VERSION` is still `"1.21.0"` (NFR-003, C-001).

## Context & Constraints

- Spec: `kitty-specs/orchestrator-contract-version-single-source-01M68ZRJ/spec.md`
- Plan: `kitty-specs/orchestrator-contract-version-single-source-01M68ZRJ/plan.md` (IC-01..IC-04)
- Research: `kitty-specs/orchestrator-contract-version-single-source-01M68ZRJ/research.md`
  (the eleven re-pins, the sibling precedent, the scan dry run)
- Charter: `.kittify/charter/charter.md` — single canonical authority; DIRECTIVE_041 (judge the
  test: a stale pin in a test that is not about pinning is stale → re-pin/replace, never weaken);
  DIRECTIVE_034 (red-first); DIRECTIVE_043 (a gate must be non-vacuous); DIRECTIVE_024 (locality).

**Sibling precedent — do not invent a new shape.** Three modules already import the constant:
`tests/agent/test_envelope_unit.py:34`, `tests/orchestrator_api/test_wp_lifecycle_structured_actor_6400.py:46,174`.
Converge on them.

**Do not** bump `CONTRACT_VERSION`, edit `envelope.py`, or touch any test module other than the two
owned files. A "fix" that deletes the assertion instead of re-sourcing it is a weakening, not a fix.

## Branch Strategy

- **Strategy**: single_branch mission (`meta.json` `topology: single_branch`, `target_branch: main`).
- **Planning base branch**: `main`
- **Merge target branch**: `main`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first: the guard test (no fix yet)

- **Purpose**: Close the drift class by detection. Without detection, fixing today's literal only
  moves the problem to the next contributor (the eleven re-pins are the measurement).
- **Steps**:
  1. Open `tests/specify_cli/orchestrator_api/test_contract_version.py`. It is already
     `pytestmark = [pytest.mark.fast]`, already imports `envelope as envelope_module`, and already
     reads `envelope.py`'s source with `inspect.getsource`, so the guard fits its purpose (this is
     the module that owns the canonical pin).
  2. Add a module constant naming the one file allowed to spell a version:
     the module's own filename, resolved from `__file__`, repo-root-relative (for example
     `"tests/specify_cli/orchestrator_api/test_contract_version.py"`, derived — do not hardcode a
     host-absolute path).
  3. Add a helper that walks `tests/**/*.py` from the repository root and yields `path:line` for a
     line that (a) names a contract version, case-insensitively — `contract_version` or
     `CONTRACT_VERSION` — and (b) contains a quoted `X.Y.Z` semver, for example with
     `re.compile(r"\d+\.\d+\.\d+")`. Parse the quoted literal so a comment or prose sentence is still
     caught only when it quotes a semver (line 22 of the canonical file is such a sentence and is
     allowed by the allowlist).
  4. Write **one** test that asserts the set of offending files is empty, with a failure message that
     lists every `path:line` and states the remedy: import `CONTRACT_VERSION` from
     `specify_cli.orchestrator_api.envelope` instead of spelling a version.
  5. Add two non-vacuity controls (DIRECTIVE_043 — a scan that always returns `[]` must not pass):
     - a synthesized offending line fed to the helper must be reported;
     - a **scanned-file floor**: assert the walk found at least 3,000 `.py` files under `tests/`, so a
       broken root or a moved tree fails instead of scanning nothing. This mirrors the existing
       `MIN_SCANNED_FILES` floor in `tests/architectural/test_no_assert_swallowed_by_own_handler.py`.
  6. Run it and **record the RED output**:
     ```bash
     uv run --frozen python -m pytest tests/specify_cli/orchestrator_api/test_contract_version.py -q
     ```
     It must fail naming `tests/orchestrator_api/test_origin_freshness_envelopes.py:29`
     (`_CONTRACT_VERSION = "1.21.0"`). Also record the measured runtime of the guard alone
     (`--durations=5`). The scan reads `tests/**/*.py` once (4,282 files, 69 MB): expect single-digit
     seconds on a loaded host, 0.4 s idle — the same order as the existing `tests/architectural/`
     source-scanning gates (NFR-001).
- **Files**: `tests/specify_cli/orchestrator_api/test_contract_version.py`
- **Parallel?**: No — T002 must not start before the RED run is recorded, or the proof is lost.
- **Notes**: The scan is `tests/**/*.py` only. `src/specify_cli/orchestrator_api/envelope.py`
  legitimately spells every historical version in its changelog comment block and is out of scope.
  Do not use `git grep`/`git ls-files` (the tree is not fully tracked); walk the filesystem.

### Subtask T002 – Green: the origin-freshness assertions read the constant

- **Purpose**: Remove the second source of truth (FR-001). After this, a `CONTRACT_VERSION` bump
  touches `envelope.py` only.
- **Steps**:
  1. In `tests/orchestrator_api/test_origin_freshness_envelopes.py`:
     - add `from specify_cli.orchestrator_api.envelope import CONTRACT_VERSION` to the import block
       (it already imports from `specify_cli.*`, so this is the established shape);
     - delete the `_CONTRACT_VERSION = "1.21.0"` line (line 29);
     - at line 122 (`test_accept_mission_refuses_stale_status_evidence`) and line 176
       (`test_consolidate_mission_refuses_stale_status_evidence`) replace
       `assert envelope["contract_version"] == _CONTRACT_VERSION` with
       `assert envelope["contract_version"] == CONTRACT_VERSION`.
  2. Update the module docstring: it ends "(contract 1.11.0)", a stale claim. Say instead that the
     envelope's `contract_version` is asserted against the module's exported `CONTRACT_VERSION`, and
     that the exact value is pinned in `tests/specify_cli/orchestrator_api/test_contract_version.py`.
  3. Do **not** delete the assertion: it still proves that a refusal envelope built by the real CLI
     subprocess (`tests/terminus/conftest.run_terminus`) carries the module constant rather than a
     hand-written literal (FR-005, C-002).
- **Files**: `tests/orchestrator_api/test_origin_freshness_envelopes.py`
- **Parallel?**: No.
- **Notes**: import order is ruff-enforced (`ruff check tests/orchestrator_api/test_origin_freshness_envelopes.py`).

### Subtask T003 – The canonical pin's prose stops claiming a stale current version

- **Purpose**: Same defect class in the file that owns the pin: no test reads prose, so a stale
  sentence there is unreachable drift (FR-004).
- **Steps**:
  1. In `tests/specify_cli/orchestrator_api/test_contract_version.py`, the docstring says
     "``CONTRACT_VERSION`` is currently ``\"1.3.0\"`` (envelope.py:28), so this test is authentically
     RED before this WP's change". The assertion now pins `1.21.0`, and `envelope.py`'s constant is
     at line 176, so both the value and the line number are wrong.
  2. Rewrite that sentence so it does not name a *current* value (for example: "this test pins the
     exact value of ``envelope.CONTRACT_VERSION``; it is the one place a literal belongs").
  3. Keep every superseded-historical entry (1.5.0 … 1.21.0): that narrative is the record of why
     each bump happened, and other missions rely on it.
- **Files**: `tests/specify_cli/orchestrator_api/test_contract_version.py`
- **Parallel?**: after T001 (same file).
- **Notes**: This is the Boy-Scout half of the change and must stay inside the two owned files
  (DIRECTIVE_024). Do not rewrite the whole docstring.

### Subtask T004 – Non-vacuity proof and the targeted suites

- **Purpose**: Prove the guard bites and that nothing else moved (SC-002, SC-004).
- **Steps**:
  1. **Mutation**: temporarily re-insert a literal (for example change one assertion in the
     origin-freshness module to `== "1.21.0"`), run the guard, confirm it fails naming that line,
     then revert and confirm `git diff` is clean of the mutation
     (`git diff --stat` shows only the intended T002 change).
  2. Run the touched modules and the siblings:
     ```bash
     uv run --frozen python -m pytest \
       tests/specify_cli/orchestrator_api/test_contract_version.py \
       tests/agent/test_envelope_unit.py \
       tests/orchestrator_api/test_wp_lifecycle_structured_actor_6400.py -q
     uv run --frozen python -m pytest tests/orchestrator_api/test_origin_freshness_envelopes.py -q
     ```
     The first selection is fast; the second takes roughly 150 s (13 tests, real git fixtures).
  3. Lint and type-check the touched files:
     ```bash
     uv run --frozen ruff check tests/orchestrator_api/test_origin_freshness_envelopes.py tests/specify_cli/orchestrator_api/test_contract_version.py
     ```
  4. Record all four results in the WP review cycle: the RED run from T001, the guard's runtime, the
     GREEN runs, and the mutation check.
- **Files**: none new (verification only).
- **Parallel?**: No — depends on T001–T003.
- **Notes**: If a sibling module is red for a reason unrelated to this diff, reproduce it on a
  pristine `origin/main` worktree before saying so, and cite it in the WP notes; never skip or xfail
  it.

## Test Strategy

- Red-first: T001's guard is the reproduction and it must fail before T002.
- The origin-freshness module is `integration` + `git_repo`; it is not part of a full-suite run
  (NO_FULL_HEAVY_SUITES_IN_MISSION). Run it exactly once per change.
- `NFR-001`: the guard must take under a second and use no fixture, no subprocess, no git.
- `NFR-002`: after T002 the scan reports exactly one file (the canonical pin module) and no
  offenders on today's tree.

## Risks & Mitigations

- **False positives in the scan** — keep the match narrow (a quoted `X.Y.Z` on a line that also names
  a contract version) and keep the allowlist to one derived path. Verify by running the guard over
  the whole `tests/` tree, not a subset.
- **The cheap cheat** — deleting the two assertions turns the guard green too. Review must see both
  `== CONTRACT_VERSION` lines present.
- **Mutation left behind** — re-revert and check `git diff` before committing.
- **Long integration run** — do not re-run it for cosmetic edits.

## Review Guidance

Reviewers must confirm, in this order:

1. The guard is genuinely RED on the pre-fix tree (the implementer records the output) and is not a
   scan that trivially returns `[]` — the synthesized-line self-check must be present.
2. Both `contract_version` assertions still exist and read `CONTRACT_VERSION`; none of the other
   assertions in those two tests changed.
3. `git diff` touches exactly two test files; `src/` is byte-identical; `CONTRACT_VERSION` is still
   `"1.21.0"`.
4. The allowlist is one file whose purpose is the pin, and the guard's failure message names
   `path:line` plus the remedy.
5. `ruff check` is clean on both touched files.

## Progress & Status

Progress, history, and status all live in the status event log (`status.events.jsonl`) — never in
this prompt file. Do **not** hand-edit a history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
