---
work_package_id: WP01
title: Filter the advertised action-critical charter sections
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
- C-003
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6968-action-critical-sections-resolve
merge_target_branch: issue-6968-action-critical-sections-resolve
branch_strategy: Planning artifacts for this mission were generated on issue-6968-action-critical-sections-resolve. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6968-action-critical-sections-resolve unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-action-critical-sections-resolve-01M6BTST
base_commit: 2c5ad4f7f63a3babf69abf0b2e3abb36f2d4dcbd
created_at: '2026-11-01T15:22:33.935769+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Fix and prove
history:
- at: '2026-11-01T15:18:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/context_renderers/
create_intent:
- tests/charter/test_context_action_critical_minimal.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/context_renderers/section_bodies.py
- src/charter/activation/context_renderers/bootstrap_text.py
- tests/charter/test_context_section_bodies.py
- tests/charter/test_context_action_critical_minimal.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Filter the advertised action-critical charter sections

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Review Feedback

Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`). Address all feedback before the work is complete, and record each response with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

`spec-kitty charter context --action implement` (and `review`) must stop
advertising action-critical charter headings the active `charter.md` does not
carry. Concretely, after this package:

1. A minimal consumer charter with none of `Terminology Canon`, `Code Review
   Checklist`, `Regression Vigilance` yields **no** `Run: spec-kitty charter
   context --include section:` line and **no** `Action-Critical Charter
   Sections (<action>):` header (FR-001, FR-003, SC-001).
2. A charter carrying all three still renders all three verbatim bodies and all
   three recovery fetch stanzas, byte-identical to today's output (FR-002,
   SC-002).
3. A charter carrying only one of them advertises only that one.
4. A direct `--include section:<slug>` for a heading the charter lacks keeps
   returning the honest placeholder (FR-004, NFR-001).
5. The regression test exercises the production entry point
   (`charter.activation.context.build_charter_context`) and fails on unpatched
   `main` (FR-005, SC-003).

## Context & Constraints

- Issue: #6968. Reproduction and origin analysis: `research.md` (D-001 … D-005).
- The configured heading set lives in
  `src/charter/activation/context_renderers/section_bodies.py`
  (`ACTION_CRITICAL_SECTIONS`). Keep it there; this package filters it, it does
  not relocate or duplicate it (C-001).
- `packs/built-in` is fetched from `spec-kitty-open-packs` and gitignored — do
  not edit pack content here (C-002 is WP02's concern, but the code must not
  start depending on pack text).
- Callers `bootstrap_text.py` and `compact_governance.py` already skip an empty
  block string; do not change their signatures.
- Token-budget substitution (`token_budget.py`) splits the rendered block by
  `### ` headings, so a heading that is not rendered can never produce a
  substitution stanza (NFR-002).

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Write the failing regression test on a minimal consumer charter

- **Purpose**: Witness the defect through the production entry point before the
  fix, so the test cannot pass vacuously.
- **Files**: `tests/charter/test_context_action_critical_minimal.py` (new).
- **Steps**:
  1. Build a temporary git-initialised project root with
     `.kittify/charter/charter.md` containing only `## Purpose` and
     `## Testing Policy`, plus `.kittify/config.yaml` with
     `mission_type_activations:\n  - software-dev` (mirror the fixture pattern
     in `tests/specify_cli/next/test_wp_prompt_governance_contract.py`).
  2. Call the production entry point
     `charter.activation.context.build_charter_context(repo_root, action="implement", mark_loaded=False)`
     and assert:
     - no `--include section:` line for `terminology-canon`,
       `code-review-checklist` or `regression-vigilance`;
     - no `Action-Critical Charter Sections (implement):` header.
  3. On the **same fixture**, assert the positive control: a charter with all
     three headings emits all three bodies and three `--include section:` lines
     (same fixture shape, different charter text), and a direct
     `build_charter_context(..., include="section:code-review-checklist")` on
     the minimal charter still returns the honest placeholder text rather than
     raising (FR-004).
  4. Confirm the test is red on the current renderer before touching
     `section_bodies.py`: `uv run pytest tests/charter/test_context_action_critical_minimal.py -q`.
- **Parallel?**: Yes — can be authored before T002.
- **Notes**: Keep the assertion on absence specific to `section:` selectors;
  other `--include directive:`/`tactic:` stanzas in the output are legitimate.

### Subtask T002 – Filter the advertised headings in the renderer

- **Purpose**: Make the advertised set equal to the resolving set.
- **Files**: `src/charter/activation/context_renderers/section_bodies.py`.
- **Steps**:
  1. Add a small private predicate (for example
     `_resolves_in_charter(charter_content: str, heading: str) -> bool`) that
     returns `True` when `_extract_section_body` yields a non-empty body.
  2. In `render_critical_section_bodies`, iterate the configured headings and
     render only those that resolve. Preserve the current per-heading shape:
     `### <heading>` then the verbatim body then the existing fetch stanza.
  3. Return `""` when no configured heading resolves, so the caller's
     `_append_block` emits no empty header (FR-003).
  4. Leave `CRITICAL_SECTION_WHEN_CLAUSES`, `critical_section_selector`,
     `critical_section_when_clause` and `_render_fetch_stanza` in place — they
     are still used for present headings and under budget substitution.
  5. Do not change `render_critical_section_include` control flow.
