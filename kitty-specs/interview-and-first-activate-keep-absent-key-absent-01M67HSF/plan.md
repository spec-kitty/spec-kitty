# Implementation Plan: Interview and first activate keep an absent activation key absent

**Branch**: `issue-6685-interview-and-first-activate-keep-absent-key-absent` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/interview-and-first-activate-keep-absent-key-absent-01M67HSF/spec.md`

## Summary

Two operator-time writers still materialise a kind's whole in-force set into an absent `activated_<kind>` key: `charter interview` (`_promote_interview_selections`) and the first `charter activate <kind> <id>` without `--only` (`_preservation_set` → `plan_activation`). Both re-create the #6629 synthesis block at operator time. The plan applies the rule #6629 / #6683 merged for the upgrade caller — *an absent key means everything in force, so writing a list changes its meaning* — to those two writers:

- **Interview (FR-001, FR-002).** Promote into a **present** list only. When the key is absent, write nothing for that kind and say so, naming `--narrow-activation`. This mirrors `_promote_org_required_to_config`, which already refuses to seed an absent key, and the `4.0.0rc8_promote_interview_selections` migration, which never writes one.
- **First activate (FR-003, FR-004).** When the key is absent, the kind's absence puts every available artifact in force, and the requested artifact is already in that in-force set, write no allow list: the activation changes nothing, so a list would only freeze the kind. A deny-only activation keeps its existing path (D-09). `mission-type`, `required`-when-absent kinds (`skill`), an unresolved effective set and an artifact that is *not* in force keep materialising exactly as today, because there not writing would lose the activation.
- **No reader changes.** `charter synthesize`, `_catalog_is_established`, the activation ledger schema and the upgrade are untouched; they simply stop seeing a list that no operator wrote.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, ruamel.yaml (existing)
**Storage**: `.kittify/charter/activation.yaml` (activation ledger), `.kittify/charter/interview/answers.yaml`, `.kittify/config.yaml`
**Testing**: pytest. Two end-to-end red-first tests (interview → `charter synthesize --dry-run --json`; first activate → `PackContext` + `charter synthesize --dry-run --json`), the `FR-015` acceptance matrix, and focused unit tests for every new branch.
**Target Platform**: the CLI on Linux, macOS and Windows
**Project Type**: single
**Performance Goals**: the interview resolves no effective set on its non-narrowing path (it needed one only to seed), so the change removes a resolution rather than adding one (NFR-001)
**Constraints**: ADR 2026-10-19-1 (activation ledger: no new key, writes through the seam); #4253 / #4400 (zero drop, never a bare restrictive list); #6408 / #6457 / #6458 (`--only` / `--narrow-activation` unchanged); #6499 (never narrow an existing list)
**Scale/Scope**: two writer modules, their call-site tests, two acceptance-matrix rows, docs and docstrings

## Charter Check

- **Single canonical authority / single write seam:** the interview keeps `promote_activations` as its only write; the activation keeps `plan_activation` + `commit_plan`. The change is a *decision not to plan a write*, not a new write path. PASS.
- **`change-apply-smallest-viable-diff` + LOCALITY:** the edit sits in the two writers the issue names; the engine branch is one guard beside the existing D-09 branch. PASS.
- **ATDD-first / DIRECTIVE_034:** both defects get a failing test through the pre-existing CLI entry point before the fix, and the tests keep running afterwards as regression pins. PASS.
- **Terminology:** "activation ledger" (not "the ledger") and "Migration Ledger" named explicitly where both appear. PASS.
- **Architectural gates:** the effective-set seam caller test (`test_fr015_effective_set_seam_is_public`), the activation-engine freeze-warning gates, the charter kind-vocabulary single-authority gate and the terminology gate are implicated and run targeted. PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/interview-and-first-activate-keep-absent-key-absent-01M67HSF/
├── spec.md
├── plan.md
├── traces/              # tooling-friction, approach, design-decisions
├── decisions/
└── tasks.md             # /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/charter/
├── interview.py                                  # _promote_interview_selections: present lists only
├── activate.py                                   # report text only if the plan needs it
└── _resynthesis_preflight.py                     # unchanged (writes nothing; re-checked)

src/charter/activation/
├── activation_engine.py                          # plan_activation: absent + already-in-force -> new_list=None
└── pack_manager.py                               # _preservation_set docstring / in-force signal

tests/
├── charter/
│   ├── test_activation_preserves_effective_4253.py       # pins flip to "key stays absent", zero drop kept
│   ├── test_activation_engine_freeze_warning.py          # + the new branch's warning text
│   ├── test_pack_manager.py                              # + activate on an absent key writes no allow list
│   └── test_skill_freeze_warning_6458.py                 # REQUIRED kinds still materialise (ratchet)
├── specify_cli/cli/commands/
│   ├── test_charter_interview_promotion.py               # absent-key fixtures move to present-list fixtures
│   └── charter/test_activate_only_6408.py                # --only unchanged (ratchet)
└── acceptance/charter_pack_cutover/test_promotion.py     # FR-015: interview + activating caller rows
```

