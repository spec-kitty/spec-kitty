# Implementation Plan: Declaration-first repo_root/branch resolution entry (Increment 1)

**Branch**: `kitty/mission-declaration-first-repo-root-resolution-01M4TB21` | **Date**: 2026-10-13 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/declaration-first-repo-root-resolution-01M4TB21/spec.md`; grounding `research/code-grounding.md`; ADR `docs/adr/4.x/2026-10-10-1`.

## Summary

Introduce **one typed, declaration-first producer** of a mission-scoped command's
`(repo_root, target_branch)` target at the command-entry layer (`specify_cli`), built on
the existing public resolvers. The `repo_root` half collapses worktree→primary
(already-canonical, CWD-invariant); the `target_branch` half is **declaration-first**
(`meta.json` `target_branch`) with an **explicit, validated, provenance-marked
primary-branch fallback that never reads the ambient checked-out HEAD**. Route a bounded,
named set of mission-scoped command-entry seeds through it; fold the "never `Path.cwd()`"
assertions at those sites into the typed call so the invariant holds by construction;
prove the behaviour correction red-first; preserve #3128/#3328 fail-closed; file-and-link
the deferred sites.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: stdlib (`pathlib`, `dataclasses`, `enum`); existing
`specify_cli.core.paths` + `specify_cli.core.git_ops` resolvers; `mission_runtime`
placement seam (consumed, not modified).
**Storage**: reads `meta.json` (`target_branch`) via the fail-closed reader
`read_target_branch_from_meta`. No new persisted state.
**Testing**: pytest unit tests over `tmp_path` git fixtures (mirror
`test_lifted_cli_project_root_resolution.py`'s worktree-fixture shape); red-first
behaviour test; negative tests over `enforce_checkout_identity` / `resolve_checkout_identity`.
**Target Platform**: Linux/macOS/Windows CLI.
**Project Type**: single project (CLI library).
**Performance Goals**: ≤ one extra `meta.json` read on the resolution path; CLI < 2 s.
**Constraints**: module chain `… <- mission_runtime <- specify_cli`; no loosening of
`test_no_write_side_rederivation.py`; ruff/mypy clean; complexity ≤ 15.
**Scale/Scope**: one new `specify_cli.core` module + a bounded set of routed command-entry
sites.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** (✓): the entry is ONE producer built on the existing
  single-authority readers (`read_target_branch_from_meta`, `resolve_canonical_root`/
  `get_main_repo_root`, `resolve_primary_branch`); it reconciles/extends, it does not add a
  second authority. It is the dual the ADR calls for.
- **Architectural alignment** (✓): lives in `specify_cli`, imports only down-chain; no
  package-set or layer-rule change (NFR-001). The `mission_runtime` write-handle is the
  deferred Increment 2.
- **ATDD / red-first** (✓): the behaviour correction is committed test-first (FR-006);
  the typed entry's branches are unit-tested directly (SC-003).
- **Architectural gate discipline** (✓): no new gate, no allowlist addition; the entry is
  itself the constructed boundary the ADR Confirmation clause + Standing Order #5 ask for;
  `test_no_write_side_rederivation.py` stays green by construction (NFR-002).
- **Terminology canon** (✓): `primary`/`merge`/`routing` senses named in code + prose
  (C-004); Mission (not Feature).
- **Tidy-first sequencing** (✓): behaviour-preserving enabler commits (entry, routing,
  assertion fold) precede the red-first behaviour-correcting change.
- **No full heavy-suite runs** (✓): calibrated blast radius only; CI owns the full suites.

No Charter violation requires a Complexity-Tracking entry.

## Project Structure

### Documentation (this mission)

```
kitty-specs/declaration-first-repo-root-resolution-01M4TB21/
├── spec.md
├── plan.md                       # this file
├── research/code-grounding.md    # grounding (committed pre-spec)
├── tracers/{approach,design-decisions,tooling-friction}.md
└── tasks.md                      # Phase 2 output (spec-kitty tasks / finalize-tasks)
```

### Source Code (repository root)

```
src/specify_cli/core/
└── command_target.py             # NEW: the typed declaration-first entry

src/specify_cli/cli/commands/     # routed command-entry sites (bounded set; see IC-3)
  (+ specify_cli/cli/helpers.py if the repo-root half composes with get_project_root_or_exit)

