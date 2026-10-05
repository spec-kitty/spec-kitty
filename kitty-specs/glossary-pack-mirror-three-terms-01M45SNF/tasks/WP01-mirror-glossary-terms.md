---
work_package_id: WP01
title: Mirror the three terms into the pack and the seed
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
- C-004
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-5761-glossary-pack-terms
merge_target_branch: issue-5761-glossary-pack-terms
branch_strategy: Planning artifacts for this mission were generated on issue-5761-glossary-pack-terms. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5761-glossary-pack-terms unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Mirror
history:
- at: '2026-10-05T10:45:00+00:00'
  actor: system
  action: Prompt generated during tasks phase
agent_profile: implementer-ivan
authoritative_surface: packs/built-in/glossary_packs/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml
- packs/built-in/pack-manifest.yaml
- .kittify/glossaries/spec_kitty_core.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Mirror the three terms into the pack and the seed

## ⚡ Do This First: Load Agent Profile

Load `implementer-ivan` via `/ad-hoc-profile-load` before proceeding.

## Objective

Add "tool-surface drift", "integrating worktree" and "target-owned bookkeeping"
to the shipped glossary pack and to this project's seed, with identical fields,
then regenerate the pack manifest. The exact definitions are fixed in
[data-model.md](../data-model.md); copy them verbatim.

## Branch Strategy

Planning/base branch `issue-5761-glossary-pack-terms`; final merge target
`issue-5761-glossary-pack-terms`. The mission is `single_branch`: the WP runs
in the repository root checkout (no lane worktree); `lanes.json` names the one
repo-root lane.

## Context

- Canonical wording: `docs/context/execution.md` (`### Tool-surface drift`,
  `### integrating worktree`) and `docs/context/orchestration.md`
  (`### Target-owned bookkeeping`). Do not edit them.
- Grounding: [research/code-grounding.md](../research/code-grounding.md).
- Precedent: `b70a344fc8` (pack + manifest), `8fc1a85560` (seed mirror).

## Red-first check (ATDD adaptation)

There is no new behavior to test. Before T002, run
`pytest tests/architectural/test_glossary_pack_parity.py -q` with only the
pack edited: it must be RED (surface-set parity). Record the result in the
review handoff. It goes GREEN after T002.

## Subtasks

### T001 — Append the three terms to the built-in pack

File: `packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml`.
Append three entries at the end of `terms:`, keys in the pack's alphabetical
order: `confidence: 0.9`, `definition`, `status: active`, `surface`,
`synonyms_to_avoid` (only where data-model.md lists one). Use a double-quoted
multi-line definition (the text contains `: `). Lowercase surfaces:
`tool-surface drift`, `integrating worktree`, `target-owned bookkeeping`.

Must NOT appear in pack text: issue numbers (`#` + digits), `WPnn`, `FR-n`,
`src/specify_cli`, `src/doctrine`, `tests/architectural`, `kitty-specs/`,
`spec-kitty merge`, the retired word "feature" as a product word.

### T002 — Mirror into the seed

File: `.kittify/glossaries/spec_kitty_core.yaml`. Append the same three terms
at the end, seed key order `surface`, `definition`, `confidence`, `status`,
`synonyms_to_avoid`. Write each definition as a single-line double-quoted
scalar (a `>` block would add a trailing newline and break parity; a wrapped
plain scalar breaks the docs page parser).

### T003 — Regenerate derived artifacts

```bash
spec-kitty doctrine regenerate-graph
spec-kitty doctrine regenerate-graph --check
uv run python -m scripts.docs.docs_index --strict
uv run python scripts/generate_contextive_glossaries.py check
```

Only `packs/built-in/pack-manifest.yaml` should change.

### T004 — Run the gates

```bash
uv run pytest tests/architectural/test_glossary_pack_parity.py tests/architectural/test_pack_manifest_no_author_edit.py tests/architectural/test_doctrine_regenerate_graph_roundtrip.py tests/architectural/test_builtin_pack_provenance_ratchet.py tests/architectural/test_no_legacy_terminology.py tests/architectural/test_no_dead_cli_paths.py tests/architectural/test_transition_guard_shrink_only.py tests/architectural/test_glossary_authority_parity.py tests/architectural/test_no_inert_schema_slots.py -q
uv run pytest tests/glossary tests/doctrine/glossary_packs tests/docs/test_glossary_linker.py tests/cross_cutting/encoding/test_contextive_traceability.py tests/cross_cutting/packaging/test_packaging_safety.py -q
uv run spec-kitty glossary list | grep -E "tool-surface drift|integrating worktree|target-owned bookkeeping"
```

## Definition of Done

- Both files carry the three terms with byte-identical definitions and the
  same `synonyms_to_avoid`; meaning matches `docs/context/` (data-model.md).
- `pack-manifest.yaml` regenerated; `--check` clean.
- Every T004 command green; 0 lines changed under `docs/context/`.

## Reviewer guidance

Compare each definition side by side with its `docs/context/` entry: every
"Do NOT use when" case must survive in condensed form. Confirm "primary-owned"
appears only as the name to avoid.
