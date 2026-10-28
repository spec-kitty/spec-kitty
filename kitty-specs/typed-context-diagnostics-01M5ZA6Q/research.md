# Research: Typed context JSON diagnostics

Phase 0 grounding, origin/main `581b5c46` (2026-10-27).

## Code grounding (re-verified)

| Cited | Current location | Finding |
|-------|------------------|---------|
| contract `diagnostics` list[str] (~76-81) | `src/charter/activation/context_contract.py:76-81` | still `list[str]`, schema `1.4.0` (`:40`) |
| doctor prefix parse (~139,161) | `src/specify_cli/runtime/doctor.py:139,161` | prefix derived from `UNKNOWN_SELECTION_DIAGNOSTIC.split("{kind}")[0]` |
| template | `src/charter/activation/resolver.py:106` | `UNKNOWN_SELECTION_DIAGNOSTIC` |
| producer | `resolver.py:642` (`GovernanceResolution.diagnostics: list[str]`), append sites `:647,703,742,745,786,788,834,889,891,913,1027` | 11 sites, 10 distinct messages + profile-path `Unresolved reference` |
| emission | `context_json.py:174-179` → `context.py:597` | passes the strings through |
| docs | `docs/api/charter-commands.md:344-348` (was `:280`) | describes "list of strings" |
| changelog | `docs/changelog/CHANGELOG.md:78` (rc8 section, was `:40`) | "top-level `diagnostics` list" |
| #6461 item 3 | `synthesizer/reach_only.py:344,349` | **renamed** `created_tactic_slugs` → `created_slugs_by_kind` / `created_slugs`; still `object`; guard returns `[]` for foreign input (`:357-358`) |
| #6461 item 1 | `cli/commands/charter/interview.py:493` | `narrowed` emitted; absent from `docs/api` |

Release status: tags end at `v4.0.0rc7` (schema 1.3.0); rc8 not tagged, so 1.4.0 is unshipped.

## Red-first reproduction

- #6460: fresh `spec-kitty init` project, `charter context --action implement --json` → `context_schema_version` `1.4.0`, `diagnostics` = 4 prose strings (no code). Consumers can only classify by wording. Note (triage, 2026-10-19): rewording the shared template alone does not break doctor because doctor derives its prefix from it; the failure mode is (a) any external consumer, and (b) a reword that moves `{kind}` to the start makes the derived prefix empty and doctor flags every diagnostic. The ATDD test pins classification by code with a reworded message and a lookalike-prefix negative control.
- #6461 item 3: `mypy` reveal of `created_slugs_by_kind` parameter is `builtins.object`.
- #6461 item 1: `grep narrowed docs/api` → no hit.

## Architectural alignment

- ADR 2026-10-22-1 (Java write service is the canonical event writer; Python keeps the EventBridge port): unrelated, no event writing touched.
- ADR 2026-10-16-1 + Amendment 2026-10-19 (charter stays in core; offering replaced in place behind `charter.offering.api`): change is in `charter.activation` (stays in core), not the offering; no seam change. Not redone by that direction.
- ADR 2026-10-19-1 (activation ledger): unrelated.
- Epic #6518 (activation contract), #6117/#6608, spec-kitty-events #92 (envelope): no overlap with resolution diagnostics; nothing here would be redone.
- Consumer impact: in-repo only `doctor` and test goldens; the spec-kitty-charter service repo is outside this session's access, impact assumed nil because 1.4.0 never shipped; flagged in the PR.

## Overlaps

