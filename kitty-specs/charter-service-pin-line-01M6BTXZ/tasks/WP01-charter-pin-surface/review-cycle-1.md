---
affected_files: []
cycle_number: 1
mission_slug: charter-service-pin-line-01M6BTXZ
reproduction_command:
reviewed_at: '2026-11-01T16:26:18Z'
reviewer_agent: reviewer-renata
wp_id: WP01
---

# WP01 review: changes requested

## Finding F1 (medium) — the CLI passthrough of `--no-attestation` and the new refusal exit code are untested

`tests/specify_cli/services/test_vendor.py` proves the vendor API path: the verifier runs per
asset, a refusal leaves the lockfile untouched, `file://` skips, and `verify_attestation=False`
skips. `tests/specify_cli/services/test_service_cli.py` proves only the flag's *usage* rules
(`--check --no-attestation` exits 2, help text). Nothing exercises the production CLI wiring
`vendor_pin(..., verify_attestation=not no_attestation)` or the `VendorError` -> exit 1 mapping
for a `SERVICE_ATTESTATION_*` code.

This matters because the CLI is the only entry point an operator uses, and a broken passthrough
(a wrong polarity, or the new code swallowed into a traceback) would leave every API test green.

### What to do

Add two tests in `tests/specify_cli/services/test_service_cli.py`, both through `_invoke`:

1. A GitHub-style bump whose verifier refuses (`AttestationError` with
   `SERVICE_ATTESTATION_FAILED`) exits 1, prints the code, and writes no
   `pins/write-service.source.yaml`. Reuse the offline https plumbing from the vendor tests:
   monkeypatch `vendor_module.remote_tag_commit` and `vendor_module.download` to serve the
   `file://` fixture under an `https://github.com/...` repository.
2. The same bump with `--no-attestation` exits 0, writes the pin, and the verifier is never
   called.

Keep both on one shared fixture (positive/negative control), and no network.

## Everything else: PASS

- Dead code: `attestation.py` is called by `vendor.py`; every helper has a live caller.
- Synthetic fixtures: tests go through `vendor_pin` and the Typer CLI, not hand-built shapes.
- Silent empty returns: none added.
- FR coverage: FR-001/FR-002/FR-003/FR-005 have behaviour assertions; FR-004's help text is
  asserted in `test_vendor_help_names_the_owning_release_repository` (docs are WP02).
- Frozen surface: `src/kernel/service_pin.py` is not frozen; no `services/` (Java) path touched.
- Locked decisions: no new dependency; kernel imports neither charter nor specify_cli; no
  `gh` on the fetch/start path.
- Shared files: WP01 and WP02 ownership is disjoint.
- Fail-loud: the new raises carry stable codes and remedies; no transient-race path.
