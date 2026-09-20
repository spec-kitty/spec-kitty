# Implementation Plan: Charter Activation Catalog Coherence

**Branch**: `issue-4785-charter-catalog-coherence` | **Date**: 2026-09-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/charter-catalog-coherence-01M2XQQF/spec.md`

## Summary

Close four charter-activation tooling gaps (issue #4785) so activating a built-in
directive keeps the derived `catalog.references` coherent, worktree-safe, and complete
**by construction**. The unifying insight: `catalog.references` has exactly ONE compiler
authority — `compile_charter` / `write_compiled_charter` in
`src/charter/activation/compiler.py` — and `charter activate` is the one activation
surface that never calls it. The fix is disciplined routing through that single authority
(never a second/minimal writer), plus a worktree-safety boundary that reuses the kernel
`git_topology` probe, a corrected fresh-project gate, corrected remediation guidance, and
a loader-parity fix so recompiled summaries are complete and deterministic.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml (existing) — **no new dependency added or upgraded** (supply-chain review N/A this mission)
**Storage**: YAML charter store — `.kittify/charter/charter.yaml` (derived `catalog.references` + authored sections)
**Testing**: pytest — `tests/charter/`, `tests/doctrine/`, `tests/specify_cli/cli/commands/charter/`, `tests/specify_cli/charter_runtime/`
**Target Platform**: Cross-platform CLI (Linux / macOS / Windows 10+)
**Project Type**: single (CLI + library)
**Performance Goals**: recompile-on-activate within the CLI budget; the measured end-to-end recompile time is recorded (target < 2 s) — NFR-001
**Constraints**: single catalog authority (C-001); do NOT change shared `find_repo_root`/`get_main_repo_root` (C-002); reuse kernel `git_topology`, no 4th root-resolution authority (C-003); reject minimal-writer design (C-004); authored sections + `charter.md` byte-identical (NFR-002); deterministic catalog ordering (NFR-005)
**Scale/Scope**: ~254 `catalog.references` entries; 37 directives across built-in + project/org DRG layers; 5 charter write commands (activate/deactivate/generate/synthesize/resynthesize)

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** (Governing Principle; DIRECTIVE_044). ✅ The plan routes
  every catalog write through the one `compile_charter`/`write_compiled_charter` authority
  and explicitly forbids a second/minimal writer (C-001/C-004). It also deletes the dead
  parallel `_build_references_from_yaml`.
- **Architectural alignment** (DIRECTIVE_001). ✅ Reuses the kernel `git_topology` probe
  rather than adding a fourth root-resolution seam; the worktree policy lives at the charter
  command boundary, leaving the shared `find_repo_root` untouched (respects module seams).
- **ATDD-first / red-first** (C-011, DIRECTIVE_041/034). ✅ Each WP lands an issue-pinned
  `@pytest.mark.regression` repro that is RED through the pre-existing entry point before the
  fix (NFR-004); transitional repros become focused unit tests after.
- **Campsite cleaning** (DIRECTIVE_025). ✅ WP04 removes the dead reference-builder it sits
  next to (domain-matched, behavior-preserving).
- **Terminology canon** (Mission not Feature). ✅ No user-facing `feature*` identifiers added.
- **No version numbers in scope** (DIRECTIVE_045). ✅ No `pyproject.toml` version bump; this
  is a bug-fix mission touching no `__init__.py` public surface version.

No violations. Complexity Tracking table not required.

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-catalog-coherence-01M2XQQF/
├── plan.md              # This file
├── research.md          # Phase 0 output (grounding-squad synthesis + decisions)
├── data-model.md        # Phase 1 output (charter store entities + derived/authored boundary)
├── quickstart.md        # Phase 1 output (how to reproduce + verify each finding)
├── contracts/           # Phase 1 output (behavior contracts per finding)
├── tracer-*.md          # Mission tracer files (tooling-friction / approach / design-decisions)
└── tasks.md             # Phase 2 output (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/charter/activation/
├── compiler.py                 # SOLE catalog authority: compile_charter / write_compiled_charter
│                               #   _build_references_from_service / _render_kind_references
│                               #   (WP04: loader-parity + determinism; delete dead _build_references_from_yaml)
├── consistency_check.py        # coherence guard producing reference_id_divergences + suggestion string (WP01)
├── pack_manager.py             # activate()/deactivate() config-only writes (called by CLI)
└── charter_yaml_io.py          # single charter.yaml section writer (leave intact)

src/specify_cli/cli/commands/charter/
├── activate.py                 # activate_cmd + run_full_synthesize + RESYNTHESIZE_HELP (WP01, WP02)
├── deactivate.py               # deactivate_cmd (WP01, WP02)
├── generate.py                 # find_repo_root call site + _is_inside_git_worktree (WP02)
├── synthesize.py               # fresh-project short-circuit predicate (WP03); find_repo_root call site (WP02)
├── _synthesis.py               # _has_generated_artifacts signal (WP03)
├── resynthesize.py             # find_repo_root call site (WP02)
└── _charter_write_root.py      # NEW shared worktree-safe root resolver via kernel/git_topology (WP02)

src/kernel/
└── git_topology.py             # canonical git probe (REUSE; not modified)

tests/
├── charter/                    # test_compiler*, test_consistency_check (WP01, WP04)
├── doctrine/                   # test_activation_parity_guard (WP01)
├── specify_cli/cli/commands/charter/  # activate/synthesize/resynthesize CLI tests (WP01, WP02, WP03)
└── specify_cli/charter_runtime/       # test_references_parity_refresh, test_boundary_heal (WP01, WP04)
```

