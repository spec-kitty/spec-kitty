---
affected_files: []
cycle_number: 1
mission_slug: command-skill-names-and-antigravity-01M5DBWT
reproduction_command:
reviewed_at: '2026-10-21T04:36:40Z'
reviewer_agent: claude
wp_id: WP04
---

# WP04 review feedback (cycle 1) — REJECT

1. **US2 scenario 9 not met, silently.** The docstring (`m_4_0_0rc8_command_skill_hyphen_names.py:14-19`) claims the command-skill manifest is git-ignored; it is not (only `.agents/skills/` and `.kittify/migrations/` are). Teammate A migrates and commits a hyphen-only manifest; teammate B pulls; B's dotted folders are unrecorded, `detect()` is True, `install()` reinstalls the hyphen set and leaves `spec-kitty.<cmd>/` in place → duplicate commands, `success`, no warning (repro: scratchpad `sc9.py`).
   **Operator ruling (2026-10-21):** an *unrecorded* dotted `spec-kitty.<cmd>/SKILL.md` (cmd in `CANONICAL_COMMANDS`) whose bytes equal `legacy_rendering(...)` exactly is Spec Kitty-owned and is retired by the installer's legacy rule (folder removed only if then empty); anything else stays, with a warning. Implement it **in the installer** (one authority, used by every repair path, `verify()` and doctor), not in the migration. Then:
   (a) the migration and every repair path emit the unrecorded-legacy warning and add kept paths to `preserved_paths` for every dotted folder left behind, not only when the manifest is missing;
   (b) add a two-clone test sharing a committed manifest (clone B ends with no duplicate, edited copy kept with warning);
   (c) correct the docstring and the design-decisions trace entry (only `.agents/skills/` is ignored; clone-local is still right). Also update spec.md US2 scenario 3 wording to the ruling ("a dotted folder not in the manifest is removed only when byte-identical to Spec Kitty's render; otherwise untouched with a warning").
2. **The e2e test does not depend on the migration** (`test_m_4_0_0rc8_command_skill_hyphen_names.py:446-487`): with `apply()` stubbed to `MigrationResult(success=True)` it still passes, because the surface repair does the work. Assert something only the migration produces (e.g. `upgrade --json` → `migration_results["4.0.0rc8_command_skill_hyphen_names"].changes_made` contains `Removed legacy dotted command skill .agents/skills/spec-kitty.specify/SKILL.md`), or stub the surface repair so the migration alone must converge the clone.
3. (orchestrator decision) Installer refusals other than an unreadable manifest, and `AgentConfigError`, become **success + warning** naming `spec-kitty doctor skills` (consistent with R-m3: the surface repair re-runs the legacy rule on every upgrade, so nothing is lost, and a failed record would block every later migration).

Optional: N2 dry-run could also list would-be-kept / collision paths; N3 test the upgrade helpers through a real prepared-repairs object.
