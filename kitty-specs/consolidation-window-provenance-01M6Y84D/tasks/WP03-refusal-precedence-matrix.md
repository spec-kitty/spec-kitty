---
work_package_id: WP03
title: Refusal-precedence matrix
dependencies: []
requirement_refs:
- FR-017
- C-006
planning_base_branch: feat/consolidation-window-provenance
merge_target_branch: feat/consolidation-window-provenance
branch_strategy: Planning artifacts for this mission were generated on feat/consolidation-window-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidation-window-provenance unless the human explicitly redirects the landing branch.
subtasks:
- T014
- T015
- T016
- T017
phase: Phase 1 - Pin and decide
history:
- at: '2026-11-08T19:52:39Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/consolidation/test_refusal_precedence_matrix.py
create_intent:
- tests/consolidation/test_refusal_precedence_matrix.py
execution_mode: code_change
model: ''
owned_files:
- tests/consolidation/test_refusal_precedence_matrix.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Refusal-precedence matrix

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP03 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

`build_approved_wp_set` (today in `src/specify_cli/consolidation/reconciliation.py`, lines ~1655-1872) refuses a claim through a fixed sequence of checks. That sequence **is** the refusal-precedence contract (C-006). Pin it before the split, so moving code cannot reorder refusals unnoticed (FR-017).

Done means `tests/consolidation/test_refusal_precedence_matrix.py`:

