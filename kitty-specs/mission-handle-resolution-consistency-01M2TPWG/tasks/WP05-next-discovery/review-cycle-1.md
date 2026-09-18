---
affected_files: []
cycle_number: 1
mission_slug: mission-handle-resolution-consistency-01M2TPWG
reproduction_command: spec-kitty agent tasks move-task WP05 --to approved --mission mission-handle-resolution-consistency-01M2TPWG
reviewed_at: '2026-09-18T19:40:56Z'
reviewer_agent: user
wp_id: WP05
---

Approved by user: Review passed (reviewer-renata, independent): C5 discovery correct — _resolve_mission_slug empty/None returns sole slug or raises typed MissingHandleDiscovery (C901<=15 verified); caller next_step raises typer.Exit(1) not BadParameter/exit2; 1=auto-select+proceed, N=list 'slug (mid8) — friendly_name' cap10 + re-run hint, 0=specify nudge; JSON parity (available_missions for N, NO_MISSIONS_FOUND for 0); uses WP01 list_missions_for_selection (legacy-tolerant, not all_missions); legacy sole mission auto-selects + backfill nudge; present-but-bad handle keeps clean MISSION_NOT_FOUND; FR-009 test runs real preflight (no bypass); assertions check semantics not 'Invalid value'. C5 co-change to test_wp02_no_selector_exit2.py validated: updates ONLY the two superseded next BadParameter assertions, TestResearchNoSelector untouched (whitespace only). Gates: tests/next+test_wp02 568 passed/1 skipped; test_next_fail_closed 13 passed; ruff check+format clean.
