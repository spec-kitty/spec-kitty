# Quickstart: witness the seed refusal (#6754)

Applies to a Mission checkout (any `kitty-specs/<mission>/` with a `status.events.jsonl`).
Substitute your own slug for `<mission>` and a WP id for `WP01`.

## 1. A caller can no longer write a seed

```bash
spec-kitty agent status emit WP01 --to claimed --mission <mission> --actor migration:backfill
```

Expected: exit 1, and a message saying a caller-supplied identity must not start with
`migration:` because reconstruction seeds are written in-process by migrations only.
Nothing is appended:

```bash
git diff --stat kitty-specs/<mission>/status.events.jsonl   # no output
```

The same refusal comes back as a machine envelope with `--json`.

```bash
spec-kitty orchestrator-api start-implementation --mission <mission> --wp WP01 \
  --actor migration:backfill --policy '{"profile":"python-pedro"}'
```

Expected: `"success": false`, `"error_code": "USAGE_ERROR"`, exit 1, no state change.

```bash
spec-kitty implement WP01 --mission <mission> --actor migration:backfill
```

Expected: exit 1 with the same refusal, and no lane worktree created.

## 2. Legitimate reconstruction still works

```bash
spec-kitty migrate backfill-wp-status --mission <mission> --dry-run --json
spec-kitty migrate backfill-wp-status --mission <mission> --json
grep -o '"actor": *"migration:[^"]*"' kitty-specs/<mission>/status.events.jsonl | sort -u
```

Expected: the seed rows the backfill writes still carry `migration:backfill_wp_status`
and still classify as seeds.

A seed already in the log keeps its status when a later command re-records that identity
with no caller option:

```bash
spec-kitty agent tasks move-task WP01 --to approved --mission <mission> --skip-review-artifact-check
```

Expected: the approval's actor is still the recorded `migration:…` identity.

## 3. An explicit `--agent` is still a live actor

```bash
spec-kitty agent tasks move-task WP01 --to claimed --mission <mission> --agent migration:x
```

Expected: the stored actor is `{"tool": "migration", "role": "implementer", "model": "x"}` —
tool `migration`, **not** a reconstruction seed. This is the operator's recorded
2026-10-29 ruling and is unchanged by this Mission.

## 4. The rule in one sentence

A `migration:` actor in a Mission's event log now means exactly one thing: a migration
module reconstructed it in-process. Nothing typed on a command line can produce one.
