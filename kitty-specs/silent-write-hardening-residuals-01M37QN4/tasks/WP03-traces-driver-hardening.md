---
work_package_id: WP03
title: 'Finding C: traces merge-driver tilde-fence + non-colliding block key'
dependencies: []
requirement_refs:
- C-002
- FR-005
- FR-006
- NFR-004
planning_base_branch: fix/silent-write-hardening-residuals
merge_target_branch: fix/silent-write-hardening-residuals
branch_strategy: Planning artifacts for this mission were generated on fix/silent-write-hardening-residuals. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/silent-write-hardening-residuals unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
- T014
history:
- event: created
  at: '2026-09-23T19:24:56Z'
  actor: architect-alphonso
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/merge_driver.py
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/merge_driver.py
- tests/merge/test_traces_driver_section_union_4894.py
role: implementer
tags: []
tracker_refs:
- '#4993'
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else in this prompt, load your assigned agent profile:

```
/ad-hoc-profile-load python-pedro
```

This profile governs your implementation style, boundaries, and quality standards for this work package.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in code blocks.

---

## Objective

Harden the traces merge driver's 3-way base-aware stale-drop against two benign-but-real edges (over-inclusion
today, never data loss): (1) `~~~` tilde fences are not recognized, so a heading-like line inside a tilde block
is misread as a section boundary; (2) block identity is the raw first heading line deduped via `setdefault`, so
two sections sharing a heading collide. **Bounded fix only — do NOT refactor the fence/section contract (C-002),
and do NOT touch `union_trace_texts`' whole-block dedup (NFR-004).**

Read `contracts/traces-merge-contract.md` first.

## Key context (verified on current main, `src/specify_cli/cli/commands/merge_driver.py`)

- `_TRACE_SECTION_BOUNDARY` (~305): matches `#{1,6} …` headings AND `<!-- section:... -->`.
- `_TRACE_FENCE_MARKER` (~308): `re.compile(r"^```")` — **backtick-only** (the fence bug).
- `_split_trace_blocks` (~311-331): toggles `in_fence` on each `_TRACE_FENCE_MARKER.match`; a boundary line
  OUTSIDE a fence starts a new block.
- `union_trace_texts` (~334-362): whole-block byte-identical dedup keyed on the full block tuple — **LEAVE AS-IS.**
- `_trace_block_key` (~365-374): `return block[0] if block else ""` — the colliding key.
- `_drop_stale_theirs_trace_blocks` (~377-415): builds `base_by_key`/`ours_by_key` via
  `setdefault(_trace_block_key(block), block)` (first-occurrence-wins → duplicate-heading collision); drops a
  theirs block only when `theirs_unchanged and ours_diverged`.

## Subtasks

### T011 — Red-first tests (prove both edges) `[P]`

**Steps**:
1. In `tests/merge/test_traces_driver_section_union_4894.py`, add a test where a `~~~`-fenced block contains a
   heading-like line (e.g. `# not a heading`) and assert the driver does NOT split at that line. MUST FAIL pre-fix.
2. Add a test with two distinct sections sharing an identical heading and assert both survive / are keyed
   distinctly through the base-aware stale-drop (no collision-drop, no mis-attribution). MUST FAIL pre-fix.
3. Run both against current code and paste the failures into review notes.

### T012 — Widen fence recognition `[P]`

**Steps**: Change `_TRACE_FENCE_MARKER` to `re.compile(r"^(?:```|~~~)")` (or `r"^(?:`{3,}|~{3,})"`). This is the
only fence-toggle site; `in_fence` propagates through `_split_trace_blocks`. Do not otherwise alter splitting.

### T013 — Non-colliding base-comparison block key `[P]`

**Steps**:
1. Give `_drop_stale_theirs_trace_blocks` a non-colliding key: prefer parsing a `<!-- section:ID -->` id from
   the block's opening delimiter when present; else fall back to `(block[0], occurrence_ordinal)` where
   `occurrence_ordinal` is the running count of prior blocks sharing that first line.
2. Replace the `setdefault`-based `base_by_key`/`ours_by_key` with occurrence-indexed keys (or
   `dict[key, list[block]]` consumed positionally) so duplicate headings map distinctly.
3. **Do NOT** key on a full-block hash — base-awareness must still detect "same section, body changed"
   (`theirs_unchanged` vs `ours_diverged`). Keep `union_trace_texts`' full-tuple dedup untouched.

### T014 — Regression `[P]`

**Steps**: Assert (a) a single-heading section that is unchanged-theirs / diverged-ours is still correctly
stale-dropped (3-way base-awareness intact); (b) `union_trace_texts` whole-block byte-identical dedup is
unchanged (existing #4894 section-union assertions stay green). Run the file and paste counts.

## Branch Strategy

Planning base and final merge target: `fix/silent-write-hardening-residuals`. Execution worktree allocated per
`lanes.json` lane during `/spec-kitty.implement`; do not hand-create branches.

## Definition of Done

- `~~~` fences recognized; tilde-fenced heading-like line not a boundary (FR-005, AC-C1).
- Duplicate-heading sections keyed distinctly; none dropped/mis-attributed (FR-006, AC-C2).
- Diverged single-heading section still stale-drops; whole-block dedup unchanged (NFR-004, AC-C3/C4).
- `union_trace_texts` untouched; no contract refactor (C-002).
- `ruff` + `mypy` clean on owned files. (Note: `merge_driver.py` was un-excluded from ruff-format in #4938 — keep it format-clean.)

## Reviewer guidance

Confirm the base-comparison key is body-insensitive (not a full-block hash) so 3-way matching survives.
Confirm `union_trace_texts` is byte-for-byte unchanged. Re-run the two red-first swaps.
