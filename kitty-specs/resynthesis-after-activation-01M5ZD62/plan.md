# Implementation Plan: Re-synthesis after activation

**Branch**: `issue-6510-resynthesis-after-activation` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/resynthesis-after-activation-01M5ZD62/spec.md`

## Summary

`charter synthesize` builds its request's graph snapshot, the set of upstream nodes that the
additive-only check (FR-020/EC-6) treats as existing, from every activated directive. Once
`activated_directives` is an explicit list, it contains the project directive that synthesis itself
promoted (`PROJECT_001`), so synthesis collides with its own output (#6510, #4226). The fix reads
the existing synthesis ownership record (manifest → provenance `artifact_urn`) and leaves
synthesis-owned directives out of the snapshot and out of the companion-tactic expansion. Activation
and delivery are untouched. The additive-only check stays strict. Its refusal gains a structured
`colliding_urn` and an origin-aware remedy, so operators stop renaming the tool's own identifiers.

## Engineering Alignment (confirmed 2026-10-27, decision `01M5ZDFE9NHWH3BH0X6YD8REBE`)

1. **Ownership reader**: a new public helper in `charter.activation.synthesizer.manifest` returns
   the URNs of synthesized artifacts of one kind. It reads the manifest entries of that kind, then
   each entry's provenance sidecar `artifact_urn`. An absent manifest gives an empty set; an
   unreadable manifest or sidecar raises (fail closed, NFR-002).
2. **Exclusion at the request seam**: in `_synthesis.py`, the snapshot build becomes a pure helper
   (a tidy-first commit, behaviour unchanged). The fix then removes owned ids from both
   `selected_directives` and the snapshot nodes. Ownership is read only when the explicit directive
   list is non-empty.
3. **Refusal**: `ProjectDRGValidationError` gets an optional `colliding_urn` field (additive,
   defaulted). The core collision wording becomes origin-neutral ("already present in the synthesis
   input graph"). A shared CLI helper, used by `synthesize` and `resynthesize`, names the origin
   (an activated project directive with no ownership record, or a built-in/org node) and the remedy.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, pydantic, ruamel.yaml (all existing; no dependency added, removed or upgraded, so DIRECTIVE_051 supply-chain controls are not triggered)
**Storage**: files: `.kittify/charter/synthesis-manifest.yaml`, `.kittify/charter/provenance/*.yaml` (read only), `.kittify/charter/activation.yaml` (read only)
**Testing**: pytest. Red-first ATDD through the real `charter synthesize` / `charter resynthesize` CLI entry points (typer `CliRunner` against a `tmp_path` git repo with the `generated` adapter and authored artifacts, with no patching of the request builder), plus unit tests for the new helpers
**Target Platform**: cross-platform CLI (Linux, macOS, Windows 10+)
**Project Type**: single (existing `src/` layout)
**Performance Goals**: request build reads the ownership record at most once per run; at most +100 ms on a 50-directive project (NFR-001)
**Constraints**: activation never written (C-002); additive-only invariant not loosened (C-003); no change to `reach_only.py` / `reconcile.py` (C-004, M2); complexity ≤ 15; no new `noqa` / `type: ignore`; diff coverage ≥ 90 %
**Scale/Scope**: ~4 source files, ~3 test files; 3 work packages

## Charter Check

| Gate | Status | Note |
|------|--------|------|
| Single canonical authority | PASS | Ownership comes from the existing manifest + provenance record; no new record (C-001). |
| Architectural alignment / layer rule | PASS | The config/record read lives in `charter`; `specify_cli` orchestrates (same rule as `resolve_config_activated_roots`). No layer-rule, package-set or gate change. |
| ADR 2026-10-16-1 (+Amend 2026-10-19) | PASS | Synthesis stays in core; the fix is in core and nothing in it is redone pre-GA. |
| ADR 2026-10-19-1 (activation ledger) | PASS | Synthesis writes no activation or deny list (C-002, FR-005). |
| ATDD-first / red-first | PASS (planned) | Each WP's acceptance test is committed failing first, through the CLI entry point (C-005). |
| Tidy-first (Standing Order #2) | PASS (planned) | A behaviour-preserving extraction of the snapshot build is the first commit. |
| Terminology canon | PASS | "Mission" only; no `--feature`. Terminology guard run before push. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | PASS (planned) | Targeted + blast radius only: `tests/charter/`, `tests/charter_offering/`, synth CLI tests, `make test-fast`. |
| `__all__` convention (charter) | PASS (planned) | The new helper is exported in `manifest.__all__` and has a `src/` caller (dead-symbol gate). |

No violations; Complexity Tracking omitted.

## Project Structure

### Documentation (this mission)

```
kitty-specs/resynthesis-after-activation-01M5ZD62/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/requirements.md
└── tasks/            (created by /spec-kitty.tasks)
```

### Source Code (repository root)

```
src/charter/activation/synthesizer/
├── manifest.py          # + synthesized_urns(repo_root, kind) (ownership reader)
├── errors.py            # ProjectDRGValidationError + colliding_urn: str | None = None
└── project_drg.py       # collision raise: neutral wording + colliding_urn (check unchanged)
src/specify_cli/cli/commands/charter/
├── _synthesis.py        # snapshot helper (tidy-first) + owned-id exclusion + collision remedy helper
├── synthesize.py        # SynthesisError branch: append remedy for a collision
└── resynthesize.py      # same
tests/charter/synthesizer/
├── test_manifest.py              # ownership reader units
└── test_project_drg.py           # colliding_urn + wording
tests/specify_cli/cli/commands/charter/
└── test_resynthesis_after_activation_6510.py   # CLI ATDD (FR-001..008)
```

**Structure Decision**: existing single-project layout; no new module.

## Implementation Concern Map

### IC-01 — Snapshot build as a seam

- **Purpose**: make the activated-directive → snapshot derivation a pure, unit-testable step before changing it (tidy-first).
- **Relevant requirements**: FR-003, FR-008 (enabler)
- **Affected surfaces**: `src/specify_cli/cli/commands/charter/_synthesis.py`
- **Sequencing/depends-on**: none
- **Risks**: must be byte-identical in output; pin with a characterization test first.

### IC-02 — Synthesis ownership reader

- **Purpose**: one public read of "which directive URNs did synthesis create", from the existing manifest + provenance record.
- **Relevant requirements**: FR-003, NFR-002, C-001
- **Affected surfaces**: `src/charter/activation/synthesizer/manifest.py`, `tests/charter/synthesizer/test_manifest.py`
- **Sequencing/depends-on**: none
- **Risks**: an import cycle between `manifest` and `provenance` (check, and import lazily if needed); fail-closed semantics must not leak into runs that never needed ownership.

### IC-03 — Exclude synthesis-owned directives from synthesis input

- **Purpose**: the functional fix: owned ids leave `selected_directives` and the snapshot; activation is untouched.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-008, SC-001, SC-002, SC-004
- **Affected surfaces**: `_synthesis.py`; CLI ATDD test file
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**: `resynthesize` builds its request through the same builder (verify `_synthesis.py:809` path); `targets.py` validates source URNs against the snapshot, so dropping a node must also drop its `selected_directives` entry (same helper).

### IC-04 — Origin-aware collision refusal

- **Purpose**: a remaining collision says where the colliding node comes from and how to recover.
- **Relevant requirements**: FR-006, FR-007, SC-003
- **Affected surfaces**: `errors.py`, `project_drg.py` (both raise sites carry `colliding_urn`), `_synthesis.py` (remedy helper), `synthesize.py`, `resynthesize.py`
- **Sequencing/depends-on**: IC-02 (uses the ownership reader to classify)
- **Risks**: existing tests assert the old wording (`grep "already exists in the built-in DRG layer" tests/`); re-pin those that judge wording, keep those that judge refusal.

## Post-design Charter re-check

Unchanged: PASS on all gates. `project_drg.py` and `errors.py` sit in the charter synthesizer core but
change only wording and an additive field; the invariant is untouched (C-003).
