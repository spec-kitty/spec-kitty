---
work_package_id: WP01
title: Record the disposition and regenerate the artefact
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6998-pinning-inventory-pause-ci-disposition
merge_target_branch: issue-6998-pinning-inventory-pause-ci-disposition
branch_strategy: Planning artifacts for this mission were generated on issue-6998-pinning-inventory-pause-ci-disposition. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6998-pinning-inventory-pause-ci-disposition unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pinning-inventory-pause-ci-disposition-01M6BTSJ
base_commit: e56ca7149e92b01aa88077034dcafc9bc4da9f13
created_at: '2026-11-01T15:22:41.245612+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - The recorded decision and its artefact
history:
- at: '2026-11-01T15:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- scripts/ci/derive_pinning_inventory.py
- tests/release/pinning_rule_inventory.json
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6998'
---

# Work Package Prompt: WP01 – Record the disposition and regenerate the artefact

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission pinning-inventory-pause-ci-disposition-01M6BTSJ`) and address every item before handing back.

## Objectives & Success Criteria

- `scripts/ci/derive_pinning_inventory.py`'s `DISPOSITIONS` carries an entry for `tests/ci/test_pause_ci_label.py::_REQUIRED_GATES`, and `tests/release/pinning_rule_inventory.json` is committed exactly as the derivation emits it.
- No row in the committed artefact carries `disposition: null`; every derived and executed row carries a vocabulary disposition and a reason of at least 60 characters.
- `PYTHONPATH=src python scripts/ci/derive_pinning_inventory.py --check` exits 0 (it exits 1 on the tip before this WP).
- `tests/release/test_pinning_inventory_fresh.py` is **not modified**, and passes in full with `SPEC_KITTY_STRICT_PINNING_INVENTORY=1`.

## Context

`eb099b70b1` (the `pr:pause-ci` label contract, #6961) added `_REQUIRED_GATES` to `tests/ci/test_pause_ci_label.py`. That list names `ci-quality.yml`, which the derivation classifies `retiring-host` + `set-equality` — a claim about that file's contents — so `is_dependency` returns `true` by its clause 3 and the derivation fails closed with `disposition: null`. Nothing adjudicated it, and nothing re-derives the artefact per PR, so the committed inventory is stale on `main` (issue #6998).

The verdict is `none`: the rule requires `ci-quality.yml`'s `clean-install-verification` job to *run* and *fail* under the `pr:pause-ci` label, so a skipped required check cannot pass. That job survives the sonarcloud retirement untouched, and the file never names the retired job. Nothing the rule asserts changes, and no edit is made to it — so `none`, never `rewrite` (claims an edit) or `relocate` (claims a move). `none` under `dependency: true` is the established shape: 26 of the 114 derived rows already carry it, each naming the surviving host.

## Subtasks

- **T001** Confirm both halves red on the tip before any edit: `--check` exits 1; `python3 scripts/ci/derive_pinning_inventory.py` followed by `pytest tests/release/test_pinning_inventory_fresh.py::test_every_entry_carries_a_disposition_from_the_vocabulary_and_a_reason` reds with `_REQUIRED_GATES: disposition None not in [...]`. Restore the artefact afterwards.
- **T002** Add the `DISPOSITIONS` entry as the trailing item of the block, matching the surrounding comment/format style. Reason must be ≥ 60 characters and must state (a) the rule pins `ci-quality.yml`'s surviving `clean-install-verification` job, (b) the file never names the retired job, (c) therefore nothing it asserts changes.
- **T003** Regenerate with `python3 scripts/ci/derive_pinning_inventory.py` (never hand-edit the JSON — its `_comment` says "DERIVED — do not hand-edit"). Confirm the only *added* row is `_REQUIRED_GATES` and zero rows were removed.
- **T004** Prove non-vacuity half by half and restore each time: delete the new entry, re-derive → completeness gate reds; hand-edit one line number in the artefact → freshness gate reds (`SPEC_KITTY_STRICT_PINNING_INVENTORY=1`).
- **T005** Confirm determinism: two consecutive derivations are byte-identical (`sha256`), and the committed artefact equals the derivation's output.
- **T006** Confirm `git diff --stat` over `scripts/` and `tests/` shows exactly the deriver and the artefact, with `tests/release/test_pinning_inventory_fresh.py` absent from the diff.

## Constraints

- `DISPOSITIONS_VOCABULARY` stays `{relocate, rewrite, retire-as-moot, none}`; `_MIN_REASON_CHARS` stays 60. No `xfail`, `skip`, or env-var default change.
- Do not special-case `pytest.mark.parametrize` in `_string_form` — the over-approximating classifier plus a human disposition is the contract's design, and changing it would silently re-adjudicate 26 existing rows.
- This rule resolves in the tree, so it belongs in `DISPOSITIONS`, never in `EXECUTED_LEDGER` (whose `relocate`/`rewrite` successors are existence-checked).
- The ~36 line-number blocks that move in the artefact are the derivation's current output. Do not hand-trim them.

## Definition of Done

- `derive_pinning_inventory.py --check` exits 0.
- `SPEC_KITTY_STRICT_PINNING_INVENTORY=1 pytest tests/release/test_pinning_inventory_fresh.py -q` passes; `git diff` over that test file is empty.
- `ruff check scripts/ci/derive_pinning_inventory.py` and `ruff format --check` are clean.
- Both halves re-verified red-then-green as in T004, with the observed messages quoted in the hand-off.
