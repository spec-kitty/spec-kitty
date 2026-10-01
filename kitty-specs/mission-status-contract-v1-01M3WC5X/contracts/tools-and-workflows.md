# Contract: `contracts/tools/` scripts, message codes and workflow jobs

This is the internal contract between the work packages of Mission `mission-status-contract-v1-01M3WC5X`. The product contract itself (the OpenAPI document) is the deliverable and lives in `contracts/mission-status/` at the repository root once built; this note fixes the shapes the scripts and workflows share so lanes can work in parallel. It is a planning artefact: the implementation may refine a code name, but must keep every property listed here (one stable code per failure cause, exit status semantics, a printed `counts:` line).

## Script conventions (all `contracts/tools/*.py`)

- Run as a bare script: `python contracts/tools/<name>.py [options]`. Standard library plus locked dependencies (PyYAML, jsonschema with `referencing`) only. Imports only sibling modules by name. Never imports pytest, anything under `tests/`, or `scripts.`.
- Exit status: `0` pass; `1` the check ran and found a violation; `2` the check **could not do its job** (missing input, missing tool, empty corpus, zero inputs, unreadable manifest). No path exits `0` having examined nothing.
- Output: failures as `CONTRACT-CHECK <name>: <CODE>: <detail>`, one per violation, naming the file and, where relevant, the property path or JSON pointer. The last line is always `counts: key=value key=value ...`, printed on pass and on fail.
- Module discovery: a module is a direct subdirectory of the contracts root holding a root `openapi.yaml`. `_shared`, `fixtures`, `gradle` and `tools` are never modules. The contracts root is a parameter (`--root`, default `contracts`) so negative tests can point a script at `contracts/tools/fixtures/<case>/`.
- Fixtures: one subdirectory per script under `contracts/tools/fixtures/`, each holding planted violations and a clean control on the same root. Planted files carry a marker line and are asserted to be detected by the text-level scan, which allow-lists exactly this directory.

## Libraries

| Module | Provides | Used by |
|---|---|---|
| `contract_resolver.py` | `resolve(module_dir)` returning the dereferenced tree and counts (`path_items`, `schemas`, `refs_resolved`); stable errors `UNRESOLVED_REF`, `URL_REF`, `ABSOLUTE_REF`, `TILDE_POINTER`, `CYCLE`, `NOT_A_MAPPING` | every check, `resolver_parity.py`, `tests/contract/test_mission_status_reality.py` |
| `leak_patterns.py` | the compiled host-path patterns (strict-field and human-text variants) and the e-mail pattern, the forbidden property names, and field-class helpers | `leak_scan.py`, the reality check's payload scan |

## Scripts, failure codes and counts

