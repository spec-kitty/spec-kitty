# Implementation Plan: Activate output and identity

**Branch**: `issue-6457-activate-output-identity` | **Date**: 2026-10-27 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/activate-output-and-identity-01M5ZA9X/spec.md`

Branch contract (from `setup-plan`): current branch at plan start, planning/base branch and final merge target are all `issue-6457-activate-output-identity`; `branch_matches_target` is true.

## Summary

Output-only fixes to `spec-kitty charter activate` plus a pinning test and two docs corrections:

1. `--only` prints only narrow-path lines (no absent-key preservation warning), treats an absent mission-type key as "nothing in force", gives the reason when an effective set cannot be resolved, and names what the kind now lists (#6457, widened).
2. A shared org-required freeze warning prints for "required"-when-absent kinds (today `skill`) on the plain path when an absent key is written and on every `--only` run; the plain path stops recommending `--only` for those kinds (#6458, warning only).
3. A resolver test pins "a file name beats a declared id regardless of layer", documented in the layering doc and linked from `_gated` (#6459).
4. The Pack Level and Charter Pack glossary entries describe `PACK_LEVEL_MISSING` as shipped (#6403).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer/rich (CLI render), ruamel.yaml (existing fixtures)
**Storage**: activation ledger `.kittify/charter/activation.yaml` — read/written exactly as today (C-001)
**Testing**: pytest; CLI tests through `typer.testing.CliRunner` on `charter_app`; engine unit tests; resolver test via `build_active_charter_service`
**Target Platform**: CLI (Linux/macOS/Windows)
**Project Type**: single
**Performance Goals**: no new filesystem scans; the reason string is already computed by `resolve_effective_sets`
**Constraints**: no change to written lists, exit codes, deny lists, JSON envelopes; complexity <= 15; no new suppressions
**Scale/Scope**: ~4 source files, 2 docs files, 1 architecture doc, changelog

## Charter Check

| Gate | Status |
|---|---|
| Single canonical authority | Pass — warning texts live once in `activation_engine` (C-004); the freeze rule keys on `ArtifactKind.effective_when_absent`, the same fact the interview exclusion uses. |
| Architectural alignment | Pass — changes stay in `charter.activation` and the `specify_cli` renderer; no `charter.offering.api` or layer change (ADR 2026-10-16-1). |
| ATDD-first / red-first | Pass — every FR row has a CLI or engine test written red first; reproductions recorded in `research.md`. |
| Terminology | Pass — "Mission", "activation ledger", "org-required"; run the terminology guard. |
| Tidy-first (Standing Order #2) | Pass — IC-01 is a behaviour-preserving refactor landed first. |
| No full heavy suites | Pass — targeted + blast radius + `make test-fast`. |
| Epic #6518 overlap | Pass — semantics untouched (C-001); referenced in the PR. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/activate-output-and-identity-01M5ZA9X/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks.md   (by /spec-kitty.tasks)
```

`contracts/`: none — no API or JSON envelope changes (recorded in `meta.json`).

### Source Code (repository root)

```
src/charter/activation/activation_engine.py   # warning constants, freeze warning, narrow-unresolved reason
src/charter/activation/pack_manager.py        # _preservation_* result, _narrow_inputs, activate() warning choice, ActivationResult.listed
src/charter/activation/resolver.py            # _gated docstring link only
src/specify_cli/cli/commands/charter/activate.py  # _render_activation_result: "Now listed for <kind> (N): ..."
docs/architecture/org-doctrine-layer.md       # stem-first note
docs/context/governance.md, docs/context/charter.md  # PACK_LEVEL_MISSING clause
docs/changelog/CHANGELOG.md                   # [Unreleased]
tests/charter/activation/test_activation_engine*.py or new test module  # engine unit tests
tests/specify_cli/cli/commands/charter/test_activate_only_6408.py / new test_activate_output_6457.py
tests/charter/test_skill_activation.py (or new test module)  # skill freeze warning
tests/charter/activation/test_stem_first_gating_6459.py  # new
```

**Structure Decision**: single project; edits stay in the owning modules above.

## Implementation Concern Map

### IC-01 — Carry the unresolved reason out of the preservation step (tidy-first)

- **Purpose**: Return the effective-set `reason` from `_preservation_ids`/`_preservation_set` (a small frozen value object instead of a 3-tuple) so the narrow path can state it; no output change.
- **Relevant requirements**: FR-003 (enabler)
- **Affected surfaces**: `pack_manager.py` `_preservation_set`, `_preservation_ids`, `activate`
- **Sequencing/depends-on**: none
- **Risks**: other callers of `_preservation_set` (grep: only `activate`); keep the existing tests green unchanged.

### IC-02 — `--only` output (#6457)