Open PRs (#6717, #6716, #6705, #6620, #5540): none touch these files. Sibling missions: M2 owns `reach_only.py` / `reconcile.py` → edit limited to two signatures + one import (operator decision `01M5ZA7YYGA9NGXEPTM16A7TZE`). #6715, #6675 and the M3–M6 surfaces do not intersect.

## Tidy-first

- `reach_only.created_slugs` defers `from ...reconcile import ReconciliationDelta` although the module already imports `reconcile` at top level: hoisting it is behaviour-preserving and enables the concrete annotation. Folded into IC-02 as its first step.
- No other preparatory refactor needed; `resolver.py` (1073 lines) is not split here (out of scope, locality).

## Decisions

- **Code set**: coarse, five codes (operator, DM `01M5ZA7FGHRYPC4FD1F2AVY1W6`, `01M5ZA8A50SYW9VSJHYKESDVNP`). Alternatives: one code per message (rejected: operator preferred categories), actionable-only (rejected: under-specifies).
- **Type depth**: domain type on `GovernanceResolution` (DM `01M5ZA7MCH04SFCC1ZV25KQCN8`). JSON-only mapping rejected: doctor would still parse strings.
- **Schema**: keep 1.4.0 (DM `01M5ZA7SA40DGDXK3Z223WH23V`); 1.5.0 rejected: no shipped consumer.
- **Home of the codes**: `_diagnostics.py` beside `CharterEncodingDiagnostic`, mirrored in `ERROR_CODES.md` — reuses the existing pattern instead of a new module.
- **`collect_governance_diagnostics`**: stays `list[str]` (text view; also returns uncoded `GovernanceResolutionError.issues`).

## Pre-PR adversarial squad (2026-10-27) — findings and dispositions

Cast: architect-alphonso (contract/architecture), debugger-debbie (live breakage), scribe-sally (docs). Verdicts: MERGE-READY, MERGE-READY, NEEDS-CHANGES (minor). No blocking finding.

| Finding | Source | Disposition | Evidence |
|---------|--------|-------------|----------|
| "`[]` when clean" misleads integrators (most projects get informational entries) | sally (MEDIUM) | accepted | `docs/api/charter-commands.md` diagnostics paragraph; `context_contract.py` comment |
| No rule for codes added later; squad diverged (open vs closed) | sally (MEDIUM) / alphonso (LOW) | changed — operator ruled: closed per schema version, a new code bumps the minor `context_schema_version`; docs keep a defensive "treat unknown as informational" hint | charter-commands.md, ERROR_CODES.md part 3 header, `context_contract.py` |
| ERROR_CODES "informational, not errors" vs doctor warning | sally (LOW) | accepted | ERROR_CODES.md part 3 header |
| `SELECTION_MERGED` row mixes categories | sally (LOW) | accepted | charter-commands.md table |
| charter-commands.md `updated:` not bumped | sally (LOW) | accepted | frontmatter `2026-10-27` |
| Changelog names `spec-kitty doctor`; the check runs under `spec-kitty agent status doctor` | sally + debbie (LOW) | accepted | CHANGELOG rc8 #6460 and #6407 entries |
| Doctor shows green ✓ next to a dropped selection (pre-existing on main) | debbie (LOW) | changed — operator ruled: fix here, `passed=False` (⚠, `healthy: false`, exit 1) | `src/specify_cli/runtime/doctor.py`; `tests/runtime/test_doctor_unit.py` |
| `d.code is ...` misses a raw-string code | debbie (LOW) | changed — `GovernanceDiagnostic.__post_init__` coerces to the enum and refuses codes outside the closed set | `_diagnostics.py`; `test_diagnostic_code_is_coerced_and_closed` |
| `collect_governance_diagnostics` returns uncoded `list[str]` | alphonso (LOW) | deferred_with_rationale — text projection with no `src/` caller that classifies; typed field is the authority (docstring says so) | `resolver.py` docstring |
| Untyped entries silently dropped in `_diagnostics_json` | alphonso (LOW) | deferred_with_rationale — production producers are typed by construction (now enforced by coercion); per-producer typing is pinned by tests | `test_context_diagnostics_typed.py` |
| `GovernanceDiagnostic` not orderable / YAML-safe | debbie (INFO) | deferred_with_rationale — no consumer needs it; serialise via `to_json()` | — |
| Removed `UNKNOWN_SELECTION_DIAGNOSTIC` public re-export | debbie (LOW) | accepted as-is — never in a tagged release (added in rc8 window) | squad evidence (`git tag --contains`) |
| 5 pre-existing mypy errors in `test_styleguide_reach_only.py`; `prompt_builder.py:512` no-any-return | WP02/WP01 review (LOW) | deferred_with_rationale — present on `origin/main`, outside this contract change | review-cycle-1 notes |
