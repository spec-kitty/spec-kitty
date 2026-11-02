---
work_package_id: WP02
title: Complete, bounded enumerations on both surfaces
dependencies:
- WP01
requirement_refs:
- FR-006
- FR-007
- FR-009
- NFR-003
- NFR-004
- C-004
- C-005
- SC-001
- SC-004
- SC-005
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on the coordination branch kitty/mission-orchestrator-error-code-prose-guard-01M6EJQS as of main 9aed3a8012. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 2 - the enumerations
history:
- at: '2026-11-02T17:05:00Z'
  actor: planner-priti
  action: Prompt generated via spec-kitty tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: claude-sonnet
owned_files:
- docs/api/orchestrator-api.md
- src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Complete, bounded enumerations on both surfaces

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (`spec-kitty agent profile show python-pedro`) and behave according
to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

## Objective

Make both documented enumerations complete and machine-bounded, so WP01's guard goes
green and a reader can enumerate the failure surface without reconstructing it from
version history.

Two files, 45 additions in total (22 codes in the API reference, 23 rows in the skill
table), plus one anchor pair each.

## Context you need

- `research.md` D-1: the exact missing sets, and the 21 non-contract sub-codes that must
  stay **outside** the checked region.
- `plan.md` "Phase 1 — Design": the anchor syntax and entry shapes.
- WP01's parser: `tests/contract/test_orchestrator_api.py`. Read it first — the docs must
  satisfy it exactly, not approximately.

## Deliverables

T001 `docs/api/orchestrator-api.md`.

- Wrap the canonical bullet list under `## Error Codes` in

  ```
  <!-- orchestrator-error-codes:begin -->
  ...
  <!-- orchestrator-error-codes:end -->
  ```

- Add the 22 missing codes as their own `- \`CODE\`` items, grouped so the list reads
  well (usage/policy → mission/WP → safe-commit → design-phase/delegation → decisions →
  design → runtime/capability), each with a short meaning where it is not obvious. The
  names: `INVALID_MISSION`, `SAFE_COMMIT_STAGED_TREE_UNCHANGED`, `MISSION_ALREADY_EXISTS`
  … `DESIGN_*` (all except the already-listed `DESIGN_STATUS_EVENT_LOG_UNREADABLE`),
  `RUNTIME_NEXT_FAILED`, `RUNTIME_BLOCKED`, `UNSUPPORTED_CAPABILITY`.
- Keep the existing per-item annotations; the guard reads only the leading code.
- Leave the `### data.preflight_error_code`, `### origin freshness` and
  `### data.teardown_error_code` subsections outside the region, unchanged.

T002 `src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md`.

- Wrap the `## Error Code Summary` table in the same anchor pair.
- Add the 23 missing rows in the table's existing three-column style. The names are the
  same 22 plus `WORKFLOW_EVIDENCE_REQUIRED`. Use the per-verb facts already in this
  document (the design-phase sections dictate the command column for the `DESIGN_*`
  rows); do not invent behaviour — where a code's meaning is not stated here, describe
  it only as far as the contract and the API reference support.

T003 Prove green, then prove red half by half.

- `uv run pytest tests/contract/test_orchestrator_api.py -q -k prose` → green.
- Revert `docs/api/orchestrator-api.md` alone (`git stash`/checkout), run again → red,
  naming that surface and its 22 codes; restore. Repeat for the skill reference (23).
  Record both red outputs as evidence for SC-005.

T004 Docs gates.

- `npx markdownlint-cli2 docs/api/orchestrator-api.md` and the skill reference (or the
  repo's markdownlint entry point) → clean.
- `uv run python -m scripts.docs.check_docs_freshness --ci` → errors=0.
- `uv run pytest tests/contract/test_orchestrator_api.py -q` → the whole module green,
  including the untouched `TestAllowedErrorCodes`.

## Constraints

- Do not touch the contract JSON (C-001), the guard's own assertions (C-002), or
  `TestAllowedErrorCodes` (C-003).
- Both surfaces stay prose a person reads (C-004): list items and table rows, no
  generated block, no "see upstream_contract.json" substitution.
- Contract-version history and per-verb narrative stay untouched (C-005).
- No markdownlint suppression, no anchor placed inside a fenced block.

## Definition of done

- Both surfaces enumerate exactly the 80 contract codes, no duplicates, one anchor pair
  each, sub-code tables outside.
- WP01's guard green on the whole module; the half-by-half reds captured.
- Docs gates clean; no other file in the diff.
