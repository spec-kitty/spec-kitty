# Tasks Action — Governance Guidelines

These guidelines govern the quality and correctness standards for work-package decomposition in the software-dev mission. They are injected at runtime via the charter context bootstrap.

---

## Core Authorship Rules

- Use repo-root-relative paths (e.g. `src/...`, `tests/...`) when referencing files, directories, and owned surfaces in WP frontmatter — these must match the repo-root-relative form the ownership validator accepts, not host-machine or worktree-prefixed paths.
- ERROR on dependency cycles, unresolved spec/plan references, or tasks that exceed the size guidance — do not silently generate a degraded plan.
- Mark `[NEEDS CLARIFICATION: …]` only when the user deliberately postpones a decision; resolve every other ambiguity against spec.md and plan.md before writing tasks.

---

## Charter Compliance

- Respect locality-of-change (DIRECTIVE_024): each WP must declare a coherent owned-files set and avoid editing surfaces owned by sibling WPs.
- Respect specification-fidelity (DIRECTIVE_010): every task must trace back to a requirement (`FR-###`, `NFR-###`, `C-###`) or a locked plan decision; do not invent scope.
- Document decomposition rationale via the ADR-drafting and problem-decomposition tactics when a structural choice is non-obvious.

---

## Subtask Granularity

- Aim for 3–7 subtasks per WP and 200–500 lines per WP prompt.
- Prefer splitting an oversized WP over padding a small one; prefer merging trivially short WPs over inflating them with unnecessary overhead.
- Each subtask must name a concrete deliverable (file, test, validation step) — not a phase of thought.

---

## Dependency Hygiene

- Every WP frontmatter declares an explicit `dependencies:` list (empty list allowed for roots).
- No cycles. `spec-kitty agent mission finalize-tasks` validates the DAG and will refuse to commit a cyclic plan.
- A WP must not depend on a sibling whose owned files it also edits — that is a decomposition smell to fix, not annotate.

---

## Phase Discipline

- This action produces `kitty-specs/<mission>/tasks.md` and `kitty-specs/<mission>/tasks/WP##*.md`. It does NOT begin implementation, create worktrees, or move WP status beyond `planned`.
- After tasks generation, hand off to `spec-kitty agent mission finalize-tasks` for dependency validation and lane assignment, then to `/spec-kitty.implement` for execution.