**Structure Decision**: no new module. The rule is a predicate both writers already have the data for ("is the key absent, and is this artifact already in force?"), so it belongs where each writer plans its write, not in a shared abstraction that would have to reach back into two different planners.

## Design

**Interview (`_promote_interview_selections`)**:

1. Resolve the selections to stems as today, keyed by `activated_<plural>`.
2. Read the write target once (`resolve_activation_write_target`).
3. If narrowing is off, keep only the keys the target already holds (`config_data.get(key) is not None`). Each dropped key gets one message: the kind is in force in full while the key is absent, nothing was written, and `charter interview --narrow-activation` writes the selection as an explicit list.
4. Promote the remainder through `promote_activations(..., effective_sets={}, ...)` — no effective set is computed at all on this path, so a key can never be seeded (the primitive's own fail-closed contract).
5. Narrowing (`--narrow-activation`) is unchanged: `_narrow_bases` + `effective_sets` for absent keys as today, because that path *is* the explicit choice.

**Activation (`plan_activation`)**:

1. The narrow branch stays first, the deny-only (D-09) branch stays second.
2. New guard: `current is None` and `effective_when_absent == "all"` and `effective_ids_in_force` and `artifact_id in set(effective_ids)` → `new_list=None`, `activated=[artifact_id]`, and a warning that the kind keeps no explicit activation set because the artifact was already in force, so writing one would freeze the kind (and that `--only` is how to choose a list).
3. Everything else falls through to today's materialisation, unchanged.

**What stays absent vs what is written** (the matrix the tests pin):

| Absent key, kind | artifact in force? | result |
|---|---|---|
| `all`-when-absent (directive, tactic, paradigm, procedure, …) | yes (resolved set) | **nothing written** — the new guard |
| `all`-when-absent, effective set unresolved | unknown (substitute) | materialised from the readable chain, as today |
| `all`-when-absent, artifact not in force | no | materialised in force set + artifact, as today |
| `mission-type` | no (absence puts nothing in force) | materialised from the chain, as today |
| `skill` (`required`-when-absent) | only org-required | materialised, as today (`--only` freezes it, #6458) |
| artifact on the deny list | — | deny-only write, allow key stays absent (D-09) |

## Complexity Tracking

No charter violations. One new predicate inside an existing branch keeps `plan_activation` under the C901 ceiling of 15; the interview extraction keeps `_promote_interview_selections` at its current shape.

## Implementation Concern Map

### IC-01 — The interview never fills an absent key

- **Purpose**: `charter interview` promotes into present lists only, and says what it left absent.
- **Relevant requirements**: FR-001, FR-002, FR-005, FR-006, FR-007, FR-008, NFR-001, NFR-002
- **Affected surfaces**: `src/specify_cli/cli/commands/charter/interview.py`, `tests/specify_cli/cli/commands/test_charter_interview_promotion.py`, `tests/acceptance/charter_pack_cutover/test_promotion.py` (interview row), a new end-to-end red-first test
- **Sequencing/depends-on**: none
- **Risks**: the message must not read as a failure (the interview still succeeds); the denied-id skip must keep working on the present-list path.

### IC-02 — A first activate keeps an in-force artifact implicit

- **Purpose**: `charter activate <kind> <id>` without `--only` writes no allow list when the artifact is already in force; every non-`all` or unresolved case materialises as today.
- **Relevant requirements**: FR-003, FR-004, FR-005, FR-006, FR-008
- **Affected surfaces**: `src/charter/activation/activation_engine.py`, `src/charter/activation/pack_manager.py`, `tests/charter/test_activation_preserves_effective_4253.py`, `tests/charter/test_activation_engine_freeze_warning.py`, `tests/charter/test_pack_manager.py`, `tests/charter/test_skill_freeze_warning_6458.py`, `tests/specify_cli/cli/commands/charter/test_activate_only_6408.py`, `tests/acceptance/charter_pack_cutover/test_promotion.py` (activating row)
- **Sequencing/depends-on**: IC-01 (shares the end-to-end test file)
- **Risks**: the `resynthesize` acceptance row's preflight assertion assumes the activation wrote a list; it must compare the preflight's proposal to the in-force set instead, without weakening it. The frozen-list warning tests must move to the rows that still materialise.

### IC-03 — Docs, docstrings and the record

- **Purpose**: the docstrings that name the interview seeding as "the #6408 residual", the operator docs, and the CHANGELOG state the rule; the gates stay green.
- **Relevant requirements**: FR-009, FR-010, NFR-003
- **Affected surfaces**: the two writers' docstrings, `docs/` operator pages for `charter interview` / `charter activate`, `docs/changelog/CHANGELOG.md`, the terminology and docs-freshness checks
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**: `docs/api/cli-commands.md` is regenerated from the installed CLI and other agents share that cache; regenerate only this diff's surface and verify with `check_docs_freshness --ci`.
