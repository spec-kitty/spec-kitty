---
affected_files: []
cycle_number: 1
mission_slug: command-skill-names-and-antigravity-01M5DBWT
reproduction_command:
reviewed_at: '2026-10-20T23:07:19Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 review feedback (cycle 1) — REJECT

User edits are never lost on any path tried (NFR-001 holds). Two behaviour defects must be fixed.

1. **Removing one agent strips the other agents' command skills** (`command_installer.py:~1152`, `remove()` `:~1354`; also `tool_surface/providers/command_skills.py:~412`). A remove-only preparation runs `migrate_legacy_entry` on every legacy entry. Repro: `init --ai codex,vibe`, convert to the legacy layout, `spec-kitty agent config remove vibe` → codex's 13 unmodified dotted skills deleted, nothing reinstalled, manifest `entries: []`, output "0 files deleted", no warning for the kept edited file (`agent/config.py:~575` never calls `install_warnings`).
   Fix: in a preparation with `remove_agents` and no `agents`, delete an owned legacy file only when the removed agent is its last owner, otherwise just drop that agent from the legacy entry (leave the migration of the remaining owners' files to their next install/upgrade). Print `install_warnings(report)` and count legacy deletions in `agent config remove`. Test: codex+vibe legacy fixture, remove vibe → codex still has its command skills (legacy or canonical) and the warning prints.
2. **Tool-surface repair misreports kept files** (`providers/command_skills.py:~442-454`, `_legacy_status` `:~348-357`). `RepairResult.skipped` must hold surface ids (as in `agent_profiles.py:465`, `repair.py:162/206`), not sentences; a kept legacy path lands in `eligible` and is reported as repaired on every later `--fix`; the visible text never says "kept, no longer managed".
   Fix: exclude `legacy_kept`/`collision` paths and verify-`legacy` instances from `eligible`; put their surface ids in `skipped`; surface the kept/no-longer-managed wording via the status finding (reuse `legacy_kept_warning`) or a rendered diagnostic. Update `test_repair_retires_legacy_skills_and_reports_the_kept_one_as_skipped`.

Also fix (orchestrator decision, recorded in traces/design-decisions.md):
3. `_verify_legacy_folders` (`command_installer.py:~1450`) must not report a `spec-kitty.<cmd>/SKILL.md` that no longer exists; report the leftover folder (`.agents/skills/spec-kitty.<cmd>/`) when only other files remain, and the SKILL.md path when it exists.
4. Exit codes: `doctor skills` (with or without `--fix`) treats a kept edited legacy skill as a **warning** (exit 0 when nothing else is wrong), because keeping it is the user's choice and would otherwise fail doctor forever; a **collision** stays a failure (exit 1), because a command skill is not installed until the user resolves it. Update the trace entry and tests.

Optional: the two pre-existing mypy `no-any-return` errors in `_command_surface_doctor.py` are not this WP's.
