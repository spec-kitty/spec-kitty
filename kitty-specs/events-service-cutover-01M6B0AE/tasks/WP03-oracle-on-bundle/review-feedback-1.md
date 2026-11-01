# WP03 review cycle 1: changes requested

Reviewer: claude:opus:reviewer-renata:reviewer. Implementer of record: claude:opus:python-pedro.

The re-point is mostly sound. Validation run: 1804 passed, 5 skipped; the 5 skips are the pre-existing performance and online cases in `test_mission_status_reality.py`. The run passes with `contracts/*` (except `contracts/fixtures`) moved aside (507 passed over six files). ruff, format (`--force-exclude`) and C901 are clean. mypy reports the same 61 errors on the base and on HEAD (identical sets). `bundled_schema` returns the same `description`, `enum`, `pattern`, `maxLength` and `properties` that the source files carried for every title a test reads (checked against `2edcea25`). Where uses disagree, a dropped key raises `KeyError`, so it does not pass vacuously.

Two findings block approval.

## 1. MEDIUM: row 8 provenance rule weakened, and a cheap strict equivalent exists

`tests/contract/test_mission_status_project.py:700-703`: "exactly one of x-source / x-derived" became "at least one" for all five new properties. Only `health` carries both in the bundle: the bundle inlines `ProjectHealth`, which brings `x-source: CompatibilityStatus`, and the property keeps its own `x-derived`. The other four properties (`specKittyVersion`, `schemaVersion`, `currentBranch`, `lastActivityAt`) still carry exactly one, so relaxing the rule for them drops a check that still holds.

Ask:
- Replace the loop with an exact expectation per property, for example
  `EXPECTED_PROVENANCE = {"specKittyVersion": ("x-source",), "schemaVersion": ("x-source",), "health": ("x-derived", "x-source"), "currentBranch": ("x-source",), "lastActivityAt": ("x-derived",)}`,
  and compare the sorted carried keys to it.
- For `health`, also assert that its `x-source` is the inlined `ProjectHealth` one (`symbol == "CompatibilityStatus"`). The extra key is then explained by the inlining and not tolerated blindly.
- Add a plant to the plant tuple at `:726`: a copy of the real schema where, for example, `schemaVersion` carries both keys, or `lastActivityAt` has lost its `x-derived`. `schema_problems` must refuse it.

## 2. MEDIUM: the corpus script reports a missing contract bundle as a conformance difference (exit 1, traceback)

`scripts/ci/mission_status_corpus_compare.py:608-626`: `default_tools_root` (`:347`) checks only the `contract_tools` extra. When the `contracts` (contract-bundles) extra is absent, importing the oracle runs `_WP_ID_SCHEMA = bundled_schema("WpId")` (`tests/contract/_mission_status_payloads.py:206`). That calls `pinned_extra("contracts")`, which raises `_pytest.outcomes.Failed`, a BaseException that `main` does not catch. The script then dies with a traceback and exit 1. Exit 1 is `EXIT_DIFFERENCE` ("rows not equal"), so the nightly would report a missing fetch as a conformance failure. It also prints the cache path, which the module docstring says the output never does.

Reproduced:
- `XDG_CACHE_HOME=<empty> python scripts/ci/mission_status_corpus_compare.py --base-url http://127.0.0.1:9 --repo-root . --report /tmp/r.json --tools-root <pinned tools dir>` gives exit 1 and the traceback `Failed: SERVICE_BINARY_MISSING contract-bundles-...`.
- The same happens with a cache that holds the tools extra but not the bundle extra.

The new `--tools-root` flag makes this the normal case for anyone who passes it without a full cache.

Ask:
- Before `open_oracle`, preflight the `contracts` extra through `extras_root(repo_root, READ_SERVICE, "contracts", ...)` regardless of `--tools-root`, and map `SyncServicesError` to exit 2 with the `SERVICE_*` code and no path. Reusing `ToolsRootUnavailable` or a sibling is fine.
- Add a test next to `tests/ci/test_mission_status_corpus_compare.py:533` that covers a missing bundle extra together with a given `--tools-root`. It must assert exit 2, the code named in the output, and no path in the output.

## Low / informational (no action required to approve, but please list in the PR)

- The deleted assertion `"ends the scan in" not in CHANGELOG.md` (`test_mission_status_drift.py`, formerly the end of `test_the_contract_prose_states_what_an_unreachable_remote_does`) is legitimate: the bundle ships no CHANGELOG. List it as a residual in the PR together with the D-6 residuals. Port it to spec-kitty-events.
- `tests/contract/test_mission_status_payloads.py:1114` uses `.get("examples") or []` and then `assert examples`. That is non-vacuous. `helper.non_empty_examples(...)` would match the other loops (optional).
- Red gate (`_local_contract_reads`): it finds hits in 11 of 12 base files. `scripts/ci/mission_status_corpus_compare.py` had 0 hits on the base because it read the tools through `load_contract_tools`. The payloads entry covers that read, so the gate is not vacuous, but that list entry proves nothing alone. The detector also misses a single-string spelling such as `joinpath("contracts/tools")`. Optional: add `contracts/tools\b` as a pattern.

## Removed assertions, accounted for

| Removed | Judgement |
|---|---|
| `_mission_status_detail.py` `assert isinstance(loaded, dict)` | replaced by the mapping check in `_bundled_document` (RuntimeError). OK |
| `test_mission_status_artifacts.py` `document.is_file()` and the per-file security assertion | replaced by root-minus-paths plus the three path items. Equivalent. OK |
| `test_mission_status_drift.py` CHANGELOG assertion | residual (no CHANGELOG in the bundle). OK, list in the PR |
| `test_mission_status_project.py` exactly-one provenance | weakened. Finding 1 |
| `test_mission_write_contract.py` success/refusal example tests, split-root test | re-keyed by title and content. The refusal list is pinned to the 5 base codes and fails on empty. Renamed to the bundled root. OK |
