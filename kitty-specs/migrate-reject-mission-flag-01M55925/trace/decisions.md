# Mission Trace — Decisions

Append-only log of load-bearing decisions. Seeded at planning; appended during implement.

- **2026-10-17 (specify)** — Scope: reject-set is FIVE commands, not four. Operator approved including `repin-hooks` (5th sibling of identical silent-swallow class) this session. Decision Moment `01M5592YNBAT1PC4P7EB2SP3Y9`.
- **2026-10-17 (specify)** — Seam: `CorpusWideCommand(TyperCommand)` in `migrate_cmd.py`, `parse_args` post-check reusing #4964 helpers (`_given_on_command_line` + `_usage_error_class`). TyperCommand subclass ⇒ walker left-alone contract ⇒ no edit to `make_leaf_commands_mission_agnostic`. Empirically verified by the brownfield grounding lens.
- **2026-10-17 (specify)** — Message is scope-neutral ("not mission-scoped"), because the five do not share one scope model (corpus-walk vs pack-scoped `rewrite-opposed-by` vs repo-repair `repin-hooks`).
- **2026-10-17 (specify)** — Real per-mission scoping explicitly DEFERRED (operator triage 2026-10-08); follow-up issue to be filed.
