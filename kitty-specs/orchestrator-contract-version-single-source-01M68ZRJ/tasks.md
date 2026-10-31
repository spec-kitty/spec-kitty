# Work Packages: Orchestrator contract version, one source of truth in tests

**Mission**: `orchestrator-contract-version-single-source-01M68ZRJ`
**Spec**: `kitty-specs/orchestrator-contract-version-single-source-01M68ZRJ/spec.md`
**Plan**: `kitty-specs/orchestrator-contract-version-single-source-01M68ZRJ/plan.md`
**Issue**: #6578

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** means the subtask can run in parallel with others in the same work package.
- Requirement refs use the mission's own IDs (`FR-###`, `NFR-###`, `C-###`, `SC-###`).

## Path Conventions

- Repository root is the project root (the checkout this mission runs in).
- Test paths are repo-root-relative: `tests/orchestrator_api/`, `tests/specify_cli/orchestrator_api/`.
- Mission artifacts live in `kitty-specs/orchestrator-contract-version-single-source-01M68ZRJ/`.

---

## Work Package WP01: The pin reads the constant, and a guard keeps it that way (Priority: P1) 🎯 MVP

**Goal**: The origin-freshness envelope tests compare against the exported `CONTRACT_VERSION`
instead of a literal, and a fast test in the canonical pin module fails when any other test module
spells a contract version.

**Independent Test**: `uv run --frozen python -m pytest
tests/specify_cli/orchestrator_api/test_contract_version.py tests/orchestrator_api/test_origin_freshness_envelopes.py -q`
— the guard is RED before the import change (recorded) and the whole selection passes after it.

**Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, C-001, C-002,
C-003, SC-001, SC-002, SC-003, SC-004

### Included Subtasks

- [T001] Write the guard test in `tests/specify_cli/orchestrator_api/test_contract_version.py`
  (fast, no fixture) scanning `tests/**/*.py` for a quoted semver on a line naming a contract
  version, allowing only that module's own file. Run it: it MUST fail naming
  `tests/orchestrator_api/test_origin_freshness_envelopes.py:29`. Record the output.
- [T002] Replace the literal: in `tests/orchestrator_api/test_origin_freshness_envelopes.py`, import
  `CONTRACT_VERSION` from `specify_cli.orchestrator_api.envelope`, delete `_CONTRACT_VERSION`, point
  the two assertions (lines 122, 176) at the constant, and drop the stale `(contract 1.11.0)` claim
  from the module docstring.
- [T003] Correct the canonical pin's prose: the docstring sentence claiming
  "``CONTRACT_VERSION`` is currently ``\"1.3.0\"``" must stop naming a current value the assertion
  contradicts; keep every superseded-historical entry.
- [T004] Prove non-vacuity and run the targeted suites: re-insert a literal in a scratch copy (or a
  temporary edit that is reverted) and show the guard fails naming it; then run the touched modules
  plus the three sibling envelope modules and record the results.

### Implementation Notes

- The guard's scan must not flag a module-constant interpolation
  (`f'CONTRACT_VERSION = "{envelope_module.CONTRACT_VERSION}"'`), the `CONTRACT_VERSION_MISMATCH`
  error code, or the `"api_version": "3.0.0"` payload in `test_fail_message_preserved.py:67`.
- Red-first order matters: T001 before T002, so the RED run is the positive control for the GREEN.
- Keep `src/` untouched. `CONTRACT_VERSION` stays `1.21.0`.
- The origin-freshness module is `integration` + `git_repo` (~150 s); run it once, not repeatedly.

### Parallel Opportunities

- T003 is independent of T002 (different file region of the same module as T001 — sequential to that
  one). T004 depends on T001–T003.

### Dependencies

- None. WP02 depends on this WP.

### Risks & Mitigations

- **Guard false positives**: match only a quoted `X.Y.Z` co-located with a contract-version token on
  one line; keep the allowlist to the single canonical file; assert the allowlist path exists.
- **Weakening instead of fixing**: deleting the two assertions would also turn the guard green. The
  review must confirm both `assert envelope["contract_version"] == CONTRACT_VERSION` lines still
  exist.
- **Mutation left behind**: if T004 edits a real file to prove the guard, `git diff` must be clean
  afterwards.

---

## Work Package WP02: Changelog entry (Priority: P1)

**Goal**: `docs/changelog/CHANGELOG.md` carries an `[Unreleased]` entry for #6578 in the repository's
enforced style.

**Independent Test**: Read the `[Unreleased]` section: the entry leads with a bold impact-first
sentence, carries `(#6578, CI)`, states **Before:** and **After:**, and is under 1,200 characters.

**Requirements**: FR-001, FR-002 (the entry must describe the shipped behaviour, not an intention)

### Included Subtasks

- [T005] Add the `[Unreleased]` entry under the same category heading the surrounding test-only
  entries use, referencing #6578 and the guard test by name.

### Implementation Notes

- Category headings are enforced by a changelog style guard; copy the heading used by neighbouring
  CI/test entries rather than inventing one.
- No docs page describes this pin, so no other doc needs updating; state that in the PR body.

### Dependencies

- Depends on WP01 (the entry names the guard that must exist).

### Risks & Mitigations

- **Stale wording**: if T002 lands differently from the plan, write the entry from the merged code,
  not from this plan.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02. WP01 is the MVP and the only behavioural change.
- **Parallelization**: none meaningful at two small work packages; WP02 is a few lines.
- **Lanes**: `single_branch` mission, so both work packages land on the mission branch in order.

## Requirements Coverage Summary

| Requirement | Work package |
|---|---|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01 |
| FR-005 | WP01 |
| NFR-001, NFR-002, NFR-003 | WP01 |
| C-001, C-002, C-003 | WP01 |
| SC-001, SC-002, SC-003, SC-004 | WP01 |

## Subtask Index (Reference)

| Subtask | Work package | Summary |
|---|---|---|
| T001 | WP01 | Red-first guard test in the canonical pin module |
| T002 | WP01 | Origin-freshness assertions read the exported constant |
| T003 | WP01 | Canonical pin prose states only what it owns |
| T004 | WP01 | Mutation proof + targeted suite runs |
| T005 | WP02 | `[Unreleased]` changelog entry for #6578 |
