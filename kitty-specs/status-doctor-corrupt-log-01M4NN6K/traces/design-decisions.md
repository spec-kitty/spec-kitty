# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-11 · planner-priti · Retain status.store canonical reader authority. Report log failure regardless of snapshot; no decision-doctor changes, automatic repair, reducer changes, or promised shared cross-doctor abstraction.

2026-10-11 · pi:implementer-ivan:openai-codex:gpt-6.1-sol · Added event_log_error Finding category using existing CLI envelope. None records failed read, distinct from empty list; expected StoreError/OSError/UnicodeError only. Canonical parser owns physical record locations; store change is only AttributeError in annotation decoder tuple. No repair, reducer, schema, adapter or dependency changes.

2026-10-11 · implementer-ivan · Cycle1 local extraction returns provisional health and membership findings separately, preserving public finding order (membership after issue/sparse/frontmatter). Guard exactly StoreError/OSError/UnicodeError over initial+dependent work. ReviewerSelfApproval uses existing canonical read_events_raw because lifecycle accessor masks OSError. No doctor parser/reducer/CLI/domain changes. Uninitialized cycle helper still masks a late PermissionError in runtime-overlay metadata; request parent's narrowly scoped authored-only dependency-reader amendment before claiming all dependent failures are guarded.

2026-10-11 · implementer-ivan · Parent-authorized two-line uninitialized_hint.py fold812d3647d48953c886e4b62b47c691b1bfb281dc uses read_authored_wp_frontmatter because dependency graph consumes only authored work_package_id/dependencies. Removing unnecessary runtime overlay eliminates swallowed canonical-log PermissionError while preserving dependency-cycle behavior; retained negative matrix green. No wp_metadata/parser/schema/decoder policy or additional production edits.
