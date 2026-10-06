# Research: Skill surface and upgrade integrity

Sources: two research agents and a post-spec adversarial squad (this session, 2026-10-06), on `main` at `abafc135`.

## R-1 Which producers conflict on `.claude`
- **Decision**: merge structurally identical directory creates in `coalesce_effects`.
- **Evidence**: live repro (`init --ai claude`, `rm -rf .claude`, `upgrade --project --yes` → `Owner effect conflict`). Conflicting effects: `managed_skills` (`skills/installer.py:611`) and `agent_profiles` (`tool_surface/providers/agent_profiles.py:766-775`); only `owner` differs.
- **Alternatives**: one shared parent-provisioning step (larger change, rejected for scope); stop `prepare_parents` from emitting parents (vacuous — apply-time `mkdir` at `agent_profiles.py:817` would fail).

## R-2 Version stamp design
- **Decision**: snapshot `version`, `last_upgraded_at`, schema version before the runner; restore when the runner or `finalize_upgrade` fails. Extends the #3334 restore pattern.
- **Rationale**: four writers (`runner.py:~180`, `_finalize_main_metadata ~737-742`, `_stamp_no_migrations_metadata upgrade.py:~711-728`, schema stamp) — deferring all of them is more invasive than one restore boundary.
- **Alternatives**: defer all writes until after finalize (rejected: touches every writer, risks #1158 repair).

## R-3 Missing pack skill predicate
- **Decision**: in `find_pack_skill_findings`, compare the in-force set (existing resolver, `charter/activation/skill_preparation.py:272`) against manifest entries per installable agent; also map absent installed file → `missing`.
- **Out of scope**: `skills/verifier.py` and `upgrade/assessment.py` blind spot (C-003) — file a follow-up issue.

## R-4 `--fix` projection
- **Decision**: call `project_pack_skills` (`skills/installer.py:1282`), as `charter activate` does; catch `OSError` into `repair_errors`; re-check.

## R-5 No configured tool folder
- **Decision**: doctor finding when none of `get_agent_dirs_for_project` roots exists; one is enough (operator answer). Not a pack-skill kind: a separate payload finding (see contracts).

## Squad dispositions (post-spec)
All 9 findings folded into spec (`01d9d78`): merge key wording, FR-003 design + surface-repair failure in SC-002, C-005 config source, C-006 additive JSON, ADR amendment in FR-007, FR-005 canonical installer, NFR-004 dropped (no measurable fixture), FR-002 diagnostic fields, C-004 restore compatibility.
