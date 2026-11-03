# Implementation Plan: tracer-append routes through the owned Mission checkout

**Branch**: `kitty/mission-tracer-append-owned-checkout-01M6G9FW` | **Date**: 2026-11-03 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/tracer-append-owned-checkout-01M6G9FW/spec.md`

## Summary

`spec-kitty agent tracer-append` is the only writer of a Mission's tracer files, and it is
the only Mission-scoped command that ignores the owned-checkout fact. It resolves
`locate_project_root()` → `get_main_repo_root()` unconditionally
(`src/specify_cli/cli/commands/agent/tracer_append.py:105-125`), then builds its protection
policy and target branch from that root. From inside an owned `single_branch` checkout `P`
(the case in #7081), the repository root `R` is on protected `main`, so the tag commit is
refused `PROTECTED_BRANCH_REFUSED` and the staged `traces/<category>.md` is left untracked
in `R`.

The fix reuses the CLI surface every other owned-capable command already has:

1. `tracer-append` declares `--owned-checkout` with the shared `OwnedCheckoutOption`
   (G5-exempt) and validates it once through `resolve_owned_or_refuse`, which also performs
   flagless adoption when the invocation is made from an owned checkout.
2. When a fact is present, the command replaces all four root-derived inputs with the
   fact's own: `repo_root = owned.owned_root`, `target_branch = owned.write_branch`,
   `policy = ProtectionPolicy.resolve_for_owned(owned, mission)`, and it passes
   `owned=owned` down to the writer.
3. `append_tracer_finding` gains an `owned` keyword and threads it into
   `write_artifact(..., owned=...)` and into the two `placement_seam(...)` reads/writes it
   already performs, so the tracer surface is resolved from the same fact rather than
   re-derived from a root.
4. A refusal from the minter reaches the operator as the canonical C2 owned refusal and
   exits before `append_tracer_finding` is called, so no staging, no coordination-surface
   materialisation and no file touch happens on an invalid target.

The non-owned path is unchanged: with no flag and no adoptable checkout, the fact is
`None` and every input is what it is today.

## Technical Context

**Language/Version**: Python 3.12 (project floor 3.11, `requires-python >=3.11` in `pyproject.toml`)
**Primary Dependencies**: typer (CLI), rich (rendering), pytest; no new dependency
**Storage**: git checkouts and the Mission's `kitty-specs/<slug>/traces/` files — N/A for a database
**Testing**: pytest targeted fast suites (`tests/specify_cli/cli/commands/agent/`, `tests/retrospective/`) plus `tests/architectural/test_owned_checkout_single_authority.py`; a two-checkout fixture driving the real `tracer-append` entry point
**Target Platform**: CLI on Linux/macOS developer hosts and CI
**Project Type**: single project (Python package `specify_cli` over the `mission_runtime` / `coordination` seams)
**Performance Goals**: one ownership validation per invocation (`resolve_owned_or_refuse`); no additional git subprocess beyond what the owned resolver already runs
**Constraints**: `--owned-checkout` declared only via `OwnedCheckoutOption` + `resolve_owned_or_refuse`; lifecycle topology set only (`LIFECYCLE_OWNED_TOPOLOGIES`); non-owned payloads byte-identical; no full heavy suites locally
**Scale/Scope**: two production modules (`tracer_append.py`, `tracer_writer.py`), one new test module, ~60 lines of production change

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
| --- | --- |
| Single canonical authority | Ownership is validated only through `specify_cli/cli/commands/_owned_checkout.py` (`resolve_owned_or_refuse`); protection through `ProtectionPolicy.resolve_for_owned`. No second resolver, no hand-rolled claim parsing. |
| Architectural alignment / module seams | The CLI edge stays in `cli/commands/agent/`; the write continues through the existing `write_artifact` seam, which already accepts `owned`. Nothing new is constructed outside the sanctioned layers. |
| ATDD-first / DIRECTIVE_034 | A failing test drives the real `tracer-append` command on a two-checkout fixture before the flag exists, and a refusal test asserts zero writes before the refusal path is wired. |
| Terminology canon | Uses the charter vocabulary: owned checkout, repository root, Mission branch, coordination surface. No retired naming. |
| Standing order 2 (campsite) | Removes `append_tracer_finding`'s stated "has no owned parameter" limitation in the same change that needs it, rather than adding a parallel path. |
| Standing order 5 (no shrink-only allowlist) | Zero new exclusions in `test_owned_checkout_single_authority.py`; the allowlist stays empty. |
| `NO_FULL_HEAVY_SUITES_IN_MISSION` | Validation = targeted fast suites + the architectural gates + the new tests; CI owns the full matrix. |
| DIRECTIVE_024 locality | Edits stay at the two call sites the defect names; no opportunistic refactor of the tracer writer's merge or outcome rendering. |

No violations; `Complexity Tracking` stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/tracer-append-owned-checkout-01M6G9FW/
├── plan.md              # This file
├── research.md          # Phase 0: discovery of the owned CLI seam and the two call sites
├── data-model.md        # Phase 1: the inputs that move from root-derived to fact-derived
├── quickstart.md        # Phase 1: how to verify the delivered behaviour by hand
├── contracts/
│   └── tracer-append-owned-selector.md  # the CLI contract this mission pins
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/
├── specify_cli/
│   ├── cli/commands/
│   │   ├── _owned_checkout.py                   # unchanged: the one owned CLI seam
│   │   └── agent/tracer_append.py               # + --owned-checkout; fact-derived inputs; owned= to writer
│   └── retrospective/tracer_writer.py           # + owned keyword, threaded into write_artifact and placement_seam
└── (no other production change)

tests/
├── specify_cli/cli/commands/agent/
│   └── test_tracer_append_owned_checkout_7081.py   # new: red-first owned routing + refusal tests
├── specify_cli/cli/commands/test_owned_refusal_format_unified.py  # existing unified-refusal ratchet (must stay green)
└── architectural/test_owned_checkout_single_authority.py          # empty allowlist (must stay green)
```

**Structure Decision**: single project. The change follows the existing CLI → writer →
coordination-seam layering; the CLI owns validation, the writer owns the write, and the
seam (unchanged) owns placement. No new module or package tree is introduced.

## Complexity Tracking

*No Charter Check violations — this section is intentionally empty.*

## Implementation Concern Map

### IC-01 — CLI: own the fact before selecting the write surface

- **Purpose**: Make `tracer-append` resolve the owned Mission fact (explicit flag or
  flagless adoption) before it computes any write input, and refuse typed before writing.
- **Relevant requirements**: FR-001, FR-002, FR-004, C-001, C-002, C-003
- **Affected surfaces**: `src/specify_cli/cli/commands/agent/tracer_append.py`
- **Sequencing/depends-on**: none
- **Risks**: liveness of the existing error branches — the owned refusal must consume its
  own exit path without swallowing the writer's structured refusals that follow.

### IC-02 — Writer: thread the fact into the seam

- **Purpose**: Let the tracer writer accept the validated fact and use it for the
  placement reads/writes and the `write_artifact` call, instead of relying on the root.
- **Relevant requirements**: FR-003, FR-006, FR-005
- **Affected surfaces**: `src/specify_cli/retrospective/tracer_writer.py`
  (`append_tracer_finding`, `_local_staging_path`, `_read_current_coord_content`)
- **Sequencing/depends-on**: IC-01 (the CLI is the only caller that passes the fact)
- **Risks**: the keyword must default to `None` so the writer's other callers and the
  non-owned CLI path stay byte-identical; the `#4959` fail-closed arms must not change.
