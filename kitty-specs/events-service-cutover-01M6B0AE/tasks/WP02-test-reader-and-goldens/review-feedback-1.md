# WP02 review feedback (cycle 1)

Reviewer: claude:opus:reviewer-renata:reviewer. Implementer of record: claude:opus:python-pedro.

## Verdict: changes requested (two small required fixes)

The core work is sound. The reader fails closed, nothing skips, the goldens are byte-identical, the scratch layout works, `--write` refuses without `--root`, and the suite passes with `services/` moved aside. Two lines still contradict the WP. Fix them and resubmit. No other change is needed.

## Required

1. **`tests/contract/test_mission_status_conformance.py:3`: a stale `services/` reference (breaks the DoD "No changed file references `services/`").**
   The module docstring still says the goldens live under ``services/mission-status-api/src/test/resources/conformance/``. Repoint it to ``conformance/`` of the pinned `conformance-fixtures` asset, as `_mission_status_conformance.py` now says. WP06's leftover scan (`git grep "services/mission-status-api" -- ':!*.md' …`) would flag this file too.

2. **`tests/glossary/test_torn_tail_repair_goldens.py:123`: the failure hint gives a command that no longer works.**
   The assertion message says `regenerate: uv run --frozen python -m tests.glossary.test_torn_tail_repair_goldens`. The `__main__` block now requires a target path, so that command exits with the usage error, and the pinned cache is read-only anyway. Make the hint say the same as the docstring: write the file into a spec-kitty-events checkout (`… test_torn_tail_repair_goldens <events checkout>/<path of repair-cases.json>`), which publishes it in its next `service-v*` release.
   Do **not** change the `"about"` text in `render_goldens()`. It must stay byte-identical to the pinned asset.

## Optional (not blocking)

3. `tests/contract/_mission_status_artifact_goldens.py` `main(["--check"])` without `--root` reads `CASES_FILE` (from `expected_extra_root`) with no fail-closed step. If the cache is missing it raises `FileNotFoundError`, not the `SERVICE_*` code and remedy. `_mission_status_conformance.main` resolves through `conformance_fixtures_root()`. Doing the same in the artifact generator would make the two CLIs consistent. The test path is already protected by the autouse fixture.

## Informational (no action)

- In `test_torn_tail_repair_goldens.py`, `pinned_extra()` runs at import, not through the `expected_extra_root` + autouse-fixture pattern. This is justified: `_COMMITTED` parametrizes at collection, so a pure path would fail with a bare `FileNotFoundError`. When the cache is empty, collection fails with `SERVICE_BINARY_MISSING … run \`make sync-services\``. That interrupts the session, but it fails closed and names the remedy.
- Contract tools are still loaded from the repo's `contracts/tools` (`_mission_status_payloads.load_contract_tools`). WP03 repoints them, so this WP correctly keeps the `"source"` string byte-identical.

## Verification run by the reviewer

- `uv run --frozen pytest tests/contract/test_pinned_service_assets.py tests/contract/test_mission_status_artifact_goldens.py tests/glossary/test_torn_tail_repair_goldens.py tests/contract/test_mission_status_conformance.py -q -p no:randomly -n 4 --dist loadfile`: 82 passed.
- The same run with `services/` moved to `/tmp/services.bak` (and moved back afterwards): 82 passed.
- `XDG_CACHE_HOME=<empty>`: the conformance and artifact modules give 62 setup errors, all `SERVICE_BINARY_MISSING … run \`make sync-services\``, with 0 skips. The torn-tail module gives a collection error with the same code.
- `python -m tests.contract._mission_status_conformance --write`: refused (`--write needs --root`). `--check`: 89 files, 0 differences.
- `ruff check`: clean on all 7 files. `ruff format --check --force-exclude`: 7 files formatted.
- `mypy tests/pinned_service_assets.py tests/contract/test_pinned_service_assets.py`: no issues. The other changed files show 5 errors, identical to the base `0c078081` (only the line numbers moved), so they are pre-existing.
