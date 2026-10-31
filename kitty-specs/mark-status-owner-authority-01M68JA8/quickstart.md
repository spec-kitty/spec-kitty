# Quickstart: verify the mark-status owner authority by hand

Disposable mission (any git repo works; `status_phase: "1"` is the event-sourced
subtask-completion authority):

```bash
mkdir -p /tmp/ms-qa kitty-specs/002-qa/tasks
cat > kitty-specs/002-qa/meta.json <<'JSON'
{"mission_id": "01QAMISSION00000000000000", "mission_slug": "002-qa", "mission_type": "software-dev", "status_phase": "1"}
JSON
```

## 1. Mixed sources are ambiguous (was: silently WP01)

```bash
# tasks.md: "## WP01\nSubtasks: T001\n\n## WP02\nSubtasks: T001"
# tasks/WP01-qa.md frontmatter: subtasks: [T001]
# tasks/WP02-qa.md frontmatter: (no subtasks key — legacy)
spec-kitty agent tasks mark-status T001 --status done --mission 002-qa --json
# expect: exit 1, "T001 is a subtask of WP01, WP02 ...; pass --wp to select one."
# expect: no kitty-specs/002-qa/status.events.jsonl
spec-kitty agent tasks mark-status T001 --status done --wp WP02 --mission 002-qa --json
# expect: exit 0, one event with "wp_id": "WP02"
```

## 2. A WP id is not a subtask (was: bogus `{"WP02": "done"}` on WP02)

```bash
# tasks.md carries "| WP | Title | Subtasks |" / "| WP02 | Foundation | T002 |"
spec-kitty agent tasks mark-status WP02 --status done --mission 002-qa --json
# expect: exit 1, "WP02: mark-status does not change work-package lanes. ..."
```

## 3. A subtask genuinely named like a WP id needs `--wp`

```bash
# tasks/WP01-qa.md frontmatter: subtasks: [WP02, T001]
spec-kitty agent tasks mark-status WP02 --status done --mission 002-qa --json
# expect: exit 1, owner named, both readings explained
spec-kitty agent tasks mark-status WP02 --status done --wp WP01 --mission 002-qa --json
# expect: exit 0, event with "wp_id": "WP01", subtasks {"WP02": "done"}
```

Regression guard (must not change): `mark-status T001 --status done` on a mission
where exactly one WP authors `T001` still writes one event and repeats are
`already_satisfied` no-ops.
