---
affected_files: []
cycle_number: 1
mission_slug: command-skill-names-and-antigravity-01M5DBWT
reproduction_command:
reviewed_at: '2026-10-21T11:37:37Z'
reviewer_agent: claude
wp_id: WP09
---

# WP09 review feedback (cycle 1) + pre-PR squad folds — REJECT

WP09 review (docs accuracy):
1. `doctor skills` prints the wrong remedy for a dotted skill the manifest still records: "remove it when you no longer need your edits" (via `_print_command_skill_guidance`, `_command_surface_doctor.py:~474-480`, which sends only `_legacy_owned` paths to the `--fix` line). Fix the CODE: recorded legacy paths get the `spec-kitty doctor skills --fix` remedy; add a human-output test next to `test_skills_still_managed_legacy_entries_need_fix`; keep ADR §5 and docs/migrations/command-skill-hyphen-names.md:76-81 consistent with the fixed output.
2. Stale counts / agent lists: docs/api/init-lifecycle.md:56 (13/4 → 12/5); docs/guides/how-to/collaboration/manage-agents.md:332 (13 → 12), :22, :61, :156 (add Antigravity), :61 home-writer wording (use :82's wording); docs/api/configuration.md:357, 403, 452 (add Antigravity).
3. AGENTS.md:153 Letta "Command Surface" → `/spec-kitty-<command>`.
Optional: adr/4.x/index.md `updated:`; use `spec-kitty-<command>/SKILL.md` instead of the `spec-kitty-*` glob where command skills are meant; supported-agents.md:384-388 stale "13 slash commands"/"feature".

Pre-PR correctness squad:
4. MAJOR — shipped charter skills still teach dotted names (core-tracked, projected to every skills agent): src/charter/offering/skills/spk-start-here/SKILL.md:16, spk-start-command-map/SKILL.md:22-25 and references/command-map.md:17-18, spk-meta-skill-authoring/SKILL.md:13-16 (rule 3 calls `spec-kitty-*` "legacy aliases" — now collides), src/charter/offering/skills/README.md:79, spk-run-verdict-capture/SKILL.md:8 ("13 slash-command harnesses" → 12). Slash agents keep `/spec-kitty.<cmd>`; command skills are `spec-kitty-<cmd>` (`$spec-kitty-<cmd>` Codex, `/skill:spec-kitty-<cmd>` Pi, `/spec-kitty-<cmd>` Vibe/Letta/Antigravity). After editing shipped skills, check whether any manifest/hash/regen gate needs refreshing (pack-manifest regen gate, managed-skills hashes, snapshots).
5. MAJOR — generated AGENTS.md orientation hard-codes `/spec-kitty.specify` for every agent (src/specify_cli/session_presence/content.py:55); wrong for Antigravity (and Codex). Make it correct per writer (the session-presence writer knows its agent; use `command_skill_names.skill_invocation_token` for skill agents, `/spec-kitty.specify` for slash agents; if one shared AGENTS.md serves several agents, name both forms). Tests.
6. minor — one kept dotted skill yields three contradictory upgrade warnings (hyphen migration loops `install()` per agent: `m_4_0_0rc8_command_skill_hyphen_names.py:~165-171`; antigravity migration installs again: `m_4_0_0rc8_retire_antigravity_workflows.py:~307-312`; upgrade.py doesn't dedupe). Fix: install once per migration for all configured command-skill agents (one batch), and dedupe kept-path warnings by path across the upgrade report (keep the "has your edits, so it was kept" wording when a kept path was released this run). `doctor tool-surfaces` lists the kept finding once per agent — dedupe by path if cheap.
7. minor — Antigravity-only upgrades never show the new-invocation notice (FR-006): set the notice when the archive migration archived anything or installed command skills for a project that had legacy workflows.
8. minor — release note: a teammate on an older CLI gets a schema error on a pulled, migrated manifest (dotted pattern + `antigravity` enum); nothing is deleted. Add a line to the CHANGELOG entry and the how-to (if not already).
