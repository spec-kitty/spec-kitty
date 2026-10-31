# Work Packages: One activation spelling at the effective-set seam

**Inputs**: `kitty-specs/effective-set-one-spelling-01M68ZYF/` — spec.md, plan.md, research.md
**Issue**: #6435
**Tests**: red-first for both slices (ATDD-First Discipline); the coverage slice pins the standing invariant.

**Organization**: two work packages. WP01 delivers the user-visible defect fix
(FR-001, FR-004, FR-005). WP02 delivers the single spelling rule and the
per-kind/per-layer pinning (FR-002, FR-003, SC-002, SC-003, SC-004).

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files).
- Record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- **Single project**: `src/`, `tests/`

---

## Work Package WP01: The required-only floor stores stems (Priority: P1) 🎯 MVP

**Goal**: `charter activate` on an absent required-only key (`skill`) writes each
in-force org-required artifact by its file stem, never by its declared id, while
a colliding required id keeps refusing.
**Independent Test**: build a project whose org pack requires an id≠stem skill,
run `charter activate skill <other>` through the CLI, and assert the written
`activated_skills` list holds stems only; the same fixture family with a
colliding required id still exits non-zero with `ActivationIdCollisionError` and
writes nothing.
**Prompt**: `tasks/WP01-required-floor-stores-stems.md`
**Requirement Refs**: FR-001, FR-004, FR-005, NFR-001, SC-001

### Included Subtasks

T001 Write the red test in `tests/specify_cli/cli/commands/charter/test_activate_required_key_stems_6435.py`: org pack with `required_skills: [acme-skill-id]` declared by `acme-skill-file.skill.yaml`; `charter activate skill other-skill-file`; assert `activated_skills == [acme-skill-file, other-skill-file]` (fails on `main` with `acme-skill-id` first)
T002 [P] Add the collision case on the same fixture family: a required id whose file name another layer uses for a different id still raises `ActivationIdCollisionError` and writes nothing (FR-005), with the non-colliding id as the same-fixture positive control
T003 Route the required floor through `org_required_stems` in `pack_manager._preservation_ids` and fold `_refuse_required_collisions` into that one call (no added scan, no added warning)
T004 Re-run the touched suites (`test_activate_required_key_stems_6435.py`, `test_stored_spelling_6527.py`, `test_activate_only_6408.py`, `test_pack_context`-owns-required suites) and the `charter` architectural gates for the touched packages

### Implementation Notes

- The stems call must not append warnings: the user-visible `activate` output must
  not grow (pass `[]`, exactly as `_refuse_required_collisions` does today).
- Keep the `_Preservation` shape and the `in_force=True` flag unchanged.
- `when_absent == "all"` kinds must be untouched (their branch is above this one).

### Parallel Opportunities

- T002 is independent of T001/T003 once the fixture helper exists.

### Dependencies

- None (starting package).

### Risks & Mitigations

- A reader that expected a declared id in `activated_skills`: the gate resolves
  either spelling (`resolver._gated` → `identity.activation_id`), and #6527 makes
  the stem the stored form everywhere else. Covered by T004.

---

## Work Package WP02: One union spelling rule, pinned per kind and layer (Priority: P2)

**Goal**: the effective-set seam computes its stem spelling in one place, used by
both the resolved and the fallback half, and the mixed two-org-pack union is
pinned for every applicable kind and both pack orders.
**Independent Test**: revert the single helper's mapping and the effective-set
suite goes red; the mixed fixture lists each id≠stem artifact once, by stem, and
`stored_spelling` maps each declared id to the same stem.
**Prompt**: `tasks/WP02-one-spelling-rule-pinned.md`
**Requirement Refs**: FR-002, FR-003, SC-002, SC-003, SC-004, NFR-002, NFR-003, C-003

### Included Subtasks

T005 Extend the existing two-org-pack fixture in `tests/charter/activation/test_effective_set.py` with an id≠stem artifact per applicable kind, in the lower- and the higher-precedence pack
T006 Add the mixed-union assertions: each artifact listed once by stem, no declared id in `ids`, and `IdentityIndex.stored_spelling(kind, declared_id) == stem` (both spellings converge) — the red-first pin for the fallback half
T007 Add the fallback-path assertion: an unresolvable set over an id≠stem org artifact yields stems only in `fallback_ids` (red on `main` when the fallback mapping is reverted)
T008 Extract the one union/mapping helper in `src/charter/activation/effective_set.py` and call it from `_resolve_one` and `_fallback_ids`; keep the unknown-token rule and document it once
T009 Run the half-by-half mutation check (drop the helper's mapping → T006/T007 red; restore) and record the result in the PR's `## Tests run`
T010 Re-run `tests/charter/activation/test_effective_set.py`, `test_identity_index.py`, `test_stored_spelling_6527.py` and the `charter` architectural layer gates

### Implementation Notes

- Behaviour must be unchanged on the resolved path; the only new code is the shared
  call site. Do not reimplement `list_available_detailed` (C-003).
- Do not touch `#6433` policy: an unknown service-only token still stays as given.
- Keep the directive half's existing treatment exactly as it is (it is scanned by
  stem already); the helper must express that as data, not as a second rule.

### Parallel Opportunities

- T005/T006/T007 (tests) can be written before T008 lands.

### Dependencies

- None; WP02 does not depend on WP01 (different files).

### Risks & Mitigations

- Fixture cost: adding kinds to the shared fixture slows the module (NFR-002).
  Mitigate by extending the existing fixture once, not by adding new service builds.