| Script | Failure codes (stable) | `counts:` keys | Cannot-do-its-job (exit 2) |
|---|---|---|---|
| `layout_check.py` | `PATH_FILE_NAME`, `MAPPED_FILE_MISSING`, `ORPHAN_PATH_FILE`, `SCHEMA_NAME_MISMATCH`, `INDEX_MISSING_FILE`, `INDEX_OMITS_FILE`, `BAD_REF_FORM`, `SHARED_MISUSE`, `TRACKED_BUNDLE` | `modules`, `path_files`, `index_files` | `NO_MODULE`, `ZERO_PATH_FILES`, `ZERO_INDEX` |
| `citation_check.py` | `MISSING_CITATION`, `BAD_DERIVED_FORM`, `EMPTY_RULE`, `EMPTY_INPUTS`, `UNRESOLVED_INPUT`, `CITED_PATH_MISSING`, `CITED_SYMBOL_UNRESOLVED`, `COUNT_MISMATCH`, `CITATION_REUSE` (reported) | `properties`, `x_source`, `x_derived`, `inputs_resolved` | `ZERO_PROPERTIES`, `ZERO_CITATIONS` |
| `provisional_check.py` | `MISSING_MARKER`, `UNDESCRIBED_MARKER`, `NOT_NULLABLE` | `provisional_elements` | `ZERO_PROVISIONAL` |
| `example_check.py` | `EXAMPLE_INVALID`, `ORPHAN_EXAMPLE`, `EXAMPLE_VALIDATES_NOTHING` | `examples`, `validated` | `ZERO_EXAMPLES` |
| `event_mapping_check.py` | `NAME_WITHOUT_SCHEMA`, `SCHEMA_WITHOUT_NAME`, `SCHEMA_MULTI_NAME` | `event_names`, `event_schemas` | `ZERO_EVENT_NAMES` |
| `enum_pin_check.py` | `ENUM_VALUE_ADDED`, `ENUM_VALUE_REMOVED`, `BOARD_GROUPING_PRESENT` | `enums`, `values` | `PIN_EMPTY`, `ENUM_UNREADABLE` |
| `leak_scan.py` | `FORBIDDEN_PROPERTY_NAME`, `HOST_PATH`, `EMAIL`, `PLANTED_NOT_DETECTED` | `files`, `values_strict`, `values_human`, `values_all` | `ZERO_FILES`, `ZERO_VALUES_IN_CLASS` |
| `structure_check.py` | `README_HEADING_MISSING`, `CHANGELOG_HEADING_MISSING`, `CHANGELOG_VERSION_HEADING_MISSING` | `readme_headings`, `changelog_headings` | `ZERO_HEADINGS` |
| `codeowners_check.py` | `RULE_MISSING`, `HANDLE_MISSING`, `PATTERN_DOES_NOT_COVER_MODULE` | `rules` | `FILE_MISSING`, `ZERO_RULES` |
| `no_pytest_scan.py` | `PYTEST_REFERENCE` (import, `python -m`, subprocess or shell string, `make` target that reaches it) | `scripts_scanned` | `ZERO_SCRIPTS` |
| `verify_pins.py` | `CHECKSUM_MISMATCH`, `CHECKSUM_MISSING`, `UNPINNED_USES`, `NOT_HTTPS`, `UNPINNED_INSTALL`, `PUBLICATION_DATE_MISSING` | `tools`, `uses_lines`, `downloads` | `MANIFEST_EMPTY`, `ZERO_TOOLS_VERIFIED`, `ZERO_USES_LINES` |
| `install_tools.py` | `CHECKSUM_MISMATCH` (before any execution) | `tools_installed` | `MANIFEST_EMPTY`, `DOWNLOAD_FAILED` |
| `bundle.py` | `BUNDLE_EMPTY`, `FEWER_THAN_FIVE_PATHS`, `BUILDS_DIFFER`, `UNRESOLVED_REFERENCE_LEFT` | `modules`, `bundles`, `path_items` | `NO_MODULE`, `MODULE_WITHOUT_ROOT`, `JVM_MISSING`, `GRADLE_MISSING`, `PLUGIN_RESOLUTION_FAILED`, `DEPENDENCY_VERIFICATION_FAILED` |
| `breaking_check.py` | `BREAKING_WITHOUT_MAJOR`, `BUNDLE_CHANGED_VERSION_SAME`, `NO_BASELINE_NOT_INITIAL` | `modules`, `baselines`, `breaking`, `provisional_changes` | `SHALLOW_CHECKOUT`, `TAG_LIST_ERROR`, `BASELINE_UNBUILDABLE`, `OASDIFF_MISSING`; the one allowed state prints `NO_BASELINE_INITIAL_VERSION` loudly and writes the job summary |
| `resolver_parity.py` | `TREE_DIFFERS` (names the first differing JSON pointer), `UNDOCUMENTED_NORMALISATION` | `path_items`, `schemas`, `refs_resolved` | `RESOLVER_IMPORT_FAILED`, `BUNDLE_MISSING_OR_EMPTY`, `BELOW_FLOOR` (fewer than five path items, zero schemas or zero resolved references) |
| `release_check.py` | `TAG_FORM`, `MODULE_UNKNOWN`, `VERSION_MISMATCH`, `CHANGELOG_HEADING_MISSING`, `CHECKSUM_MISMATCH` | `modules`, `bundles`, `verified` | `NO_MODULE`, `MODULE_ROOT_EMPTY`, `BUNDLE_EMPTY` |

