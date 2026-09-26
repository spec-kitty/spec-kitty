# Quickstart — verifying Silent-Write Hardening Residuals

How to confirm each finding is fixed. All commands from the repo root; `PWHEADLESS=1` where a test touches UI-adjacent fixtures (none here, but the convention is harmless).

## Finding A — repair preserves an unregistered authoritative row

Red-first (proves the test witnesses the bug), then green:

```bash
# 1. Extend the guard/repair tests with an authoritative-shaped row whose event_type
#    is deliberately NOT in AUTHORITATIVE_NON_LANE_EVENT_TYPES.
# 2. Confirm red against the pre-inversion repair, then green after:
uv run pytest tests/migration/test_mission_state_repair.py \
             tests/status/test_authoritative_non_lane_registry_4897.py \
             tests/integration/migration/test_lifecycle_events_preserved.py \
             tests/unit/migration/test_canonicalization_rules.py \
             tests/status/test_read_events_tolerates_decision_events.py -q
```

Expected after fix: the unregistered authoritative row survives `--fix` (AC-A1); a would-be quarantine of any `event_type`-bearing row surfaces a non-zero/error (AC-A2); legacy `WPStatusChanged` still canonicalizes into `status.json` (AC-A3, #3066); duplicate-`event_id` dedupe does not hard-error (AC-A4).

## Finding B — one `catalog.mission` reader

```bash
# Parity + single-accessor tests:
uv run pytest tests/specify_cli/cli/commands/charter/test_recompile_preserves_mission_4908.py \
             tests/specify_cli/charter_runtime/test_references_parity_refresh.py -q

# SSOT proof — exactly one reader of catalog.mission remains:
grep -rnE "catalog.*\bmission\b|\[.?mission.?\]" src/specify_cli/charter_runtime src/specify_cli/cli/commands/charter src/charter/activation \
  | grep -iE "catalog" | grep -v "read_catalog_field\|read_catalog_mission"
# → expect: no direct catalog.mission reads outside the shared accessor
```

## Finding C — traces merge survives unusual markdown

```bash
uv run pytest tests/merge/test_traces_driver_section_union_4894.py -q
```

Expected after fix: a `~~~`-fenced heading-like line is not a boundary (AC-C1); duplicate-heading sections key distinctly and neither is dropped (AC-C2); a diverged single-heading section still stale-drops (AC-C3); whole-block dedup unchanged (AC-C4).

## Whole-mission gates (before hand-off)

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/architectural/test_no_legacy_terminology.py -q      # after any prose touch
PYTHONPATH=. uv run python -m scripts.docs.check_docs_freshness --ci      # after ADR/docs/changelog touch (errors=0)
```

Plus the mission's changed-file + owning-subsystem suites per the charter test policy (`tests/status/`, `tests/migration/`, `tests/merge/`, charter reader tests), and the ADR frontmatter description 50–180 char SEO gate.