**Structure Decision**: Single-project layout. Changes are confined to the charter
activation library (`src/charter/activation/`) and the charter CLI command surface
(`src/specify_cli/cli/commands/charter/`), plus a new small worktree-safe root helper
that delegates to the existing kernel `git_topology`. No new top-level modules or packages.

## Parallel Work Analysis

### Dependency Graph

```
WP04 (compiler: completeness + determinism + campsite)   ── foundation ──┐
                                                                          ▼
WP01 (activate/deactivate recompile-by-default + remediation strings)  ← depends on WP04
                                                                          │  (activate's DEFAULT recompile must be
                                                                          │   complete + stable, or it re-introduces
                                                                          │   placeholders / churn)
WP03 (synthesize fresh-project gate)  ── independent, small ──
WP02 (worktree-safe charter-write boundary)  ── independent, cross-cutting ──
```

- **WP04 is the foundation** and lands first: it makes a full recompile complete (no silent
  placeholders) and diff-stable, which WP01's recompile-by-default depends on.
- **WP01 depends on WP04** (semantic dependency, not merely file overlap).
- **WP02 and WP03 are independent** of the catalog-content work; they can proceed in parallel.

### Lane / write-scope expectation

Lanes collapse by owned-file overlap (finalize-tasks). Expected:
- **WP04** owns `compiler.py` (disjoint) → its own lane.
- **WP01 / WP02 / WP03** overlap on `activate.py` / `synthesize.py` → likely one shared lane,
  implemented sequentially (WP01 → WP03 → WP02 order within the lane is fine).
- Because WP01 (CLI lane) depends on WP04 (compiler lane), the compiler lane merges first;
  before implementing WP01's default recompile, merge the WP04 lane branch into the CLI lane
  (dependent-lane reconciliation). This will be validated against `lanes_preview` at
  `finalize-tasks --validate-only`.

## Implementation Concern Map

| WP | Finding | Concern | Owned files | Red-first repro (RED before fix) |
|----|---------|---------|-------------|----------------------------------|
| WP04 | F4b + F4a + campsite | Recompiled catalog resolves real summaries for every directive in the authoritative bundled enumeration; genuine misses → diagnostics not silent placeholders; deterministic entry order; delete dead `_build_references_from_yaml` | `src/charter/activation/compiler.py` | activating/compiling a store leaves ≥1 directive as `Definition unavailable` though it has a bundled definition; a second recompile reorders/churns the `catalog.references` section |
| WP01 | F1 + F2-strings | `activate`/`deactivate` recompile the catalog by default via `compile_charter(from_interview=False)`; `--no-compile` opt-out; coherence-guard suggestion + `RESYNTHESIZE_HELP` name `generate`, never `synthesize` | `src/specify_cli/cli/commands/charter/activate.py`, `deactivate.py`, `src/charter/activation/consistency_check.py` | `charter activate <built-in directive>` reds `test_this_project_charter_pack_is_coherent`; the guard suggestion string names `synthesize` |
| WP03 | F2-core | `synthesize` classifies an established store (compiled catalog present) as non-fresh; no fresh-project short-circuit that skips real work | `src/specify_cli/cli/commands/charter/synthesize.py`, `_synthesis.py` | `charter synthesize` on a store with `charter.yaml` but no `generated/` prints "fresh project" and short-circuits |
| WP02 | F3 | Every charter write command fails closed (non-zero + "use a repository-root checkout or dedicated clone") when invoked from a linked worktree; retire the `chdir` hack + split-brain; reuse kernel `git_topology` | NEW `src/specify_cli/cli/commands/charter/_charter_write_root.py`, `generate.py`, `synthesize.py`, `resynthesize.py`, `activate.py` | a charter write command run from a linked worktree modifies the PRIMARY checkout's `.kittify/charter/` |

## Complexity Tracking

*No Charter Check violations — table intentionally empty.*

## Phase 0 / Phase 1 Outputs

- Phase 0 → `research.md` (grounding-squad synthesis, the four root causes, the settled
  design decisions, adversarial-evidence dispositions).
- Phase 1 → `data-model.md` (charter store entities + derived/authored boundary),
  `contracts/` (one behavior contract per finding), `quickstart.md` (repro + verify).

## Branch Contract (restated)

- Current branch at plan start: `issue-4785-charter-catalog-coherence`
- Planning/base branch: `issue-4785-charter-catalog-coherence`
- Final merge target for completed changes: `main` (via a non-draft PR; the operator merges)
- `branch_matches_target`: true (planning base = current branch)
