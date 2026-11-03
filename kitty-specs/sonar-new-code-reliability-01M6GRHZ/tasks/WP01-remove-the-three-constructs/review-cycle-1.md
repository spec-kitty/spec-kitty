---
affected_files: []
cycle_number: 1
mission_slug: sonar-new-code-reliability-01M6GRHZ
reproduction_command:
reviewed_at: '2026-11-03T13:33:13Z'
reviewer_agent: user
wp_id: WP01
---

# WP01 review — round 1 (reviewer-renata)

Verdict: REJECT (one accuracy finding; everything else passes)

Anti-pattern checklist: 1 PASS · 2 PASS · 3 PASS · 4 PASS · 5 PASS · 6 PASS · 7 PASS · 8 PASS

## F1 — the new comment names a flag that does not exist (accuracy)

`src/specify_cli/cli/commands/events.py`:

```
#: The kind tailed when ``--kind`` is omitted, and the registry key it resolves through.
```

The command is `spec-kitty events tail` and the option is `--log`, not `--kind`
(`tail_command(..., log: _LogKind = typer.Option(_LOG_KIND_DEFAULT, "--log", ...))`).
The comment documents the wrong flag, and it is the first thing a reader sees on the changed
lines. Fix the comment (and any other new prose) to name `--log`.

## Notes that are not findings

- `assert refusal is not None` in `_tracked_mission_id`: the invariant holds by construction
  (`tracked_meta_refusal` returns `None` only when `not tracked.unavailable`, and this call sits
  inside `if tracked.unavailable:`), it is documented in both places, and it is not inside a
  `try` that catches `AssertionError`, so it cannot become the `S5779` class this mission is
  about. Behaviour under `python -O` is unchanged from the pre-change code for every reachable
  input. Accept.
- The guard module's shape probes strip comments before matching (`_code_only`), and the AST probe
  carries a positive control on each side, so none of the three can pass vacuously. Each of the
  three single-hunk reverts was re-run and reds only its own assertion — verified in review.
- Cold-cache pytest cost for the module is ~100 s on this checkout (bytecode recompile), 0.75 s
  warm. That is a cold-cache artefact, not the module's cost; recorded in the hand-off.
