# Work Packages: Charter escape-report convergence

**Inputs**: Design documents from `/kitty-specs/charter-escape-report-convergence-01M66YM0/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md (D1–D6)

**Tests**: required — this is a defect fix; every surface gets a red-first test through its
pre-existing entry point (charter C-011, `DIRECTIVE_034`).

**Organization**: fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work
package is independently deliverable and testable.

**Prompt Files**: each work package references a matching prompt file in `tasks/`. This file is the
high-level checklist; implementation detail lives in the prompt files.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

Single project: `src/`, `tests/`.

---

## Work Package WP01: Status surface reports escaping org-pack paths (Priority: P0) 🎯 MVP

**Goal**: `charter status --json` reports an escaping authored fragment `body_path` and an escaping
asset sidecar `path` on its existing `org_layer.errors` channel, using the same offering predicates
`doctor charter-packs` uses, before the merge so a refused merge cannot hide them.
**Independent Test**: a project with one configured org pack whose node `body_path` escapes its root
reports a finding in `org_layer.errors`; a contained pack reports none.
**Prompt**: `tasks/WP01-status-escape-findings.md`
**Requirement Refs**: FR-001, FR-002, FR-003, NFR-001, NFR-003, C-001

### Included Subtasks

T001 Red-first: `charter status` reports an escaping node `body_path` (CLI + collector level)
T002 Red-first: `charter status` reports an escaping asset sidecar `path`
T003 Positive control and degraded-read tests: contained pack clean, crashed check reported
T004 Implement the two escape helpers and call them before the merge in `_collect_org_layer_status`
T005 Targeted pytest + `mypy --strict` on the touched module

### Implementation Notes

- Import the registry-aware wrappers (`find_org_body_path_escapes`, `find_org_asset_path_escapes`)
  from `charter.activation.drg_activation`; never restate containment.
- Append `escape.message` to `result["errors"]`. Add no new key (NFR-003).
- Catch exceptions per check and append `org-layer body_path check failed: …` /
  `org-layer asset path check failed: …`.
- Place the calls after the fragments load and before `merge_three_layers`.

### Parallel Opportunities

- T001 and T002 touch one test module together; no parallel split needed.
- Independent of WP02 (different files).

### Dependencies

- None. Starting package.

### Risks & Mitigations

- Registry lookup raises `KeyError` for an unregistered pack → caught and reported as "check could
  not run" (T003 covers it).
- A false positive on a contained pack → T003's positive control on the same fixture builder.

---

## Work Package WP02: Validator refuses an escaping fragment body_path (Priority: P0)

**Goal**: `charter org validate` reports an authored fragment `body_path` that escapes its pack root
as a structured `body_path_escape` finding and exits non-zero, mirroring the existing
`asset_path_escape` leg.
**Independent Test**: `charter org validate <pack>` on a pack with an escaping node `body_path`
prints a `body_path_escape` error and exits 1; a contained pack produces no such finding.
**Prompt**: `tasks/WP02-validator-body-path-finding.md`
**Requirement Refs**: FR-004, NFR-001, NFR-002, C-002

### Included Subtasks

T006 Red-first: `validate_pack` reports a `body_path_escape` finding for an escaping authored node
T007 Red-first: the `charter org validate` CLI exits non-zero and names the node; both findings
survive together (asset + body_path)
T008 Positive control: a contained `body_path` is not a finding; discovered nodes are not judged
T009 Implement `_validate_fragment_body_paths` and extend the documented category vocabulary
T010 Targeted pytest + `mypy --strict` on the touched module

### Implementation Notes

- Call `find_body_path_escapes(loaded_fragment, pack_dir)` — the same predicate `doctor` uses — and
  print the predicate's own `message`.
- `artifact_type="drg"`, `artifact_id=<node id>`, `file=<drg/fragment.yaml>`,
  `category="body_path_escape"`.
- Keep `asset_path_escape` exactly as it is (C-002).

### Parallel Opportunities

- Independent of WP01 (different files).

### Dependencies

- None.

### Risks & Mitigations

- Firing on discovered nodes or an empty `body_path` → the predicate already excludes both; the test
  in T008 pins it so a future change to the leg cannot reintroduce them.

---

## Work Package WP03: Conformance case table, docs and changelog (Priority: P1)

**Goal**: state the containment rule as portable data that asserts all three reporting surfaces
agree, and bring the user-facing docs, changelog and promise index in line.
**Independent Test**: the case table runs green and fails if any surface stops reporting an escape;
`docs/api/charter-commands.md` documents the status behaviour and the new validator category.
**Prompt**: `tasks/WP03-conformance-corpus-docs.md`
**Requirement Refs**: FR-005, FR-006, SC-001, SC-002, SC-003, SC-004, NFR-004, C-004

### Included Subtasks

T011 Author `tests/charter/conformance/pack_containment_cases.yaml` (four cases, plain data)
T012 Author the runner with three adapters over the production entry points
T013 Document the status behaviour and the `body_path_escape` category in `docs/api/charter-commands.md`
T014 Add the `[Unreleased]` changelog entry for #6733
T015 Extend `tests/scenarios/charter/PROMISES.md` row `PR-CHARTER-SHARING-004` to name all three surfaces
T016 Run the corpus, the docs gates and the touched test modules

### Implementation Notes

- The runner must call production entry points: doctor's `_collect_org_layer_data`, the status
  collector, and the `charter org validate` CLI. An `expect` key an adapter does not observe fails
  the case (same discipline as the activation corpus runner).
- Changelog entry: impact-first lead with `(#6733)`, before/after, under 1,200 characters.
- No docs index regeneration is needed unless a new doc page is added (it is not).

### Parallel Opportunities

- T011/T012 (corpus) and T013–T015 (prose) are separable once WP01 and WP02 are green.

### Dependencies

- Depends on WP01
- Depends on WP02

(the table asserts their behaviour, so it cannot be green until both have landed)

### Risks & Mitigations

- Corpus runner duplicating the unit tests → keep it to the cross-surface assertions; per-surface
  edge cases stay in the WP01/WP02 test modules.
- Docs freshness gate drift → run `check_docs_freshness --ci` and the terminology gate.

---

## Dependency & Execution Summary

- **Sequence**: WP01 and WP02 in parallel → WP03.
- **Parallelization**: WP01 and WP02 own disjoint files and can run concurrently.
- **MVP Scope**: WP01 alone already removes the worst symptom (a machine-readable clean bill for an
  unclean pack); WP01 + WP02 is the issue's requested convergence; WP03 makes it stick.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP02 |
| FR-005 | WP03 |
| FR-006 | WP01, WP02, WP03 |
| NFR-001 | WP01, WP02 |
| NFR-002 | WP02 |
| NFR-003 | WP01 |
| NFR-004 | WP03 |
| C-001 | WP01 |
| C-002 | WP02 |
| C-003 | WP01, WP02, WP03 |
| C-004 | WP03 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Red-first: status reports escaping node `body_path` | WP01 | P0 | No |
| T002 | Red-first: status reports escaping asset `path` | WP01 | P0 | No |
| T003 | Positive control + degraded-read tests | WP01 | P0 | No |
| T004 | Implement the two escape helpers in the status collector | WP01 | P0 | No |
| T005 | Targeted pytest + mypy | WP01 | P0 | Yes |
| T006 | Red-first: validate reports `body_path_escape` | WP02 | P0 | No |
| T007 | Red-first: CLI exit code, both findings together | WP02 | P0 | No |
| T008 | Positive control: contained path, discovered node | WP02 | P0 | No |
| T009 | Implement `_validate_fragment_body_paths` | WP02 | P0 | No |
| T010 | Targeted pytest + mypy | WP02 | P0 | Yes |
| T011 | Conformance case table (YAML) | WP03 | P1 | Yes |
| T012 | Conformance runner, three adapters | WP03 | P1 | No |
| T013 | `docs/api/charter-commands.md` | WP03 | P1 | Yes |
| T014 | Changelog `[Unreleased]` entry | WP03 | P1 | Yes |
| T015 | `PROMISES.md` `PR-CHARTER-SHARING-004` row | WP03 | P1 | Yes |
| T016 | Corpus + docs gates + touched test modules | WP03 | P1 | No |
