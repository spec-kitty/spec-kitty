# Mission Specification: Owned Research Placement Containment

**Mission Branch**: `issue-5882-owned-research-placement-and-plan`
**Created**: 2026-10-12
**Status**: Draft
**Input**: Issue #5882 — "Owned Mission research redirects into dirty primary; specify-to-plan lacks an owned authoring path"

## User Scenarios & Testing *(mandatory)*

An operator or agent harness runs a single-branch Mission from a linked **owned
checkout** (the isolation pattern ADR `2026-08-12-1` sanctions): the write
surface (P) is a linked worktree whose `.git` is a pointer back to the primary
checkout (R), and the primary holds unrelated, protected work. Every authoring
command that writes Mission artifacts must land them in P, never silently in R.
PR #6002 threaded a validated `OwnedCheckout` through the owned single-branch
lifecycle commands (`setup-plan`, `record-analysis`, `check-prerequisites`,
`decision`, `map-requirements`, `finalize-tasks`, `charter generate`). Two
authoring surfaces were left unwired: the `research` discovery scaffolder and
the top-level `plan` wrapper.

### User Story 1 - Research honours the owned checkout (Priority: P1)

The discovery step directs `spec-kitty research --mission <handle>`. Run from an
owned checkout, `research` must scaffold `research.md`, `data-model.md` and the
two research CSV stubs into the owned Mission directory — or refuse before
writing — and must never resolve, read or write the primary checkout's
`kitty-specs/`.

**Why this priority**: This is the reported data-containment defect. On current
main, `research` has no owned selector, follows the worktree `.git` pointer to
the primary, and scaffolds its four assets into a stale primary copy (or refuses
`Mission not found`). That silently redirects authoring into an unowned, dirty
primary — the exact invariant #5882 and epic #2624 forbid.

**Independent Test**: Build the canonical R/P owned triple with the Mission only
in P; run the real `research` command once with `--owned-checkout P` and once
flagless from inside P; assert the four assets land under
`P/kitty-specs/<slug>/` and R is byte-for-byte unchanged (even when R holds a
stale same-slug copy).

**Acceptance Scenarios**:

1. **Given** an owned single-branch Mission in P and a stale same-slug copy in R,
   **When** `spec-kitty research --mission <slug> --owned-checkout P` runs,
   **Then** the four research assets are scaffolded under `P/kitty-specs/<slug>/`
   and R's working tree, index and HEAD are unchanged.
2. **Given** the same setup, **When** `spec-kitty research --mission <slug>` runs
   with the current directory inside P and no flag, **Then** `research`
   auto-adopts P (mirroring `record-analysis`/`setup-plan`), scaffolds into P,
   and leaves R unchanged.
3. **Given** an owned checkout whose path is refused by the ownership gate (e.g.
   the repository root), **When** `research --owned-checkout <bad>` runs, **Then**
   it emits a typed owned refusal and writes nothing.

---

### User Story 2 - The top-level `plan` wrapper forwards the owned selector (Priority: P2)

`spec-kitty plan` is a thin wrapper over the already-owned-aware `setup_plan`
seam, but it exposes no `--owned-checkout`, so the literal
"`spec-kitty plan --help` exposes no owned selector" complaint stands. Add the
selector and forward it.

