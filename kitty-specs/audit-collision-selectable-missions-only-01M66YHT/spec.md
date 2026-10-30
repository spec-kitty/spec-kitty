# Mission Specification: Audit collisions only between selectable Missions

**Mission Branch**: `kitty/mission-audit-collision-selectable-missions-only-01M66YHT`
**Created**: 2026-10-30
**Status**: Draft
**Input**: GitHub issue spec-kitty/spec-kitty#6757 — "Audit engine reports a fake
prefix collision on a healthy Mission when a spec.md-only folder shares its prefix"
(follow-up from the pre-merge squad on #5875).

## User Scenarios & Testing *(mandatory)*

The user in this Mission is a maintainer or CI operator who runs
`spec-kitty doctor mission-state --audit` over a repository that has accumulated
leftovers under `kitty-specs/`. Today the report tells them a healthy Mission is
in a prefix collision with a folder that Mission selection, `doctor identity` and
`doctor mission-type` all refuse to treat as a Mission at all. They cannot trust
a warning that is manufactured by a folder no command can select.

### User Story 1 - A residue folder cannot fake a collision on a healthy Mission (Priority: P1)

A repository has one real Mission `001-real` and, next to it, a leftover folder
`001-tracked-spec-only` whose only committed content is a `spec.md` and which has
no `meta.json`. The operator runs the audit. The report names `001-real` with no
findings, and names the leftover folder only with its own identity problem. The
operator no longer has to argue with a collision report that the rest of the tool
inventory contradicts.

**Why this priority**: This is the reported defect. Until it is fixed the audit's
two collision reports (`DUPLICATE_PREFIX`, `AMBIGUOUS_SELECTOR`) are noisy on
exactly the repositories that need auditing most, which trains operators to
ignore them — the warning stops doing its job for the real cases.

**Independent Test**: Build that two-folder fixture in a git repository, run
`run_audit(AuditOptions(repo_root=...))` (the production entry point the CLI
calls), and assert `001-real` has no findings while the residue folder keeps only
`IDENTITY_MISSING`.

**Acceptance Scenarios**:

1. **Given** a committed Mission `001-real` with a `mission_id` and a committed
   `spec.md`-only folder `001-tracked-spec-only`, **When** the audit runs,
   **Then** `001-real` carries no `DUPLICATE_PREFIX` and no `AMBIGUOUS_SELECTOR`
   finding, and `001-tracked-spec-only` carries `IDENTITY_MISSING` but neither
   collision finding.
2. **Given** the same fixture, **When** `doctor mission-state --audit --fail-on
   error` runs, **Then** it still exits non-zero, because the residue folder's
   `IDENTITY_MISSING` remains an error finding (the engine's looser Mission rule
   still governs that finding, #5875 / FR-008).
3. **Given** a non-git scan root holding a `spec.md`-only folder beside a real
   Mission with the same prefix, **When** the audit runs, **Then** the real
   Mission carries no collision finding and the folder still carries
   `IDENTITY_MISSING`.

### User Story 2 - A real collision is still reported (Priority: P1)

Two genuine Missions share the numeric prefix `080`. The audit reports
`DUPLICATE_PREFIX` on both of them and `AMBIGUOUS_SELECTOR` for the handle `080`,
exactly as before. A pre-identity Mission — a tracked `meta.json` with no
`mission_id` yet — the legacy/backfill shape `doctor identity` calls `legacy` —
still participates in collisions.

**Why this priority**: The fix must not buy calm by going blind. Weakening real
collision detection would be a worse defect than the one being fixed, and it
would hide selector ambiguity that breaks `spec-kitty` dispatch.

**Independent Test**: Build a two-real-Mission prefix collision plus a
pre-identity member, run the audit, and assert the findings are all present with
their existing codes, severities, artifact paths and details.

**Acceptance Scenarios**:

1. **Given** Missions `080-alpha` and `080-beta`, **When** the audit runs,
   **Then** each carries `DUPLICATE_PREFIX` ("prefix '080' shared with: …") and
   `AMBIGUOUS_SELECTOR` ("handle '080' also matches: …").
2. **Given** a Mission `081-legacy` whose tracked `meta.json` has no
   `mission_id` and a Mission `081-real`, **When** the audit runs, **Then** both
   carry `DUPLICATE_PREFIX` and `AMBIGUOUS_SELECTOR` (a pre-identity Mission is
   selectable, so it still collides).
3. **Given** two real Missions and one residue folder that all share prefix
   `082`, **When** the audit runs, **Then** the two Missions carry
   `DUPLICATE_PREFIX` naming each other only, and the residue folder carries no
   collision finding.

### User Story 3 - `doctor identity` keeps its own, already-correct report (Priority: P2)

The operator runs `doctor identity` on the same repository and sees what #5875
already delivers: one Mission, one residue row, no collision. The audit engine's
change does not alter that report.

**Why this priority**: The two commands must not drift apart again in the
opposite direction. #5875 settled `doctor identity`; this Mission must reuse its
rule rather than invent a third is-a-Mission predicate.

**Independent Test**: Run the same fixture through `doctor identity` before and
after the change; the output is byte-identical.

**Acceptance Scenarios**:

1. **Given** the residue fixture, **When** `doctor identity` runs, **Then** the
   output is unchanged by this Mission (residue is already excluded from both of
   its collision reports).

### Edge Cases

- **A pre-identity Mission must still collide.** Selection lists a folder with a
  tracked `meta.json` and no `mission_id` (the `legacy` state `backfill-identity`
  repairs); dropping it from collision checks because it lacks identity would
  hide a real collision. Both `001-real` and `001-legacy` (tracked id-less
  `meta.json`) must be reported.
- **A residue folder inside a real collision group.** With `082-alpha`,
  `082-beta` and `082-leftover` present, the group must be recomputed over the
  selectable population, so the two real Missions are reported against each
  other, not silenced by the group's third member.
- **A folder the engine already calls residue.** A directory the engine's own
  `is_mission_dir` rule rejects (for example a stray `*.lock`) keeps its single
  `RESIDUE_DIRECTORY` finding; it never gains a collision finding either.
- **Non-git scan root.** Outside git the residue rule falls back to `meta.json`
  presence on disk, so a `spec.md`-only folder is residue for collisions while
  the engine's existence rule still reports `IDENTITY_MISSING` for it.
- **Broken git index.** The engine is a read-only reporter: it keeps raising the
  `GitCommandError` it raises today rather than degrading to a weaker answer.
- **Fixtures scan root / `--mission` scoping.** A non-default scan root
  (audit fixtures) must behave exactly as it does today — the collision pass is
  anchored on `repo_root` and never re-walks the scan root; `--mission` scoping
  must keep reporting collisions as it does today.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Collisions judged on selectable Missions | As an operator, I want `DUPLICATE_PREFIX` and `AMBIGUOUS_SELECTOR` computed over the Mission population that selection can reach, so a residue folder cannot manufacture a collision. | High | Open | [build] | no — a no-op keeps reporting the fake collision from the #6757 fixture |
| FR-002 | `IDENTITY_MISSING` population unchanged | As an operator, I want the engine's looser `is_mission_dir` rule to keep governing `IDENTITY_MISSING`, so a tracked `spec.md`-only folder is still reported and `--fail-on error` still exits 1. | High | Open | [ratchet] | yes — guarded by the same-fixture positive control in FR-001's test (the folder keeps this finding while it loses the collisions) |
| FR-003 | Real collisions preserved | As an operator, I want two selectable Missions sharing a prefix, or a pre-identity Mission, to keep producing `DUPLICATE_PREFIX` and `AMBIGUOUS_SELECTOR`, so the fix cannot buy calm by going blind. | High | Open | [ratchet] | yes — guarded by the same-fixture positive control in FR-001's test (the identical fixture yields findings when both folders are Missions) |
| FR-004 | Pin both directions in the engine suite | As a maintainer, I want the engine's contract pinned in both directions (fake collision gone, real collision kept) so a later loosening cannot regress either side silently. | High | Open | [build] | no — the current pin test asserts the old, wrong contract |
| FR-005 | `doctor identity` unchanged | As an operator, I want `doctor identity` output to stay exactly as #5875 delivers it, so the two commands converge on one rule instead of drifting. | Medium | Open | [ratchet] | yes — guarded by the existing residue-aware suite, run as the positive control |
| FR-006 | One is-a-Mission rule for collisions | As a maintainer, I want the collision pass to reuse the read-side selectable rule (`audit_repo(..., residue_aware=True)` / `find_duplicate_prefixes(..., residue_aware=True)`), so a third predicate is not introduced. | High | Open | [build] | no — a no-op leaves the engine on the default walk |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No per-Mission git subprocess | The extra selectable-Missions populations cost a constant number of additional batch `git ls-files` probes per audit (one per residue-aware walk, so at most two) and never one git call per Mission; the full audit of a 200-Mission repository (half without a `mission_id`) stays under 3 s, matching the existing identity-audit budget. | Performance | High | Open |
| NFR-002 | Deterministic report | The audit report keeps its determinism contract: missions sorted by slug, findings sorted by `(artifact_path, code)`, no timestamps, and the serialised JSON identical across runs. | Reliability | High | Open |
| NFR-003 | Read-only | The audit writes no file, spawns no non-git process and makes no network call; a broken git index still raises `GitCommandError` to the CLI rather than degrading silently. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Reuse the #5875 read-side rule | The collision population comes from the existing residue-aware walk (`residue_aware=True`), not from a new predicate, a copy of `is_selectable_mission_dir`, or a regex on directory names. | Technical | High | Open |
| C-002 | No weakening of the identity gate | `IDENTITY_MISSING` severity, code, detail and the `--fail-on error` behaviour stay as they are; the change is scoped to the two collision codes. | Business | High | Open |
| C-003 | Changelog + docs where user-facing | The `[Unreleased]` changelog entry names #6757 impact-first, and any doc that states the audit's collision rule is corrected. | Technical | Medium | Open |

### Key Entities

- **Selectable Mission**: a `kitty-specs/` child that Mission selection can reach
  — a `meta.json` on disk plus either a `mission_id` or git-tracked markers
  (`is_selectable_mission_dir`, #5875). The population collisions are judged on.
- **Engine Mission population**: the looser `is_mission_dir` population the
  engine classifies per folder, which also keeps a tracked `spec.md`-only folder
  in the report with `IDENTITY_MISSING`.
- **Collision finding**: `DUPLICATE_PREFIX` (warning, prefix shared with ≥ 1 other
  Mission) and `AMBIGUOUS_SELECTOR` (warning, a handle resolving to ≥ 2).
- **Residue folder**: a `kitty-specs/` child that is not a Mission; reported as
  `RESIDUE_DIRECTORY` (info) or, when the engine's looser rule still calls it a
  Mission, `IDENTITY_MISSING` (error).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the #6757 fixture (`001-real` + `001-tracked-spec-only`), the
  audit report contains zero findings for `001-real` and exactly
  `IDENTITY_MISSING` for the residue folder. — [build] · no-op passable: no
- **SC-002**: On a real-collision fixture (`080-alpha`/`080-beta`, plus an
  id-less `081-legacy`/`081-real` pair), every `DUPLICATE_PREFIX` and
  `AMBIGUOUS_SELECTOR` finding still appears with its current code, severity,
  artifact path and detail text. — [ratchet] · no-op passable: yes — positive
  control is the shared fixture that also proves the residue case above
- **SC-003**: `doctor mission-state --audit --fail-on error` keeps exiting 1 on
  the #6757 fixture (the residue folder's `IDENTITY_MISSING` is an error), and
  exits 0 on a repository with no findings at all. — [ratchet] · no-op
  passable: yes — the zero-finding half is the positive control that the gate can
  be passed
- **SC-004**: The mission's test selection passes: `tests/audit/`,
  `tests/doctor/test_identity_audit.py`, `tests/context/test_is_mission_dir.py`,
  and `tests/integration/test_colliding_mission_flow.py`. — [ratchet] · no-op
  passable: no
- **SC-005**: `doctor identity` output on the residue fixture is unchanged by
  this Mission. — [ratchet] · no-op passable: yes — guarded by the existing
  residue-aware assertions on the same fixture
