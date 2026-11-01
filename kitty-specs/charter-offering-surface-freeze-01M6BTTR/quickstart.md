# Quickstart — verify the offering surface freeze

## Prove the freeze can fail (red proof)

1. Add a name to the census `surface` section that is not exported, or drop a row:

   ```bash
   uv run pytest -q tests/architectural/test_charter_offering_public_surface.py \
     -k census_enumerates_exactly_the_live_surface
   ```

   Expected: failure naming the drift. Revert.

2. Add a symbol to `charter.offering.api.__all__` without a census row:

   ```bash
   uv run pytest -q tests/architectural/test_charter_offering_public_surface.py \
     -k census
   ```

   Expected: failure listing the unlisted export. Revert.

3. Mark a row `dto_status: final` or blank its `today_type`:

   ```bash
   uv run pytest -q tests/architectural/test_charter_offering_public_surface.py \
     -k dto_forward
   ```

   Expected: failure naming the row. Revert.

## Read the frozen surface

```bash
# The list maintainers read:
sed -n '/^__all__/,/^]/p' src/charter/offering/api.py

# The frozen census with provenance, facades and DTO direction:
cat tests/architectural/charter_offering_public_surface.yaml
```

## Full verification for this mission

```bash
uv run pytest -q tests/architectural/test_charter_offering_public_surface.py \
                 tests/architectural/test_charter_facades_reexport_offering.py \
                 tests/architectural/test_charter_activation_api_reexport.py \
                 tests/architectural/test_charter_offering_does_not_import_activation.py
uv run pytest -q tests/charter tests/charter_offering
uv run pytest -q tests/architectural/test_no_legacy_terminology.py
make test-fast
uv run ruff check src/charter/offering/api.py tests/architectural/test_charter_offering_public_surface.py
uv run mypy src/charter/offering/api.py
uv run python -m scripts.docs.check_docs_freshness --ci
```

Expected: all green. `check_docs_freshness` reports `errors=0`; its warnings are a
pre-existing baseline on this branch and are not caused by this mission.

## Change the surface later (the sanctioned path)

1. Edit `charter.offering.api.__all__` and its import.
2. Add or remove the matching `surface` row in the census with origin, facade,
   kind, today's type and DTO direction.
3. Re-run the gate files above; a mismatch in either direction fails.
4. If a runtime consumer needs a symbol that is not on the surface, record it in
   `public_contract_delta` and take it to the operator — do not widen the surface
   in the same change.
