# Work Packages: One synthesis-ownership reader, one unreadable-record error

**Inputs**: Design documents from `kitty-specs/synthesis-ownership-single-reader-01M68ZJM/`
**Prerequisites**: plan.md, spec.md, research.md

**Tests**: Required. The charter's ATDD-first rule applies: every WP opens with a failing test through the pre-existing entry point, committed before the implementation commits.

**Organization**: Subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work package is independently deliverable and testable.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are reference rows: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first test module for the one reader and the one coded error | WP01 | |
| T002 | `SynthesisMembershipUnreadableError` in the error taxonomy, with code and record metadata | WP01 | |
| T003 | Move the created-artifacts record read/write primitives into the record module | WP01 | |
| T004 | `sidecar_artifact_urn`: the one strict sidecar reader | WP01 | |
| T005 | `synthesized_urns` / `synthesized_slugs`: the one ownership reader with one fallback | WP01 | |
| T006 | `synthesis_owned_directive_ids` and `manifest_slugs` read through the one reader; delete the private URN reader | WP01 | |
| T007 | Update the ownership assertions in `test_manifest.py` and retire the private-class test | WP01 | |
| T008 | Red-first: reach-only delivery fixtures describe a real synthesis tree (sidecar per entry) | WP02 | |
| T009 | `reach_only_ids` derives its slugs from `synthesized_slugs`; delete the manifest/record readers | WP02 | |
| T010 | Re-export the one reader and the one error through `charter.activation.api` | WP02 | |
| T011 | Re-run the reach-only/delivery/compiler suites; confirm no governance outcome changed beyond the documented case | WP02 | |
| T012 | Red-first: envelope degrades an unreadable sidecar to `artifact_id: null` without raising | WP03 | |
| T013 | Envelope reads the sidecar through `sidecar_artifact_urn`; delete the lenient parser | WP03 | |
| T014 | Collision remedy catches the one coded error and keeps naming the offending file | WP03 | |
| T015 | Update the coded-error import sites and re-export lists | WP03 | |
| T016 | Architectural guard: one sidecar parser, one ownership reader, one code | WP04 | |
| T017 | Changelog entry under `[Unreleased]` | WP04 | |
| T018 | Docs freshness and terminology check | WP04 | [P] |
| T019 | Final verification sweep over the touched suites plus ruff/mypy | WP04 | [P] |

---

## WP01 — The record module owns both records and the one reader

**Goal**: `charter.activation.synthesizer.manifest` is the only module that reads the synthesis
ownership record, and `errors.py` carries the one coded refusal.

**Subtasks**: T001 T002 T003 T004 T005 T006 T007
**Depends on**: none
**Parallel**: safe against WP02 (different files) and WP03 (different files)

**Reference rows** (tracked by `mark-status`, not by checkboxes):

T001 Red-first test module for the one reader and the one coded error (WP01)
T002 `SynthesisMembershipUnreadableError` in the error taxonomy, with code and record metadata (WP01)
T003 Move the created-artifacts record read/write primitives into the record module (WP01)
T004 `sidecar_artifact_urn`: the one strict sidecar reader (WP01)
T005 `synthesized_urns` / `synthesized_slugs`: the one ownership reader with one fallback (WP01)
T006 `synthesis_owned_directive_ids` and `manifest_slugs` read through the one reader; delete the private URN reader (WP01)
T007 Update the ownership assertions in `test_manifest.py` and retire the private-class test (WP01)

---

## WP02 — Both ownership consumers read only through it

**Goal**: `reach_only_ids` has no reader of its own; delivery gating and directive ownership cannot
disagree, and the delivery fixtures describe a real synthesis tree.

**Subtasks**: T008 T009 T010 T011
**Depends on**: WP01
**Parallel**: safe against WP03 (different files)

**Reference rows**:

T008 Red-first: reach-only delivery fixtures describe a real synthesis tree (sidecar per entry) (WP02)
T009 `reach_only_ids` derives its slugs from `synthesized_slugs`; delete the manifest/record readers (WP02)
T010 Re-export the one reader and the one error through `charter.activation.api` (WP02)
T011 Re-run the reach-only/delivery/compiler suites; confirm no governance outcome changed beyond the documented case (WP02)

---

## WP03 — One sidecar parser, and the display path that wraps it

**Goal**: the `charter synthesize --json` envelope and the collision remedy consume the strict
reader; no production code parses the sidecar shape twice.

**Subtasks**: T012 T013 T014 T015
**Depends on**: WP01
**Parallel**: safe against WP02 (different files)

**Reference rows**:

T012 Red-first: envelope degrades an unreadable sidecar to `artifact_id: null` without raising (WP03)
T013 Envelope reads the sidecar through `sidecar_artifact_urn`; delete the lenient parser (WP03)
T014 Collision remedy catches the one coded error and keeps naming the offending file (WP03)
T015 Update the coded-error import sites and re-export lists (WP03)

---

## WP04 — Evidence, docs and the cross-cutting guards

**Goal**: the convergence is documented and cannot drift back: one reader, one parser, one code,
pinned by an architectural guard.

**Subtasks**: T016 T017 T018 T019
**Depends on**: WP01, WP02, WP03

**Reference rows**:

T016 Architectural guard: one sidecar parser, one ownership reader, one code (WP04)
T017 Changelog entry under `[Unreleased]` (WP04)
T018 Docs freshness and terminology check (WP04)
T019 Final verification sweep over the touched suites plus ruff/mypy (WP04)

---

## Dependency graph

```
WP01 ──> WP02 ──┐
   └───> WP03 ──┴──> WP04
```

WP02 and WP03 are independent of each other and can run in parallel lanes from WP01's approved
base.
