# Quickstart: verifying the quick-win fixes

Run from the repository root checkout with the synced venv (`make sync-packs` once per checkout). Each WP's prompt names its exact commands; this page gives the reviewer's short path.

## Reproduce on the base (should fail before the fix)

| Issue | Probe |
|---|---|
| #7439 | Write a `status.events.jsonl` row with `"reason": "x y"` written `ensure_ascii=False`; `read_events(feature_dir)` raises `StoreError: Invalid JSON on line 1`; `read_events_lenient` returns 0 events. |
| #7441 | `serialize_event_line({"wp_id": "WP01", "evidence": {"x": float("inf")}})` returns text containing `Infinity`. |
| #7440 | `sanitize_event_for_log` with naive `session_started_at` + aware `session_ended_at` raises `TypeError`. |
| #7443 | Mission with `tasks/wp02-x.md` declaring `dependencies: [WP01]`: the dependency guard reads `()`. |
| #7442 | WP with `subtasks: [{id: T001, title: x}]`: `authored_subtask_roster` returns `["{'id': 'T001', …}"]`. |
| #7445 | BOM-prefixed `meta.json`: `load_meta(d)` raises `ValueError`; `load_meta(d, on_malformed="none")` returns `None`. |
| #7463 | `_extract_conflicts_from_events` on n requested + n resolved events grows ~×4 per doubling of n. |

## Verify after the fix

```bash
# WP01
.venv/bin/python -m pytest -q tests/status/test_store_line_framing.py tests/status/test_store.py \
  tests/specify_cli/status/test_store_sanitized.py tests/specify_cli/events/test_sanitizer.py
# WP02 + WP05
.venv/bin/python -m pytest -q tests/status/test_dependency_guard.py tests/specify_cli/core/test_subtask_rows_snapshot.py \
  tests/specify_cli/status/test_reconstruct_wp_view.py tests/specify_cli/cli/commands/agent/test_mark_status_authored_roster.py \
  tests/specify_cli/migration/test_dogfood_corpus_backfilled.py tests/architectural/test_archive_root_byte_identical.py
# WP03
.venv/bin/python -m pytest -q tests/specify_cli/test_mission_metadata.py tests/tasks/test_tasks_support.py
# WP04
.venv/bin/python -m pytest -q tests/agent/cli/commands/test_glossary.py
```

Red-first check (reviewer): check out the WP's test commit alone and confirm its new tests fail; then the WP tip and confirm they pass.

Mission 058 check: `git diff <base> -- kitty-specs/058-hybrid-prompt-and-shim-agent-surface/tasks/` shows only removed `title:`/`status:` lines and `- id: TNNN` → `- TNNN` rewrites (28 entries).