`release_check.py` takes `--root`, and either `--tag <tag>` (a tag push) or no tag (a pull request or dry run: the candidate tag `contract-<module>-v<info.version>` is derived for every discovered module). It builds through the shared build wrapper, writes `openapi.yaml.sha256`, verifies it with `sha256sum -c` semantics, and never publishes.

## `pins.json` shape

A JSON object with a list of tools, each with `name`, `version`, `url` (HTTPS only), `sha256`, `published` (date), and `advisory_feed_checked` (text naming the feed consulted). The verifier and the installer read this single file. The `uses:` pins are verified from the workflow text, not from this file. The manifest is authored by the implementer from the vendors' published artefacts; the plan invents no version.

## Workflow job contract

`contracts.yml` (name `Contracts`): `pull_request` and `push`, `branches: [main]`, `paths` exactly `contracts/**`, `.github/CODEOWNERS`, `.github/workflows/contracts.yml`; top-level `permissions: contents: read`; concurrency per ref; every job has `timeout-minutes`.

| Job | Needs | Root (fork guard) | Does | Artefact |
|---|---|---|---|---|
| `verify-pins` | none | yes | `verify_pins.py` over `pins.json` and both workflow files | none |
| `python-checks` | none | yes | the ten Python checks over the resolved tree, then `no_pytest_scan.py` | none |
| `validate-bundle` | `verify-pins` | no | `install_tools.py`, `bundle.py` (validate every module, bundle twice, compare digests) | `bundle-<module>` (`openapi.yaml`, `openapi.yaml.sha256`) |
| `lint` | `validate-bundle` | no | vacuum with the Spectral-format ruleset over each bundle | none |
| `breaking-change` | `validate-bundle` | no | `breaking_check.py`, full-history checkout | job summary |
| `resolver-parity` | `validate-bundle` | no | `resolver_parity.py` against each bundle | none |
| `release-dry-run` | `validate-bundle` | no | `release_check.py` (no tag; derived candidate), upload, no publication | `release-dry-run-<module>` |
| `negative-tests` | `verify-pins` | no | every script and tool against its planted fixtures; asserts the failure code; clean control on the same root | none |
| `contracts-gate` | all of the above | no | fails unless every needed job is `success` (non-fork runs) | none |

`contracts-release.yml` (name `Contracts Release`): `push` of tags `contract-*-v*.*.*` and `workflow_dispatch` (input `dry_run`, default true); no `pull_request`, no branch push; top-level `contents: read`, the one job `contents: write`; one root job (fork guard) running `install_tools.py`, `bundle.py`, `release_check.py --tag <ref name>`, an upload step, and publish steps (`gh release create` and asset upload) each carrying `if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/')`.

Guard tests (`tests/ci/test_contracts_workflows.py`) evaluate that publish condition for `pull_request`, `workflow_dispatch`, a push to `main`, and a push of `refs/tags/contract-mission-status-v1.0.0` (false, false, false, true), fail on zero publish steps, and implement GitHub's filter-pattern semantics for the tag-namespace check (`*` does not cross `/`, `**` does).

## Edits to shared CI (the complete list)

1. `.github/workflows/ci-router.yml`: one added line, `- 'contracts/**'`, in the `corpus` filter group.
2. `scripts/ci/fleet_verdict.py`: one `PR_WORKFLOWS` entry, `contracts.yml`.
3. `.github/workflows/ci-fleet-verdict.yml`: one name (`Contracts`) in the `workflow_run` list.
4. `tests/ci/test_fleet_verdict.py`: expected-set edits (campsite constant first, then the new member), and `tests/ci/test_fleet_main.py` only if a test turns red.
5. `tests/architectural/test_ci_corpus_trigger_completeness.py`: registry rows only.
6. `tests/release/pinning_rule_inventory.json`: regenerated by `scripts/ci/derive_pinning_inventory.py`.

Untouched by design: `.github/ci-module-registry.yml`, `pytest.ini`, `scripts/ci/fleet_main.py`, `_CORPUS_GLOBS` and `_CORPUS_DATA_ROOTS`, `tests/release/ci_retirement_scrub.json`, `contracts/fixtures/`, everything under `src/`.
