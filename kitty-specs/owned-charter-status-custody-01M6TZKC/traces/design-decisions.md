# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-07 · planner-priti · [planning] Accept exactly two same-Mission surfaces: owned.mission_dir through the existing fast path and canonical STATUS_STATE.read_dir through mission_context_for only on inequality. Keep CharterScope.resolve anchored to owned_root/mission_dir and retain every foreign-path refusal.

2026-11-07 · implementer-ivan · [implement] Used canonical pre-PR fragment name 6788-owned-charter-status-custody.fixed.md per unreleased README rather than the WP shorthand 6788.fixed.md; rename to the PR number after creation. No planning or requirement change, so no analysis re-run is needed.
2026-11-07 · landing (operator-run review) · [land] The changelog fragment ships as docs/changelog/unreleased/7320.fixed.md (renamed by 43183fc057 after the PR number was known); WP01 owned_files/create_intent and lanes.json now name it. Plan-time prose keeps the planned name.
