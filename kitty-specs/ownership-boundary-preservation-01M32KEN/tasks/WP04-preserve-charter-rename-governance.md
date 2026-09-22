---
work_package_id: WP04
title: Preserve Skipped governance files in charter-rename (#4862 + B1)
dependencies:
- WP01
requirement_refs:
- FR-006
- NFR-001
- NFR-006
planning_base_branch: fix/ownership-boundary-preservation
merge_target_branch: fix/ownership-boundary-preservation
branch_strategy: Planning artifacts for this mission were generated on fix/ownership-boundary-preservation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/ownership-boundary-preservation unless the human explicitly redirects the landing branch.
subtasks:
- T013
- T014
phase: Phase 2 - Route destructive sites
history:
- at: '{{TIMESTAMP}}'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py
create_intent:
- tests/specify_cli/upgrade/migrations/test_m_3_1_1_charter_rename.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py
- tests/specify_cli/upgrade/migrations/test_m_3_1_1_charter_rename.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Preserve Skipped governance files in charter-rename (#4862 + B1)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ Binding post-tasks corrections (supersede any conflicting text below)

- **Guard performs the delete.** T014 replaces the `:195`/`:148` `rmtree` and `:161` `unlink` with
  `guard_destructive_removal(...)` calls (archive to an EXTERNAL `backup_parent` for parent-removed
  sites); no raw destructive literal remains at the site (contract C1.0/C3). A now-empty residual
  dir is then removed via the guard (proving-owned) or the allowlisted empty-only `rmdir` category —
  never a fresh raw `rmtree` literal.
- **T013 `:161` seed fix:** the stale-`memory/constitution.md` sub-repro MUST also create
  `.kittify/charter/charter.md`, else the migration takes the MOVE branch at `:172` (no loss) and the
  test is falsely GREEN.

## Objectives & Success Criteria

Route the charter-rename migration's residual `rmtree(constitution_dir)` through
`AnyProver([CanonicalContentProver, ManagedPathProver])` (effectively preserve-always for
governance) so a file reported "Skipped" is not destroyed — plus the two B1 sites — closing #4862.

- A constitution-side file reported "Skipped" (a same-named, differing file already in `charter/`)
  is PRESERVED (in place or in a recoverable backup) with a diagnostic, and is NOT destroyed by the
  residual directory removal.
- B1: `missions/<m>/constitution/` rmtree and stale `memory/constitution.md` unlink PRESERVE their
  content unless canonical-proven.
- A no-collision residual directory (all files merged) is STILL removed as before (legitimate
  cleanup, US3 scenario 2).
- **Success**: tests RED on base `32cfc272ee`, GREEN on this WP's final commit.

## Context & Constraints

- **Requirement refs**: FR-006, NFR-001, NFR-006.
- **The sites** (verified on base, `m_3_1_1_charter_rename.py`):
  `:148` `shutil.rmtree(mission_constitution)` (B1); `:161` `memory_constitution.unlink()` (B1
  stale); `:192` emits `"Skipped {item.name} (already exists in charter/)"`; `:195`
  `shutil.rmtree(constitution_dir)` — the residual removal that destroys the "Skipped" file (#4862).
- **The proof**: governance files carry no version marker and no shipped canonical ⇒ `AnyProver`
  returns `None` ⇒ preserve. Where the parent (`constitution_dir`) is being removed, archive with an
  external `backup_parent`; the now-empty residual dir then `rmtree`s fine.
- **Design**: [data-model.md](../data-model.md) census row 9 + borderline B1; [spec.md](../spec.md)
  US3; [research.md](../research.md) Decision 5 (B1);
  [contracts/ownership-guard-contract.md](../contracts/ownership-guard-contract.md) C4 US3.
- **CAUTION**: this file is one of only two permitted to contain "constitution" strings — do NOT
  introduce retired `sync` tokens (C-005); do not touch the non-collision `shutil.move` sites
  (`:172/188/205/219/322/347` — allowlisted relocations).

## Branch Strategy

- **Strategy**: shared-lane
- **Planning base branch**: fix/ownership-boundary-preservation
- **Merge target branch**: fix/ownership-boundary-preservation

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T013 – Red-first: "Skipped" file survives + B1 sites

- **Purpose**: Pin US3 + B1 BEFORE the fix.
- **Steps**:
  1. In `test_m_3_1_1_charter_rename.py`, seed `.kittify/constitution/<file>` and a DIFFERING
     `.kittify/charter/<file>`; run the migration; assert the "Skipped" constitution-side file
     SURVIVES (in place or recoverable backup) with a diagnostic, and is NOT destroyed by the
     residual `rmtree(constitution_dir)`.
  2. B1: seed a `missions/<m>/constitution/` member and a stale `memory/constitution.md`; assert
     both PRESERVE unless canonical-content-proven.
  3. No-collision case: a `constitution/` whose files all merge without collision ⇒ the now-empty
     residual dir is still removed (US3 scenario 2 stays green).
  4. Confirm RED on base, GREEN after T014.
- **Files**: `tests/specify_cli/upgrade/migrations/test_m_3_1_1_charter_rename.py`.

### Subtask T014 – Route `:195` + B1 sites via `AnyProver`

- **Purpose**: Ownership-gate the governance removals.
- **Steps**:
  1. Before the residual `shutil.rmtree(constitution_dir)` at `:195`, route each colliding
     ("Skipped") file through `guard_destructive_removal(file, project_path,
     prover=AnyProver([CanonicalContentProver(...), ManagedPathProver(...)]),
     backup_parent=<external, e.g. .kittify/.backup-<ts>/>)`. Archive the preserved file OUT of the
     doomed tree first, then let the (now content-free) residual dir `rmtree` proceed.
  2. Route B1 `:148` (`rmtree(mission_constitution)`) and `:161`
     (`unlink(memory_constitution)`) through the same `AnyProver` → preserve unless
     canonical-proven; archive to an external `backup_parent` where a parent is removed.
  3. Add one-line in-code ownership-proof rationale comments at each routed site (NFR-006).
- **Files**: `src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py`.
- **Notes**: preserve the migration's existing "Skipped" warning text OR fold it into the guard
  diagnostic — but the file must survive.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest \
  tests/specify_cli/upgrade/migrations/test_m_3_1_1_charter_rename.py -q
uv run --frozen mypy --strict src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py
pytest tests/architectural/test_no_retired_subsystems.py -q   # confirm no retired token slipped in
```

- Record RED-on-base → GREEN-on-fix in the PR.

## Risks & Mitigations

- **Archive ordering** — the preserved file must be copied OUT before `rmtree(constitution_dir)`,
  with `backup_parent` outside that tree (contract C1.4).
- **"constitution" string / sync-token gates** — run `test_no_retired_subsystems.py`; keep the
  permitted "constitution" scope, add no `sync` vocabulary.
- **Non-collision cleanup regression** — US3 scenario 2 must stay green.

## Review Guidance

- Confirm the "Skipped" file survives AND the empty residual dir is still removed on the
  no-collision path.
- Confirm B1 sites are routed (not left raw).
- Confirm the in-code rationale comments and that no retired `sync` tokens were added.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

- {{TIMESTAMP}} – system – Prompt created.
