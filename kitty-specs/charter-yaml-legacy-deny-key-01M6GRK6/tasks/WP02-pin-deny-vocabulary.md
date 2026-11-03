---
work_package_id: WP02
title: Pin the deny-side contract and record the change
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-004
- C-002
- SC-001
- SC-003
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 2 - Contract pin and record
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-11-03T13:15:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/charter/
create_intent:
- docs/changelog/unreleased/6855-charter-yaml-legacy-deny-key.internal.md
execution_mode: code_change
model: ''
owned_files:
- tests/charter/test_activation_vocabulary_setequal.py
- docs/changelog/unreleased/6855-charter-yaml-legacy-deny-key.internal.md
role: implementer
task_type: implement
---

# Work Package Prompt: WP02 – Pin the deny-side contract and record the change

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
(or any user-defined profile), and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log
  (`spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

- The decision "the deny vocabulary is **not** part of `charter.yaml`'s shape" is a pinned
  invariant, beside the allow-side parity gate #6556 added (FR-002, FR-004).
- Every key of `charter.activation.activation_ledger.DENY_KEYS` is refused by `CharterYaml`, and
  no model field is a deny key (SC-001).
- `DENY_KEYS` and `ACTIVATION_YAML_KEYS` are disjoint, asserted both ways (SC-003).
- A changelog fragment records the decision (one file, no edit to `docs/changelog/CHANGELOG.md`).

## Context & Constraints

- **Depends on WP01**: the refusal message asserted here is the one WP01 introduces; run WP01's
  tests first.
- **One deny vocabulary (C-002)**: read it from `activation_ledger.DENY_KEYS`, derived from
  `ArtifactKind`. Never hand-list keys in the test, and never restate a kind table in
  `schemas.py`.
- **Lazy import discipline**: the guard file already imports activation modules inside test
  bodies/functions (module-level imports of `pack_manager` from the test would defeat the
  import-graph gate the file also owns). Follow the same pattern.
- **Positive control**: the same fixture without the deny key must validate in the same test, so
  a failure cannot pass for an unrelated reason (the `acceptance-criteria-non-vacuity` tactic
  requires the same-fixture control).

## Branch Strategy

- **Strategy**: planning artifacts were generated on
  `issue-6855-charter-yaml-legacy-deny-key`; completed changes must merge back into
  `issue-6855-charter-yaml-legacy-deny-key`.
- **Planning base branch**: `issue-6855-charter-yaml-legacy-deny-key`
- **Merge target branch**: `issue-6855-charter-yaml-legacy-deny-key`

## Subtasks & Detailed Guidance

### Subtask T006 – Derive the deny vocabulary and pin disjointness

- **Purpose**: make the allow/deny asymmetry an assertion instead of a comment.
- **Steps**:
  1. In `tests/charter/test_activation_vocabulary_setequal.py`, add a `#6855` section after the
     #6556 block, with a local `_deny_vocabulary()` helper that imports `DENY_KEYS` from
     `charter.activation.activation_ledger` inside the function body.
  2. `test_deny_vocabulary_is_non_empty_and_prefixed` — sanity: non-empty, every key starts with
     `deactivated_` (a guard on the helper, so the pins below cannot pass vacuously).
  3. `test_deny_vocabulary_is_disjoint_from_the_activation_allow_vocabulary` — no intersection
     with `_authority()` (SC-003).
  4. `test_charter_yaml_declares_no_deny_field` — no `CharterYaml.model_fields` name starts with
     `deactivated_` (FR-002).
- **Files**: `tests/charter/test_activation_vocabulary_setequal.py`
- **Parallel?**: yes.
- **Notes**: keep the file's existing `pytestmark` (`unit`, `fast`); do not add markers that
  change the module's tier.

### Subtask T007 – The parametrized refusal pin + positive control

- **Purpose**: pin actual behaviour, not just set arithmetic (SC-001).
- **Steps**:
  1. Build the same sound document shape the file's #6556 block uses (or a minimal inline one:
     `governance: {}`, `directives: {directives: []}`, a `catalog` with
     mission/template_set/languages/references, `metadata`).
  2. `test_charter_yaml_refuses_every_deny_key_with_the_contract_message`, parametrized over
     `sorted(_deny_vocabulary())`: each document must raise `ValidationError`, and the message
     must contain `.kittify/charter/activation.yaml` and `never applied`.
  3. Positive control in the same test: `CharterYaml.model_validate(document)` (the document
     without the deny key) succeeds.
