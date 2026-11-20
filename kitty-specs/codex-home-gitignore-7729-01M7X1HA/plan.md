# Implementation Plan: Keep a project-local Codex home ignored after agent-gitignore narrowing (#7729)

**Branch**: `fix/7729-codex-home-gitignore` | **Date**: 2026-11-20 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/codex-home-gitignore-7729-01M7X1HA/spec.md`
**Grounding**: [research/code-grounding.md](research/code-grounding.md)

## Summary

Two layers, because `.codex/config.toml` means two different things:

1. **Committed layer (every clone, deterministic).** Widen the Codex rows that
   `agent_ignore_entries` returns with Codex home state that is never team
   configuration. The rc8 migration and every later `upgrade` refresh write the
   block from that live list, so the shipped rc8 module stays untouched.
2. **Clone-local layer (per clone).** A new migration,
   `4.0.0rc9_exclude_project_local_codex_home` (`clone_local_effect = True`),
   runs in every clone, including clones that pulled the narrowed rules. When
   git shows files from a `.codex/` that is a Codex home (home markers present,
   or `CODEX_HOME` points at it), it adds `.codex/` to the clone's
   `.git/info/exclude`. In every clone it lists the untracked files git shows in
   the agent folders the old whole-folder rules hid.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: existing `kernel.git` (`status_entries`), `specify_cli.core.git_ops` (`exclude_from_git_index`, `is_git_repo`)
**Storage**: `.gitignore` (committed), `.git/info/exclude` (clone-local), migration ledger partitions
**Testing**: pytest; real `git init` repositories; two real clones for the pulled-clone case; `MigrationRunner(...).upgrade("4.0.0rc9")` with a ledger that settles every other migration (seam from `test_gitignore_backfills_superseded_6589.py`)
**Target Platform**: Linux, macOS, Windows (paths compared as POSIX strings from git)
**Project Type**: single
**Performance Goals**: no added git call when the project has no agent folder; at most 2 otherwise (NFR-002)
**Constraints**: C-001..C-004 (shipped rc8 module byte-identical; deterministic committed block; nothing deleted or untracked; ledger model)
**Scale/Scope**: 3 source files touched or added, 1 manifest line, tests, changelog fragment

## Charter Check

- **Standing Order 4 (bug-fix discipline)**: the reproduction exists on `main` (`p0_repro(issue=7729)`). It is extended red-first (drive the real upgrade runner; add the pulled-clone half) in a commit before the fix, then its marker is removed. PASS.
- **DIRECTIVE_044 (canonical sources, shipped migrations immutable)**: the rc8 module is not edited; the new behaviour is a new migration with an order-manifest entry. PASS.
- **Single canonical authority**: Codex-home knowledge lives in one new module (`agent_utils/codex_home.py`) that both the entry list and the migration read. PASS.
- **User Customization Preservation**: only adds a local exclude line and warns; never deletes or untracks. PASS.
- **NO_FULL_HEAVY_SUITES_IN_MISSION**: targeted tests plus named architectural gate files only. PASS.
- **Terminology**: Mission; `consolidate` is local-only. PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/codex-home-gitignore-7729-01M7X1HA/
├── spec.md
├── plan.md
├── research/code-grounding.md
├── tracers/            # tooling-friction, approach, design-decisions
└── tasks/
```

### Source Code (repository root)

```
src/specify_cli/agent_utils/codex_home.py                  # NEW: Codex home layout + detection
src/specify_cli/agent_utils/ignore_entries.py              # widen the committed Codex rows
src/specify_cli/upgrade/migrations/m_4_0_0rc9_exclude_project_local_codex_home.py   # NEW, clone-local
src/specify_cli/upgrade/migrations/order_manifest.txt      # one appended line
tests/specify_cli/agent_utils/test_codex_home.py           # NEW
tests/specify_cli/agent_utils/test_ignore_entries.py       # committed-block coverage
tests/specify_cli/upgrade/migrations/test_m_4_0_0rc9_exclude_project_local_codex_home.py  # NEW
tests/specify_cli/upgrade/migrations/test_p0_repro_7729_codex_home_exposed.py   # extended, marker removed
docs/changelog/unreleased/7729-codex-home-gitignore.fixed.md
```

**Structure Decision**: single project; the new module sits beside `ignore_entries.py` (the agent-folder ignore authority) so the migration and the block share one Codex layout.

## Implementation Concern Map

### IC-01 — Red-first reproduction of both halves

- **Purpose**: pin the defect through the real upgrade entry point, including the pulled clone.
- **Relevant requirements**: FR-006, FR-003, FR-004, FR-005
- **Affected surfaces**: `tests/specify_cli/upgrade/migrations/test_p0_repro_7729_codex_home_exposed.py`
- **Sequencing/depends-on**: none (first commit)
- **Risks**: running the full registry on a minimal fixture can trip unrelated migrations; settle every other migration in the ledger first (proven seam).

### IC-02 — Codex home layout and the committed block

- **Purpose**: one definition of Codex home state; the committed block ignores everything in it except `config.toml`.
- **Relevant requirements**: FR-001, FR-002
- **Affected surfaces**: `agent_utils/codex_home.py`, `agent_utils/ignore_entries.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: over-ignoring a team file. `rules/default.rules` is Codex's per-user approval file; team rules use other names. `config.toml` is deliberately left out (test pin kept).

### IC-03 — Clone-local exclusion and every-clone warning

- **Purpose**: protect a Codex-home `.codex/` per clone and tell each clone what the narrowing exposed.
- **Relevant requirements**: FR-003, FR-004, FR-005, FR-007, NFR-001, NFR-002
- **Affected surfaces**: new migration module, `order_manifest.txt`
- **Sequencing/depends-on**: IC-02
- **Risks**: noise in fresh projects (one notice per clone, only when untracked agent-folder files exist; a success settles it); an exclude write that silently fails (re-read git status after writing).
