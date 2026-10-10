# Tooling-friction trace

Format: `[date][phase] SYMPTOM — anchor — disposition`

- [2026-10-10][specify] `agent mission create` without `--topology` on a topic branch with no upstream chose `coord`, never created the coordination branch, printed output the JSON parse could not read, and left a malformed scaffold (`MISSION_RESUME_MALFORMED`: coordination branch declared but missing) — `agent mission create` — workaround: removed the untracked scaffold, re-created with `--topology lanes`; open: file an issue.
- [2026-10-10][tasks] `finalize-tasks` failed twice with `index.lock: File exists` (no lock on disk afterwards, no git process besides gitstatusd) while `status.json`/`status.events.jsonl` were left staged by an earlier attempt; succeeded once those were unstaged — finalize-tasks / safe_commit — workaround: `git reset` the staged status files; open: investigate safe_commit staging when the index already holds the paths.
- [2026-10-10][implement] `agent action implement WP02` failed with `index.lock: File exists` at the status-start safe_commit (workspace created, status not started); the collider is likely the zsh prompt's gitstatusd daemons (5 running) refreshing the index — retry succeeded — safe_commit — open: safe_commit could retry briefly on index.lock contention.
