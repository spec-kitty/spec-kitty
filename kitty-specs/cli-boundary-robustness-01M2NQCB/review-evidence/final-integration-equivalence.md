# Final integration equivalence

Independent read-only verification after successful canonical merge, captured at immutable HEAD `ea5fc3678ebbf2d474fe55ecf1a2e02eba5c8c92`. Prior shared-CLI candidate `5e561a4670ea2c60e39836b46fab00ff8b35f23b`; upstream base `b17a81506331bc434b93a692f4f6261d008dc81e`. Merge completion observed in `merge-final.log` before capture. No tests or lifecycle commands executed for this comparison; no checkout files changed.

## Approved package preservation

Compared Git blob bytes at each approved source ref against final HEAD, computing SHA-256 for each pair. **49/49 files byte-identical; no lost edits.**

| Package | Approved ref | Files matched |
|---|---|---:|
| WP01 | d8d9bd47c | 11 |
| WP02 | 105ef7167 | 11 |
| WP03 | 466c75b3d (includes red f9e9b9bdb) | 2 |
| WP04 | 4ea7b2f9700f248f2f6c6e515e000a0d9b39f73c | 6 |
| WP05 | 819e78c8b | 17 |
| WP06 | 36e945bd8 (includes red e75d427e2) | 2 |

Full per-file byte hashes: `final-integration-equivalence.json`. Final tracked product/test/config Git object manifest: `final-integration-product-blobs.json`.

## Shared CLI reuse boundary

`git diff --name-status 5e561a4670ea2c60e39836b46fab00ff8b35f23b ea5fc3678ebbf2d474fe55ecf1a2e02eba5c8c92 -- src tests pyproject.toml uv.lock pytest.ini Makefile .github ruff.toml` yields exactly these five expected paths:

- `src/specify_cli/cli/commands/context.py`
- `tests/architectural/test_cli_placeholder_output.py`
- `tests/architectural/test_json_contract_enumeration.py`
- `tests/specify_cli/cli/commands/agent/fixtures/tasks_cli/json/envelopes.json`
- `tests/specify_cli/cli/commands/test_cli_boundary_context.py`

There are zero unexpected or missing expected paths. All other files in those trees are byte-identical to the candidate; config/dependencies are unchanged. Exact patch saved as `final-integration-product.diff`.

This supports reuse of the reported 5,035 passing shared-CLI tests for unchanged code. It does not pretend the candidate tested the later workspace-read correction, changed frozen fixture, or new architectural tests. WP03 correction has separately recorded 178 passing focused/subsystem tests; final gates must cover the changed fixture and both WP06 guards. Preserve the candidate's baseline failure/skip/deselection classifications, including the known slow help sweep #4636; equality cannot turn those into passes. This is equivalence evidence, not a final test or mission-review verdict.

## Planning whitespace and checkout state

Only two changed CSVs were compared to candidate: `research/evidence-log.csv` (five CRLF lines) and `research/source-register.csv` (four), under the mission directory. Both final byte streams equal candidate bytes with CRLF replaced by LF; parsed CSV rows are identical. Final CRLF count is zero. Other planning/lifecycle changes are outside the product reuse claim.

Both whole-repository and product-only `git diff --check` against the captured upstream base exit 0. `git status --porcelain` was empty at capture. Source SHA remains the explicit validity boundary if later changes occur.
