# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-11 · planner-priti · Retain status.store canonical reader authority. Report log failure regardless of snapshot; no decision-doctor changes, automatic repair, reducer changes, or promised shared cross-doctor abstraction.

2026-10-11 · pi:implementer-ivan:openai-codex:gpt-6.1-sol · Added event_log_error Finding category using existing CLI envelope. None records failed read, distinct from empty list; expected StoreError/OSError/UnicodeError only. Canonical parser owns physical record locations; store change is only AttributeError in annotation decoder tuple. No repair, reducer, schema, adapter or dependency changes.
