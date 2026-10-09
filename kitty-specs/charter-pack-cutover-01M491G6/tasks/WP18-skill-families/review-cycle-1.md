---
affected_files: []
cycle_number: 1
mission_slug: charter-pack-cutover-01M491G6
reproduction_command:
reviewed_at: '2026-10-07T21:20:22Z'
reviewer_agent: claude
wp_id: WP18
---

# WP18 review, cycle 1: changes requested

Reviewer: reviewer-renata (claude). Lane head reviewed: 320a8287 (lane-r, merged to a98139b9).

## Blocking

1. **New ruff error (F401) from the red-first commit.** Commit 0a4bd6a1 removed the last
   `@pending_until("WP18", ...)` in `tests/acceptance/charter_pack_cutover/test_upgrade_migration.py`,
   so `pending_until` is now an unused import on line 42:

   ```
   F401 [*] `._support.pending_until` imported but unused
     --> tests/acceptance/charter_pack_cutover/test_upgrade_migration.py:42:101
   ```

   At the lane base (8ff0df36) `ruff check tests/acceptance/charter_pack_cutover/` passes; at the lane
   head it reports 1 error, so CI's whole-repo `ruff check .` turns red. Remove `pending_until` from
   that import line, then re-run
   `uv run --frozen ruff check tests/acceptance/charter_pack_cutover/` and
   `uv run --frozen ruff format --check --force-exclude tests/acceptance/charter_pack_cutover/test_upgrade_migration.py`.
   This only removes an import, so C-006 still holds.

That is the only change requested. Everything else below was checked and is accepted as is.

## Verified (no action)

- Fold fidelity: for each of the four rich skills, the old `SKILL.md` and the new
  `references/*-workflow.md` differ only in frontmatter/title, `.kittify/doctrine` -> `.kittify/charter-packs`,
  "doctrine pack" prose (FR-018), sibling-relative reference links, one corrected `../` depth and the
  new skill names. The thin `spk-doctrine-*` flows survive in the new short `SKILL.md` files, and both
  sources' triggers and "Does NOT handle" text are in each `description:`. There is no "Legacy Alias" or
  alias section. The 80-line cap in `test_spk_skill_pack.py` is unchanged.
- WP01 test edits: the `A | B - C` precedence fix is a real bug fix (the old test could never pass).
  The global-copy seeding now matches `AssetPreparation.retire`, which removes only
  inventory-owned, unchanged nodes (#4017). The assertions are unchanged.
- The 13 retired names equal WP12's `REMOVED_SKILL_NAMES`. The T089 validation grep over living
  surfaces returns only `retired.py`, `_charter_pack_cutover_skills.py` and the `m_3_1_1` docstring.
  `name:` matches the directory for every skill. `doctrine-daphne` is untouched, and so is the
  name `references/doctrine-artifact-structure.md`; its only content change repoints the path to
  `default.yaml`. The rc35 profile-handoff migration is keyed on sentinels, so changing the literal
  does not re-patch migrated projects.
- Generated files: `regen --check`, `doctrine regenerate-graph --check`, `docs_index` check and
  `check_cli_reference_freshness` all exit 0. No agent copy was hand-edited. Out-of-ownership
  edits are logged in the commit bodies.