- **Files**: `tests/charter/test_activation_vocabulary_setequal.py`
- **Parallel?**: no (needs T006's helper).
- **Notes**: parametrizing over the derived vocabulary is what makes a future kind's deny key
  covered without editing the test; the literal `deactivated_tactics` case belongs in
  `tests/charter/test_charter_yaml_model.py` (WP01).

### Subtask T008 – Changelog fragment

- **Purpose**: record the decision in the unreleased section without touching the shared
  changelog (fragments are consumed at release time).
- **Steps**:
  1. Create `docs/changelog/unreleased/6855-charter-yaml-legacy-deny-key.internal.md` with one
     entry in the fragment style (bold impact-first lead, `(#6855, #6850)` reference, before and
     after, under 1,200 characters). Rename the file to `<pr>.internal.md` once the PR number
     exists.
  2. `uv run --frozen python -m scripts.docs.check_changelog_style` — exit 0.
  3. `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased` — exit 0.
- **Files**: `docs/changelog/unreleased/6855-charter-yaml-legacy-deny-key.internal.md`
- **Parallel?**: yes.
- **Notes**: the section is `internal` because no supported workflow and no production reader
  validates `charter.yaml` through this model yet (issue #6855's own impact section); the
  decision and the clearer refusal are maintainer-facing.

### Subtask T009 – Targeted validation

- **Purpose**: prove the pin and the import graph.
- **Steps**:
  1. `uv run --frozen pytest tests/charter/test_activation_vocabulary_setequal.py tests/charter/test_charter_yaml_model.py -q`
  2. `uv run --frozen ruff check` and `ruff format --check` on the two touched files.
  3. Re-run the import-graph gate specifically:
     `uv run --frozen pytest tests/charter/test_activation_vocabulary_setequal.py -k import -q`
  4. Record commands and counts in `## Progress & Status`.
- **Files**: none (validation only).
- **Parallel?**: no.

## Test Strategy

- The pin must fail if a `deactivated_*` field is later added to the model, if a deny key is
  added to `ACTIVATION_YAML_KEYS`, or if the refusal stops raising.
- The positive control must pass on the same fixture in the same test (non-vacuity).
- Do not run whole-directory suites (`tests/architectural/` as a whole) — see
  `NO_FULL_HEAVY_SUITES_IN_MISSION`.

## Risks & Mitigations

- **Vacuous pin** (asserting only "a ValidationError of some kind"): assert the two stable
  message facts.
- **A hidden second vocabulary**: if the helper ever grows a literal list, the derived-authority
  assertion in T006 stops proving anything; keep it derived.
- **Fragment name collision**: rename to the PR number after the PR exists.

## Review Guidance

- Confirm the deny vocabulary is read from `DENY_KEYS`, not restated.
- Confirm the positive control runs on the same fixture and passes.
- Confirm the fragment is a new file under `docs/changelog/unreleased/`, and that
  `docs/changelog/CHANGELOG.md` is untouched.
- Confirm no `deactivated_*` field exists on the model and `extra="forbid"` is intact.

## Progress & Status

- Implementation: pending.

## Definition of Done

- [ ] T006/T007 pins added and green.
- [ ] T008 fragment added, style and spelling checks exit 0.
- [ ] T009 targeted tests + import gate green; counts recorded.
