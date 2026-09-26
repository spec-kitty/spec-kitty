# Contract: Audit-Trail Output (exit summary + `--json`)

Scope: `spec-kitty doctor mission-state --fix` (and the `upgrade`-invoked path). Placement/visibility only.

## Exit summary (human, stdout)

**Always** (every completed `--fix` run, including zero-quarantine):
```
Audit trail written to <audit_manifest_path> (tracked, uncommitted).
Commit it to preserve the record of this repair.
```

**Additionally, when ≥1 row was quarantined**:
```
<N> row(s) quarantined verbatim to <audit_quarantine_path>.
Commit the audit trail before running 'git clean'.
```

Requirements:
- C-EX-1: `<audit_manifest_path>` is repo-relative and under the tracked Audit Root.
- C-EX-2: the "tracked, uncommitted" phrasing is present so the operator knows durability requires a commit (C-002).
- C-EX-3: the quarantine line appears **iff** `quarantined_rows > 0`.
- C-EX-4: no path printed is git-ignored (asserted via `git check-ignore` in tests).

## `--json` payload additions

The `--fix --json` object gains (names final at implement time; keep snake_case):
```json
{
  "audit_manifest_path": ".kittify/mission-state-audit/<run_id>.json",
  "audit_quarantine_path": ".kittify/mission-state-audit/quarantine/<run_id>/<slug>/status.events.jsonl",
  "quarantined_rows": 0
}
```

Requirements:
- C-JS-1: `audit_manifest_path` present on every run.
- C-JS-2: `audit_quarantine_path` present (non-null) **iff** `quarantined_rows > 0`; otherwise `null` or omitted (choose one, document it).
- C-JS-3: `quarantined_rows` equals the count reported in the human summary (B-3 parity).
- C-JS-4: existing `--json` fields are unchanged (additive only).

## Non-goals (explicit)

- No change to which rows are quarantined/preserved.
- No git add/stage/commit performed by `--fix`.
- No migration of pre-existing artifacts at the old gitignored path.
