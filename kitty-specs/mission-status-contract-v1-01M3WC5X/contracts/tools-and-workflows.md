# Contract: `contracts/tools/` scripts, message codes and workflow jobs

This is the internal contract between the work packages of Mission `mission-status-contract-v1-01M3WC5X`. The product contract itself (the OpenAPI document) is the deliverable and lives in `contracts/mission-status/` at the repository root once built; this note fixes the shapes the scripts and workflows share so lanes can work in parallel. It is a planning artefact: the implementation may refine a code name, but must keep every property listed here (one stable code per failure cause, exit status semantics, a printed `counts:` line).

## Script conventions (all `contracts/tools/*.py`)

- Run as a bare script: `python contracts/tools/<name>.py [options]`. Standard library plus locked dependencies (PyYAML, jsonschema with `referencing`) only. Imports only sibling modules by name. Never imports pytest, anything under `tests/`, or `scripts.`.
- Exit status: `0` pass; `1` the check ran and found a violation; `2` the check **could not do its job** (missing input, missing tool, empty corpus, zero inputs, unreadable manifest). No path exits `0` having examined nothing.
- Output: failures as `CONTRACT-CHECK <name>: <CODE>: <detail>`, one per violation, naming the file and, where relevant, the property path or JSON pointer. The last line is always `counts: key=value key=value ...`, printed on pass and on fail.
- Module discovery: a module is a direct subdirectory of the contracts root holding a root `openapi.yaml`. `_shared`, `fixtures`, `gradle` and `tools` are never modules. The contracts root is a parameter (`--root`, default `contracts`) so negative tests can point a script at `contracts/tools/fixtures/<case>/`.
- Fixtures: one subdirectory per script under `contracts/tools/fixtures/`, each holding planted violations and a clean control on the same root. Committed planted files contain nothing leak-shaped. Leak-class plants (host paths, e-mail addresses, forbidden property names) are never committed: `fixture_builder.py` assembles them from string fragments into a temporary root at run time, the `negative-tests` job and the unit tests point the scan at that root, and only the clean controls are committed. The text-level `leak_scan` has no exempt directory and no exempt marker line.

## Libraries

| Module | Provides | Used by |
|---|---|---|
| `contract_resolver.py` | `resolve(module_dir)` returning the dereferenced tree and counts (`path_items`, `schemas`, `refs_resolved`); stable errors `UNRESOLVED_REF`, `URL_REF`, `ABSOLUTE_REF`, `TILDE_POINTER`, `CYCLE`, `NOT_A_MAPPING` | every check, `resolver_parity.py`, `tests/contract/test_mission_status_reality.py` |
| `leak_patterns.py` | the compiled host-path patterns (strict-field and human-text variants) and the e-mail pattern, the forbidden property names, and field-class helpers | `leak_scan.py`, the reality check's payload scan |
| `fixture_builder.py` | `build(kind, out_dir)` assembling each leak-class planted fixture from fragments (no literal leak-shaped string appears in its source); CLI `--out <dir>` | `negative-tests`, the unit tests of `leak_scan.py` and the payload scan |

## Scripts, failure codes and counts

