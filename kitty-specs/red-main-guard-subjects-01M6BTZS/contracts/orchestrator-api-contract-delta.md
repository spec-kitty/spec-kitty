# Orchestrator-API contract delta — #6997

Mission: `red-main-guard-subjects-01M6BTZS`
Contract: `orchestrator_api`, `1.21.0` → `1.22.0` (minor, additive)

## What changes

One `error_code` is added to the declared set `orchestrator_api.allowed_error_codes`:

| Error code | Verb | Meaning | Payload |
| --- | --- | --- | --- |
| `SAFE_COMMIT_DIRECTORY_ARGUMENT` | `append-history` (the safe-commit surface) | `safe_commit` commits an exact file set, so a **directory** pathspec is refused. Raised in `preflight_commit` **before** any HEAD, ref or index mutation: nothing was committed and no partial commit exists. | `data.offending_path` names the refused path |

No verb, field or existing code is added, renamed or removed. `MIN_PROVIDER_VERSION`
stays `0.1.0`.

## Why it is a fix, not a new failure mode

`SafeCommitDirectoryArgument.error_code` has been
`SAFE_COMMIT_DIRECTORY_ARGUMENT` since the #6750 fix shipped it; the contract simply
never registered it, so `tests/contract/test_orchestrator_api.py::TestAllowedErrorCodes`
was red on `main`. The declared set now matches what core can emit. The minor bump
records the contract-visible change, not a behaviour change.

## Surfaces kept in step

| Surface | Change |
| --- | --- |
| `src/specify_cli/core/upstream_contract.json` | code added to `orchestrator_api.allowed_error_codes` |
| `docs/contracts/upstream-3.0.0-shape.json` | the same insertion, byte-identical (equality gate: `test_vendored_contract_matches_planning_artifact`) |
| `docs/api/orchestrator-api.md` | error-code list entry, `1.22.0` ledger bullet, `CONTRACT_VERSION` line and sample envelope |
| `src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md` | `Error Code Summary` row |
| `src/specify_cli/orchestrator_api/envelope.py` | `1.22.0` ledger comment and `CONTRACT_VERSION` |
| `tests/contract/test_orchestrator_api.py` | the code is named in the existing explicit-code tuple; the `SafeCommitError` descendant walk and the subset assertion are unchanged |
| `tests/specify_cli/orchestrator_api/test_contract_version.py`, `tests/orchestrator_api/test_origin_freshness_envelopes.py` | the two assertions that mirror the current version |
| `docs/changelog/unreleased/6997.fixed.md` | the per-PR changelog fragment (#6988 convention) |

## Consumer impact

An external orchestrator that keys on `error_code` can now name this refusal instead of
falling back to an unknown code. A consumer that mirrors the 1.21.0 list sees one
additional member; nothing it already handled changes.

## Out of scope (recorded in the PR's `## Deferred`)

The prose enumerations in the API reference and the operator skill remain
hand-maintained and already omit 22 other registered codes (the `DESIGN_*` and
`RUNTIME_*` families are documented in prose form, not as list items). Making those
enumerations machine-checked against the contract is its own mission.
