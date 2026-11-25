# Mission Specification: One authority for committed orientation content

**Mission Branch**: `fix/5215-orientation-content-authority`
**Created**: 2026-11-20
**Status**: Draft
**Input**: #5215 — committed orientation blocks name the checkout directory instead of the recorded project, and neither upgrade nor `doctor tool-surfaces --fix` repairs them; the SessionStart hook shows the correct name, so the two disagree.

## Intent Summary (confirmed)

The discovery brief and three operator rulings (2026-11-20, recorded as resolved Decision Moments) are the confirmed intent:

- **Primary actor:** a developer whose project's recorded name (`project.slug`) differs from the name of the directory it is checked out in (a clone named `t3-pilot-local-agent-bus`, a fixture dir `dirname-differs`).
- **Trigger:** `spec-kitty upgrade`, `spec-kitty doctor tool-surfaces --fix`, `spec-kitty init`, or the SessionStart hook.
- **Outcome:** every committed orientation block names the recorded project and carries deterministic content; every repair surface converges on the same bytes; a wrong block at the current version is reported and repaired.
- **Invariant:** the directory name is never used as the project name in an orientation block.
- **Rulings:** (1) committed blocks carry deterministic health ("healthy"); only the live SessionStart hook shows live health. (2) A missing `project.slug` falls back to the git remote repository name, then "unknown". (3) No new migration, the shipped rc39 migration is not edited; content-aware staleness repairs existing projects through upgrade surface repair and `doctor --fix`. The untracked `dist/spec-kitty-plugins/` tree that `--fix` creates is out of scope (separate issue).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A wrong block at the current version is repaired (Priority: P1)

A project at the current CLI version has an orientation block that names the checkout directory. `doctor tool-surfaces` reports it as stale and `--fix` rewrites it to name the recorded project; `upgrade` does the same.

**Why this priority**: today the wrong block is reported `present`, so nothing ever repairs it (S1).

**Independent Test**: fixture project with `project.slug: local-agent-bus` in a directory named `dirname-differs` and a current-version block naming `dirname-differs`.

**Acceptance Scenarios**:

1. **Given** that fixture, **When** the tool-surface probe runs, **Then** the orientation surface is stale, not present.
2. **Given** that fixture, **When** `doctor tool-surfaces --fix` runs, **Then** the block names `local-agent-bus`.
3. **Given** that fixture, **When** `upgrade` surface repair runs, **Then** the block names `local-agent-bus`.

### User Story 2 - Upgrade and repair never write the directory name (Priority: P1)

A block stamped with an older version in a clone whose directory name differs from the project name is refreshed by `upgrade` and by `doctor --fix` to name the recorded project (S3, S4).

**Independent Test**: an older-version block; run each repair surface; inspect the written block.

**Acceptance Scenarios**:

1. **Given** an older-version block, **When** upgrade surface repair runs, **Then** the written block names the recorded project, not the directory.
2. **Given** an older-version block, **When** `doctor --fix` runs, **Then** the written block names the recorded project.
3. **Given** either repair, **When** the other repair runs afterwards, **Then** no bytes change (convergence).

### User Story 3 - The hook and the files agree (Priority: P2)

The SessionStart hook and the committed block name the same project; only the health indicator of the hook may differ, because the hook shows live health.

**Acceptance Scenarios**:

1. **Given** a project, **When** the hook output and the committed block are compared, **Then** they name the same project.
2. **Given** a newer CLI version is known to be available, **When** a committed block is written, **Then** it still carries "healthy" and no upgrade line, while the hook shows the upgrade line.

### Edge Cases

