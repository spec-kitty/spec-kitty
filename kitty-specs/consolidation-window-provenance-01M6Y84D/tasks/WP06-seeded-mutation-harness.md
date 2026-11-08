---
work_package_id: WP06
title: Seeded-mutation harness and mutation table
dependencies:
- WP02
- WP04
requirement_refs:
- NFR-008
- SC-005
- C-008
planning_base_branch: feat/consolidation-window-provenance
merge_target_branch: feat/consolidation-window-provenance
branch_strategy: Planning artifacts for this mission were generated on feat/consolidation-window-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidation-window-provenance unless the human explicitly redirects the landing branch.
subtasks:
- T030
- T031
- T032
- T033
phase: Phase 1 - Pin and decide
history:
- at: '2026-11-08T19:52:39Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/consolidation/test_reconciliation_seeded_mutations.py
create_intent:
- tests/consolidation/test_reconciliation_seeded_mutations.py
execution_mode: code_change
model: ''
owned_files:
- tests/consolidation/test_reconciliation_seeded_mutations.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Seeded-mutation harness and mutation table

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
- **Report progress**: `spec-kitty agent tasks add-history WP06 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

A characterization corpus that cannot fail proves nothing. Before any code moves, show that each check Phase 3 will move is **guarded**: one deterministic seeded mutation of that check, applied in the process where the corpus computes verdicts, turns at least one named corpus cell red (NFR-008, SC-005, C-008, DIRECTIVE_043).

Done means `tests/consolidation/test_reconciliation_seeded_mutations.py`:

1. Holds a checked-in **mutation table** `MUTATIONS: tuple[Mutation, ...]`, one row per check: `check` (kebab id), `target` (function or `Class.method` name), `mutation` (one-line description), `apply` (callable taking `monkeypatch`), `expected_red_cells` (corpus cell keys from WP02's golden file).
2. For each row, applies the mutation through `RECONCILIATION_FAMILY` (WP04) and recomputes **only** the expected cells in process; asserts each expected cell now differs from the golden value.
3. Has an unmutated control: the same cells recomputed without a mutation equal the golden values.
4. Asserts that every check Phase 3 moves has at least one row (coverage test).

The same file is re-run unchanged (or retargeted only through the family helper) after the split in WP15.

## Context & Constraints

- `kitty-specs/consolidation-window-provenance-01M6Y84D/plan.md` — IC-17 (Purpose, Risks), IC-10/IC-11 (the checks that move and their target modules).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/research.md` — R-07, R-18.
- WP02's `tests/consolidation/characterization_support.py`: use its cell recomputation API (`assert_cells_match`, the per-cell runner) — do not build another runner.
- WP04's `tests/consolidation/reconciliation_family.py`: `setattr_reconciliation_family(monkeypatch, name, value)`. For methods, patch the class attribute with `monkeypatch.setattr(MergeOutcomeVerifier, "<method>", fake)`: the class object stays identical across the split.
- Checks to cover (from plan IC-10/IC-11, mapped to today's functions in `src/specify_cli/consolidation/reconciliation.py`):

  | check id | candidate target(s) | mutation idea |
  |---|---|---|
  | `kernel-bookkeeping` | `_is_bookkeeping` | always `False` (bookkeeping paths become content) or always `True` |
  | `kernel-anchors` | `_closed_world_anchors` | return `[]` |
  | `closed-world` | `_collect_excluded` | return an empty excluded set |
  | `external-dependency-refs` | `resolve_external_dependency_refs` | accept every declared ref |
  | `approved-bound` | `_approved_bound_verdict` / `approved_bound_refusal` | verdict forced to "no refusal" |
  | `write-branch` | `_write_branch_verdict` | verdict forced to pass |
  | `lane-tip-recheck` | `lane_tips_moved_refusal` | return `None` |
  | `mixed-lane` | `_resolve_mixed_lane` | resolve as clean |
  | `canceled-dependency` | `_resolve_canceled_dependency_lanes` | return no carried content |
  | `authorship` | `_collect_authored` / `_final_authored_walk` | drop every deletion or every authored blob |
  | `presence` | `unmet_approved_content` | return no gaps |
  | `verifier-squash-axis` | `MergeOutcomeVerifier._unattributable_content_squash` | return no unattributable paths |
  | `verifier-presence-axis` | `MergeOutcomeVerifier._approved_content_divergence` | return no divergence |
  | `verifier-canceled-axis` | `MergeOutcomeVerifier._canceled_content_divergence` | return no divergence |
  | `rendering` | a text helper that moves to `reconciliation_rendering.py` in WP11: `_join_refusals`, `_attest_tail` or a `_describe_*` clause helper. **Not** `_compound_refusal`: it moves to `reconciliation_claim.py` in WP14, and WP15 asserts the `rendering` row's target is defined in `reconciliation_rendering.py` | drop a joined clause or the recovery/attest tail |
  | `claim-orchestration` | `build_approved_wp_set` | skip one check (wrap and remove the bound refusal) |

  Confirm each target exists and its signature before writing the fake (`codegraph_explore` or read the function). Choose the expected red cells by running the mutation and looking at which cells change; then **pin** them in the table.
- Cross-cutting: C-009, C-013, C-014.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on kitty/mission-consolidation-window-provenance-01M6Y84D; completed changes must merge into feat/consolidation-window-provenance.
- **Planning base branch**: feat/consolidation-window-provenance
- **Merge target branch**: feat/consolidation-window-provenance

> Populated by `finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP06 --agent <name> --mission consolidation-window-provenance-01M6Y84D
```

## Subtasks & Detailed Guidance

### Subtask T030 – Mutation table

- **Steps**:
  1. Define `@dataclass(frozen=True) class Mutation` with the five fields above.
  2. Write one row per check id of the table in Context. Each `apply` is a small named function (`_mutate_kernel_bookkeeping(monkeypatch)`, ...) that installs the fake through `setattr_reconciliation_family` (or the class-attribute form for methods).
  3. Each fake must be **deterministic** and minimal: force the verdict to pass, flip one predicate, or drop one result. No randomness, no I/O.
  4. Put a module docstring table (check -> function -> mutation -> expected red cell) that a reviewer can read without running anything; keep it consistent with `MUTATIONS` (a test asserts they agree, see T033).

### Subtask T031 – Apply through `RECONCILIATION_FAMILY`

- **Steps**:
  1. Every function target is patched with `setattr_reconciliation_family`, never with a string on the facade: after the split, the facade no longer looks names up (WP04 guard), and the family helper patches every module that binds the name.
  2. Do not patch the facade module object directly.
  3. If a check is only reachable in a subprocess (it should not be: WP02's runner is in process), use an env-gated shim in the child and say so in the row; never a parent-process monkeypatch on a child.

### Subtask T032 – Per-mutation red test and the green control

- **Steps**:
  1. `@pytest.mark.parametrize("mutation", MUTATIONS, ids=lambda m: m.check)` `test_seeded_mutation_turns_cells_red(mutation, monkeypatch, tmp_path)`: apply, recompute `mutation.expected_red_cells`, assert each differs from its golden value; on failure print the cell, golden value and recomputed value.
  2. `test_unmutated_cells_match_golden`: recompute the union of all expected red cells without any mutation; assert equal to golden. This proves the mutated run, not the fixture, causes the difference.
  3. Keep runtime bounded: recompute only the listed cells; share builds per shape via WP02's helpers.

### Subtask T033 – Coverage of every moved check

- **Steps**:
  1. `PHASE3_CHECKS = frozenset({...})` with every check id from the Context table.
  2. `test_every_moved_check_has_a_mutation`: `{m.check for m in MUTATIONS} >= PHASE3_CHECKS`.
  3. `test_docstring_table_matches_mutations`: parse the docstring table rows and compare check ids and targets with `MUTATIONS`.

## Test Strategy

Tests are the deliverable. All must pass on unchanged production code.

## Definition of Done

```bash
uv run --frozen pytest -q tests/consolidation/test_reconciliation_seeded_mutations.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py tests/consolidation/test_reconciliation_family_guard.py
uv run --frozen pytest -q tests/consolidation/test_single_rollback_authority.py
uv run --frozen ruff check tests/consolidation/test_reconciliation_seeded_mutations.py
uv run --frozen ruff format --check --force-exclude tests/consolidation/test_reconciliation_seeded_mutations.py
uv run --frozen mypy tests/consolidation/test_reconciliation_seeded_mutations.py
make test-fast
```

- [ ] Every row of `MUTATIONS` turns its named cells red; the unmutated control is green.
- [ ] Coverage test lists all 16 check ids (or the reviewer agreed in writing to a merged id, recorded in the WP history).
- [ ] No patch uses a facade string target.
- [ ] No production code changed.
- [ ] **Tracer files**: dated entry in `kitty-specs/consolidation-window-provenance-01M6Y84D/traces/design-decisions.md` with any check that needed an unusual mutation; `traces/tooling-friction.md` for friction. Format `- **[YYYY-MM-DD][implement WP06] <summary>.** <detail>`. No `kitty-specs/` in your checkout: `spec-kitty agent tasks add-history WP06 --note "..."`.
- [ ] Never run `make test-full`.

## Risks & Mitigations

- **Mutation does not reach the corpus**: the green control plus the red assertion catch it; a vacuous row fails.
- **Rendering mutations change only text**: pick cells that pin text (WP02's FR-023 all-gap cell) or the refusal codes the rendering produces.

## Review Guidance

- Reviewer profile: `reviewer-renata`.
- **Model tier: mid**.
- For three random rows, revert the mutation locally and confirm the cell goes back to golden.
- Check that each mutation targets the check's own logic (not a shared helper that would make several rows redundant).

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP06 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP06 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`
