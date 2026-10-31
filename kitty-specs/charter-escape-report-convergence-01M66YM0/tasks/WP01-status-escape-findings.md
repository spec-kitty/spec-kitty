---
work_package_id: WP01
title: Status surface reports escaping org-pack paths
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-003
- C-001
planning_base_branch: issue-6733-charter-escape-report-convergence
merge_target_branch: issue-6733-charter-escape-report-convergence
branch_strategy: Planning artifacts for this mission were generated on issue-6733-charter-escape-report-convergence. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6733-charter-escape-report-convergence unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-escape-report-convergence-01M66YM0
base_commit: e7a727a2ed7a987a5839e2750b648c491fef6c5e
created_at: '2026-10-30T17:52:05.506728+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Convergence of the two disagreeing surfaces
history:
- at: '2026-10-30T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/
create_intent:
- tests/specify_cli/cli/commands/charter/test_status_org_layer_path_escapes.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/charter/_status_collectors.py
- tests/specify_cli/cli/commands/charter/test_status_org_layer_path_escapes.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Status surface reports escaping org-pack paths

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or
any user-defined profile), and behave according to its guidance before parsing the rest of this
prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) before starting, and
address every feedback item as its own TODO. Record what you changed with
`spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

`charter status --json` must never hand out `org_layer.errors: []` for an org pack whose declared
paths escape their roots. After this WP:

- an authored `drg/fragment.yaml` node whose `body_path` escapes its pack root appends the offering
  predicate's message to `org_layer.errors`, and the human `charter status` output prints it;
- an org asset sidecar whose `path` escapes its `assets/` root does the same;
- a contained pack still reports no errors (no false positive);
- a check that cannot run appends `org-layer <kind> check failed: …`, never a silent "clean";
- the escape findings survive a refused merge (they are collected before the merge);
- `charter status --json` gains no new key (`org_layer` keys and their types are unchanged).

Success: the new tests are red before the change and green after; the touched module passes
`mypy --strict`.

## Context & Constraints

- Mission: `kitty-specs/charter-escape-report-convergence-01M66YM0/` — read `spec.md`
  (FR-001..FR-003), `plan.md` (D-1), `research.md` (D1–D3).
- Issue #6733: `charter status` and `charter org validate` disagree with `doctor charter-packs` on
  the same pack. This WP fixes the status half only.
- The authority is `charter.offering.drg.org_pack_loader.find_body_path_escapes` and
  `charter.offering.assets.repository.find_asset_path_escapes`, reached through the registry-aware
  wrappers `charter.activation.drg_activation.find_org_body_path_escapes` /
  `find_org_asset_path_escapes` (the pair `doctor charter-packs` already uses). Do **not** restate
  containment (C-001).
- Mirror `specify_cli/cli/commands/_charter_pack_collect.py::_record_body_path_escapes` /
  `_record_asset_path_escapes`: same wrapper, same message, same "check could not run" discipline.
- `_collect_org_layer_status`'s docstring already explains why findings ride `errors` instead of a
  dedicated key; keep that reasoning intact (NFR-003).
- Layer rule (`kernel <- charter <- specify_cli`): importing `charter.activation.drg_activation`
  from `specify_cli` is the sanctioned direction. `charter.offering.api` is untouched (C-003).

## Branch Strategy

- **Strategy**: planning and merge target are this Mission's topic branch; the PR targets `main`.
- **Planning base branch**: `issue-6733-charter-escape-report-convergence`
- **Merge target branch**: `issue-6733-charter-escape-report-convergence`

> These fields are populated by `spec-kitty agent mission finalize-tasks`. Do not change them by
> hand unless the topology has genuinely changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first: status reports an escaping node `body_path`

- **Purpose**: pin FR-001 through the pre-existing entry point before touching production code.
- **Steps**:
  1. Create `tests/specify_cli/cli/commands/charter/test_status_org_layer_path_escapes.py` with the
     same fixture shape the sibling status tests use
     (`tests/specify_cli/cli/commands/charter/test_status_org_layer_completeness.py`): copy
     `tests/architectural/_fixtures/org_packs/example_org`, write a `.kittify/config.yaml` with
     `charter_packs.org.packs[0] = {name: example-org, local_path: <tmp>/example_org}`, and add one
     authored node to `drg/fragment.yaml` with an escaping `body_path`
     (`../../../../etc/hostname`).
  2. Assert `_collect_org_layer_status(repo)["errors"]` contains an entry that names the pack, the
     node and the escaping path (the predicate message reads
     `… body_path '…' is not contained in the pack root: …`).
  3. Add one CLI-level case through `charter status --json` (CliRunner on the `charter_app`) that
     reads `org_layer.errors` from the JSON, so the production wiring is exercised, not only the
     collector.
- **Files**: `tests/specify_cli/cli/commands/charter/test_status_org_layer_path_escapes.py`.
- **Parallel?**: No (shares the module with T002).
- **Notes**: keep the fixture builder shared with T002/T003 so the escaping and contained cases can
  never drift apart. Mark the module `pytestmark = [pytest.mark.unit, pytest.mark.fast]`.

### Subtask T002 – Red-first: status reports an escaping asset sidecar `path`

- **Purpose**: pin FR-002.
- **Steps**: in the same module, build a pack whose `assets/team-logo.asset.yaml` declares
  `path: ../../../../etc/hostname` (sidecar schema: `id`, `mime`, `path`), and assert
  `org_layer.errors` names the asset and the path.
- **Files**: the same test module.
- **Notes**: a sidecar that fails its own schema is a schema fault, not a containment fault — keep it
  schema-valid.

### Subtask T003 – Positive control and degraded-read tests

- **Purpose**: prove the check is not vacuous in either direction (FR-003, FR-006, SC-003).
- **Steps**:
  1. Contained pack: the unmodified fixture has no escaping path; assert `errors == []` (this is the
     paired positive control — same builder, escaping case above).
  2. Check cannot run: monkeypatch `charter.activation.drg_activation.find_org_body_path_escapes`
     (and the asset sibling) to raise, then assert `errors` says
     `org-layer body_path check failed: …` / `org-layer asset path check failed: …` and the
     collector still returns a payload.
  3. Refused merge: monkeypatch `merge_three_layers` to raise and assert the escape finding is still
     present (the collection happens before the merge).
- **Files**: the same test module.

### Subtask T004 – Implement the two escape helpers in the status collector

- **Purpose**: deliver FR-001..FR-003.
- **Steps**:
  1. In `src/specify_cli/cli/commands/charter/_status_collectors.py`, add
     `_record_body_path_escapes(result, repo_root, fragments)` and
     `_record_asset_path_escapes(result, repo_root, fragments)` beside
     `_collect_org_layer_status` — feature-detector shape, one concern per helper, with docstrings
     that say what they add and why the channel is `errors`.
  2. Each helper imports its wrapper lazily (`from charter.activation.drg_activation import …`),
     calls it, extends `result["errors"]` with `escape.message` for each escape, and on any
     exception appends `org-layer <kind> check failed: <exc>`.
  3. Call both from `_collect_org_layer_status` right after the `fragments` loop and **before** the
     `merge_three_layers` block, and update that function's docstring to name the new findings.
  4. Keep the function's existing return shape and key set.
- **Files**: `src/specify_cli/cli/commands/charter/_status_collectors.py`.
- **Notes**: keep each new function small (Sonar cognitive-complexity guard); ruff/mypy strict must
  pass. Do not change the merge/conflict handling.

### Subtask T005 – Targeted validation

- **Steps**:
  1. `uv run pytest tests/specify_cli/cli/commands/charter/test_status_org_layer_path_escapes.py tests/specify_cli/cli/commands/charter/test_status_org_layer_completeness.py tests/specify_cli/cli/commands/test_doctor_charter_packs_org_layer.py -q`
  2. `uv run mypy --strict src/specify_cli/cli/commands/charter/_status_collectors.py`
  3. `uv run ruff check src/specify_cli/cli/commands/charter/_status_collectors.py tests/specify_cli/cli/commands/charter/test_status_org_layer_path_escapes.py`
- **Files**: none (validation only).
- **Parallel?**: Yes, after T004.
- **Notes**: no full-suite sweep (`NO_FULL_HEAVY_SUITES_IN_MISSION`). Record the exact commands and
  counts in the WP history.

## Test Strategy

- Mandatory: the three test groups in T001–T003, all through the production entry points.
- Fixtures: a shared pack builder in the test module (copied `example_org` fixture + a
  `.kittify/config.yaml`), with one escaping node, one escaping sidecar, and the unmodified
  contained control.
- Typed sources: run `mypy --strict` on the changed module (matches CI).

## Risks & Mitigations

- **False positive on a sound pack** → T003's contained case runs on the same builder.
- **A crash turns status into a traceback** → the per-check `try/except` reports it as a finding.
- **Duplicate authority** → only the offering predicates judge containment; this WP adds none.
- **Unread payload slot** → no new key; the messages ride `errors`, which status already renders.

## Review Guidance

- Confirm the new tests fail on the planning base (`git stash` or check out the base) and pass here.
- Confirm no new `org_layer` key and no change to the merge/conflict paths.
- Confirm every message comes from the predicate, not from a re-derived sentence.
- Confirm `mypy --strict` and ruff were run on the touched files.

## Progress & Status

Progress, history and status live in the status event log (`status.events.jsonl`), never in this
file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
