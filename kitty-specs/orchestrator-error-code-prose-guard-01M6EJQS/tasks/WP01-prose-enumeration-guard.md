---
work_package_id: WP01
title: The red-first prose-enumeration guard
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-008
- FR-009
- FR-010
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
- SC-002
- SC-003
- SC-005
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on the coordination branch kitty/mission-orchestrator-error-code-prose-guard-01M6EJQS as of main 9aed3a8012. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - the guard, red-first
history:
- at: '2026-11-02T17:05:00Z'
  actor: planner-priti
  action: Prompt generated via spec-kitty tasks
agent_profile: python-pedro
authoritative_surface: tests/contract/
create_intent: []
execution_mode: code_change
model: claude-sonnet
owned_files:
- tests/contract/test_orchestrator_api.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – The red-first prose-enumeration guard

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (`spec-kitty agent profile show python-pedro`) and behave according
to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

## Objective

Add one contract test class to `tests/contract/test_orchestrator_api.py` that makes the
two documented error-code enumerations impossible to drift from
`orchestrator_api.allowed_error_codes` without CI going red — and that fails closed when
its own parsing anchor disappears.

This WP ships the guard **only**. The docs are WP02's. Running this WP's tests at the
end of WP01 must show a genuine RED that names the missing codes; capture that output.

## Context you need (read it, do not re-derive it)

- `kitty-specs/orchestrator-error-code-prose-guard-01M6EJQS/research.md` — D-1 (measured
  drift, and the 21 non-contract sub-codes a whole-section scan would wrongly demand),
  D-2 (anchor semantics), D-3 (read the authority at test time), D-4 (why this module).
- `kitty-specs/orchestrator-error-code-prose-guard-01M6EJQS/plan.md` — "Phase 1 — Design"
  fixes the anchor syntax and the parse rules; implement exactly those.
- `tests/contract/test_orchestrator_api.py::TestAllowedErrorCodes` — the sibling class.
  Do not modify it.
- `tests/contract/conftest.py` — the `orchestrator_api_contract` fixture you must use.

## Deliverables

T001 The surface table and the pure parser.

- Two surface constants: the API reference path and the shipped skill-reference path,
  plus the surface kind (`bullets` / `table`).
- `parse_enumeration_entries(text, surface_kind) -> list[str]`:
  - locate `<!-- orchestrator-error-codes:begin -->` … `<!-- orchestrator-error-codes:end -->`
    (a fenced-code-block occurrence must not be mistaken for the anchor — pick a rule and
    state it in a comment);
  - `bullets`: each `^- \`CODE\`` line contributes its **leading** backticked token only;
  - `table`: each `| \`CODE\` | … |` row contributes its first cell only;
  - every other non-blank line must be a heading, a table header/separator, or an HTML
    comment; otherwise raise a message naming the offending line number and text.
- A `SurfaceParseError` (or a `ValueError` with a precise message — your call, but the
  test must surface it as a failure naming the file).

T002 The fail-closed paths, each with its own in-memory fixture text.

- Missing anchors (both absent, or only one present) → naming the anchor it expected.
- A region that parses to zero entries → a failure, not "agrees with the empty set".
- A duplicate code inside one region → reported with the code named.

T003 The per-surface equality test against the real documents.

- One test parameterised over the two surfaces: parse the file, compare with
  `set(orchestrator_api_contract["allowed_error_codes"])`, and assert both directions
  with a single message carrying the surface path and sorted `missing` / `unexpected`
  lists (FR-003).
- A duplicate assertion per surface (FR-008).
- A **same-fixture positive control**: the same parsed list must contain a code known to
  be present today (`USAGE_ERROR`), so a probe that silently returns `[]` cannot pass.
- A `fast`/`contract` marker consistent with the module's existing `pytestmark`.

T004 The red-first proof.

- Run the new class against the unmodified docs and capture the failure output: the API
  reference must report the 22 missing codes, the skill table the 23. Save the exact
  command and the relevant lines in your acceptance evidence; this is the RED step.
- Do **not** edit either documentation file in this WP.

## Constraints

- No contract JSON edit (C-001); no change to `TestAllowedErrorCodes` (C-003); no marker,
  xfail, skip or deselection added to make anything pass (C-002).
- Offline, no subprocess, under 2 s for the whole class (NFR-001); sorted, stable failure
  text (NFR-002).
- Ruff-clean and format-clean for the touched file: `uv run ruff check` and
  `uv run make format-check-files FILES=tests/contract/test_orchestrator_api.py`.

## Definition of done

- `uv run pytest tests/contract/test_orchestrator_api.py -q -k prose` shows the RED
  described in T004, with both surfaces named and their counts.
- The fail-closed and duplicate tests pass (they are green from the start — they use
  in-memory text, not the real docs).
- No documentation file is modified.
