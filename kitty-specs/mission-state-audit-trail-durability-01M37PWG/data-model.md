# Data Model: Mission-State Repair Audit-Trail Durability

## Entities

### Audit Root
The git-tracked directory that houses all mission-state repair audit artifacts, replacing the git-ignored `MANIFEST_ROOT` for these outputs.
- **Location**: `.kittify/mission-state-audit/` (repo-relative)
- **Invariant AR-1**: never git-ignored — `git check-ignore` reports paths under it as tracked-ok.
- **Invariant AR-2**: inside the repository boundary — passes `_assert_git_safe`.
- **Invariant AR-3**: declared in `_POLICY_TRACKED`, and `.gitignore` does not exclude it (the two agree).

### Repair Manifest
The per-run JSON record of what a repair did.
- **Fields** (unchanged from today): `run_id`, per-mission `{slug, reason, quarantined_rows}`, aggregate `quarantined_rows`, `file_changes`, `manifest_path`.
- **Written by**: mission-state repair (`_run_id.json`) and duplicate-key repair (`<dup-key-prefix><run_id>.json`).
- **Invariant M-1**: written on **every** run, including a no-op run that quarantines zero rows (a durable record of every repair).
- **Invariant M-2**: path is under the Audit Root (or an explicit caller-supplied `manifest_path`, honored as-is).

### Quarantine Artifact
The verbatim copy of rows removed from a mission's `status.events.jsonl`.
- **Path**: `<AuditRoot>/quarantine/<run_id>/<safe_mission_slug>/status.events.jsonl`.
- **Invariant Q-1**: written **only** when the repair removes ≥1 row.
- **Invariant Q-2**: byte-preserving — removed rows are stored verbatim.
- **Invariant Q-3**: under the Audit Root, so it survives `git clean` once committed.

## State / behavior invariants

- **B-1 (write-only)**: producing the audit trail performs no git add/stage/commit; the git index is unchanged by a repair run.
- **B-2 (no canonicality change)**: which rows are quarantined vs preserved is decided entirely by the unchanged #4897 registry path; this mission never alters that decision.
- **B-3 (parity)**: the human exit summary and the `--json` payload report the same audit paths and quarantined-row count.
- **B-4 (legacy)**: pre-existing artifacts under the old gitignored path are left untouched; the old path is retired for new writes, not dual-written.

## Relationships

```
Repair run ──writes──▶ Repair Manifest (1 per run)   ──under──▶ Audit Root
          └─writes──▶ Quarantine Artifact (0..N)     ──under──▶ Audit Root
Audit Root ──declared-in──▶ _POLICY_TRACKED  ──agrees-with──▶ .gitignore (not excluded)
```