| Script | Failure codes (stable) | `counts:` keys | Cannot-do-its-job (exit 2) |
|---|---|---|---|
| `layout_check.py` | `PATH_FILE_NAME`, `MAPPED_FILE_MISSING`, `ORPHAN_PATH_FILE`, `SCHEMA_NAME_MISMATCH`, `INDEX_MISSING_FILE`, `INDEX_OMITS_FILE`, `BAD_REF_FORM`, `BRACE_REF_SPELLING` (a `$ref` to a brace-named file not in the canonical spelling decided in the IC-07a spike), `SHARED_MISUSE`, `TRACKED_BUNDLE` | `modules`, `path_files`, `index_files` | `NO_MODULE`, `ZERO_PATH_FILES`, `ZERO_INDEX` |
| `citation_check.py` | `MISSING_CITATION`, `BAD_DERIVED_FORM`, `EMPTY_RULE`, `EMPTY_INPUTS`, `UNRESOLVED_INPUT`, `CITED_PATH_MISSING`, `CITED_SYMBOL_UNRESOLVED`, `COUNT_MISMATCH`, `CITATION_REUSE` (reported) | `properties`, `x_source`, `x_derived`, `inputs_resolved` | `ZERO_PROPERTIES`, `ZERO_CITATIONS` |
| `provisional_check.py` | `MISSING_MARKER`, `UNDESCRIBED_MARKER`, `NOT_NULLABLE` | `provisional_elements` | `ZERO_PROVISIONAL` |
| `example_check.py` | `EXAMPLE_INVALID`, `ORPHAN_EXAMPLE`, `EXAMPLE_VALIDATES_NOTHING`, `REQUIRED_EXAMPLE_MISSING` (against a committed required-example manifest: one per resource, one per event kind, a populated provisional example, a discarded-Mission example, and the first, middle and last page-cursor cases) | `examples`, `validated` | `ZERO_EXAMPLES` |
| `event_mapping_check.py` | `NAME_WITHOUT_SCHEMA`, `SCHEMA_WITHOUT_NAME`, `SCHEMA_MULTI_NAME`; informational line `LIFECYCLE_TYPE_NOT_FORWARDED` for each member of `LIFECYCLE_EVENT_TYPES` outside the contract-owned seven-type allow-list (never a failure) | `event_names`, `event_schemas`, `lifecycle_not_forwarded` | `ZERO_EVENT_NAMES` |
| `enum_pin_check.py` | `ENUM_VALUE_ADDED`, `ENUM_VALUE_REMOVED`, `BOARD_GROUPING_PRESENT` | `enums`, `values` | `PIN_EMPTY`, `ENUM_UNREADABLE` |
| `leak_scan.py` | `FORBIDDEN_PROPERTY_NAME`, `HOST_PATH`, `EMAIL`, `PLANTED_NOT_DETECTED` | `files`, `values_strict`, `values_human`, `values_all` | `ZERO_FILES`, `ZERO_VALUES_IN_CLASS` |
| `structure_check.py` | `README_HEADING_MISSING`, `CHANGELOG_HEADING_MISSING`, `CHANGELOG_VERSION_HEADING_MISSING` | `readme_headings`, `changelog_headings` | `ZERO_HEADINGS` |
| `codeowners_check.py` | `RULE_MISSING`, `HANDLE_MISSING`, `PATTERN_DOES_NOT_COVER_MODULE` | `rules` | `FILE_MISSING`, `ZERO_RULES` |
| `no_pytest_scan.py` | `PYTEST_REFERENCE` (import, `python -m`, subprocess or shell string, `make` target that reaches it) | `scripts_scanned` | `ZERO_SCRIPTS` |
| `verify_pins.py` | `CHECKSUM_MISMATCH`, `CHECKSUM_MISSING`, `UNPINNED_USES`, `NOT_HTTPS`, `UNPINNED_INSTALL`, `PUBLICATION_DATE_MISSING` | `tools`, `uses_lines`, `downloads` | `MANIFEST_EMPTY`, `ZERO_TOOLS_VERIFIED`, `ZERO_USES_LINES` |
| `install_tools.py` | `CHECKSUM_MISMATCH` (before any execution) | `tools_installed` | `MANIFEST_EMPTY`, `DOWNLOAD_FAILED` |
| `bundle.py` | `BUNDLE_EMPTY`, `FEWER_THAN_FIVE_PATHS`, `BUILDS_DIFFER`, `UNRESOLVED_REFERENCE_LEFT` | `modules`, `bundles`, `path_items` | `NO_MODULE`, `MODULE_WITHOUT_ROOT`, `JVM_MISSING`, `GRADLE_MISSING`, `PLUGIN_RESOLUTION_FAILED`, `DEPENDENCY_VERIFICATION_FAILED` |
| `breaking_check.py` | `BREAKING_WITHOUT_MAJOR` (removed property or path, newly required parameter, narrowed enum, changed type), `BUNDLE_CHANGED_VERSION_SAME`, `NO_BASELINE_NOT_INITIAL`; informational `PREVIEW_DELTA` lines against the latest tag under `preview/<module>/` and `PREVIEW_REF_NONE` when there is none (never a failure, never a changed exit status); changes confined to `x-provisional` elements are reported in their own section and do not fail | `modules`, `baselines`, `breaking`, `provisional_changes`, `preview_ref` | `SHALLOW_CHECKOUT`, `TAG_LIST_ERROR`, `BASELINE_UNBUILDABLE`, `OASDIFF_MISSING`; the one allowed state prints `NO_BASELINE_INITIAL_VERSION` loudly and writes the job summary |
| `resolver_parity.py` | `TREE_DIFFERS` (names the first differing JSON pointer), `UNDOCUMENTED_NORMALISATION`, `NORMALISATION_CAP_EXCEEDED` (more than `MAX_NORMALISATIONS`, eight), `INDEPENDENT_DEREF_DISAGREES` (an example validates under the resolver's tree but not under `jsonschema` with a `referencing.Registry` retrieving the split files, or the reverse) | `path_items`, `schemas`, `refs_resolved`, `normalisations`, `examples_cross_checked` | `RESOLVER_IMPORT_FAILED`, `BUNDLE_MISSING_OR_EMPTY`, `BELOW_FLOOR` (fewer than five path items, zero schemas or zero resolved references) |
| `release_check.py` | `TAG_FORM`, `MODULE_UNKNOWN`, `VERSION_MISMATCH`, `CHANGELOG_HEADING_MISSING`, `CHECKSUM_MISMATCH` | `modules`, `bundles`, `verified` | `NO_MODULE`, `MODULE_ROOT_EMPTY`, `BUNDLE_EMPTY` |

`release_check.py` takes `--root`, and either `--tag <tag>` (a tag push) or no tag (a pull request or dry run: the candidate tag `contract-<module>-v<info.version>` is derived for every discovered module). It builds through the shared build wrapper, writes `openapi.yaml.sha256`, verifies it with `sha256sum -c` semantics, prints the exact `gh release create` argument list it would use (always including `--latest=false`, and `--prerelease` only for a prerelease semver), and never publishes.

## `pins.json` shape

A JSON object with a list of tools, each with `name`, `version`, `url` (HTTPS only), `sha256`, `published` (date), and `advisory_feed_checked` (text naming the feed consulted). The verifier and the installer read this single file. The `uses:` pins are verified from the workflow text, not from this file. The manifest is authored by the implementer from the vendors' published artefacts; the plan invents no version.

## Workflow job contract

`contracts.yml` (name `Contracts`): `pull_request` and `push`, `branches: [main]`, `paths` exactly `contracts/**`, `.github/CODEOWNERS`, `.github/workflows/contracts.yml`; top-level `permissions: contents: read`; concurrency per ref; every job has `timeout-minutes`.

**Prelude (every job that runs a `contracts/tools/` script, FR-018, plan D-P12).** A SHA-pinned checkout; the SHA-pinned `astral-sh/setup-uv` action with `python-version: '3.12'`; `uv sync --frozen --no-install-project`; the scripts then run from the synced environment. This is the only Python install form. `verify_pins` fails any other (a bare `pip install`, an unfrozen sync) with `UNPINNED_INSTALL` and has a planted fixture for the bad form and a clean control that is exactly this prelude. The JVM jobs add `install_tools.py` after the prelude.

**Fork guard.** The canonical guard is `(github.repository == 'spec-kitty/spec-kitty' || github.event_name == 'pull_request' || github.event_name == 'workflow_dispatch')`, the first top-level conjunct of the `if:` of every root job and of every job whose `if:` uses `always()` (`tests/ci/test_fork_guard.py` counts both as self-starting). The `needs` column below is the single authority for the job graph and `tests/ci/test_contracts_workflows.py` asserts it exactly.

| Job | Needs | Guarded (fork guard in `if:`) | Does | Artefact |
|---|---|---|---|---|
| `verify-pins` | none | yes | `verify_pins.py` over `pins.json` and both workflow files | none |
| `python-checks` | none | yes | the ten Python checks over the resolved tree, then `no_pytest_scan.py` | none |
| `validate-bundle` | `verify-pins` | no | `install_tools.py`, `bundle.py` (validate every module, bundle twice, compare digests), and the generate-from-split client smoke (informational until the stable marker; plan, UI early-start point) | `bundle-<module>` (`openapi.yaml`, `openapi.yaml.sha256`) |
| `lint` | `validate-bundle` | no | `install_tools.py`, vacuum with the Spectral-format ruleset over each bundle | none |
| `breaking-change` | `validate-bundle` | no | `install_tools.py`, `breaking_check.py`, full-history checkout with tags | job summary |
| `resolver-parity` | `validate-bundle` | no | `resolver_parity.py` against each bundle (and the independent dereference check) | none |
| `release-dry-run` | `validate-bundle` | no | `install_tools.py`, `release_check.py` (no tag; derived candidate), upload, no publication | `release-dry-run-<module>` |
| `negative-tests` | `verify-pins` | no | `install_tools.py` (it needs the JVM toolchain for the planted dangling-reference, tampered-metadata, vacuum and oasdiff cases), `fixture_builder.py` for the leak-class plants, then every script and tool against its planted fixtures; asserts the failure code; clean control on the same root | none |
| `contracts-gate` | the eight jobs above (`verify-pins`, `python-checks`, `validate-bundle`, `lint`, `breaking-change`, `resolver-parity`, `release-dry-run`, `negative-tests`) | **yes**: `if: (<canonical guard>) && always()` (`always()` makes it self-starting so the guard is required) | fails unless every needed job is `success` (non-fork runs) | none |

`contracts-release.yml` (name `Contracts Release`): `push` of tags `contract-*-v*.*.*` and `workflow_dispatch` (input `dry_run`, default true); no `pull_request`, no branch push; top-level `contents: read`, the one job `contents: write`; one root job whose `if:` is `(github.repository == 'spec-kitty/spec-kitty' || github.event_name == 'workflow_dispatch')` (the guard test accepts it: a fork's tag push skips, a fork's manual dry run stays allowed), running the same prelude, then `install_tools.py`, `bundle.py`, `release_check.py --tag <ref name>`, an upload step, and publish steps (`gh release create ... --latest=false`, with `--prerelease` only for a prerelease semver, and asset upload) each carrying `if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/')`.

Guard tests (`tests/ci/test_contracts_workflows.py`) evaluate that publish condition for `pull_request`, `workflow_dispatch`, a push to `main`, and a push of `refs/tags/contract-mission-status-v1.0.0` (false, false, false, true), fail on zero publish steps, assert `--latest=false` in the publish step, assert the release workflow's trigger rules (tag push `contract-*-v*.*.*` and `workflow_dispatch` with `dry_run` defaulting to true only; no `pull_request`, no branch push), assert the fork guard on `contracts-gate` and on the release job, assert the exact `needs` set of every job, and implement GitHub's filter-pattern semantics for the tag-namespace check (`*` does not cross `/`, `**` does), including that the preview tags `preview/mission-status/p<N>` are matched by neither the contract release filter nor the CLI's `v*.*.*`.

## Edits to shared CI (the complete list)

1. `.github/workflows/ci-router.yml`: one added line, `- 'contracts/**'`, in the `corpus` filter group.
2. `scripts/ci/fleet_verdict.py`: one `PR_WORKFLOWS` entry, `contracts.yml`.
3. `.github/workflows/ci-fleet-verdict.yml`: one name (`Contracts`) in the `workflow_run` list.
4. `tests/ci/test_fleet_verdict.py`: expected-set edits (the optional opening campsite commit first, if its re-count holds: a constant for the repeated `".github/workflows"` literal; then the new member), and `tests/ci/test_fleet_main.py` only if a test turns red. Items 2 to 4 and 6 land in the IC-07a skeleton commit together with `contracts.yml`, because a new `pull_request` workflow without its `PR_WORKFLOWS` entry fails the finite inventory check closed.
5. `tests/architectural/test_ci_corpus_trigger_completeness.py`: registry rows only.
6. `tests/release/pinning_rule_inventory.json`: regenerated by `scripts/ci/derive_pinning_inventory.py`.
7. `tests/release/ci_retirement_scrub.json`: one root (`contracts/**`) added by hand to the documentation copy `non_src_router_groups` (corpus), in the same commit as item 1. No script generates that file and nothing reads that key (verified), so the edit only keeps the copy equal to the router.

Tier of what these edits add: the router glob and the guard tests are tier 1 (via `router-gate` and `modules-gate`); the contracts workflow's jobs are tier 2 (fleet-reported, not blocking); see the plan's Branch contract.

Untouched by design: `.github/ci-module-registry.yml`, `pytest.ini`, `scripts/ci/fleet_main.py`, `_CORPUS_GLOBS` and `_CORPUS_DATA_ROOTS`, `contracts/fixtures/`, everything under `src/`.
