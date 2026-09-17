---
work_package_id: WP04
title: Repair mission-type configuration failures, aliases and list defaults
dependencies:
- WP02
requirement_refs:
- C-001
- C-003
- C-004
- C-005
- C-006
- FR-002
- FR-003
- FR-005
- FR-007
- FR-008
- FR-010
- FR-011
- FR-012
- NFR-002
- NFR-003
- NFR-006
planning_base_branch: fix/cli-boundary-robustness
merge_target_branch: fix/cli-boundary-robustness
branch_strategy: Planning artifacts for this mission were generated on fix/cli-boundary-robustness. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/cli-boundary-robustness unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cli-boundary-robustness-01M2NQCB
base_commit: 25f33493ca755f339d90984a3dc91c93cae286f7
created_at: '2026-09-16T21:07:46.731911+00:00'
subtasks:
- T016
- T017
- T018
- T019
- T020
- T021
phase: Implementation
history:
- at: '2026-09-16T19:28:18Z'
  actor: codex:planner-priti
  action: Prompt generated via canonical tasks workflow
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/mission_type.py
create_intent:
- tests/specify_cli/cli/commands/test_cli_boundary_mission_types.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/mission_type.py
- src/specify_cli/cli/commands/charter/mission_type.py
- tests/specify_cli/cli/commands/test_cli_boundary_mission_types.py
- src/specify_cli/cli/commands/doctrine.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 — Repair mission-type configuration failures, aliases and list defaults

## ⚡ Do This First: Load Agent Profile

Use `/ad-hoc-profile-load` to load `python-pedro` before parsing the rest of this prompt.
Profile: `python-pedro`. Role: `implementer`. Agent/tool: `codex`.
The current CLI exposes profiles through `spec-kitty profiles show` and governed
work through `spec-kitty dispatch --profile`; use the installed canonical surface,
not the retired `ask` command. Read the project charter before changing code.

## Review Feedback

Read the current review reference from `spec-kitty agent tasks status` and the
event log. Address every returned blocker before resubmission. Never overwrite
a reviewer artifact or synthesize an approval. This prompt starts with no review.

## Objectives & Success Criteria

Required configuration failures become named command errors, the mission/mission-type/charter aliases respect activated-only defaults and doctrine preserves its full-roster success behavior, and mission-type JSON siblings share the canonical error contract.

Priority: P0. Requirement refs: FR-002, FR-003, FR-005, FR-007, FR-008, FR-010, FR-011, FR-012, NFR-002, NFR-003, NFR-006, C-001, C-003, C-004, C-005, C-006.

- #4600 Instance-2 requires its own @pytest.mark.regression: parseable but invalid charter config passed through mission list/mission-type list, triggering the actual existing_mission_types loader. No mock that bypasses configuration loading.
- Read failures at content-load name .kittify/config.yaml and the decode/domain error; no raw traceback. Import-time tolerance from WP01 does not satisfy this requirement.
- Fix #4598 by explicitly passing include_inactive=False at the delegating call site; do not coerce Typer sentinels in charter_mission_type_list.
- Test mission list, mission-type list and charter mission-type list for activated-only parity; supported --include-inactive on the canonical surface exposes the full roster. Separately test doctrine mission-type list: preserve its established full-roster membership and row schema (C6), while converging configuration/JSON error boundaries.
- Same-file --json paths include show, run, reopen and follow-up: missing root, unknown selectors/types and emitted failure envelopes must converge without altering success payloads or exit codes.

## Context & Constraints

Audience: software engineers implementing and independently reviewing this WP.
Read these canonical mission inputs before coding:

- `.kittify/charter/charter.md` and repository `AGENTS.md`.
- `../spec.md`: requirements, constraints, non-goals and ratified decisions.
- `../plan.md`: concern map, amendments A/B and dependency graph.
- `../data-model.md`, `../research.md` and `../quickstart.md`.
- `../contracts/json-envelope-contract.md` and `../contracts/enumeration-gate-contract.md`
  for the machine contract and bounded enumeration refinement.

The spec and contracts take precedence over suggestive line numbers in the plan.
No dependency, release-version, hosted API, tracker transport or schema change is
authorized. Keep `SPEC_KITTY_ENABLE_SAAS_SYNC` untouched: do not set, unset, or
override it. The root venv is warm; use direct binaries. A separate lane worktree
must verify its own environment before running tools; never assume a shared venv.

## Branch Strategy

- Planning base branch: `fix/cli-boundary-robustness`.
- Merge target branch: `fix/cli-boundary-robustness`.
- Strategy: computed execution lanes from `lanes.json`; consume the workspace
  returned by the CLI rather than constructing a worktree path.