tests/specify_cli/core/
└── test_command_target.py        # NEW: unit coverage of every resolver branch
tests/specify_cli/cli/            # red-first behaviour test + per-routed-site tests
tests/specify_cli/workspace/ , tests/mission_runtime/   # negative fail-closed tests (#3128/#3328)
```

**Structure Decision**: Single project. The entry is a new `specify_cli.core` module
(it depends on `core.paths`/`core.git_ops`, so it cannot live in `mission_runtime`
without inverting the chain — see design-decisions tracer D1). Routed sites are existing
`cli/commands/**` modules.

## Design: the typed entry (concrete)

```python
# src/specify_cli/core/command_target.py  (shape — final names settled in implement)
class TargetProvenance(Enum):
    DECLARATION = "declaration"              # target_branch read from meta.json
    VALIDATED_FALLBACK = "validated_fallback"  # explicit configured-primary fallback

@dataclass(frozen=True)
class CommandRepoTarget:
    repo_root: Path          # canonical primary root (worktree -> primary collapsed)
    target_branch: str       # declaration-first resolved branch
    provenance: TargetProvenance

def resolve_command_repo_target(
    mission_slug: str, *, cwd: Path | None = None, repo_root: Path | None = None,
) -> CommandRepoTarget: ...
```

Resolution contract (the invariant, held **by construction**):
1. **repo_root** — if `repo_root` is passed, `get_main_repo_root(repo_root)`; else
   `resolve_canonical_root(cwd or Path.cwd())`. The single sanctioned ambient read is the
   `cwd or Path.cwd()` default **here, once**, documented as the one boundary; the result
   is always the canonical primary (worktree→primary collapse), never a raw worktree.
2. **target_branch** — `read_target_branch_from_meta(repo_root/"kitty-specs"/mission_slug)`;
   if present → `provenance=DECLARATION`. If absent → `resolve_primary_branch(repo_root,
   bias=False)` → `provenance=VALIDATED_FALLBACK`. The entry **never reads the ambient
   checked-out HEAD** as the target (no `bias=True`, no `get_current_branch` as target) —
   so "the ambient branch never wins when it disagrees with the declaration" is true by
   construction, not by a downstream guard.
3. **fail-closed** — a corrupt `meta.json` propagates `MissionMetaReadError`; a cwd with
   no git marker propagates `WorkspaceRootNotFound`. No silent primary default.

Why it keeps `test_no_write_side_rederivation.py` green (NFR-002): it resolves *branch
strings* only (constructs no `CommitTarget`/`safe_commit`, so the AST grammar never
fires) and adds **no** `get_current_branch(...) or <fallback>` / `coord_branch or current`
token grammar — it routes through the existing public resolvers, exactly the fix the
ratchet prescribes.

## Implementation Concern Map

> Concerns, not work packages. `spec-kitty tasks` translates these into WPs.

- **IC-1 — The typed value + resolver** (FR-001/002/003, NFR-001/002/003/004). The new
  `command_target.py`: the frozen value, the provenance enum, the resolver composed on the
  public readers. Pure, directly unit-testable. *Tidy-first enabler.*
- **IC-2 — Route the bounded command-entry seeds + fold assertions** (FR-004/005, C-004).
  Selection criteria (applied per-site at implement, after reading each): route a site iff
  (a) it is **mission-scoped** (operates on a named/stored Mission, not project-global),
  (b) it today seeds `repo_root`/branch from ambient location, (c) routing is
  behaviour-preserving **except** in the ambient-disagreement case (the intended
  correction), and (d) it is **not** a consolidation/branch-integration site, **not** the
  `implement_claim` #2453-deferred ratchet-allowlisted guard, **not** create-time, **not**
  an honest-invocation-identity input. Candidate set (from the similar-surfaces squad,
  C.1): `cli/commands/decision.py` prologues, `agent/issue_verdict.py:362`, `verify.py`,
  `context.py:96`, and the `specify_cli/mission.py` facade root seeds. Each routed site's
  hand-placed "never `Path.cwd()`" comment is replaced by the typed call. *Tidy-first
  enabler (behaviour-preserving at routed sites).*
- **IC-3 — Red-first behaviour correction + fail-closed preservation** (FR-006/007,
  C-002/C-003). One red-first test witnessing a routed mission-scoped command resolving to
  the declaration (not ambient) when they disagree; negative tests proving
  `enforce_checkout_identity` (#3128) and `resolve_checkout_identity` (#3328) still refuse,
  and that `get_status_read_root`'s worktree-preferring READ contract is untouched.
  *Behaviour-correcting change — committed test-first, AFTER the IC-1/IC-2 enablers.*
- **IC-4 — Deferred-scope hygiene** (FR-008). Name the filed-and-linked out-of-scope sites
  (merge-target `mission_accept_merge`, `implement_claim` #2453 guard, create-time,
  project-scoped, identity inputs) in the PR's Deferred section + a follow-up issue; Refs
  the still-open siblings #2802 and #5114 the entry forecloses.

## Rebase cadence

Onto the canonical remote's `main` after spec, after plan, after tasks (before
implement); thereafter only on a staleness notice from CI or the operator.

## Complexity Tracking

*No Charter Check violations — table intentionally empty.*
