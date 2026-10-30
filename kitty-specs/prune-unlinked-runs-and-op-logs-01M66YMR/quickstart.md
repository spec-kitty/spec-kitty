# Quickstart — see the new verdicts for yourself

The change is in `spec-kitty doctor event-logs`. Nothing new to install or configure;
`ledger.retention` keeps its two keys.

## Reproduce the defect (before the fix)

In a throwaway project with a merged Mission, an old run whose run-index entry is
gone (its `state.json` names its Mission only through `inputs.mission_slug`), and an
old `profile-invocation-<id>.events.jsonl` for a completed Op:

```bash
cd /tmp/repro6739 && spec-kitty doctor event-logs --json
```

Before: `candidates: []`, and every one of those items is listed under `kept` with
`"reason": "Mission not found"`.

## After the fix

```bash
spec-kitty doctor event-logs          # preview; names each item and its reason
spec-kitty doctor event-logs --json   # same payload, machine readable
spec-kitty doctor event-logs --apply  # delete exactly the listed candidates
```

Expect:

- the unindexed run of the merged Mission to be a candidate with `mission` set to
  that Mission and reason `past retention; Mission completed`;
- an old run that names nothing to be a candidate with
  `past retention; no Mission recorded`;
- an old log of a completed Op to be a candidate with
  `past retention; Op completed`;
- an old log of an **open** Op to be kept with `Op is open`;
- an old log whose Op has no record here to be a candidate with
  `past retention; no Op recorded`;
- a run whose recorded Mission this checkout cannot find to still be kept with
  `Mission not found`.

## Tune the limits

Unchanged: `.kittify/config.yaml`

```yaml
ledger:
  retention:
    keep_runs: 50      # protect the newest 50 items of each kind
    max_age_days: 90   # and everything modified in the last 90 days
```

Nothing is deleted unless it is **both** outside the newest `keep_runs` of its kind
**and** older than `max_age_days`, and its work is over.

## Where the tests live

```bash
uv run pytest tests/core/test_event_log_retention.py -q      # engine verdicts + apply
uv run pytest tests/cli/commands/test_doctor_event_logs.py -q # command surface, JSON
uv run pytest tests/specify_cli/invocation/test_doctor_ops.py -q  # Op-open predicate
```
