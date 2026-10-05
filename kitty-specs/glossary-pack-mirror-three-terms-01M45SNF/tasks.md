# Tasks: Mirror three glossary terms into the built-in pack

**Mission**: glossary-pack-mirror-three-terms-01M45SNF
**Planning/base branch**: issue-5761-glossary-pack-terms · **Merge target**: issue-5761-glossary-pack-terms

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Append the three terms to the built-in glossary pack | WP01 | |
| T002 | Mirror the three terms into the project seed with identical fields | WP01 | |
| T003 | Regenerate the pack manifest; confirm docs index and contextive unchanged | WP01 | |
| T004 | Run the gates named in research/code-grounding.md section 2 | WP01 | |

## WP01 — Mirror the three terms into the pack and the seed

**Goal**: the built-in `spec-kitty-core` glossary pack and the project seed both carry "tool-surface drift", "integrating worktree" and "target-owned bookkeeping" with identical fields whose meaning matches `docs/context/`.
**Priority**: P1 (the whole mission). **Independent test**: the parity, manifest round-trip and provenance gates pass and `spec-kitty glossary list` shows the three terms.
**Prompt**: [tasks/WP01-mirror-glossary-terms.md](tasks/WP01-mirror-glossary-terms.md) (~150 lines; a data-only WP, deliberately below the 200-line guide).

T001 Append the three terms to the built-in glossary pack (WP01)
T002 Mirror the three terms into the project seed with identical fields (WP01)
T003 Regenerate the pack manifest; confirm docs index and contextive unchanged (WP01)
T004 Run the gates named in research/code-grounding.md section 2 (WP01)

**Implementation sketch**: T001 → T002 → T003 → T004, sequential (one file set).
**Dependencies**: none. **Parallel opportunities**: none (single WP).
**Risks**: seed/pack string mismatch; an issue number or `src/` path in pack text; stale manifest.
