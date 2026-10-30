# Contract: converged refusal code for an unreadable org pack registry

Mission: charter-packs-refusal-code-convergence-01M66FC9 (#6772)
Status: approved with WP01/WP02
Authority: spec.md FR-001..FR-005, NFR-001/002, C-001..C-003

## Behavior contract

For a `.kittify/config.yaml` whose `charter_packs` registry cannot be read
(malformed shape, e.g. `[1, 2]`):

- `charter activate <kind> <id>` and `charter deactivate <kind> <id>` BOTH
  refuse with error code `ACTIVE_CHARTER_CONFIG_INVALID`, exit 1, in the text
  form and the `--json` envelope, and write nothing.
- The refusal message keeps the lead `the org pack registry cannot be read:`
  (activate) / names the org pack registry (deactivate), chaining the
  underlying parse failure.
- A declared org pack that was never fetched stays a DISTINCT refusal:
  `ACTIVATION_FAILED` on `activate`, with the `spec-kitty charter fetch`
  remedy in the message.

## Implementation contract

- The typed refusal is `OrgPackRegistryUnreadableError(ActiveCharterConfigError,
  ValueError)` in `src/charter/activation/activation_ledger.py` (the
  `ActiveCharterConfigError` family's error home).
- The seam respects the C-004 one-way boundary (activation → offering only):
  `charter.offering.drg.org_pack_config.require_declared_org_roots` raises the
  offering-owned `UnreadableOrgPackRegistry(ValueError)` from its registry-read
  arm, and `charter.activation.layer_roots.resolve_pack_chain(strict=True)` —
  the chain authority every strict consumer already goes through — maps exactly
  that error onto the typed refusal (`from cause`, body preserved). The lazy
  import of the typed error lives in that same-package mapping helper
  (`activation_ledger` transitively imports `layer_roots`, so an eager import
  would cycle); `charter.offering` imports no `charter.activation` code at any
  scope (gated statically by
  `tests/architectural/test_charter_offering_does_not_import_activation.py`).
- The dual base is load-bearing and pinned by test: `ActiveCharterConfigError`
  gives the code and the CLI's existing config-refusal mapping (zero CLI
  change); `ValueError` keeps every strict org-chain reader's documented
  `except ValueError` contract (`effective_set`, `preset_application`,
  `manifest_loader`). `str()` returns the body, not the code, because strict
  readers interpolate `str(exc)` into their refusal text.
- No CLI mapping table, code constant, or message-text branching changed for
  this convergence (spec NFR-002).

## Pinned by

- `tests/specify_cli/cli/commands/charter/test_activation_json_6525.py::test_a_malformed_charter_packs_config_is_refused`
  (both verbs, text + JSON; re-pinned red-first on `activate`)
- `tests/charter_offering/drg/test_org_pack_config_cr04_charter_packs.py`
  (`test_an_unreadable_registry_is_the_typed_refusal_on_both_bases`,
  `test_a_declared_but_unfetched_pack_stays_a_plain_value_error`,
  `test_the_offering_raise_never_imports_activation`)
