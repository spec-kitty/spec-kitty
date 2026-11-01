# Mission review report: charter-service pin line (#6909)

Aggregate review of the integrated diff (WP01 + WP02) before local consolidation,
2026-11-01. Lenses applied to the union of both lanes, not to each WP in isolation.

## Verdict: LAND

No finding blocks the hand-off. Two disclosures are recorded under Residual risks.

## L1 — Correctness of the trust path

- The provenance check runs inside `_verified_asset` after the `SHA256SUMS` digest comparison
  and before `write_service_pin`: a refused attestation raises `VendorError`, so the lockfile
  is never written. Verified by `test_a_refused_attestation_leaves_the_lockfile_unchanged`
  (seeded lockfile, byte comparison) and the CLI-level `test_vendor_cli_refuses_a_release_whose_attestation_fails`.
- The command carries both `--signer-workflow` and `--source-ref refs/tags/<tag>`, the exact
  shape spec-kitty-charter ADR-0046 decision 6 and spec-kitty-events ADR 0003 document;
  `test_the_attestation_arguments_pin_the_signer_and_the_tag_ref` asserts the argv element by
  element, so dropping either flag is caught.
- A `file://` release performs no subprocess (asserted with a verifier that fails if called) and
  the user path (`service fetch`, `status`, launcher, `sync_services.py`) never imports the seam.
- The default repository resolution keeps the precedence explicit argument > current pin >
  service default, with one test per tier (`test_the_default_repository_is_the_current_pins`,
  `test_the_default_repository_names_each_services_own_release_home`,
  `test_a_new_charter_service_pin_defaults_to_the_charter_repository`).

## L2 — Boundaries and single authority

- Repository identities and `gh` live in `specify_cli.services`; `kernel.service_pin` keeps the
  tag rule, targets and prefix table and gains only a comment/docstring change. The
  `test_remote_contact_owner` and `test_release_asset_download_owner` gates pass (86 tests).
- No second download path: the new code hashes the file the existing `kernel.release_assets`
  owner downloaded. No second repository table: `DEFAULT_REPOSITORIES` is the only one, and a
  test pins its key set to `KNOWN_SERVICES` and the policy registry.
- No new dependency (`pyproject.toml` untouched); `gh` is an external maintainer tool invoked
  from the vendor path only.

## L3 — Test quality and non-vacuity

- Every new behaviour test goes through the production entry point (`vendor_pin` or the Typer
  CLI), never a hand-built shape; the refusal assertions are paired with same-fixture positive
  controls (valid GitHub release passes; tampered charter asset is refused while the same
  fixture's valid asset is cached and digest-checked).
- Red evidence: with the WP01 source changes stashed and `attestation.py` removed, the new tests
  fail at collection/import; they are green with the change. The CLI passthrough tests added in
  review round 1 are coverage of the wiring, not a red-first defect proof.
- The charter prefix ratchet test asserts all three recorded names and that the provisional
  marker is gone, with a present-marker positive control.

## L4 — Security and error surface

- No shell: `subprocess.run(argv, check=False, timeout=120)` with an explicit argv list.
- Refusal messages carry the asset name, tag, and a one-line `gh` detail with any 64-hex run
  replaced by `<digest>`; the repository preview redacts `user:secret@`. Tests assert both.
- `gh` absence, a non-zero exit and a timeout each map to their own stable code with a remedy;
  usage errors still exit 2 and release refusals exit 1.

## L5 — Charter, docs and change hygiene

- Changelog fragment (`docs/changelog/unreleased/6909-charter-service-pin-line.changed.md`,
  898 chars, impact-first, cites #6909) follows the current per-PR convention rather than
  editing `CHANGELOG.md`.
- `pins/README.md` and the service-pins how-to match the shipped code (repository table,
  prefixes, codes, flag semantics); the generated CLI reference's `service`, `service status`
  and `service vendor` blocks were spliced from `capture_help()` and match the live help.
- `check_docs_freshness --ci`: errors=0; `test_no_legacy_terminology`: 98 passed; changelog
  style: 0 errors; spelling: 0 findings.
- No ADR edited: the charter repository's ADR-0046 sentence that says core does not check the
  attestation yet is now stale and is noted for the charter maintainer in the PR hand-off.

## Findings

None blocking. No follow-up issue is required for this mission's own scope.

## Residual risks and disclosures

1. **Pre-review regression gate was skipped explicitly for both WPs.** The gate's auto-scope
   produced empty targets and fell back to `make test-fast`, which exceeds the 300 s
   `review.test_timeout_seconds` on this host (known #6865); the documented per-WP
   `pre_review_test_scope` override is rejected by `WPMetadata(extra="forbid")`. The touched
   modules were run directly instead (219 passed, 1 skipped; 64 passed in the CLI module; 86
   architectural ownership tests). Disclosed in the PR's `## Deferred`.
2. **`check_pin --online` still verifies only `SHA256SUMS` and the tag commit, not
   attestations.** That path downloads no assets by design; provenance is established when the
   pin is written. Not required by #6909, but a future tightening would extend the seam there.
