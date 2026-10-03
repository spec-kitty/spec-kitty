# Contract: `spec-kitty migrate backfill-wp-status`

Operator-facing contract delivered by WP01 (engine) and WP02 (CLI). The user
documentation is `docs/migrations/backfill-wp-status.md`; this file pins the
contract the tests hold.

## Inputs

- `--mission <handle>`: optional; resolved mission_id → mid8 → slug (ambiguous → `MISSION_AMBIGUOUS`, unknown → `MISSION_NOT_FOUND`; both exit 1, nothing written). Absent → whole `kitty-specs/` corpus.
- `--dry-run`: report the plan; write nothing.
- `--evidence-manifest <file>`: YAML `missions: {<exact Mission dir name>: {reason: <non-empty text>}}`, validated before any write.
- `--json`: one JSON object on stdout.

## Behaviour

| Case | Events appended |
|------|-----------------|
| WP file with no lane event | `genesis → planned`, actor `migration:backfill_wp_status` |
| Same, Mission finished (`meta.json` `merged_at` > `accepted_at` > manifest entry) | plus forced `planned → done`, `force: true`, `evidence: null`, reason citing the evidence |
| WP with any lane event | none |
| Snapshot WP with no file | none (reported `snapshot_only`) |

Event ids are deterministic; re-runs append nothing. Terminal evidence supplied on a later run is a no-op. `status.json` is regenerated only where it already exists. Writes go through the existing migration writer (`migration/backfill_runtime_state.py`, same lock and atomic verified append).

## Output

- Exit `0`: every visited Mission repaired or needed nothing. Exit `1`: any per-Mission error, invalid manifest, unknown/ambiguous handle.
- JSON keys: `dry_run`, `result`, `mission`, `summary{scanned, missions_seeded, missions_would_seed, events_seeded, events_would_seed, finished_missions, snapshot_only_missions, malformed_missions, skipped, errors}`, `manifest{path, entries, unused[{mission, reason}]}`, `missions[{slug, seeded, would_seed, files_only, snapshot_only, malformed, terminal_reason, status_json_refreshed, skip_reason, error}]`. Pre-write failure: `{success: false, error_code, error}`.

## Invariant held by the corpus gate

For every committed Mission, the WP-file id set is contained in the reduced snapshot's WP keys; extra snapshot keys are allowed only through a reasoned, shrink-only exemption (`tests/specify_cli/migration/test_corpus_wp_snapshot_parity.py`).
