---
work_package_id: WP03
title: Gates, ADR amendment and changelog
dependencies:
- WP02
requirement_refs:
- FR-005
- FR-006
- NFR-003
- C-003
- SC-002
- SC-004
planning_base_branch: issue-6331-mission-type-capability-offering-seam
merge_target_branch: issue-6331-mission-type-capability-offering-seam
branch_strategy: Planning artifacts for this mission were generated on issue-6331-mission-type-capability-offering-seam. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6331-mission-type-capability-offering-seam unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 3 - Record
history:
- at: '2026-10-31T12:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent: []
execution_mode: code_change
owned_files:
- tests/architectural/test_doctrine_census.py
- docs/adr/4.x/2026-10-03-1-charter-read-write-service-strangler.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6331'
---

# Work Package Prompt: WP03 – Gates, ADR amendment and changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
(or any user-defined profile), and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: claude

---

## Objectives & Success Criteria

Record the seam addition honestly:

1. The new offering module carries a `PUBLIC` row in the authoritative census manifest, so the
   disposition-coupling and no-leak gates accept the three seam symbols.
2. ADR `2026-10-03-1` gains an amendment recording the additive seam symbols, in the same shape
   the `LANGUAGE_TOKENS` amendment (#6541) used.
3. `docs/changelog/CHANGELOG.md` carries an `[Unreleased]` entry that names #6331, states the
   before/after for a consumer, and stays under 1,200 characters.

Success: the three gate files pass, and `git diff` shows no gate weakening — only a new
disposition row, a new amendment section and a new changelog entry.

## Context & Constraints

- Spec FR-005/FR-006, NFR-003, C-003, SC-002; plan IC-03 and design decision 5.
- **Never weaken a gate.** No `pytest.skip`, no `xfail`, no relaxed assertion, no widened
  allowlist. The census row is the sanctioned mechanism; the ADR amendment is the sanctioned
  record for an additive seam symbol.
- Precedent: `docs/adr/4.x/2026-10-03-1-charter-read-write-service-strangler.md`, section
  "## Amendment 2026-10-20 (Accepted): `LANGUAGE_TOKENS` joins the frozen seam (#6541)".
- Changelog: `docs/changelog/CHANGELOG.md` (root `CHANGELOG.md` is a symlink to it). Entry format:
  bold impact-first lead with `(#6331)`, then before/after, under 1,200 characters.

## Branch Strategy

- **Strategy**: Planning base and merge target are `issue-6331-mission-type-capability-offering-seam`.
- **Planning base branch**: `issue-6331-mission-type-capability-offering-seam`
- **Merge target branch**: `issue-6331-mission-type-capability-offering-seam`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Census disposition row

- **Purpose**: FR-006. `test_every_public_symbol_originates_from_a_public_disposition` resolves
  each seam symbol's origin module by longest-prefix against `DISPOSITION`; without a row the
  gate fails.
- **Steps**:
  1. In `tests/architectural/test_doctrine_census.py`, add
     `"charter.offering.missions.capabilities": "PUBLIC",` in the `missions cluster` block, with a
     comment naming #6331: the mission-type capability contract, narrowed by
     `charter.offering.api.__all__` and pinned by
     `tests/charter_offering/test_mission_type_capabilities_seam.py`.
  2. Do not touch any other row, the taxonomy, or the baseline sets.
- **Files**: `tests/architectural/test_doctrine_census.py`
- **Parallel?**: No (the gates are the acceptance proof).
- **Notes**: the table is a documented superset of reached paths, so a row for a module the AST
  census does not reach is legal — but say that in the comment is unnecessary; keep the comment
  to what the row means.

### Subtask T002 – ADR amendment

- **Purpose**: C-003. Additive seam symbols are recorded by amendment of ADR
  `2026-10-03-1`, following the #6541 precedent.
- **Steps**:
  1. Append a section after the last amendment:
     `## Amendment 2026-10-31 (Accepted): the mission-type capability contract joins the frozen seam (#6331)`.
  2. State: `charter.offering.api` gains `MissionTypeCapabilities`,
     `MissionTypeCapabilitySource` and `capabilities_of`; what crosses the seam (the *contract*:
     the two capability answers plus a structural protocol); what stays internal (the activation
     resolver `resolve_mission_type_context` and `ResolvedMissionType`, which remain in
     `charter.activation`); why a re-export of those would invert the verified zero-edge
     dependency direction recorded in ADR `2026-10-16-1`; how it is narrowed (the census is
     module-keyed with a `PUBLIC` row, `charter.offering.api.__all__` bounds the symbol set, and
     `tests/charter_offering/test_mission_type_capabilities_seam.py` pins it); and that core
     reaches it through the `charter.missions` facade.
  3. Keep it to one tight section in the existing voice. Do not renumber or edit earlier
     amendments.
- **Files**: `docs/adr/4.x/2026-10-03-1-charter-read-write-service-strangler.md`
- **Parallel?**: Yes, with T003.
- **Notes**: if `uv run python -m scripts.docs.freshen_adr_inventory` or `docs_index --write` is
  required by the freshness gate for an amendment-only edit, run the *specific* generator and then
  `uv run python -m scripts.docs.check_docs_freshness --ci` (expect errors=0). Do not regenerate
  the whole docs surface.

### Subtask T003 – Changelog entry

- **Purpose**: the user-facing record.
- **Steps**:
  1. Add one bullet under `## [Unreleased]` (top of the file's unreleased section), following the
     existing entries' shape.
  2. Lead with the impact in bold: a consumer of the charter offering seam can now read a mission
     type's `wp_driven` and `requires_substantive_spec` without importing
     `charter.activation.*`.
  3. Include the before (only reachable from `charter.activation.mission_type_profiles`) /
     after (also on `charter.offering.api` and the `charter.missions` facade, with a protocol and
     a value object) and the `(#6331)` reference.
  4. Under 1,200 characters. No emoji, no marketing.
- **Files**: `docs/changelog/CHANGELOG.md`
- **Parallel?**: Yes, with T002.
- **Notes**: if the changelog has a 4.0.0 section structure, put the entry in `[Unreleased]` per
  the brief, not in a released version's section.

## Test Strategy

- `uv run pytest tests/architectural/test_doctrine_census.py -q`
- `uv run pytest tests/architectural/test_charter_offering_public_surface.py -q`
- `uv run pytest tests/architectural/test_charter_facades_reexport_offering.py -q`
- `uv run pytest tests/charter_offering/test_mission_type_capabilities_seam.py tests/charter/test_resolved_mission_type_context.py -q`
- `uv run python -m scripts.docs.check_docs_freshness --ci` (errors must be 0)

## Risks & Mitigations

- **Gate weakening temptation** — if a gate fails, fix the record or the code, never the
  assertion. Record any failure you cannot attribute in the PR's `## Deferred` with its issue.
- **Docs freshness churn** — regenerate only what the amendment touches; if a generator rewrites
  unrelated docs because of shared-cache state, stop and report rather than committing churn.
- **Changelog length** — the validator enforces 1,200 characters; count it.

## Review Guidance

- Confirm the only change to the gate file is the new disposition row.
- Confirm the ADR amendment states what crosses the seam *and* what deliberately does not.
- Confirm the changelog entry is impact-first, has `(#6331)`, and is under 1,200 characters.
- Re-run the four test commands and the freshness check; record the counts.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP03 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP03 --to <status>`
