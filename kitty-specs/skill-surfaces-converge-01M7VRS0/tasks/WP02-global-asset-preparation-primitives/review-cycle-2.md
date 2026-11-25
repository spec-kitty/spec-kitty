---
affected_files: []
cycle_number: 2
mission_slug: skill-surfaces-converge-01M7VRS0
reproduction_command:
reviewed_at: '2026-11-20T08:01:15Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP02
---

# WP02 review feedback 2: changes requested

Reviewer: claude::reviewer-renata (independent). Reviewed range up to 7fc00ee31d1a (fix 119b4e5654).

B1 (cycle 1) is resolved. The main file stays schema 1 with an `anchor` marker, an `external` sidecar holds the
other entries, and older readers accept the file (red 02869bad4b, then green). N1, N3 and N4 are done.
`test_global_asset_inventory_anchor.py` and `test_asset_preparation_retire_proof.py`: 20 passed.

## Blocking

### B2. A pre-#7722 inventory loses its records for a root outside home, so those files stop refreshing

`_read_inventory` legacy path → `_place_legacy_key(..., confinement=(home, kittify_home))`. A record the old CLI
wrote while `CLAUDE_CONFIG_DIR` (or `OPENCODE_CONFIG_DIR`, or `XDG_CONFIG_HOME`) pointed outside `$HOME` names a
path outside both confinement roots, so it is dropped from proof. Base a053b674 proves that file from the very
same record and refreshes it. This is a regression for exactly the users #7722 is about.

Reproduced, end to end, with an isolated `HOME` and `CLAUDE_CONFIG_DIR=<tmp>/outside`:

1. The base CLI writes `global_skills-assets.json` (552 entries, including `.../outside/skills/...`, anchored on
   `commonpath(home, outside).parent`).
2. I made `outside/skills/adversarial-squad/SKILL.md` an older render, with the inventory record carrying its
   sha256 (what an earlier release writes).
3. `assess_global_assets()` on base plans a refresh (`PhysicalEffect`). On lane-b it reports
   `preserve | Unproven existing asset` and plans no effect.

Skills may later be rescued by WP03's historical-render list, but slash commands (`~/.claude/commands` under the
moved root) have no historical list, so they stay stale until the user deletes them.

Fix direction: the T008 rule. Also confine placement to the owner's current roots (`known_roots`, the
`global_asset_root` inputs the three callers already hold), so a pre-#7722 key that lands inside a current root is
placed and proven. Records under a root that has since moved elsewhere may still be dropped; that stays fail-safe.

Add a red test with the shape above: a pre-#7722 inventory anchored above home that names a file under a root
outside home, and the root is still configured. The file must be refreshed (an effect), not kept as unproven.
Also add the slash-commands owner variant if it differs.

## Non-blocking

- N5. The moved-anchor test covers only keys under home. With the B2 test added, that's enough.
