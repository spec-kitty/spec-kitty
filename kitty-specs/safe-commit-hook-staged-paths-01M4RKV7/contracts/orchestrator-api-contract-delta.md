# Contract delta — safe-commit-hook-staged-paths (#5903)

This mission adds one contract-visible outcome to the orchestrator-api surface. The single
canonical authority is `src/specify_cli/core/upstream_contract.json`; its JSON-equal mirror is
`docs/contracts/upstream-3.0.0-shape.json`, and the version/narrative lives in
`src/specify_cli/orchestrator_api/envelope.py`.

## New error code

| Code | Raised by | Meaning | Family |
|------|-----------|---------|--------|
| `SAFE_COMMIT_UNREQUESTED_PATHS` | `safe_commit` (the `append-history` / safe-commit verbs) | The commit **landed** (`commit_sha` is set) but it carries paths the operation never requested — a pre-commit hook staged them. The operator's real index is re-synced for those paths before the error is raised. | Refines `SAFE_COMMIT_RECOVERY_FAILED` (the commit landed), like `SAFE_COMMIT_INDEX_RESIDUE`. |

## Version

- Orchestrator-api `CONTRACT_VERSION`: **1.14.0 → 1.15.0** (additive: a new `error_code` on existing
  verbs; no field removed or renamed; `MIN_PROVIDER_VERSION` unchanged).

## Consumer guidance

A consumer that already treats `SAFE_COMMIT_INDEX_RESIDUE` as "the commit landed, but needs
attention" should treat `SAFE_COMMIT_UNREQUESTED_PATHS` the same way: the failure `data` carries
`commit_sha` (the landed commit) and `unrecovered_paths` (the extra paths a hook swept in). It is
**not** a failure-to-land.

## Parity gates

- `tests/specify_cli/core/test_contract_gate.py::test_vendored_contract_matches_planning_artifact`
  (vendored JSON == docs mirror).
- `tests/contract/test_orchestrator_api.py::TestAllowedErrorCodes::test_safe_commit_failure_codes_are_contract_allowed`
  (every `SafeCommitError` descendant's code ∈ `allowed_error_codes`).
- `tests/specify_cli/orchestrator_api/test_contract_version.py` (version pin + changelog comment).