- **Parallel?**: No — after T001 exists to prove the change.
- **Notes**: An "empty body" heading counts as not resolving (research D-004).

### Subtask T003 – Update the unit-test expectations

- **Purpose**: The existing unit suite pins the defective missing-heading arm;
  move it to the filtered-set rule without weakening any present-section test.
- **Files**: `tests/charter/test_context_section_bodies.py`.
- **Steps**:
  1. Replace `TestMissingSectionFetchStanza::test_missing_section_emits_fetch_stanza`
     with an assertion that the missing heading is **not** advertised and that
     the still-present headings are.
  2. Re-check every count-based assertion (for example the unbalanced-fence
     test's `result.count("  Run: spec-kitty charter context --include") == 3`)
     and update it to the new resolved-heading count, keeping the fence/masking
     assertions themselves intact.
  3. Keep `render_critical_section_include` tests unchanged except where they
     assert the *advertised* path rather than the direct fetch.
  4. Leave the `test_context_display_charter_md.py` empty-charter expectations
     green; adjust only if they encode the removed header.
- **Parallel?**: Yes — after T002's behaviour is settled.
- **Notes**: Do not delete an assertion that still guards present-section
  behaviour (C-003).

### Subtask T004 – Docstrings state the filtered-set rule

- **Purpose**: A reader of the module must learn that missing headings are not
  advertised, and why.
- **Files**: `src/charter/activation/context_renderers/section_bodies.py`.
- **Steps**:
  1. Update the module docstring: the renderer emits a body-or-fetch block **for
     each resolving heading**, and skips a heading the active charter does not
     carry.
  2. Update `render_critical_section_bodies`'s Notes section (currently "Missing
     sections never crash the renderer … they emit the fetch stanza instead") to
     the new rule, keeping the no-crash guarantee (NFR-001).
  3. Note that `render_critical_section_include`'s honest placeholder remains the
     explicit-fetch surface, not an advertised one.
  4. Update the call-site comment in `bootstrap_text.py` (line ~297), which still
     says "an absent heading emits a fetch stanza"; the renderer now omits an
     unresolved heading entirely. Comment-only edit — do not change the call.
- **Parallel?**: Yes.
- **Notes**: Keep the ATDD anchor names mentioned in the module docstring
  accurate; they still govern present-section behaviour.

### Subtask T005 – Run the targeted suites plus ruff and mypy

- **Purpose**: Prove the change is green on its own surface and does not disturb
  the WP-prompt governance contract.
- **Commands**:
  ```bash
  uv run pytest tests/charter/test_context_section_bodies.py tests/charter/test_context_action_critical_minimal.py tests/charter/test_context_display_charter_md.py -q
  uv run pytest tests/specify_cli/next/test_wp_prompt_governance_contract.py -q
  uv run ruff check src/charter/activation/context_renderers/section_bodies.py tests/charter/test_context_section_bodies.py tests/charter/test_context_action_critical_minimal.py
  uv run mypy src/charter/activation/context_renderers/section_bodies.py
  ```
- **Parallel?**: No.
- **Notes**: Do not run a full-directory or whole-repo sweep
  (`NO_FULL_HEAVY_SUITES_IN_MISSION`). Record commands and counts for the PR.

## Test Strategy

- Red-first: T001 fails on the unpatched renderer with the three advertised
  selectors; T002 makes it pass.
- Absence assertions are paired with a positive control on the same fixture
  shape (all-three-headings charter ⇔ no-headings charter), so the "not
  advertised" probe is non-vacuous.
- Half-by-half: the filter (T002) and the unit-test migration (T003) are both
  required; reverting the filter must make T001 and the updated T003 case red.
- Production path: T001 calls `build_charter_context`, not the private helper.

## Risks & Mitigations

- **Regression in present-section rendering**: the ATDD contract tests in
  `tests/specify_cli/next/test_wp_prompt_governance_contract.py` run in T005 and
  must stay green.
- **Silent header removal**: covered by the T001 absence assertion on the
  header line.
- **Masked heading treated as present**: `_extract_section_body` already returns
  `None` for fenced-off headings; T003's unbalanced-fence test pins the outcome.

## Review Guidance

- Confirm the advertised set is derived from the active `charter.md` only, with
  no new config, list, or pack dependency.
- Confirm no present-section assertion was deleted, only the one that pinned the
  defect.
- Confirm the direct `--include section:<slug>` surface still degrades honestly.
- Confirm the targeted command list was actually run and passes.
