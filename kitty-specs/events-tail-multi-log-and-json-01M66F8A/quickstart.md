# Quickstart — following any ledger with `events tail`

`spec-kitty events tail` is the local subscriber for the event ledger (ADR
2026-10-13-2 D-2). Since #6611 it can follow every canonical ledger kind, and
its output is human-readable by default.

## Follow a mission's status stream (unchanged default)

```bash
spec-kitty events tail --mission <slug>
```

One readable line per event. Add `--json` for machine-readable JSON lines —
the same byte-for-byte envelope scripted consumers used before (each line
carries `tail_offset`/`tail_invariant` so a restart can resume by cursor).

## Follow another ledger kind

```bash
spec-kitty events tail --mission <slug> --log decisions   # decision-log stream
spec-kitty events tail --mission <slug> --log run         # latest run journal
spec-kitty events tail --mission <slug> --log glossary    # the mission's glossary log
spec-kitty events tail --mission <slug> --log mission     # Mission v1 events
spec-kitty events tail --mission <slug> --log ops         # Op lifecycle log (project)
spec-kitty events tail --mission <slug> --log canonical   # project canonical events
```

- `decisions` resolves through the same topology-aware status surface as the
  default `status` kind, so a coordination-routed mission's decision stream is
  followed on its real home.
- `run` picks the mission's **most recently modified** run journal under
  `.kittify/runtime/runs/`. If no run belongs to the mission, the command
  refuses (`run_log_unavailable` on stderr, exit 1) rather than show another
  mission's run.
- A log that does not exist yet is waited for, not an error: `--once` prints
  nothing and exits 0; a stream starts with the first write.

## One-shot poll, bounded streams, resume

```bash
spec-kitty events tail --mission <slug> --log decisions --once        # poll once, exit
spec-kitty events tail --mission <slug> --log run --max-events 50     # bounded stream
spec-kitty events tail --mission <slug> --log decisions --json \
    --from-offset <tail_offset> --from-invariant <tail_invariant>     # resume by cursor
```

Resume offsets validate against whichever log `--log` selected; a refused
resume (`invalid_resume_offset`, `resume_content_mismatch`) prints its envelope
on stderr and exits 2 without streaming anything.

## Where each log lives

| `--log` | Path |
|---------|------|
| `status` (default) | the mission's resolved status surface, `status.events.jsonl` |
| `decisions` | same resolved surface, `decisions.events.jsonl` |
| `mission` | `kitty-specs/<mission>/mission-events.jsonl` |
| `run` | `.kittify/runtime/runs/<run_id>/run.events.jsonl` (latest for the mission) |
| `glossary` | `.kittify/events/glossary/<mission_id>.events.jsonl` |
| `ops` | `kitty-ops/lifecycle.jsonl` |
| `canonical` | `.kittify/canonical-events.jsonl` |
