# Research: mark-status owner authority (issue #6463)

## Decisions

### D1 — Ground the report against `main`, not the report

The issue body (written against 3.2.7) claims a bare `T001` always resolves to
the alphabetically first WP. On `main@35318ef51c` that is **no longer true**:
`agent tasks mark-status` exposes `--wp`, `_resolve_task_owners`
(`src/specify_cli/cli/commands/agent/tasks_mark_status.py:341-371`) refuses a
shared id before writing, and `test_tasks_mark_status.py:90-156` pins it
(#5067, landed in #5953, changelog line 325).

Decision: do not re-fix the reported path. Ground the *class* — silent wrong-WP
writes — and close the residue that still produces them. This matches the
planner triage note on the issue (`triage:repro-needed`).

### D2 — The surviving defect is three ways the ownership decision is not single-sourced

Evidence gathered by running the built CLI (`uv`-installed, this checkout) against
disposable missions in `research/evidence/`:

1. **Roster-or-history fallback hides a second claim.** `_owners_for_task` is
   `authored_roster_owners(owner_map, task_id) or history_wp_ids(tasks_content, task_id)`.
   A WP with no `subtasks:` frontmatter (legacy) that claims the id in a
   structured `tasks.md` row never contributes an owner when *any* WP authors the
   id. Observed: WP01 roster `[T001]`, legacy WP02 with `## WP02` +
   `Subtasks: T001`, unscoped `mark-status T001` → `{"wp_id": "WP01", "subtasks":
   {"T001": "done"}}`, exit 0, no refusal. The WP02 implementer's mark lands on
   WP01.
2. **A `WP<digits>` id skips the ownership check entirely**
   (`if re.fullmatch(r"WP\d+", ...): continue`), and the resolver chain runs
   `_resolve_pipe_table`/`_resolve_inline_subtasks` *before* `_resolve_wp_id`'s
   lane-transition rejection. Observed: a `tasks.md` WP index table plus
   `mark-status WP02 --status done` → `{"wp_id": "WP02", "subtasks": {"WP02":
   "done"}}`, exit 0 — a work package recorded as its own subtask instead of the
   documented rejection.
3. **The write path re-derives ownership by first match.**
   `_ms_emit_subtask_state` uses
   `st.task_wps.get(id) or _resolve_history_wp_id(...) or owning_wp_from_authored_roster(...)`.
   When the resolution phase recorded no owner, the event's target WP is decided
   by document order or alphabetical filename. This is the mechanism that makes
   1 and 2 land *somewhere* instead of failing.

### D3 — Sources that may feed the owner map, and sources that may not

`history_wp_ids` only counts **structured** `tasks.md` rows (checkbox, pipe-table
row, inline `Subtasks:` list under a WP heading); prose mentions never yield an
owner (#5953 commit `cf40a5850c`). So unioning the two sources (`D4`) cannot
reintroduce the prose false-positive that #5953 removed. Authored
`subtasks:` frontmatter stays the canonical static intent; `tasks.md` structured
rows only add *claims* that make an id shared.

Decision: union, and keep unreadable rosters fail-closed (unchanged).

### D4 — Refuse, do not guess

Where two sources/WPs claim an id, or a `WP`-shaped id is also an authored
subtask, the command refuses with the owner list and the exact `--wp` to rerun
(exit 1, no event). Where a `WP`-shaped id is claimed by nobody, the existing
lane-transition rejection is kept but moved ahead of the legacy row shapes so a
WP index row cannot claim it.

### D5 — The emit has one authority

`_ms_emit_subtask_state` will attribute only from `st.task_wps`; an updated id
with no recorded owner refuses before any event is appended (it already collects
all unresolved ids before emitting, so the refusal is pre-write).

## Evidence

- `research/evidence/repro-mixed-source.txt` — D2.1, transcript.
- `research/evidence/repro-wp-index-row.txt` — D2.2, transcript.
- `research/evidence/grounding-command.txt` — the built CLI invocations used.

## Open questions

- **Q1** — Should `owning_wp_from_authored_roster` stay exported once the emit no
  longer uses it? Keep it: `_resolve_authored_roster` still needs an existence
  probe, and the `tasks` compat re-export surface requires it.
- **Q2** — Does the union rule add a refusal for the shipped `software-dev`
  template? No: that template's `tasks.md` lists subtasks as plain lines (not
  checkbox/pipe/inline), so `history_wp_ids` yields nothing and the roster stays
  the sole source — pinned by a compatibility test (NFR-001).
- **Q3** — Message wording for the `WP`-shaped ambiguous case: name the owner and
  both readings (subtask vs lane) so the caller can pick.