- `project.slug` missing, git remote present: the block names the remote repository name.
- `project.slug` missing, no remote: the block names "unknown", never the directory.
- Hand-edited managed block: still preserved, not overwritten (existing behaviour).
- Block written with live health ("upgrade-available") or pre-#5757 glyphs at the current version: converges once to the deterministic rendering, then stays unchanged on every later upgrade (no #2265 churn).
- Installed version unknown: committed content refuses (ValueError), as today.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One content authority | As a maintainer, I want one module to decide the committed orientation content so that every writer and checker uses the same bytes. | High | Open | [build] | no — S1/S3/S4 tests fail on the old split authority |
| FR-002 | Identity slug, never dirname | As a developer, I want the committed block to name `project.slug`, else the repository name of the project's own `origin` remote (only when the project root is itself a git repository or worktree; a project nested in another repository shows "unknown"), else "unknown", so that it never names the checkout directory. | High | Open | [build] | no — fixture dir name differs from slug and remote |
| FR-003 | Deterministic committed health | As a developer, I want committed blocks to carry "healthy" with no upgrade line so that live state never leaks into committed files. | High | Open | [build] | no — test caches a newer version and asserts no upgrade line |
| FR-004 | Content-aware staleness | As a developer, I want a block whose content differs from the expected rendering to be reported stale so that doctor and upgrade repair it. | High | Open | [build] | no — same-version wrong-slug fixture is stale; a correct block is present (positive control) |
| FR-005 | Writer rewrites a differing canonical block | As a developer, I want the writer to rewrite a canonical block whose bytes differ from the expected rendering so that repair actually changes it. | High | Open | [build] | no — today the version shortcut leaves it untouched |
| FR-006 | Repair surfaces converge | As a developer, I want upgrade surface repair and `doctor --fix` to produce identical bytes, with a second pass changing nothing. | High | Open | [build] | no — byte comparison of both paths plus idempotence |
| FR-007 | Hook shows live health with the same slug | As a developer, I want the SessionStart hook to keep live health and to name the same project as the files. | Medium | Open | [ratchet] | no — paired with FR-003 on the same fixture |
| FR-008 | One applicability predicate | As a maintainer, I want the manager and the provider to select orientation-writable harnesses with one predicate. | Medium | Open | [build] | yes — refactor; guarded by existing provider/manager tests |
| FR-009 | Hand-edited blocks preserved | As a developer, I want a hand-edited managed block to stay preserved. | Medium | Open | [ratchet] | yes — existing preserve tests pin it |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No churn | A project whose block equals the expected rendering sees 0 changed bytes across 2 consecutive upgrade or `--fix` runs. | Reliability | High | Open |
| NFR-002 | Quality gates | ruff, `ruff format --check --force-exclude` and mypy report 0 issues on changed files. | Maintainability | High | Open |
| NFR-003 | Probe cost | Probing an orientation surface spawns at most 1 `git` subprocess, and none when `project.slug` is recorded. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No new migration | No new migration; the shipped rc39 and 3.3.0 session-presence migration modules are not edited. | Technical | High | Open |
| C-002 | No layer change | The authority lives in `specify_cli`; no layer rule, package set or gate changes. | Technical | High | Open |
| C-003 | Scope | Fold set is #5215 plus the `manager.update(dry_run)` variant; #2344, #6472, #4927 and the `dist/spec-kitty-plugins/` issue are out of scope. | Business | High | Open |
| C-004 | History stays green | Tests for #4706, #4707, #4782, #2265, #5757 and #4893 stay green. | Technical | High | Open |

### Key Entities

- **Expected orientation**: the committed orientation content for a project — installed version, project name, deterministic health, invocation line.
- **Live orientation**: what the SessionStart hook prints — same project name, live health.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the #5215 reproduction fixture, 0 orientation blocks name the directory after `upgrade` or after `doctor --fix` (today: 1). — [build] · no-op passable: no
- **SC-002**: Upgrade repair and `doctor --fix` produce byte-identical blocks in 100% of the acceptance fixtures. — [build] · no-op passable: no
- **SC-003**: The hook output and the committed block name the same project in 100% of the acceptance fixtures. — [build] · no-op passable: no

## Assumptions

- Existing blocks with live health, legacy glyphs or a directory name are rewritten once by the next upgrade (an auto-committed change); this is the intended convergence and is called out in the changelog.
