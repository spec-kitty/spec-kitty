# Quickstart: Mission-State Repair Audit Trail (operator view)

## Before (defect #4928)

```bash
$ spec-kitty doctor mission-state --fix
Mission-state repair complete (updated=1, unchanged=0, errors=0).
# (no mention of where the audit trail went)

$ git check-ignore -v .kittify/migrations/mission-state/<run_id>.json
.gitignore:76:.kittify/migrations/    .kittify/migrations/mission-state/<run_id>.json   # IGNORED

$ git clean -xfd     # routine cleanup
# → manifest + quarantined rows silently destroyed; no record of the repair survives
```

## After (this mission)

```bash
$ spec-kitty doctor mission-state --fix
Mission-state repair complete (updated=1, unchanged=0, errors=0).
Audit trail written to .kittify/mission-state-audit/<run_id>.json (tracked, uncommitted).
Commit it to preserve the record of this repair.
2 row(s) quarantined verbatim to .kittify/mission-state-audit/quarantine/<run_id>/<slug>/status.events.jsonl.
Commit the audit trail before running 'git clean'.

$ git check-ignore -v .kittify/mission-state-audit/<run_id>.json
# (no output → NOT ignored, tracked-ok)

$ git add .kittify/mission-state-audit && git commit -m "record mission-state repair <run_id>"
$ git clean -xfd     # audit trail is committed → survives
```

## Verifying (`--json`)

```bash
$ spec-kitty doctor mission-state --fix --json | jq '{audit_manifest_path, audit_quarantine_path, quarantined_rows}'
{
  "audit_manifest_path": ".kittify/mission-state-audit/<run_id>.json",
  "audit_quarantine_path": ".kittify/mission-state-audit/quarantine/<run_id>/<slug>/status.events.jsonl",
  "quarantined_rows": 2
}
```

## What did NOT change

- Which rows the repair keeps vs quarantines (that is the #4897 registry, untouched).
- `--fix` still performs no git commit — you commit the audit trail yourself.
