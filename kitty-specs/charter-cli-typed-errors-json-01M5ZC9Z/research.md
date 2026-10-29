# Research: Charter CLI typed errors and JSON

Phase 0 grounding for #6557 and the independent local-acceptance slices of #6525 and #6526,
recorded 2026-10-27 against `origin/main` at `f90c9f2a`. Sibling checkouts:
`spec-kitty-charter` at `bc6ad11`, `spec-kitty-events` at `efb3d66`.

## 1. Code grounding (re-verified on origin/main)

| Claim | Location | Verified |
|-------|----------|----------|
| `charter status` catch-all renders "Unexpected error" | `src/specify_cli/cli/commands/charter/status.py:321-323` (`except Exception` → `_emit_error(..., unexpected=True)`) | yes |
| `charter status` errors use the legacy envelope `{result, success, error, code?}` | `status.py:319,322` → `_common.py:113` `_emit_error` | yes |
| Soundness gate exists (PR #6555) | `_charter_yaml_gate.py:33` `assert_charter_yaml_sound` → `charter.activation.api.load_charter_yaml_mapping`, raises `ActiveCharterConfigError` (`ACTIVE_CHARTER_CONFIG_INVALID`) | yes |
| `synthesize` / `resynthesize` already call the gate and render the code | `synthesize.py:223,713`; `resynthesize.py:110,275` | yes |
| A non-mapping charter reaches the bundle-compat check first | `status.py:55-56` `_assert_bundle_compatible` → "Bundle schema version not found; treating as v1" | yes |
| Canonical JSON error envelope | `src/specify_cli/cli/json_contract.py:17` `json_error` → `{ok:false, error:{code,message}}`; rendered by `_coded_errors.py:24` `render_coded_error` | yes |
| Positional `activate` / `deactivate` have no `--json` | `activate.py:1062` (`--json` is preset-only, enforced by `_check_preset_flags`, `activate.py:887-913`); `deactivate.py:314-337` (no option) | yes |
| Cascade rendering prints inside the mutation loops | `activate.py:293-330` (`_activate_cascade_targets`), `activate.py:393-458`; `deactivate.py:177-294` (`_cascade_child`, `_render_cascade_deactivation`) | yes |
| `CascadeActivationResult.to_report` (named by #6525) does not exist | `src/charter/activation/cascade.py:371` (fields only) | confirmed absent |
| Activation state read API | `charter.activation.activation_ledger.load_activation_ledger` (`:463`, `ActivationLedger` `:180` with `path`, `source`, `allow`, `deny`, `activated_kinds`, `mission_type_activations`); `required_not_in_force` (`:1101`) is the single authority for "required but kept out of force" | yes |
| JSON registration inventory gate | `tests/architectural/test_json_contract_enumeration.py`: `charter status` and `charter activate` in `PARSEABLE`; a new `--json` on `charter deactivate` must be classified | yes |

### Red-first reproduction (#6557)

Scratch project (`spec-kitty init` + `charter interview --defaults` + `charter generate --from-interview`):

- Unparseable `charter.yaml`: `charter status` exit 1, `Unexpected error: mapping values are not allowed here …`;
  `--json` → `{"error": "...", "result": "error", "success": false}` (no code, no remedy).
- List-rooted `charter.yaml`: exit 1, `Error: Bundle schema version not found; treating as v1. Run spec-kitty upgrade.` (misleading).

#6525 / #6526 are additive (no `--json` / no `activation` block exist), so their red tests are the new acceptance tests.

## 2. Architectural alignment

| ADR / epic | Bearing |
|------------|---------|
| ADR 2026-10-22-1 (Java write service is canonical event writer) | status events only; no conflict |
| ADR 2026-10-13-2 (ledger publication seam, local retention) | event ledger only; no conflict |
| ADR 2026-10-16-1 + Amend 2026-10-19 (charter stays in core, offering replaced behind `charter.offering.api`) | local CLI JSON does not change the frozen seam; read activation via `charter.activation` public API, add no offering imports |
| ADR 2026-10-19-1 (+Amend 2026-10-20) (activation ledger) | read activation only through its module; the camelCase `ActivationConfig` mapping is a seam-layer concern (#6520, held), so the status block is labelled local |
| Epic #6518 (#6520 field mapping, #6521 revision, #6524 refusal codes) | held; this mission mints no contract code, revision or field, and closes neither #6525 nor #6526 |
| spec-kitty-charter ADR-0020 (activation contract, provisional) | contract codes are snake_case (`artifact_required`, `activation_invalid`, …); core's local codes stay UPPER_SNAKE and are not presented as contract codes |
| spec-kitty-charter ADR-0016 / corpus harness (#9) | relies on `charter context`, `pack list`, `doctor charter-packs`; no expectation on these three commands yet |
| Epics #6117 / #6608, spec-kitty-events #92 | no file overlap; nothing here would be redone by that direction |

Conclusion: no part of this mission is pre-empted by the stated direction.

## 3. Related issues, PRs and sessions

- Open PRs in all three repos (spec-kitty #6716, #6620, #5540; charter #249; events #142, #129) touch none of the files in scope.
- #6460 (typed `charter context` diagnostics, mission M1) is adjacent: it changes `context.py`, not status/activate/deactivate. Its diagnostics adopt `{code, message}` entries, consistent with the canonical envelope chosen here.
- #4664 tracks convergence of every command onto the canonical envelope; this mission moves `charter status`, `activate` (positional) and `deactivate` onto it.
- #6556 (CharterYaml model rejects activation keys) does not affect the gate (it reads through `load_charter_yaml_mapping`).
- #6715, #6675, #6193/PR #6716, missions M2–M6 and sibling missions M9–M16: no overlap on these files.
- Community: Venkatasai200628 offered on #6557 (2026-10-22); asked on 2026-10-27 whether work exists.

## 4. Operator decisions (2026-10-27)

| Decision | Ruling | Decision Moment |
|----------|--------|-----------------|
| Error envelope | Canonical `{ok:false, error:{code,message}}` for all three commands; `charter status` errors move off the legacy envelope (breaking for status error consumers; CHANGELOG note) | `01M5ZCANVH16B2ANT1BJ115S8R` |
| Schema version | Local `schema_version: "1.0.0"` on the activate/deactivate success payload and inside the status `activation` block; not the contract revision | `01M5ZCAVRVKZDA0FG068BRK6WZ` |
| Activation block naming | snake_case, labelled local; camelCase contract mapping left to #6520 | `01M5ZCB1Z9H59Y3ZW0MBWQQK4T` |
| Volunteer credit | `Co-authored-by` only if they share work before the PR | `01M5ZCB8BGSJS0VXC7Y2F5T3V2` |

## 5. Tidy-first

The cascade activate/deactivate paths interleave mutation and printing. Before adding `--json`, a
behaviour-preserving refactor separates collection (a report value) from rendering, so text output stays
byte-identical and JSON serializes the same report. This is the first work package.
