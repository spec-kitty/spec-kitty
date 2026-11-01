# Implementation Plan: Clear the two pre-existing contract-guard reds (#6997)

**Branch**: `issue-6997-red-main-guard-subjects` | **Date**: 2026-11-01 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/red-main-guard-subjects-01M6BTZS/spec.md`

**Note**: This plan was authored for a `software-dev` mission via `spec-kitty agent
mission setup-plan`; the workflow reference is
`packs/built-in/missions/mission-steps/software-dev/plan/prompt.md`.

## Summary

Two guards under `tests/contract/` are red on `origin/main` @ `287a226cfe` because
their subjects drifted, not because the guards are wrong:

1. `docs/development/how-to/unclog-ci.md:95` still carries the deprecated
   main-centric phrasing ``merge to `main` `` that the branch-intent terminology
   guard exists to retire from live docs.
2. `SAFE_COMMIT_DIRECTORY_ARGUMENT` — the `error_code` of
   `SafeCommitDirectoryArgument`, shipped with the #6750 fix — is emitted by
   `specify_cli.git.commit_helpers` but is missing from
   `orchestrator_api.allowed_error_codes` in both copies of the vendored contract,
   and from the two prose enumerations that mirror it.

The technical approach is the one the last registration (#5443, commit
`46f37835ca`) used, applied to one code: correct the doc sentence, register the
code on the four surfaces, and pin the specific code by name in the contract test's
assertion list without touching the guard's walk. No guard's patterns, scope,
severity or invocation changes.

## Technical Context

**Language/Version**: Python 3.11 (the repository's `requires-python` floor; `uv`
managed venv)
**Primary Dependencies**: `pytest` (contract suite), `typer` (the CLI surface the
contract describes); no dependency is added, upgraded or removed by this mission
**Storage**: N/A — the "data" is two JSON contract documents and Markdown pages in
the repository
**Testing**: `pytest` — the two failing contract guards are the red-first proof;
`tests/contract` (terminology guard + orchestrator-api contract tests),
`tests/specify_cli/core/test_contract_gate.py` (vendored/planning-artifact equality)
and `tests/docs/` (docs freshness) form the targeted set
**Target Platform**: Linux/macOS/Windows developer and CI checkouts of this
repository (CI runs Linux; `ci-windows` runs the same contract shards)
**Project Type**: single project (the CLI package `src/specify_cli` plus its docs and
doctrine trees)
**Performance Goals**: N/A — no runtime path changes; the contract test's existing
code walk is unchanged in cost
**Constraints**: the contract test walks every `SafeCommitError` descendant and
asserts `emitted <= allowed_error_codes`; both contract copies must stay
byte-identical (a parsed-JSON equality gate enforces it); the mission-064 archive
copy of the shape is byte-frozen (SK-154) and must not be edited
**Scale/Scope**: 1 doc sentence; 1 code added to 2 JSON documents and 2 Markdown
enumerations; 1 changelog entry; 1 named assertion added to an existing test

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — PASS: the contract's `allowed_error_codes` in
  `src/specify_cli/core/upstream_contract.json` stays the one machine-readable
  authority; the pinned `docs/contracts/` copy is its enforced mirror, and the two
  prose surfaces are enumerations of it, not new sources.
- **Terminology adherence / Branch-Intent Terminology Governance** — PASS: the fix
  removes deprecated main-centric wording rather than exempting it; the charter's
  rule that `main` is a branch, not a synonym for "the repository root checkout", is
  what the reworded sentence must respect.
- **ATDD-First Discipline / red-first** — PASS: both failures reproduce on the base
  commit through the pre-existing entry point (`pytest`, unmodified test ids) before
  any edit; each fix half is reverted to confirm the corresponding guard goes red.
- **Locality of change / smallest viable diff** — PASS: no refactor, no formatting
  sweep, no CI-configuration change; the docs line stays inside its existing wrap.
- **Architectural gate discipline** — PASS: no allowlist is loosened; the only
  test-side edit *adds* a named code to an explicit assertion list (the #5443
  precedent), which strengthens the pin.
- **NO_FULL_HEAVY_SUITES_IN_MISSION** — PASS: targeted shards only; CI owns the
  full sweep.
- **Supply chain (DIRECTIVE_051)** — N/A: no dependency changes.
- **Frozen surfaces (ADR D-9)** — PASS: nothing under `services/` or the frozen set
  is touched.

## Project Structure

### Documentation (this mission)

```
kitty-specs/red-main-guard-subjects-01M6BTZS/
├── plan.md              # This file
├── research.md          # Discovery/Phase 0 findings (reproduction, precedent, decisions)
├── spec.md              # Mission specification
├── checklists/
│   └── requirements.md  # Spec-quality checklist
├── decisions/           # Decision-moment records minted by the runtime
├── tasks.md             # Phase 2 output (`/spec-kitty.tasks`) — NOT created here
└── traces/              # Mission tracer files (approach, design-decisions, tooling-friction)
```

### Source Code (repository root)

```
docs/
├── development/how-to/unclog-ci.md          # FR-001: the reworded sentence
├── contracts/upstream-3.0.0-shape.json      # FR-003: pinned contract mirror
├── api/orchestrator-api.md                  # FR-004: prose error-code list
└── changelog/unreleased/6997.fixed.md       # FR-006: the per-PR changelog fragment
src/
├── specify_cli/core/upstream_contract.json  # FR-002: allowed_error_codes
└── charter/offering/skills/
    └── spec-kitty-orchestrator-api-operator/
        └── references/orchestrator-api-contract.md   # FR-004: skill table
