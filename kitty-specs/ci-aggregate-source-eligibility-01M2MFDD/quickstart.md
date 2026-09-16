# Quickstart: CI Aggregate Source-Eligibility

## What ships
- `scripts/ci/source_eligibility.py` — pure provenance/eligibility decision + `gh`-at-the-edge `main()`.
- `tests/ci/test_source_eligibility.py` — red-first unit cases + execution-grounded wiring guard + guard-byte pin.
- `.github/workflows/ci-aggregate.yml` — `last-success` step rewired to call the helper (guard byte-unchanged).
- `docs/adr/3.x/2026-09-15-1-...md` — #4360-A annotated (mechanism superseded; failure cosmetic).

## Run the tests (from repo root)
```bash
export PYTHONPATH=$(pwd)/src         # global spec-kitty resolves a sibling checkout — force local (memory)
uv run --frozen python -m pytest tests/ci/test_source_eligibility.py -q
```

## Local gates before pushing (hard-won)
```bash
export PYTHONPATH=$(pwd)/src
uv run --frozen python -m pytest tests/ci/test_source_eligibility.py -q
uv run --frozen ruff check .
uv run --frozen ruff format --check .                       # SEPARATE gate from ruff check
uv run --frozen python -m pytest tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen python -m pytest tests/contract/test_example_round_trip.py -q   # contracts/*.md yaml needs skip marker
# actionlint is NOT installed — download the release binary and run it on the touched workflow; paste RAW output in the PR
./actionlint .github/workflows/ci-aggregate.yml
```

## Manual smoke of the decision
```bash
# eligible push-main source present:
echo '{"event":"push","head_branch":"main","conclusion":"success"}' > /tmp/trigger.json
echo '[{"databaseId":123,"conclusion":"success","headBranch":"main","event":"push"}]' > /tmp/cands.json
python3 scripts/ci/source_eligibility.py --trigger /tmp/trigger.json --candidates /tmp/cands.json
# → run-id=123 / eligibility=eligible-source

# PR-head trigger → named not-a-main-source, empty run-id:
echo '{"event":"pull_request","head_branch":"feat/x","conclusion":"failure"}' > /tmp/trigger.json
python3 scripts/ci/source_eligibility.py --trigger /tmp/trigger.json --candidates /tmp/cands.json
# → run-id= / eligibility=pr-head-trigger
```
(Exact CLI arg shape is the implementer's, matching `select_source_artifacts.py`; the contract fixes only the emitted `run-id`/`eligibility` keys.)

## Post-merge verification (C-005 / NFR-002 — proven on the merged main tip, not the PR head)
- Find a real push-main CI Aggregate run → confirm it resolved an eligible source.
- Find a real PR-head-triggered CI Aggregate run → confirm the surface classified it `pr-head-trigger` (empty `run-id`), and confirm (unchanged) that no main-verdict consumer read it.
