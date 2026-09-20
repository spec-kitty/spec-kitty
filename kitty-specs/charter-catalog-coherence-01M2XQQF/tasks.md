# Tasks: Charter Activation Catalog Coherence (#4785)

**Mission**: charter-catalog-coherence-01M2XQQF
**Branch**: `issue-4785-charter-catalog-coherence` → merges to `main` via non-draft PR (operator merges)

WPs are partitioned by **file ownership** (no `owned_files` overlap) because the four findings
cross-cut the charter command files. Each WP lands an issue-pinned red-first regression.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first repro: placeholder summary + non-deterministic catalog recompile | WP01 | |
| T002 | Resolve DRG-surfaced directive ids to the canonical typed-repository key in `_render_kind_references` | WP01 | |
| T003 | Route genuinely-unresolved ids through `graph.unresolved` diagnostics (no silent placeholder) | WP01 | |
| T004 | Emit `catalog.references` entries in a canonical deterministic order (NFR-005) | WP01 | |
| T005 | Preserve `metadata.generated_at` when the catalog is byte-unchanged (NFR-002/FR-008) | WP01 | |
| T006 | Delete dead, uncalled `_build_references_from_yaml` (FR-009) | WP01 | |
| T007 | Extend compiler/parity-refresh tests to pin completeness + determinism | WP01 | |
| T008 | Red-first repro: charter write from a linked worktree mutates the PRIMARY checkout | WP02 | [P] |
| T009 | New `_charter_write_root.py`: worktree-safe root resolver via kernel `git_topology`, fail-closed on linked worktree, git-absent safe | WP02 | [P] |
| T010 | Unit tests: primary OK, linked-worktree fails closed, git-absent safe, cross-platform via monkeypatch | WP02 | [P] |
| T011 | Red-first repro: `activate <built-in directive>` reds the coherence guard | WP03 | |
| T012 | Route `activate` through `compile_charter(from_interview=False)` by default; `--no-compile` opt-out with explicit notice | WP03 | |
| T013 | Symmetric `deactivate` recompile | WP03 | |
| T014 | Wire the WP02 worktree guard into `activate`/`deactivate`; fix the `run_full_synthesize` chdir split-brain | WP03 | |
| T015 | Fix coherence-guard suggestion string (`consistency_check`) + `RESYNTHESIZE_HELP` to name `generate`, never `synthesize` | WP03 | |
| T016 | Reconcile pre-existing config-only-activation tests to the new default (C-006, enumerated) | WP03 | |
| T017 | Red-first repro: `synthesize` fresh-project short-circuit on an established store | WP04 | |
| T018 | Gate the fresh-project predicate on catalog emptiness, not `generated/` absence | WP04 | |
| T019 | Wire the WP02 worktree guard into `generate`/`synthesize`/`resynthesize` | WP04 | |
| T020 | Reconcile synthesize/resynthesize tests | WP04 | |

---

## WP01 — Catalog compiler: completeness, determinism, campsite (F4b/F4a)

**Priority**: P1 (foundation) · **Prompt**: [tasks/WP01-catalog-compiler-completeness.md](tasks/WP01-catalog-compiler-completeness.md)
**Goal**: A full recompile resolves real summaries for every directive with a bundled definition,
routes genuine misses to diagnostics (not silent placeholders), emits entries in a deterministic
canonical order, and preserves `generated_at` when the catalog is byte-unchanged. Delete the dead
reference-builder. **Foundation for WP03's recompile-by-default.**
**Independent test**: recompile leaves 0 `Definition unavailable` for directives in the typed
enumeration; a second recompile is a zero-line diff of `catalog.references`.
**Dependencies**: none. **Subtasks**: T001–T007.

## WP02 — Worktree-safe charter-write root helper (F3 core)

**Priority**: P1 (foundation) · **Prompt**: [tasks/WP02-worktree-safe-write-root.md](tasks/WP02-worktree-safe-write-root.md)
**Goal**: A single shared resolver (reusing kernel `git_topology`) that every charter write command
uses to fail closed when invoked from a linked worktree. Carries the tested worktree-detection logic.
**Independent test**: resolver returns the checkout root from a primary checkout; raises a fail-closed
error from a linked worktree; degrades safely when git is absent.
**Dependencies**: none. **Subtasks**: T008–T010.

## WP03 — Activate/deactivate coherent-by-construction + remediation (F1/F2-strings/F3-wiring)

**Priority**: P1 · **Prompt**: [tasks/WP03-activate-deactivate-recompile.md](tasks/WP03-activate-deactivate-recompile.md)
**Goal**: `activate`/`deactivate` recompile the catalog by default (via WP01's complete, deterministic
compiler), with a `--no-compile` opt-out; the coherence-guard suggestion + `RESYNTHESIZE_HELP` name
`generate`; the WP02 worktree guard is wired into both and the `run_full_synthesize` split-brain is fixed.
**Independent test**: `charter activate <built-in directive>` leaves the coherence guard GREEN.
**Dependencies**: WP01 (complete recompile), WP02 (worktree helper). **Subtasks**: T011–T016.

## WP04 — Synthesize fresh-gate + worktree wiring for generate/synthesize/resynthesize (F2-core/F3-wiring)

**Priority**: P2 · **Prompt**: [tasks/WP04-synthesize-freshgate-worktree.md](tasks/WP04-synthesize-freshgate-worktree.md)
**Goal**: `synthesize` no longer misclassifies an established store as fresh; `generate`/`synthesize`/
`resynthesize` fail closed from a linked worktree via the WP02 helper.
**Independent test**: `synthesize` on an established store with no `generated/` does not report "fresh".
**Dependencies**: WP02 (worktree helper). **Subtasks**: T017–T020.

---

## Dependency graph

```
WP01 (compiler)  ─┐
WP02 (helper)  ───┼─→ WP03 (activate/deactivate)   [needs WP01 + WP02]
                  └─→ WP04 (synthesize/generate)   [needs WP02]
```

## MVP scope

WP01 + WP03 deliver the reported blocker (activation coherent-by-construction with complete summaries).
WP02 + WP04 add worktree safety and the fresh-gate fix.
