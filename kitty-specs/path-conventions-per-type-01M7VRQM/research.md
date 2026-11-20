# Research: Per-mission-type path conventions and a narrow path waiver

## R-1 Return shape of the reader (backward compatibility)

- **Decision**: `load_project_path_conventions(repo_root)` returns `ProjectPathConventions`, a `dict[str, str]` subclass holding the flat overrides, with a `per_type` mapping and a `for_mission_type(type_id)` method.
- **Rationale**: the existing reader tests compare the result with a plain dict, and a dict subclass with the same content compares equal, so FR-005 / NFR-002 hold without editing those pins. It is one read and one object, so NFR-001 holds.
- **Alternatives considered**: a frozen dataclass (cleaner, but every flat pin would be edited, which weakens FR-005's positive control); a second reader function (a second config read and a second authority).

## R-2 Which mission-type ids are valid section keys

- **Decision**: the layered roster (built-in → org → project), per operator ruling Q3. It is resolved through the existing seam `specify_cli.cli.commands.charter.mission_type.resolve_layered_roster`, imported lazily, and only when a mapping value is present.
- **Rationale**: the same roster `charter mission-type list` and the runtime use. No third copy of the `(mission_types_dirs, PackContext)` construction is added (DIRECTIVE_044).
- **Alternatives considered**: built-in ids only (rejected by the operator: it breaks org types); validating lazily at evaluation time for the Mission's own type only (an unknown id would pass silently whenever no Mission of that type is accepted, so it is not fail-closed).
- **Testability**: the reader takes an optional injected `mission_type_ids` callable; tests inject a fixed roster.
- **Failure**: an exception from the roster read becomes a `PathConventionsConfigError` that names the cause (fail-closed, and a clean accept refusal rather than a traceback).

## R-3 How the Mission's type is determined at the seam

- **Decision**: `get_mission_type(feature_dir) or "software-dev"`, the same expression `get_mission_for_feature` uses to load the Mission.
- **Rationale**: the per-type override must use the same type the Mission's conventions came from. `_mission_type_slug` (a path heuristic) is kept only as the remedy fallback when no type is passed.

## R-4 Waiver mechanics

- **Decision**: per operator ruling Q1 (C), both mechanisms:
  - per run: `accept --waive-path-conventions --waive-reason "<why>"`. A blank or missing reason is refused before any write. Recorded on the acceptance history entry as `path_conventions_waived: {"reason": ...}`.
  - per Mission: `meta.json` `"path_conventions": "waived"` plus `"path_conventions_rationale"`. It is read by the generalized #5298 waiver reader (exact value, non-blank rationale, fail-closed warning). The rationale is surfaced in the accept warning.
- **Effect**: identical to `--lenient`'s path effect (path misses become the warning text), with `strict_metadata` untouched.
- **orchestrator-api** (operator ruling Q4, option b): calls `collect_feature_summary(..., strict_metadata=True)` without the new keyword, so the per-run waiver is unavailable there. The per-Mission declaration is Mission data and applies wherever accept is evaluated, orchestrator-api included, the same as `contracts: none`. Metadata stays strict on both paths.

## R-5 Remedy ordering (#3783 contract)

- **Decision**: the text order becomes:
  1. "Path Convention Errors" plus the misses;
  2. the per-type remap snippet for the failing type (the first remedy, FR-006);
  3. the narrow waiver (the flag and the meta.json declaration), then `accept --lenient` as the broad escape;
  4. the last-resort mission.yaml copy note, marked as freezing the definition;
  5. `mkdir -p` Required Actions for deliverable paths only, with `contracts: none` named for `contracts/`.
- **Rationale**: the brief and #7566 require the per-type remap as the preferred first suggestion. The #3783 pin "--lenient before mkdir" still holds (mkdir is last). The #7512 pin "no mkdir for remappable" still holds.
- **Pins updated deliberately**: `test_format_errors_names_lenient_before_mkdir_and_drops_unconditional_claim` (still holds), `test_strict_failure_keeps_mkdir_for_artifact_path_after_lenient_and_remap` (the order assertion changes to remap < waiver < lenient < mkdir), and the full-text payload in `test_acceptance_support.py::test_no_override_still_blocks_strict`.

## R-6 The precedence contract source

The original `contracts/precedence-contract.md` (Mission `accept-path-convention-override-01M14P41`) is no longer in the tree. ADR `2026-08-28-1` is its durable record. This Mission writes `contracts/precedence-contract.md` for the new order and amends the ADR.