tests/
└── contract/test_orchestrator_api.py        # FR-005: name the code in the existing list
docs/changelog/unreleased/6997.fixed.md      # FR-006: the fragment the release assembles
```

**Structure Decision**: single project — the change lands entirely inside the
repository's existing documentation, contract-data and contract-test trees; no new
module, package or directory is introduced.

## Complexity Tracking

No charter-check violations. Nothing to justify.

## Implementation Concern Map

### IC-01 — The live doc page's branch-intent wording

- **Purpose**: Remove the last deprecated main-centric phrasing from a live
  first-party doc page without losing the fact the sentence states, so the
  branch-intent terminology guard is green on an unedited guard.
- **Relevant requirements**: FR-001, SC-001, SC-002, NFR-001
- **Affected surfaces**: `docs/development/how-to/unclog-ci.md` (the "Why each step
  works" / "Why the queue clogs" bullet at line 92-95)
- **Sequencing/depends-on**: none
- **Risks**: a rewrite that only swaps a synonym for the forbidden phrase would be a
  grep dodge rather than a fix. The sentence must keep the causal claim (a PR
  landing causes a new CI wave) while dropping the instruction-shaped wording; the
  surrounding sentences already name `main` as the trunk that moves, so the
  reworded sentence does not need to repeat it.

### IC-02 — The orchestrator contract's safe-commit error-code set

- **Purpose**: Make `orchestrator_api.allowed_error_codes` admit every code the
  safe-commit path can emit, keep the two contract copies identical, and keep the
  prose enumerations in step with them.
- **Relevant requirements**: FR-002, FR-003, FR-004, FR-005, FR-006, SC-001,
  SC-003, SC-004, NFR-002
- **Affected surfaces**: `src/specify_cli/core/upstream_contract.json`,
  `docs/contracts/upstream-3.0.0-shape.json`, `docs/api/orchestrator-api.md`,
  `src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md`,
  `src/specify_cli/orchestrator_api/envelope.py` (the contract version constant and its
  ledger comment), `tests/contract/test_orchestrator_api.py`,
  `tests/specify_cli/orchestrator_api/test_contract_version.py`,
  `tests/orchestrator_api/test_origin_freshness_envelopes.py`, and the per-PR changelog
  fragment `docs/changelog/unreleased/6997.fixed.md`
- **Sequencing/depends-on**: none (independent of IC-01)
- **Risks**: the code is a *pre-mutation* refusal, so it must not be documented as a
  `SAFE_COMMIT_RECOVERY_FAILED` refinement (that family means the commit may have
  landed). The two JSON copies must change together or the equality gate fails.
  Editing a file under `src/charter/offering/skills/` must not be mistaken for
  editing the fetched `packs/` tree — the pack trees are generated and are not
  touched here.
