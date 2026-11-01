---
work_package_id: WP03
title: Pin every unknown-token policy, docs and changelog
dependencies:
- WP01
- WP02
requirement_refs:
- FR-007
- FR-009
planning_base_branch: issue-6433-charter-identity-single-authority
merge_target_branch: issue-6433-charter-identity-single-authority
branch_strategy: Planning artifacts for this mission were generated on issue-6433-charter-identity-single-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6433-charter-identity-single-authority unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
phase: Phase 3 - Pins and communication
history:
- at: '2026-10-30T12:55:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/charter/activation/
create_intent:
- tests/charter/activation/test_unknown_token_policies_6433.py
execution_mode: code_change
owned_files:
- tests/charter/activation/test_unknown_token_policies_6433.py
- docs/architecture/activation-ledger-and-charter-contract.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Pin every unknown-token policy, docs and changelog

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (`spec-kitty agent profile show python-pedro`) before parsing the rest of this prompt.

## Objectives & Success Criteria

- One module names and pins the unknown-token policy of all four surfaces: runtime gate (warn and keep), consistency check (report once and keep), compile (refuse), cascade-source resolution (no source, no error).
- The architecture doc says the three facades answer from `IdentityIndex` and that a cascade source accepts stem, declared id and URN.
- The changelog carries an `[Unreleased]` entry with a bold impact-first lead and `(#6433)`.

## Context & Constraints

- Read: `spec.md` (FR-007, FR-009), `research.md` §5.
- `tests/charter/activation/test_compile_check_identity_6433.py` already pins the first three policies; do not duplicate its fixtures — either extend that module or write a small module that reuses the same fixture helpers and adds the cascade-source row. Prefer a new module with its own minimal fixture so the policy table reads as one place.
- Changelog style: see the `[Unreleased]` `### Fixed` section; bold lead, before/after, under 1,200 characters.

## Branch Strategy

- **Strategy**: single branch on `issue-6433-charter-identity-single-authority`.
- **Planning base branch**: `issue-6433-charter-identity-single-authority`
- **Merge target branch**: `issue-6433-charter-identity-single-authority`

## Subtasks & Detailed Guidance

### Subtask T010 – The policy module

- **Purpose**: one place states the four policies, so a flip fails exactly one assertion.
- **Steps**: for each surface, a test that (a) feeds `ghost-token` and asserts the surface's observable policy, and (b) feeds a known token on the same fixture as the positive control.
- **Files**: `tests/charter/activation/test_unknown_token_policies_6433.py`.
- **Notes**: the cascade-source row asserts `_source_urn(...) is None` (no raise) and that the command still reports its activation; the compile row asserts `UnknownArtifactIdError`.

### Subtask T011 – Architecture doc

- **Purpose**: tell a maintainer where the authority lives.
- **Steps**: in `docs/architecture/activation-ledger-and-charter-contract.md`, add a short paragraph (or extend the identity section) saying activation tokens resolve through `IdentityIndex`, that `resolve_artifact_urn`/`resolve_config_id` are facades over it, and that stem, declared id and `<kind>:<id>` URN are accepted everywhere including the cascade source.
- **Files**: `docs/architecture/activation-ledger-and-charter-contract.md`.
- **Notes**: no new page, so no docs index regeneration is needed; still run the freshness check.

### Subtask T012 – Changelog

- **Purpose**: the operator-visible effect.
- **Steps**: add one `### Fixed` entry: lead with "`--cascade` now starts from the artifact you named, however you spelled it"; before: a URN or normalised directive id activated the artifact but skipped the cascade and its shared-artifact report; after: all three spellings cascade identically; `(#6433)`.
- **Files**: `docs/changelog/CHANGELOG.md`.
- **Notes**: keep it under 1,200 characters; do not restate the refactor.

## Test Strategy

```bash
uv run pytest tests/charter/activation/test_unknown_token_policies_6433.py -q
uv run pytest tests/charter/activation/test_compile_check_identity_6433.py -q
uv run python -m scripts.docs.check_docs_freshness --ci
uv run pytest tests/architectural/test_no_legacy_terminology.py -q
```

## Risks & Mitigations

- Docs freshness reads an installed CLI cache shared with other agents: regenerate nothing beyond what this diff changes, and verify with the freshness check rather than a full rebuild.

## Review Guidance

- Confirm each policy assertion fails if its surface changes policy (not a tautology).
- Confirm the changelog entry names the operator-visible effect first and stays under the length limit.
