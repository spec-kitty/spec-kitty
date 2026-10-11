# Trace: Approach

- Grounded via CodeGraph: located the single emit site `emit_captured._build`
  (`src/specify_cli/retrospective/lifecycle_events.py:466`) setting
  `record_path=str(canonical_path)` (absolute).
- Confirmed `canonical_path` is always under `repo_root` → `relative_to` is safe.
- Forward-only fix (no backfill). One WP: red-first regression + one-line surface change.