1. Lists every claim-time refusal of `build_approved_wp_set` in today's order.
2. For every **pair** that can occur together, builds a fixture with both conditions, asserts **both** refusal markers are present in the refusal text, then asserts their order and the joining text (incl. `_compound_refusal`'s "This Mission also has:" tail).
3. Lists every pair that **cannot** co-occur, each with the short-circuit site (function name) that prevents it — as data in the test module, asserted to cover every unordered pair exactly once (matrix completeness).
4. Contains a deliberately swapped-order control that proves the pin can fail.

## Context & Constraints

- `kitty-specs/consolidation-window-provenance-01M6Y84D/plan.md` — IC-03 (Purpose, Risks).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/research.md` — R-06, paula P-02.
- `src/specify_cli/consolidation/reconciliation.py`: `build_approved_wp_set`, `_compound_refusal` (~1884), `_join_refusals` (~1875), `_refusal_claim` (~2892), `_ALSO_HAS` / `_BOTH_NEEDED` constants (~160-164), `claim_integrity_refusal` (~2861).
- Today's order (plan IC-03): **dependency refs -> unresolvable branches -> canceled dependency -> mixed lane -> bound -> evidence -> presence -> authored -> excluded**, with `_compound_refusal` appending the bound's refusals after "This Mission also has:". Verify this order by reading the function; if the code differs, the **code** wins — record the difference in the tracer and the WP history, do not change code.
- Fixture builders: `tests/consolidation/test_reconciliation.py` (claim-level fixtures), `tests/consolidation/test_approved_bound.py`, `tests/consolidation/test_canceled_dependency_attribution.py`, `tests/consolidation/test_dependency_merge_attribution_7307.py`, `tests/terminus/post_approval_support.py`, `tests/terminus/canceled_dependency_support.py`, `tests/terminus/mixed_lane_support.py`. Prefer calling `build_approved_wp_set` directly (claim time) over the CLI: this matrix pins the claim text, and in-process direct calls are fast and reachable by mutations.
- Cross-cutting: C-009, C-013, C-014, NFR-004/005.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on kitty/mission-consolidation-window-provenance-01M6Y84D; completed changes must merge into feat/consolidation-window-provenance.
- **Planning base branch**: feat/consolidation-window-provenance
- **Merge target branch**: feat/consolidation-window-provenance

> Populated by `finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP03 --agent <name> --mission consolidation-window-provenance-01M6Y84D
```

## Subtasks & Detailed Guidance

### Subtask T014 – Inventory the refusals and their short-circuit sites

- **Steps**:
  1. Read `build_approved_wp_set` top to bottom. For each `return` / refusal construction, record: a short id (`dependency_refs`, `unresolvable_branches`, `canceled_dependency`, `mixed_lane`, `bound`, `evidence`, `presence`, `authored`, `excluded`), the helper that builds its text, a stable **marker** substring of its text (a refusal code such as `LANE_MOVED_AFTER_APPROVAL`, `APPROVAL_STAMP_MISSING`, `CANCELED_REACHABLE_VIA_DEPENDENCY`, `DEPENDENCY_REF_MOVED`, or a fixed phrase constant from the module), and whether it returns early (short-circuits everything after it) or composes.
  2. Encode this as a module-level tuple `REFUSALS: tuple[RefusalSpec, ...]` in the test module (frozen dataclass with `id`, `marker`, `short_circuits: bool`).
  3. Import marker constants from the module where they are constants (e.g. `_ALSO_HAS`) instead of retyping strings, so a rename fails loudly.
- **Files**: `tests/consolidation/test_refusal_precedence_matrix.py`.

### Subtask T015 – Pairwise fixtures

- **Steps**:
  1. For each unordered pair (A, B) where A precedes B and A does **not** short-circuit B, write a fixture factory that produces both conditions. Typical compositions: canceled dependency + bound (the `_compound_refusal` case, cf. CLAUDE.md "This Mission also has:"), mixed lane + bound, evidence + presence.
  2. Reuse existing builders; keep each factory small (< 40 lines) and named `_pair_<a>__<b>`.
  3. Where building a pair requires a real-git mission, mark the test `integration` + `git_repo` like `tests/consolidation/test_approved_bound_residuals.py`.
- **Notes**: A pair whose co-occurrence needs a state the builders cannot reach without production changes goes into the "cannot co-occur" table with reason `unreachable_without_production_change` — tell the reviewer in the WP history.

### Subtask T016 – Matrix test

- **Steps**:
  1. `@pytest.mark.parametrize("pair", CO_OCCURRING_PAIRS, ids=...)`.
  2. For each: build, call `build_approved_wp_set(...)` with the fixture's arguments, take the refusal text.
  3. Assert `pair.a.marker in text` **and** `pair.b.marker in text` first (with a message naming the missing one), then `text.index(a.marker) < text.index(b.marker)`, then the joining substring between them when the pair composes through `_compound_refusal` / `_join_refusals`.
  4. Snapshot the normalized full refusal text per pair in the test module as a literal (SHAs normalized as in WP02: replace 40-hex with `<sha>`), so a wording change is caught too.
- **Files**: the test module.

### Subtask T017 – Swapped-order control and the cannot-co-occur table

- **Steps**:
  1. `NON_CO_OCCURRING: dict[tuple[str, str], str]` mapping each pair to the function name that short-circuits it (e.g. `("dependency_refs", "bound"): "build_approved_wp_set: early return after resolve_external_dependency_refs"`).
  2. `test_matrix_is_complete`: every unordered pair of `REFUSALS` ids appears in exactly one of `CO_OCCURRING_PAIRS` / `NON_CO_OCCURRING`.
  3. `test_swapped_order_control`: take one composing pair, build the text, then apply the order assertion with the arguments swapped and assert it raises `AssertionError` (use `pytest.raises(AssertionError)` around a call to the same helper the matrix uses). This proves the order assertion is not vacuous.
- **Files**: the test module.

## Test Strategy

Tests are the deliverable; they must pass on unchanged production code.

## Definition of Done

```bash
uv run --frozen pytest -q tests/consolidation/test_refusal_precedence_matrix.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation.py tests/consolidation/test_approved_bound.py tests/consolidation/test_canceled_dependency_attribution.py
uv run --frozen pytest -q tests/consolidation/test_single_rollback_authority.py
uv run --frozen ruff check tests/consolidation/test_refusal_precedence_matrix.py
uv run --frozen ruff format --check --force-exclude tests/consolidation/test_refusal_precedence_matrix.py
uv run --frozen mypy tests/consolidation/test_refusal_precedence_matrix.py
make test-fast
```

- [ ] Matrix completeness test passes; every pair is classified.
- [ ] Every co-occurring pair asserts both markers before order.
- [ ] The swapped-order control passes (it expects the assertion to fail).
- [ ] No production code changed.
- [ ] **Never rewrite a pushed lane commit** (post-tasks squad R-13): lane-a merges this lane's tip when WP02 starts and again on every lane-a reuse (`allocate_lane_worktree` merges resolvable dependency-lane tips). Once a commit is on the lane branch, never amend, rebase, squash or force-push it, even before approval; fix forward with a new commit. A rewritten commit that lane-a already merged is reachable from no approval stamp and no window, and this Mission's own `consolidate` would refuse it. `git reflog` of the lane branch shows no rewrite at review.
- [ ] **Tracer files** (canonical writer only, no hand edits of `traces/*.md`, no `add-history` fallback; post-tasks squad R-02): `spec-kitty agent tracer-append --mission consolidation-window-provenance-01M6Y84D --category design-decisions --actor "implement WP03" --entry "<summary>. <detail>"` for the verified refusal order and any difference from plan IC-03; `--category tooling-friction` for any friction. The command works from any checkout (lane worktree included) and commits to the coordination surface itself.
- [ ] Never run `make test-full`.

## Risks & Mitigations

- **Vacuous pass**: a fixture that yields one refusal; mitigated by asserting both markers first.
- **Text snapshot too brittle**: normalize SHAs and temp paths only; keep everything else literal (wording drift is exactly what this pin must catch).

## Review Guidance

- Reviewer profile: `reviewer-renata`.
- **Model tier: mid**.
- Cross-check `REFUSALS` against `build_approved_wp_set` line by line.
- Run the swapped-order control mentally: would a reorder of two checks fail at least one matrix row?

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP03 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP03 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`
