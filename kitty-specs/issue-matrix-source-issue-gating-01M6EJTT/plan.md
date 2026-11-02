# Implementation Plan: Never auto-demote the issue a Mission exists to fix

**Branch**: `issue-7011-issue-matrix-source-issue-gating` | **Date**: 2026-11-02 | **Spec**: [`spec.md`](spec.md)
**Input**: Mission specification from `kitty-specs/issue-matrix-source-issue-gating-01M6EJTT/spec.md`

## Summary

A positional citation label (`parent #`, `epic #`, a leading `see #`) currently demotes
*every* reference on its line, because `Occurrence` keeps only the stripped line and
`_CONTEXT_MARKER_PATTERN` is searched over all of it. The fix retains the citation's
character offset on `Occurrence` and requires a positional label to end exactly where
the citation begins — the rule the pattern's own comment already states. Independently,
a Mission's own source issue (from `meta.json` `source_description`, the spec's
`**Input**:` line, or a `Closes`/`Fixes`/`Resolves #N` line) is promoted to
`implementation_target` in the single gating seam every consumer shares, so prose can
never silence the issue the Mission exists to fix. Both behaviours are driven red-first
through `scaffold_issue_matrix`, the observable production path.

## Technical Context

**Language/Version**: Python 3.11+ (project baseline; `uv`-managed venv)
**Primary Dependencies**: stdlib only for the change (`re`, `json`, `pathlib`, `enum`, `typing`)
**Storage**: `kitty-specs/<slug>/meta.json` (read-only here) and `issue-matrix.json`
**Testing**: pytest, `pytest.mark.fast` unit tests plus the `regression` marker for the
issue-named repro; no heavy/architectural suite is run locally (`NO_FULL_HEAVY_SUITES_IN_MISSION`)
**Target Platform**: the `spec-kitty` CLI (cross-platform, POSIX + Windows)

**Performance Goals**: no change to scan complexity; source-issue derivation reads at
most one `meta.json` and one `spec.md` per discovery call (NFR-003)
**Constraints**: `classify_occurrence`/`classify_occurrences` stay pure and
deterministic (NFR-001); an unreadable `meta.json` must not raise inside the approval
blocker (NFR-002); one `#NNNN` pattern definition (C-002)
**Scale/Scope**: two source modules, one reference doc page, one changelog fragment;
no CLI surface change

## Charter Check

| Charter rule | How this plan satisfies it |
| --- | --- |
| Single canonical authority | Gating stays owned by `is_gating` / `gating_issue_numbers`; promotion is applied there, not in a fourth predicate. |
| ATDD-first | Each behaviour gets a failing test through `scaffold_issue_matrix` before the implementation lands. |
| `change-apply-smallest-viable-diff` | Two modules touched; the optional field keeps every existing call site working (C-001). |
| `DIRECTIVE_024` Locality of Change | Edits stay in the classification seam and its two consumers; no unrelated refactor of `issue_matrix.py`. |
| Fail-safe over fail-open | Ambiguity keeps gating; the only new demotion-free path is *promotion* to gating. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Only `tests/tasks/*`, `tests/specify_cli/tasks/*`, `tests/policy/test_issue_matrix_cross_site_consistency.py` and `tests/status/*` issue-matrix modules are run locally; CI owns the rest. |

No violations; no complexity to track.

## Project Structure

### Documentation (this mission)

```
kitty-specs/issue-matrix-source-issue-gating-01M6EJTT/
├── plan.md              # This file
├── spec.md              # Authored specification
├── research/
│   └── code-grounding.md   # Reproduction, causes, consumers, existing test surfaces
├── tasks/               # WP files (from /spec-kitty.tasks)
└── traces/              # approach.md, design-decisions.md, tooling-friction.md
```

### Source Code (repository root)

```
src/specify_cli/tasks/
├── issue_reference_discovery.py   # Occurrence.ref_offset, positional label scoping,
│                                  # source-issue derivation + promotion
├── issue_matrix.py                # _GH_ISSUE_PATTERN owner: shared text helper;
│                                  # _scaffold_issue_matrix_locked applies the promotion
└── issue_matrix_approval.py       # unchanged consumer (still is_gating/discovery)

tests/tasks/
└── test_issue_matrix_source_issue_7011.py   # new red-first repro (both causes)
tests/tasks/test_issue_reference_classification.py   # untouched; the ratchet control
docs/development/reference/issue-matrix-verdicts.md  # demotion rules + promotion
docs/changelog/unreleased/<pr>.fixed.md              # per-PR fragment
```

**Structure Decision**: single project, existing `src/specify_cli/tasks` package. The
new tests live beside the existing classification tests under `tests/tasks/` because
that directory already owns the `Occurrence`/classification contract.

## Implementation Concern Map

### IC-01 — Citation position and positional-label scoping

- **Purpose**: Stop a label attached to one number from demoting a different number on
  the same line, without disabling the label itself.
- **Relevant requirements**: FR-001, FR-005, NFR-001, C-001, C-002
- **Affected surfaces**: `src/specify_cli/tasks/issue_reference_discovery.py`
  (`Occurrence`, `classify_occurrence`, marker patterns), and the occurrence
  construction in `src/specify_cli/tasks/issue_matrix.py::detect_issue_references`.
- **Sequencing/depends-on**: none (first).
- **Risks**: the `^`-anchored `see` arm and the `#`-terminated `parent|epic` arm must
  both keep working; an unknown offset must reproduce today's whole-line result so the
  pre-existing suite stays green byte-for-byte.

### IC-02 — Source-issue derivation and promotion

- **Purpose**: Guarantee the Mission's own issue is never classified non-gating,
  whatever its prose looks like.
- **Relevant requirements**: FR-002, FR-003, FR-004, NFR-002, NFR-003, C-003
- **Affected surfaces**: `src/specify_cli/tasks/issue_reference_discovery.py`
  (derivation helper + promotion in `discover_issue_references`) and
  `src/specify_cli/tasks/issue_matrix.py::_scaffold_issue_matrix_locked` (the
  `detect_issue_references` caller that has no `feature_dir` discovery).
- **Sequencing/depends-on**: IC-01 (the promotion must land on a correctly-classified
  reference, and its tests assert both causes' outcomes together).
- **Risks**: two call sites must share one promotion helper; a promotion that invents
  rows for uncited numbers would break the zero-reference rule (#6653).

### IC-03 — Cross-consumer agreement, docs and changelog

- **Purpose**: Prove the four consumers agree, pin the behaviour against regression,
  and document the narrowed demotion rule.
- **Relevant requirements**: FR-004, SC-003, SC-004
- **Affected surfaces**: `tests/policy/test_issue_matrix_cross_site_consistency.py`
  (extend with the new fixture), `docs/development/reference/issue-matrix-verdicts.md`,
  `docs/changelog/unreleased/<pr>.fixed.md`.
- **Sequencing/depends-on**: IC-01, IC-02.
- **Risks**: the docs page states the demotion signals as a flat list; it must say the
  positional ones bind to the reference they precede, or the docs will contradict the
  code it documents.
