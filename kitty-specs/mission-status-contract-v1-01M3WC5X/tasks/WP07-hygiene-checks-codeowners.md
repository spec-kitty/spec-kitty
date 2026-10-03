---
work_package_id: WP07
title: Hygiene checks, pin verifier and CODEOWNERS (IC-06)
dependencies:
- WP06
requirement_refs:
- FR-001
- FR-017
- FR-018
- FR-021
- FR-023
- FR-025
- NFR-003
- C-005
- SC-010
planning_base_branch: issue-5558-mission-status-contract-v1
merge_target_branch: issue-5558-mission-status-contract-v1
branch_strategy: Planning artifacts for this mission were generated on issue-5558-mission-status-contract-v1. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5558-mission-status-contract-v1 unless the human explicitly redirects the landing branch.
subtasks:
- T042
- T043
- T044
- T045
- T046
- T047
history: []
agent_profile: python-pedro
authoritative_surface: contracts/tools/
create_intent:
- contracts/tools/structure_check.py
- contracts/tools/codeowners_check.py
- contracts/tools/no_pytest_scan.py
- contracts/tools/verify_pins.py
- tests/contract/test_structure_check.py
- tests/contract/test_codeowners_check.py
- tests/contract/test_no_pytest_scan.py
- tests/contract/test_verify_pins.py
- .github/CODEOWNERS
execution_mode: code_change
model: sonnet
owned_files:
- contracts/tools/structure_check.py
- contracts/tools/codeowners_check.py
- contracts/tools/no_pytest_scan.py
- contracts/tools/verify_pins.py
- contracts/tools/fixtures/structure_check/**
- contracts/tools/fixtures/codeowners_check/**
- contracts/tools/fixtures/no_pytest_scan/**
- contracts/tools/fixtures/verify_pins/**
- tests/contract/test_structure_check.py
- tests/contract/test_codeowners_check.py
- tests/contract/test_no_pytest_scan.py
- tests/contract/test_verify_pins.py
- .github/CODEOWNERS
- .gitignore
- tests/architectural/test_ci_corpus_trigger_completeness.py
role: implementer
tags: []
tracker_refs: []
---

# WP07 - Hygiene checks, pin verifier and CODEOWNERS (IC-06)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Implement `structure_check.py`, `codeowners_check.py`, `no_pytest_scan.py` and `verify_pins.py` with planted fixtures and controls, add the new tracked `.github/CODEOWNERS`, and make it trackable through the two `.gitignore` lines.

## Context

- Plan concern **IC-06**. Follows WP06 in the single code lane (the plan allowed a parallel lane; see the lane model in WP01). Its files are disjoint from every other WP's apart from the registry file.
- **`.github/CODEOWNERS` is git-ignored today** (the `.github/*` rule ignores new files in that directory; verified with `git check-ignore -v`). A plain add would skip it and `codeowners_check` would pass on an untracked file. The `.gitignore` negation `!.github/CODEOWNERS` lands in the **same commit** as the file, together with the line `.gradle/` (Gradle's local cache; `build/` is already covered); this WP owns **both** `.gitignore` lines (the whole edit). Acceptance includes `git ls-files .github/CODEOWNERS` being non-empty and `git check-ignore .github/CODEOWNERS` printing nothing; `codeowners_check` exits 2 `NOT_TRACKED` for an ignored or untracked file in a git checkout.
- `.gitignore` is a shared repository file; **overlap check 2026-10-02: no open PR touches `.gitignore`**, `.github/CODEOWNERS` or `.github/workflows/` (#5540 and #5326 do not). Re-run at start.
- CODEOWNERS content (maintainer decision for this Mission): a rule for `contracts/` owned by `@stijn-dejongh` and `@MOES-Media`; the pattern must cover `contracts/mission-status/`. Review is advisory: nothing on GitHub enforces it today (charter), and the body of PR 3 says so (orchestrator, assembled in WP12's ledger).
- `verify_pins.py` is tested against **fixture manifests** under `contracts/tools/fixtures/verify_pins/`; it does **not** write `pins.json` (WP02 creates it, WP08 appends). It verifies the manifest, the `uses:` lines of the workflow files and the install form. Accepted Python install form is exactly the shared prelude (SHA-pinned `astral-sh/setup-uv`, `python-version: '3.12'`, `uv sync --frozen --no-install-project`); a bare `pip install` or an unfrozen sync is `UNPINNED_INSTALL`. Codes: `CHECKSUM_MISMATCH`, `CHECKSUM_MISSING`, `UNPINNED_USES`, `NOT_HTTPS`, `UNPINNED_INSTALL`, `PUBLICATION_DATE_MISSING`; counts `tools uses_lines downloads`; exit 2 `MANIFEST_EMPTY`, `ZERO_TOOLS_VERIFIED`, `ZERO_USES_LINES`. Checksum code carries `# noqa: TID251` with a file-integrity rationale.
- `structure_check.py`: README headings (one per required topic, see WP01's README skeleton list) and CHANGELOG headings (added, changed, removed, provisional, and a heading for the module's current `info.version`); codes `README_HEADING_MISSING`, `CHANGELOG_HEADING_MISSING`, `CHANGELOG_VERSION_HEADING_MISSING`; counts `readme_headings changelog_headings`; exit 2 `ZERO_HEADINGS`. Node-free (C-005): markdown lint of those files stays advisory; do not add a Node markdownlint step.
- `no_pytest_scan.py`: scans every script in `contracts/tools/` **including itself**; detects an import, a `python -m` invocation, a subprocess or shell string, or a `make` target that reaches pytest; builds its own search strings from fragments so it does not flag itself; count `scripts_scanned`; code `PYTEST_REFERENCE`; exit 2 `ZERO_SCRIPTS`. **Keep it last in this WP** so it covers all scripts present (a scan that ran before the other three exist would pass vacuously on them). It runs on every `contracts/**` edit through the workflow path filter (WP09 wires the job); the `tests/ci/` half of the guard is WP09's.
- Conventions: as in WP06 (bare scripts, stdlib plus locked dependencies, `--root`, `CONTRACT-CHECK <name>: <CODE>: <detail>`, `counts:`, exit 0/1/2, floors before properties, no import of pytest/`tests/`/`scripts.`).
- **Python hygiene and S-rules (binding for this WP)**: run `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .` before the final commit and record both results (NFR-007). `contracts/tools/*.py` are non-test code, so ruff's bandit rules (`S`) apply there in full: shell out only with argument lists and `shutil.which`-resolved binaries (S603, S607), call `urlopen` only after an explicit `https` scheme check (S310), and make any suppression a one-line `# noqa: S###` with a stated rationale, never a blanket one. Run `mypy --strict` locally over new modules as discipline (no CI job). In `tests/`, never import `datetime` and never call `datetime.now()` or `time.time()` (clock-ban gates, named below): compare ISO-8601 strings or use the kernel clock door.
- Registry rows: this WP owns `tests/architectural/test_ci_corpus_trigger_completeness.py` for one purpose, four sorted rows.
- Does not touch the migration chain, runtime-state schema, event contract or any shared CI gate other than `.gitignore`, the new `.github/CODEOWNERS` and the registry rows.
- Baseline from WP01's hand-off; red-first per script (C-010).

### Test surface, gates and baseline

- Targeted: `tests/contract/test_structure_check.py tests/contract/test_codeowners_check.py tests/contract/test_no_pytest_scan.py tests/contract/test_verify_pins.py`.
- Named gates: `tests/architectural/test_clock_import_ban.py tests/architectural/test_clock_call_ban.py`, `tests/architectural/test_ci_corpus_trigger_completeness.py`, `tests/architectural/test_workflow_coherence.py`. Plus `ruff check .` and `ruff format --check .`.
- Verify by command, record output: `git ls-files .github/CODEOWNERS`, `git check-ignore -v .github/CODEOWNERS` (must print nothing).

## Subtasks

### Subtask T042: `structure_check.py`

**Purpose**: FR-001 structural check and FR-024 current-version heading.
**Steps**: failing tests and fixtures first (README with a heading removed; CHANGELOG missing the current-version heading; zero headings read; clean control on the same root); implement with the README heading list defined as a constant in `structure_check.py`, **copied verbatim from the exact heading strings in WP01's T007 hand-off** (WP01's T007 list is the single authority: it includes every topic WP11 lists, among them the local validate-and-bundle command with its prerequisite, the `src/specify_cli/contracts/` collision note, the board-column mapping convention, the versioning rule, the residual-risk statement, the reader-author warning and the preview tag namespace). Add a test that plants the removal of each heading in turn and expects `README_HEADING_MISSING` each time.
**Files**: ~140 lines plus tests.
**Validation**: codes asserted; real `contracts/` run recorded (README skeleton passes; final text is WP11).

### Subtask T043: `verify_pins.py`

**Purpose**: FR-018, NFR-003.
**Steps**: planted: altered checksum, missing checksum, empty manifest, unpinned `uses:` (floating tag or branch), non-HTTPS URL, bare `pip install`, unfrozen sync, missing publication date; clean control exactly the shared prelude; implement reading `pins.json`-shaped manifests (`name`, `version`, `url`, `sha256`, `published`, `advisory_feed_checked`) and workflow text.
**Files**: ~220 lines plus tests and fixtures.
**Validation**: each code asserted; zero uses lines exits 2.

### Subtask T044: `.gitignore` allowlist and `.github/CODEOWNERS`

**Purpose**: FR-023 deliverability.
**Steps**: add `!.github/CODEOWNERS` and `.gradle/` to `.gitignore` (the first near the existing `.github/*` allowlist lines), create `.github/CODEOWNERS` with the `contracts/` rule and both handles, confirm `git check-ignore -v .github/CODEOWNERS` prints nothing and `git ls-files .github/CODEOWNERS` lists it after the commit. Land both in the same commit.
**Files**: `.gitignore` (+2 lines), `.github/CODEOWNERS` (new, ~5 lines).
**Validation**: the two commands recorded.

### Subtask T045: `codeowners_check.py`

**Purpose**: FR-023 check.
**Steps**: failing tests first: planted missing file, zero rules, missing handle, pattern not covering `contracts/mission-status/`, and an ignored or untracked file (a throw-away git repository whose ignore rules cover the path; exit 2 `NOT_TRACKED`); unit test asserting `git ls-files .github/CODEOWNERS` lists the real file; implement (`RULE_MISSING`, `HANDLE_MISSING`, `PATTERN_DOES_NOT_COVER_MODULE`; exit 2 `FILE_MISSING`, `ZERO_RULES`, `NOT_TRACKED`; count `rules`).
**Files**: ~110 lines plus tests.
**Validation**: real file passes.

### Subtask T046: `no_pytest_scan.py` (last)

**Purpose**: FR-017 no-pytest half.
**Steps**: failing tests with planted scripts (import, `python -m`, subprocess string, shell string, `make` target) and a clean control; a test that the scanner scans itself and every sibling and fails on zero; implement building search strings from fragments.
**Files**: ~120 lines plus tests.
**Validation**: run against the real `contracts/tools/` and record `scripts_scanned` (must equal the number of `.py` files at that moment).

### Subtask T047: Registry rows and final runs

**Purpose**: gates green.
**Steps**: append four sorted rows; run targeted tests, the gate files and ruff; record counts.
**Files**: `tests/architectural/test_ci_corpus_trigger_completeness.py` (+4 rows).
**Validation**: green.

## Definition of Done

- Four scripts with unit tests (planted plus clean control each, codes asserted, floors asserted), red first.
- `.github/CODEOWNERS` tracked (`git ls-files` non-empty, `git check-ignore` empty); `.gitignore` diff is exactly the two lines.
- `no_pytest_scan` covers all sibling scripts including itself.
- Registry rows appended in sorted order.
- `structure_check.py`'s heading constant equals WP01's T007 list entry for entry (the planted-removal test covers every heading).
- `ruff check .` and `ruff format --check .` clean; no S603, S607 or S310 finding left unjustified; the two clock-ban gate files green.
- Per-subtask completion recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Risks

- Committing CODEOWNERS without the allowlist line silently drops the file: same-commit rule above.
- `verify_pins` accepting an install form that is not the prelude: the clean control is exactly the prelude, planted forms must fail.
- `no_pytest_scan` flagging itself: fragments.

## Reviewer Guidance

Run the two git commands yourself. Check the planted forms fail by code and the control passes on the same root. Confirm the scan lists itself in its count. Confirm no Node tooling appears.

Implementation command: `spec-kitty agent action implement WP07 --agent claude`
