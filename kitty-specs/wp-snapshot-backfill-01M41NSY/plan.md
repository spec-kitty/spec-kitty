# Implementation Plan: Drain the snapshot-versus-files work-package disagreement

**Branch**: `issue-5579-wp-snapshot-backfill` (planning base = merge target) | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/wp-snapshot-backfill-01M41NSY/spec.md`

## Summary

Repair the event log, not the reducer. A pure planner computes, per Mission, the WP-id gap between `tasks/WP*.md` and the reduced snapshot, resolves terminal evidence (`meta.json` `accepted_at`/`merged_at` or an operator evidence manifest), and builds deterministic seed events (`planned`, plus a forced `planned → done` for finished Missions) with a `migration:` actor. The write reuses the existing migration writer in `migration/backfill_runtime_state.py` (same status lock, same atomic verified append), so no new event-log writer or allowlist entry appears. A `spec-kitty migrate backfill-wp-status` subcommand exposes it. This repository's corpus is then drained with an evidence manifest and held by a set-based corpus parity test.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml, pydantic; `spec_kitty_events` (consumed, unchanged)
**Storage**: Mission files — `kitty-specs/<slug>/status.events.jsonl` (append-only JSONL), derived `status.json`, `meta.json`
**Testing**: pytest (unit for planner/writer, CLI tests via typer runner, corpus test over committed `kitty-specs/`), mypy --strict, ruff
**Target Platform**: Linux, macOS, Windows (CLI)
**Project Type**: single (CLI library)
**Performance Goals**: corpus parity test < 15 s over ~550 Missions (NFR-001); repair of one Mission < 2 s
**Constraints**: reducer unchanged (C-001); single writer — no new `_unsafe.ALLOWED_CALLERS` / writes-gate ledger entries (C-002); `migration:` actor (C-003); no dependency on PR #5581 (C-004); frozen-root sanctioned corrections (C-005)
**Scale/Scope**: 51 disagreeing Missions on this repository; ~545 Missions scanned

## Charter Check

- **Single canonical authority**: event log stays the sole lane authority; the write extends the existing migration writer rather than adding a second one. PASS.
- **Architectural alignment**: pure planner in `specify_cli/migration/` (same layer as the writer); no `status/` or `kernel` layering change. PASS.
- **ATDD / red-first**: WP01 lands an issue-pinned `@pytest.mark.regression` repro (a fixture Mission whose snapshot misses file WPs) RED through `materialize` before the fix, converted to a focused unit test after. WP03's corpus test is RED on the planning base (51 disagreements) and GREEN after the drain.
- **Gate discipline (SO #5)**: the parity gate starts with only reasoned bucket-C exemptions, is shrink-only (stale exemption fails), and carries a self-mutation control.
- **Archive freeze**: modifications to frozen files are ledgered as operator-sanctioned corrections (precedent #5258), citing Decision Moment `01M41NVK4T6Y912R0JBYS0A5DH`.
- **No full heavy suites**: run the named arch gate files only (list below).

## Project Structure

### Documentation (this mission)

```
kitty-specs/wp-snapshot-backfill-01M41NSY/
├── spec.md
├── plan.md
├── research.md
├── evidence-manifest.yaml     # WP03: terminal evidence for the corpus drain
└── tasks.md / tasks/WP0*.md
```

### Source Code (repository root)

```
src/specify_cli/migration/
├── wp_status_backfill.py          # NEW (WP01) pure planner: gap, evidence, seed events
└── backfill_runtime_state.py      # EXTEND (WP01) writer: apply a WP-status seed plan under the existing lock/append
src/specify_cli/cli/commands/
└── migrate_cmd.py (+ migrate/backfill_wp_status.py)   # WP02 subcommand
tests/unit/migration/test_wp_status_backfill.py          # WP01
tests/cli/test_migrate_backfill_wp_status.py             # WP02
tests/specify_cli/migration/test_corpus_wp_snapshot_parity.py  # WP03 corpus gate
tests/architectural/test_archive_root_byte_identical.py  # WP03 sanctioned-corrections entries
tests/architectural/test_json_contract_enumeration.py    # WP02 --json inventory
docs/ (how-to/reference for the subcommand), docs/changelog/CHANGELOG.md  # WP04
```

## Implementation Concern Map

| IC | Concern | Owner WP |
|----|---------|----------|
| IC-01 | Gap detection + terminal evidence + deterministic seed construction (pure) | WP01 |
| IC-02 | Applying a seed plan through the existing writer (lock, dedupe by event id, atomic append, regenerate `status.json` only if present) | WP01 |
| IC-03 | Operator CLI surface + JSON contract inventory | WP02 |
| IC-04 | Corpus drain (evidence manifest, run, sanctioned corrections) + parity gate | WP03 |
| IC-05 | Docs + CHANGELOG | WP04 |

## Architectural gate files to run (targeted, not the directory)

`test_status_events_writes_gate.py`, `test_status_unsafe_allowlist.py`, `test_no_legacy_status_emit_callers.py`, `test_2093_authority_invariant.py`, `test_archive_root_byte_identical.py`, `test_json_contract_enumeration.py`, `test_safety_registry_completeness.py`, `test_layer_rules.py`, `test_no_dead_symbols.py`, `test_no_legacy_terminology.py`; plus `tests/specify_cli/migration/test_dogfood_corpus_backfilled.py`, `tests/unit/migration/`, `tests/migration/`.