- **Purpose**: Under `--only`, replace (not concatenate) preservation warnings with narrow warnings; mission-type absent key yields no unresolved warning; the unresolved warning carries the reason; the CLI prints "Now listed for <kind> (N): ids".
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004
- **Affected surfaces**: `pack_manager._narrow_inputs`, `ActiveCharterManager.activate`, `ActivationResult` (new `listed` field), `activation_engine` (`narrow_unresolved_warning(reason)` helper beside `NARROW_UNRESOLVED_WARNING`), `activate._render_activation_result`
- **Sequencing/depends-on**: IC-01
- **Risks**: existing test `test_only_with_an_unresolvable_effective_set_keeps_the_warnings_...` asserts "could not be resolved" — still satisfied by the narrow warning; `NARROW_UNRESOLVED_WARNING` constant stays for the interview promotion planner (unchanged).

### IC-03 — Org-required freeze warning (#6458, warning only)

- **Purpose**: One engine-owned warning for kinds with `effective_when_absent == "required"`, emitted by `_materialise_absent` (replacing `FROZEN_LIST_NOTE` for those kinds) and by the narrow branch of `plan_activation`.
- **Relevant requirements**: FR-005, FR-006, FR-007
- **Affected surfaces**: `activation_engine.py` (`_materialise_absent`, `plan_activation`)
- **Sequencing/depends-on**: none (touches the engine only; independent of IC-02's manager changes)
- **Risks**: must not change written lists (C-001); must not fire on a present key without `--only`.

### IC-04 — Pin and document stem-first gating (#6459)

- **Purpose**: Resolver test: built-in `DIRECTIVE_024` (file `024-locality-of-change`) vs a project file named `DIRECTIVE_024` declaring another id; activation `[DIRECTIVE_024]` admits the project artifact only; positive control without the project file admits the built-in. Doc note in `org-doctrine-layer.md` §Precedence; `_gated` docstring links it.
- **Relevant requirements**: FR-008, FR-009
- **Affected surfaces**: new test module, `resolver.py` docstring, `docs/architecture/org-doctrine-layer.md`
- **Sequencing/depends-on**: none
- **Risks**: none (no behaviour change, C-002).

### IC-05 — Glossary `PACK_LEVEL_MISSING` clause (#6403)

- **Purpose**: Replace the wrong clause in both entries with the shipped behaviour, naming ADR 2026-10-11-2; do not promise that the validator switch alone changes loading.
- **Relevant requirements**: FR-010
- **Affected surfaces**: `docs/context/governance.md` (Pack Level), `docs/context/charter.md` (Charter Pack)
- **Sequencing/depends-on**: none
- **Risks**: #6439 edits the same sentence's "tier" wording later — left untouched.

## Validation (per WP)

- Targeted: the new/changed test modules; `tests/specify_cli/cli/commands/charter/test_activate_*.py`; `tests/charter/test_skill_activation.py`; `tests/charter/activation/test_identity_index.py`.
- Blast radius: `tests/charter/`, `tests/charter_offering/`, `tests/specify_cli/cli/commands/charter/`; `make test-fast`.
- Gates: `ruff check`, `ruff format --check --force-exclude <files>`, `mypy` on touched files, `pytest tests/architectural/test_no_legacy_terminology.py`, `make docs-lint`.

## Addendum (2026-10-27): #6527 local slice

### IC-06 — One stored spelling: stems (#6527 local, #6435)

- **Purpose**: `IdentityIndex` accepts URNs and indexes built-in step contracts; the effective set emits stems; presets and every writer store stems; compensating stem mappings removed; one all-writers test.
- **Relevant requirements**: FR-011, FR-012, FR-013, FR-014, FR-015
- **Affected surfaces**: `src/charter/activation/identity_index.py`, `kind_vocabulary.py` (step-contract scan only if that is where the index scans), `effective_set.py`, `preset_application.py`, `org_charter.py` (`_normalize_required_ids` skip→keep), `pack_manager._narrow_inputs` (compensation removal), `specify_cli/cli/commands/charter/interview.py` (`_stem_spelled_effective` removal), tests listed in `research-6527-grounding.md` §4.
- **Sequencing/depends-on**: after IC-02 (shared `pack_manager.py`)
- **Risks**: `test_activation_preserves_effective_4253.py:249-268` must stay green unchanged; no migration (existing lists normalise on next write).

### IC-07 — Compile and consistency check through `IdentityIndex` (#6433)

- **Purpose**: compile resolves stems/declared ids/URNs through the index (project layer included) and stays strict on truly unknown tokens; the consistency check uses one index, warns-and-keeps unknown tokens, reports each once, fixes reverse paradigm parity.
- **Relevant requirements**: FR-016, FR-017
- **Affected surfaces**: `src/charter/activation/compiler.py` (`_resolve_config_activated_ids`), `src/charter/activation/consistency_check.py`, `drg_activation.py`/`preset_application.py` `resolve_artifact_urn` fallbacks (remove only if the index now covers them)
- **Sequencing/depends-on**: IC-06 (URN + step-contract index)
- **Risks**: complexity (`compiler.py`, `consistency_check.py` are large; keep touched functions <= 15).
