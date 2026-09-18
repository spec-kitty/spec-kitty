---
affected_files: []
cycle_number: 1
mission_slug: mission-handle-resolution-consistency-01M2TPWG
reproduction_command: spec-kitty agent tasks move-task WP02 --to approved --mission mission-handle-resolution-consistency-01M2TPWG
reviewed_at: '2026-09-18T19:20:21Z'
reviewer_agent: user
wp_id: WP02
---

Approved by user: Review passed (forced past unrelated blocker). Sole uncommitted-file blocker was WP03-plan-tasks-notfound/review-cycle-1.md, an untracked review-cycle artifact owned by WP03 — not in WP02 owned_files, not in WP02's commit; unrelated planning-ahead runtime noise. WP02 substance: FR-001 existence gate added right after path-safety-only resolve, before every mkdir/scaffold; emits canonical 'Mission not found: <handle>' via WP01 mission_not_found_message seam + Exit(1), killing the phantom kitty-specs/<handle>/ write. Red-first test reproduces phantom (pre-fix exit0 + scaffolds kitty-specs/zznope/ with data-model.md/research.md/research/*.csv) and asserts byte-identical snapshot after via in-process CliRunner (pytestmark present). Path-safety ../x refusal preserved as distinct Exit(2); no --json added. ruff/mypy clean, complexity<=15. pyproject exclude edit validated shrink-only (removes research.py + WP01's stale mission_resolver.py entries; baseline 2809 satisfied) and FORCED by test_ruff_format_exclude_ratchet::test_every_exclude_entry_still_genuinely_reformats (both now format-clean); reformat is pure line-joins. Gates green: ratchet+pyproject_shape 13 passed; tests/research 73 passed.
