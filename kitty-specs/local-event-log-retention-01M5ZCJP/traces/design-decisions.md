# Design decisions

- **[2026-10-27][specify] Operator rulings.** `keep_runs=20`, `max_age_days=30`, both limits must be exceeded, preview by default (2026-10-23, #6610); command `doctor event-logs --apply`, caches in scope, unknown Missions protected, `CleanupPolicy(retention, cleanup_command)` shape (2026-10-27). Disposition: decided.
- **[2026-10-27][plan] Lock files are never cleanup-eligible.** kernel/locks.py G3: release truncates, never unlinks. Disposition: decided.
- **[2026-10-27][plan] Age is file mtime; lock order run → index for a run deletion.** See research.md §7. Disposition: decided.

2026-10-27 · claude · [implement] WP02 rewrites feature-runs.json with run_index.write_index_file, not save_index, so unrelated entries stay byte-identical; test_no_dead_symbols stays red between WP02 and WP03 because the CLI is the engine's only src caller. Disposition: decided; WP03 closes the gate.

2026-10-28 · claude · [implement] Operator ruling 2026-10-28: keep the one dead-symbol allowlist entry for _event_logs_doctor::register (category_c_doctor_auto_discovery_seam, same reach path as the other doctor siblings); recorded as priced debt owned by #3508 in the PR's Deferred section. Disposition: decided.
