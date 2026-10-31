# Quickstart — verifying the dry-run payload authority

## For a reviewer

```bash
# 1. The red-first parity pin (fails on the pre-fix base, passes on the branch tip)
uv run pytest tests/migration/test_mission_state_teamspace_payload_authority.py -q

# 2. The existing dry-run / repair regression surface
uv run pytest tests/migration/ -q

# 3. The canonical-producer lint (no new violation, exemption retired)
uv run python scripts/lint_canonical_producers.py \
  --paths src/ scripts/ tests/ \
  --baseline scripts/canonical_producer_lint_baseline.txt

# 4. The facade, dead-symbol and integration-boundary gates
uv run pytest tests/architectural/test_status_module_boundary.py \
  tests/architectural/test_no_dead_symbols.py \
  tests/architectural/test_integration_boundary.py -q
```

## For an operator

```bash
# Run the dry-run over a repo and inspect one synthesized payload
spec-kitty doctor mission-state --teamspace-dry-run --json > /tmp/dry-run.json

# A model-rejected row shows up as a report entry, never a traceback:
#   {"error": "PAYLOAD_INVALID", "event_id": "...", "model_violations": [...]}
```

## What to look for

- The payload of a modern row carries `mission_id`; a legacy row without one has
  no `mission_id` key at all (not `null`).
- `reason`, `review_ref` and `evidence` are present as explicit `null` when unset.
- `summary` is absent.
- Two runs over the same repo produce identical `to_dict()` output (determinism).
