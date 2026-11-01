# Implementation Plan: Record the `pr:pause-ci` pin's disposition and refresh the derived pinning inventory

**Branch**: `issue-6998-pinning-inventory-pause-ci-disposition` | **Date**: 2026-11-01 | **Spec**: `kitty-specs/pinning-inventory-pause-ci-disposition-01M6BTSJ/spec.md`
**Input**: Mission specification from `kitty-specs/pinning-inventory-pause-ci-disposition-01M6BTSJ/spec.md`

## Summary

The derivation `scripts/ci/derive_pinning_inventory.py` discovers one rule it has never been told how to adjudicate: `tests/ci/test_pause_ci_label.py::_REQUIRED_GATES`, added by `eb099b70b1` (the `pr:pause-ci` label contract, #6961). Because the derivation fails closed, that rule is emitted with `disposition: null` — so the committed artefact cannot be regenerated without reding the blocking completeness gate. The fix is two halves and they are independent:

1. **Record the decision.** Add one entry to `DISPOSITIONS` in the deriver: `"none"` plus a stated reason. `none` is the vocabulary's "adjudicated, nothing it asserts changes" — the correct verdict because the rule pins `ci-quality.yml`'s surviving `clean-install-verification` job and never names the retired `sonarcloud` job.
2. **Regenerate the artefact.** `tests/release/pinning_rule_inventory.json` is committed exactly as the deriver emits it: the one new row plus the line-number drift accumulated since the artefact was last refreshed on 2026-10-18 (`7604688425`).

No executable logic changes, no test changes, no gate changes. The whole delivery is one `dict` entry, a machine-generated JSON artefact, and one changelog entry.

## Technical Context

**Language/Version**: Python 3.11 (the supported floor; the deriver is written to be byte-deterministic across 3.11–3.14 — see the module docstring's PEP 701 note).
**Primary Dependencies**: standard library only (`ast`, `tokenize`); `pytest` + `pyyaml` for the gates. No new dependency.
**Storage**: two committed files — the derivation script and the JSON artefact it emits.
**Testing**: the artefact's own two gates, `tests/release/test_pinning_inventory_fresh.py` (freshness, byte-identical, strict-mode-gated; completeness, per-PR blocking), plus the issue's own entry point `scripts/ci/derive_pinning_inventory.py --check`.
**Target Platform**: CI (`CI Modules` shard) and any developer checkout.
**Project Type**: single project — a CI tooling script plus its derived artefact.
**Performance Goals**: not applicable; the derivation is a one-shot text+AST scan of `tests/` and `scripts/`, recorded at ≈3.5 s of call time by the gate's own durations.
**Constraints**: the artefact is byte-identity-checked, so the change must be produced by the deriver rather than edited; `DISPOSITIONS` reasons have a 60-character floor enforced by the gate.
**Scale/Scope**: 114 derived rows currently; this mission adds one and re-derives the rest. One source file touched.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter clause / directive | Verdict | Note |
|---|---|---|
| Single canonical authority | Pass | The disposition and the derivation stay the one authority for this inventory; no second list is introduced and the artefact is never hand-edited. |
| `change-apply-smallest-viable-diff` | Pass | One `dict` entry plus regenerated output. The 36 line-number blocks in the artefact are the derivation's own current output, not opportunistic edits. |
| `DIRECTIVE_024` Locality of Change | Pass | Blast radius is the deriver's decision map, its artefact, and the changelog. Nothing else reads either file. |
| `DIRECTIVE_034` test-first-bug-fixing / ATDD-First | Pass | Both halves are proven red before the change and green after, through the pre-existing entry points (the `--check` flag and the two gates), with no test modified. |
| `DIRECTIVE_041` (a test only where it guards real behaviour) | Pass | **No new test is added.** The invariant this defect violates is already owned by two existing gates; the defect is missing *data*, and a third test asserting the same row would be duplication, not coverage. Non-vacuity is instead shown by reverting each half (see `## Verification Strategy`). |
| `NO_FULL_HEAVY_SUITES_IN_MISSION` | Pass | Only the two pinning gates plus the changelog validators run locally; the full suite stays CI's. |
| Pre-existing Failure Reporting Rule | Pass | The structural cause (freshness is warn-only per PR; hard-gating it on `main` pushes is open #4845) is cited in the PR's `## Deferred`, not absorbed into this diff. |
| Standing Order #9 (red CI, no release) | Pass | The branch's head is the bar; no gate is skipped, xfailed, or made permissive. |
| Code rules (CLAUDE.md) | Pass | No `ruff`/`mypy` concern: the change is a typed `dict[str, tuple[str, str]]` entry in an existing literal. |

No violations, so `## Complexity Tracking` stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/pinning-inventory-pause-ci-disposition-01M6BTSJ/
├── plan.md              # This file
├── spec.md              # Mission specification
└── tasks.md             # Phase 2 output (spec-kitty tasks)
```

`research.md`, `data-model.md`, `quickstart.md` and `contracts/` are intentionally omitted: there is no research question (the issue states the root cause and the contract document `sonar-per-pr-coverage-reuse-01M2FR32/contracts/gate-disposition-contract.md` already owns the rules), no new data model (the row shape is fixed by `_entry`), no new API, and no consumer-facing quickstart. Adding them would be structure copied from a larger mission, which the procedure forbids.

### Source Code (repository root)

```
scripts/ci/derive_pinning_inventory.py          # the recorded decision (DISPOSITIONS)
tests/release/pinning_rule_inventory.json       # regenerated derived artefact
docs/changelog/CHANGELOG.md                     # [Unreleased] entry
```

Read but not modified — the two gates that own the invariant:

```
tests/release/test_pinning_inventory_fresh.py   # freshness (strict) + completeness (blocking)
tests/ci/test_pause_ci_label.py                 # the rule being adjudicated
```

**Structure Decision**: the repository's existing single-project layout; the work sits entirely inside the `scripts/ci` derivation and the `tests/release` artefact it owns.

## Verification Strategy

The defect has two independent halves, so it is proven half by half (`acceptance-criteria-non-vacuity`, "prove compound fixes half by half"):

| Half | Red before (observed) | Green after | Revert check |
|---|---|---|---|
| FR-001/FR-002 — disposition recorded | Delete nothing, regenerate: `test_every_entry_carries_a_disposition_from_the_vocabulary_and_a_reason` reds with `_REQUIRED_GATES: disposition None not in [...]` | passes, test unmodified | remove the `DISPOSITIONS` entry, re-derive → reds again (positive control on the same fixture) |
| FR-003 — artefact regenerated | `derive_pinning_inventory.py --check` exits 1 ("is stale"); strict freshness gate fails | exits 0; strict gate passes | hand-edit one line of the artefact → freshness gate reds |

Non-vacuity of the freshness gate is already established by its own design (it diffs against a fresh derivation); this mission does not need to re-prove it, only to stop violating it.

## Implementation Concern Map

### IC-01 — The recorded adjudication

- **Purpose**: Give the deriver the human decision it is missing, so the row it derives stops being `disposition: null`.
- **Relevant requirements**: FR-001, FR-002, C-001, C-003, NFR-001.
- **Affected surfaces**: `scripts/ci/derive_pinning_inventory.py` — `DISPOSITIONS` (post-change keys; this rule resolves in the tree, so it is *not* an `EXECUTED_LEDGER` entry).
- **Sequencing/depends-on**: none.
- **Risks**: the verdict must be `none`, not `rewrite`/`relocate` — those claim an edit or a move that did not happen, and `EXECUTED_LEDGER` entries' successors are existence-checked. Choosing `none` under `dependency: true` is the established shape (26 existing rows). A reason shorter than 60 characters reds the completeness gate.

### IC-02 — The regenerated artefact

- **Purpose**: Bring `tests/release/pinning_rule_inventory.json` back to byte-identity with its derivation, clearing both the undispositioned row and the accumulated line drift.
- **Relevant requirements**: FR-003, FR-004, C-002, NFR-002, NFR-003.
- **Affected surfaces**: `tests/release/pinning_rule_inventory.json` only.
- **Sequencing/depends-on**: IC-01 — regenerating *before* the disposition is recorded produces the `null` row that reds the completeness gate.
- **Risks**: line-number churn (~36 blocks) is expected and correct; it must not be hand-trimmed. If a sibling mission touches the same artefact, resolve by re-deriving rather than merging JSON.

### IC-03 — The record

- **Purpose**: Put the adjudication in the changelog so the next occurrence of this class is recognised rather than re-diagnosed.
- **Relevant requirements**: FR-005.
- **Affected surfaces**: `docs/changelog/CHANGELOG.md` (`[Unreleased]`).
- **Sequencing/depends-on**: none (can be written before implementation).
- **Risks**: the entry must be impact-first, name #6998, use before/after, and stay under 1,200 characters, or `test_validate_changelog_entry.py` reds.