- Dependencies: WP02. An approved dependency is sufficient; do not wait for done.
- WP01 is the independent P0 and is scheduled first; WP02 remains structurally independent.
- Claim with `spec-kitty agent action implement WP04 --mission cli-boundary-robustness-01M2NQCB --agent codex:<model>:python-pedro:implementer`.
- `spec-kitty next` controls sequencing; the orchestration agent owns scheduling.
- Local lane consolidation targets the topic branch. Publication is a PR to
  origin/main; neither this implementer nor the orchestrator publishes to main.

## Ownership & Safeguards

Only the frontmatter `owned_files` are assigned to this WP. Tests use distinct
new files to avoid parallel collisions. `create_intent` lists every planned new
literal path. No code-change WP owns `kitty-specs/` artifacts. Send tracer updates,
issue evidence and planning corrections to the orchestrator, who owns those writes.

A minimal out-of-map edit needs a recorded rationale and an overlap check with
the orchestrator before proceeding. Do not change a sibling WP file silently.
Do not rewrite a shared conftest, packaging config, or global lint suppression.
Keep successful payload shapes and non-JSON exit behavior stable.

## Subtasks & Detailed Guidance

### T016 — Commit configuration and alias reproductions

**Purpose:** Commit configuration and alias reproductions.

Build realistic partially activated, malformed-but-parseable and non-UTF-8 project fixtures. Pin #4600 I2, #4598 and #4601. Drive production commands and record red-on-base evidence separately from WP01, then commit tests first.

**Files:** the owned surface and dedicated test files listed in frontmatter.
**Sequence:** follows the preceding subtask; no implementation before the red-test commit.
**Validation:** preserve exact command, exit status, failing/passing node IDs and
the commit that establishes the result. A passing synthetic payload is insufficient.
**Review evidence:** state what pre-existing entry point reaches the changed
behavior and which negative case would fail if that behavior were removed.

### T017 — Scout and tidy the mission-type command boundary

**Purpose:** Scout and tidy the mission-type command boundary.

Dispatch a bounded campsite scout for the large mission_type.py surface under an appropriate loaded profile. Keep cleanup limited to owned changed methods, separately tested and committed; avoid unrelated command decomposition.

**Files:** the owned surface and dedicated test files listed in frontmatter.
**Sequence:** follows the preceding subtask; no implementation before the red-test commit.
**Validation:** preserve exact command, exit status, failing/passing node IDs and
the commit that establishes the result. A passing synthetic payload is insufficient.
**Review evidence:** state what pre-existing entry point reaches the changed
behavior and which negative case would fail if that behavior were removed.

### T018 — Translate configuration content-load errors

**Purpose:** Translate configuration content-load errors.

Move/cover existing_mission_types and other required config loads inside the relevant command-layer boundary. Catch the precise existing domain/decode errors and render an actionable file-naming message. JSON mode uses the WP02 envelope; human mode retains established semantics.

**Files:** the owned surface and dedicated test files listed in frontmatter.
**Sequence:** follows the preceding subtask; no implementation before the red-test commit.
**Validation:** preserve exact command, exit status, failing/passing node IDs and
the commit that establishes the result. A passing synthetic payload is insufficient.
**Review evidence:** state what pre-existing entry point reaches the changed
behavior and which negative case would fail if that behavior were removed.

### T019 — Correct activated-only delegation and alias parity

**Purpose:** Correct activated-only delegation and alias parity.

Pass explicit include_inactive=False at the wrapper. Test the three activated-only registration/delegation aliases against a real activation subset. doctrine.py::mission_type_list is a separate, intentionally full-roster implementation, not a delegating wrapper: preserve membership and successful row schema while adopting only the config/JSON error boundary. Ownership of doctrine.py is limited to this command and its directly needed local helper; unrelated doctrine subcommands remain deferred. Preserve explicit inactive discovery on its supported surface.

**Files:** the owned surface and dedicated test files listed in frontmatter.
**Sequence:** follows the preceding subtask; no implementation before the red-test commit.
**Validation:** preserve exact command, exit status, failing/passing node IDs and
the commit that establishes the result. A passing synthetic payload is insufficient.
**Review evidence:** state what pre-existing entry point reaches the changed
behavior and which negative case would fail if that behavior were removed.

### T020 — Adopt all mission-type JSON siblings

**Purpose:** Adopt all mission-type JSON siblings.

Enumerate every --json option in mission_type.py and charter/mission_type.py, plus the specifically adopted doctrine.py::mission_type_list command. Do not use the newly assigned doctrine.py path to widen scope into its unrelated subcommands. Opt callers into the root helper and replace same-file divergent errors, including selector errors, with the shared builder. Verify success paths and command-specific exit fidelity using safe fixtures for mutating commands.