**Why this priority**: The agent-facing `agent mission setup-plan` already honours
owned (PR #6002); only the top-level wrapper is missing the pass-through. It
completes the "owned plan authoring path" half of the issue cheaply, without a
new resolver.

**Independent Test**: `spec-kitty plan --help` lists `--owned-checkout`; invoking
`spec-kitty plan --mission <slug> --owned-checkout P` reaches the owned-aware
`setup_plan` seam with the validated owned fact (asserted via a seam spy / the
owned scaffolding landing in P).

**Acceptance Scenarios**:

1. **Given** an owned single-branch Mission in P with a committed spec, **When**
   `spec-kitty plan --mission <slug> --owned-checkout P --json` runs, **Then**
   `setup_plan` receives the owned checkout and plan authoring resolves against
   `P/kitty-specs/<slug>/`, not R.

---

### Edge Cases

- What happens when `research` is run from the repository root (no owned
  checkout, no flag)? → Unchanged behaviour: it resolves the primary and
  scaffolds there (the non-owned path must stay byte-for-byte identical).
- How does `research` handle an explicit `--owned-checkout` pointing at a path
  that is not a valid owned checkout of the Mission? → Typed owned refusal
  (`emit_owned_refusal`), no filesystem mutation.
- What happens when the owned Mission's `plan.md` is not yet filled? → The
  existing `validate_plan_filled` gate still fires, now against the owned
  `plan.md`, with the same remediation guidance.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Research accepts an owned selector | As an operator, I want `spec-kitty research --owned-checkout P` so that discovery artifacts are authored in my owned checkout, not the primary. | High | Open | [build] | no — paired control: the non-owned invocation still resolves the primary |
| FR-002 | Research auto-adopts an owned cwd | As an agent harness, I want flagless `research` run from inside an owned checkout to adopt it so the existing discovery prompt stays correct. | High | Open | [build] | no |
| FR-003 | Research never redirects into an unowned/dirty primary | As a maintainer, I want `research` to write under the owned Mission dir (or refuse) so a stale primary copy is never silently authored into. | High | Open | [build] | no — asserted by R-snapshot equality against a stale primary copy |
| FR-004 | Top-level `plan` forwards the owned selector | As an operator, I want `spec-kitty plan --owned-checkout P` to reach the owned-aware setup-plan seam so the plan authoring path honours ownership. | Medium | Open | [folded] | no |
| FR-005 | Discovery prompt surfaces the owned affordance | As an agent, I want the research discovery prompt to note the owned selector so authoring commands it invokes render ownership. | Low | Open | [build] | yes — documentation affordance, paired with the FR-001/FR-002 behaviour |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Non-owned behaviour preserved | The non-owned `research`/`plan` code path is byte-for-byte behaviour-identical; existing research read-surface tests stay green. | Reliability | High | Open |
| NFR-002 | No new resolver | Ownership is resolved only through the existing `_owned_checkout` / `core.owned_mission` seam (ADR `2026-08-12-1`); no new root resolver is introduced (aligns with #6001). | Maintainability | High | Open |
| NFR-003 | Typed refusal, no partial writes | An invalid owned target refuses via `emit_owned_refusal` before any `mkdir`/copy; the filesystem is left unchanged. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Mirror the #6002 pattern | Thread a validated `OwnedCheckout` into the placement seam (`placement_seam(..., owned=owned)`) and resolve mission dirs from `owned.mission_dir`; do not re-key the walkers. | Technical | High | Open |
| C-002 | Coord topology out of scope | The coord-topology research/plan split is owned by #2683; this Mission covers owned/single_branch only and cross-links #2683. | Technical | Medium | Open |
| C-003 | Non-goals honoured | Do not force runtime phases, hand-edit status, copy the Mission into the primary, or alter the scaffold template-capture boundary (#5925 family). | Business | Medium | Open |

### Key Entities

- **OwnedCheckout**: the validated ownership fact — `repository_root` (R),
  `owned_root` (P, ≠ R), `mission_dir` (under P), `topology`, `write_branch`.
- **PlacementSeam**: the kind-aware resolver that maps a Mission artifact kind to
  its read/write directory; accepts `owned=` to resolve against P.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `spec-kitty research --mission <slug> --owned-checkout P` scaffolds all four research assets under the owned Mission dir and leaves R unchanged. — [build] · no-op passable: no
- **SC-002**: Flagless `research` run from inside P never writes to R, proven by R-snapshot equality against a stale primary copy. — [build] · no-op passable: no
- **SC-003**: `spec-kitty plan --help` lists `--owned-checkout` and the flag reaches the owned-aware setup-plan seam. — [folded] · no-op passable: no
- **SC-004**: The pre-existing `tests/specify_cli/cli/commands/test_research_read_surface.py` suite and `make test-fast` stay green (non-owned behaviour preserved). — [ratchet] · no-op passable: yes