**Files:** the owned surface and dedicated test files listed in frontmatter.
**Sequence:** follows the preceding subtask; no implementation before the red-test commit.
**Validation:** preserve exact command, exit status, failing/passing node IDs and
the commit that establishes the result. A passing synthetic payload is insufficient.
**Review evidence:** state what pre-existing entry point reaches the changed
behavior and which negative case would fail if that behavior were removed.

### T021 — Validate integration and hand off

**Purpose:** Validate integration and hand off.

Run mission-type/charter focused suites plus every owned regression. Confirm the red tests now pass through live registration, record independent red evidence for I2, and run lint/type/format and architectural seam checks.

**Files:** the owned surface and dedicated test files listed in frontmatter.
**Sequence:** follows the preceding subtask; no implementation before the red-test commit.
**Validation:** preserve exact command, exit status, failing/passing node IDs and
the commit that establishes the result. A passing synthetic payload is insufficient.
**Review evidence:** state what pre-existing entry point reaches the changed
behavior and which negative case would fail if that behavior were removed.

## Test Strategy

Tests are required by C-003 and the charter. Do not use production state or
credentials in fixtures. Preserve installed behavior through realistic temporary
git/config/mission fixtures. Explicitly select regression tests: make test-fast
excludes the regression marker and therefore cannot substitute for them.

Mandatory targeted command:

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_mission_type*.py tests/specify_cli/cli/commands/test_cli_boundary_mission_types.py tests/cli/test_mission_type_malformed_yaml_cli_boundary.py tests/charter/test_mission_type*.py tests/integration/test_mission_type_resolution_integration.py -q
```

Also run every test file that exercises a touched module and the full directory
of each owning subsystem per AGENTS.md. Discover callers/test ownership before
handoff and record any additions to the blast radius. The root orchestrator runs
the shared `make test-fast` baseline and whole-repo format gate on integration;
do not launch duplicate broad runs while parallel lanes are active.

New and changed Python must pass these direct-binary checks (substitute the
actual diff paths, including committed changes since the lane planning base):

```bash
.venv/bin/ruff check <changed-python-files>
.venv/bin/ruff format --check <changed-python-files>
.venv/bin/mypy --strict <changed-python-files>
```

Respect the repository mypy config; do not blanket-ignore diagnostics. If the
package-level quickstart check reports inherited errors, compare the same command
against the baseline and report exact provenance; fix new diagnostics. The final
integrated format check is `.venv/bin/ruff format --check .`. No whole-repo pytest
run or `make test-full`: CI owns the whole-repo suite. Architectural scope follows
the charter and the mission review policy, not arbitrary repeated full test runs.

## Risks & Mitigations

- Exit-code drift: compare identical conditions in human and JSON mode.
- False-positive coverage: use the registered production entry point and real
  fixture state; patch external side effects only, never the behavior under test.
- Stream masking: inspect stdout and stderr separately; combined output is only
  used for the negative traceback/placeholder assertion.
- Latent base failures: reproduce on the original base before attribution.
  Never retry-to-green or remove honest red-main reproduction coverage.
- Scope creep: preserve domain-matched cleanup only; record deferred issues and
  residual JSON convergence under https://github.com/spec-kitty/spec-kitty/issues/4664.

## Definition of Done

- Acceptance tests were committed before implementation and red evidence retained.
- All subtasks satisfy the declared requirements through live command paths.
- Tests cover success, relevant errors and empty data, with no hidden traceback.
- Focused tests, diff-scoped lint, format and strict type checks pass; inherited
  failures are explicitly separated with base evidence.
- No overlapping ownership, duplicate contract authority or unused new module.
- Implementer gives the orchestrator issue-to-test evidence, red/green commits,
  test counts and tracer notes; no premature fixed verdict for unfinished issues.
- Commit functional changes separately from the red tests and tidy-first cleanup.
- Record subtasks with the event-sourced CLI, not markdown checkboxes:
  `spec-kitty agent tasks mark-status T016 T017 T018 T019 T020 T021 --status done --mission cli-boundary-robustness-01M2NQCB`.
- Move WP04 to for_review using the runtime-generated handoff instruction;
  never self-approve or manually force done.

## Review Guidance

An independent reviewer checks the actual diff against this contract, the red-test
commit, and the recorded baseline. Verify each mapped FR and all applicable C/NFR
clauses, including forbidden behavior. Confirm live caller wiring and assert that
removing the implementation would break the claimed acceptance tests.

Reject undocumented envelope divergence, human text on JSON stdout, placeholder
leaks, swallowed config corruption at a required-content boundary, and weakened
test assertions. Changes to issue-matrix verdicts are the orchestrator’s work;
the reviewer supplies evidence rather than marking unrelated issues complete.

## Activity Log

- 2026-09-16T19:28:18Z – codex:planner-priti – Prompt authored from the mission contract; no implementation yet.

Status and subtask completion are event-sourced in `status.events.jsonl`.
Append later entries chronologically using actual UTC timestamps.
