---
work_package_id: WP02
title: Validator refuses an escaping fragment body_path
dependencies: []
requirement_refs:
- FR-004
- NFR-001
- NFR-002
- C-002
planning_base_branch: issue-6733-charter-escape-report-convergence
merge_target_branch: issue-6733-charter-escape-report-convergence
branch_strategy: Planning artifacts for this mission were generated on issue-6733-charter-escape-report-convergence. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6733-charter-escape-report-convergence unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-escape-report-convergence-01M66YM0
base_commit: daf614c70e85ca419d91ba43de215f053087c3aa
created_at: '2026-10-30T18:35:51.883685+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - Convergence of the two disagreeing surfaces
history:
- at: '2026-10-30T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/packs/
create_intent:
- tests/charter/packs/test_pack_validator_body_path_escape.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/offering/packs/pack_validator.py
- tests/charter/packs/test_pack_validator_body_path_escape.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Validator refuses an escaping fragment body_path

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
`spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

`charter org validate` already rejects an asset sidecar whose `path` escapes the pack's `assets/`
root (`asset_path_escape`). It silently accepts an authored `drg/fragment.yaml` node whose
`body_path` escapes the pack root, so a pack author's own pre-share gate is weaker than the doctor.
After this WP:

- `validate_pack` reports one structured error per escaping authored node, with
  `category="body_path_escape"`, the node id as `artifact_id`, and the fragment file as `file`;
- the `charter org validate` CLI exits non-zero and prints the finding;
- a contained `body_path` produces no finding, an empty `body_path` is not judged, and a discovered
  (validator-owned) node's `body_path` is still not judged here;
- the asset and body_path findings coexist in one run (neither hides the other);
- `asset_path_escape` and every existing category keep their current meaning (C-002).

Success: the new tests are red before the change and green after; `mypy --strict` passes on the
touched module.

## Context & Constraints

- Mission: `kitty-specs/charter-escape-report-convergence-01M66YM0/` — read `spec.md` (FR-004),
  `plan.md` (D-2), `research.md` (D3).
- Issue #6733. The authority is
  `charter.offering.drg.org_pack_loader.find_body_path_escapes(fragment, pack_root)`, which judges
  only `OrgDRGFragment.authored_nodes` through `resolve_relative_path_within_root`. Call it with the
  fragment `load_org_pack` already returned from `_validate_org_fragment` and with `pack_dir` as the
  root — never re-validate a copy (the loader's own copy caveat) and never re-derive containment
  (C-001).
- Message: print the predicate's own `escape.message` (it names the pack, node, kind, path and
  reason), so `charter org validate` and `doctor charter-packs` say the same sentence.
- Category vocabulary lives in the `ValidationIssue` docstring; add `body_path_escape` there.
- The validator is charter-layer; it must not import from `specify_cli`. Keep the offering import
  lazy, as the module does elsewhere, so `--help` stays fast.
- No `charter.offering.api`, layer-chain or packaging change (C-003).

## Branch Strategy

- **Strategy**: planning and merge target are this Mission's topic branch; the PR targets `main`.
- **Planning base branch**: `issue-6733-charter-escape-report-convergence`
- **Merge target branch**: `issue-6733-charter-escape-report-convergence`

> These fields are populated by `spec-kitty agent mission finalize-tasks`. Do not change them by
> hand unless the topology has genuinely changed.

## Subtasks & Detailed Guidance

### Subtask T006 – Red-first: `validate_pack` reports a `body_path_escape` finding

- **Purpose**: pin FR-004 at the validator API before the implementation.
- **Steps**:
  1. Create `tests/charter/packs/test_pack_validator_body_path_escape.py` with a minimal
     org pack builder: `pack.yaml` (`pack_id`, `name`, `pack_level: org`), `drg/fragment.yaml` with
     one authored node (`{id: team-asset, kind: assets, title: …, body_path: <escaping>}`) and no
     other artifacts, so the only findings are the ones under test.
  2. Assert `validate_pack(pack)["errors"]` carries exactly one issue with
     `category == "body_path_escape"`, `artifact_type == "drg"`, `artifact_id == "team-asset"`,
     `file` naming `drg/fragment.yaml`, and a message naming the node and the escaping path.
  3. Cover the escape shapes the predicate covers: `..`-traversal and an absolute POSIX path (and a
     Windows-form path if it keeps the module readable; the predicate's own tests already cover the
     full matrix — this module only needs to prove the wiring).
- **Files**: `tests/charter/packs/test_pack_validator_body_path_escape.py`.
- **Notes**: `pytestmark = [pytest.mark.unit, pytest.mark.fast]`.

### Subtask T007 – Red-first: CLI exit code and both findings together

- **Purpose**: prove the production path (CLI), not only the function (FR-004 acceptance 1 and 3).
- **Steps**: with `typer.testing.CliRunner` on `specify_cli.cli.commands.charter.charter_app`, run
  `charter org validate <pack>` for (a) an escaping `body_path`, (b) a pack with both an escaping
  `body_path` and an escaping asset sidecar; assert `exit_code != 0` and that the output contains
  both category tokens (`body_path_escape`, `asset_path_escape`).
- **Files**: the same test module.
- **Notes**: if the CLI needs a project root, follow what the existing charter CLI tests do; do not
  invent a new harness.

### Subtask T008 – Positive control: contained path and discovered node

- **Purpose**: keep the check non-vacuous in both directions (SC-003, FR-006).
- **Steps**: assert `body_path_escape` is absent for (a) a contained relative path, materialised or
  not, (b) a node with no `body_path`, (c) a discovered artifact whose file declares an escaping
  `body_path` (that fault belongs to the kind's own validator, per #6418's predicate contract).
- **Files**: the same test module.
- **Notes**: guard the premise in case (c) — assert the discovered node really carries the escaping
  string before asserting no finding, so the test cannot pass for the wrong reason.

### Subtask T009 – Implement `_validate_fragment_body_paths`

- **Purpose**: deliver FR-004.
- **Steps**:
  1. Add `body_path_escape` to the `ValidationIssue` category docstring and to the module-level
     category list in the module docstring.
  2. Write `_validate_fragment_body_paths(pack_dir: Path, fragment: OrgDRGFragment) -> list[ValidationIssue]`
     next to the asset leg (same shape, same lazy-import convention): import
     `find_body_path_escapes`, iterate the escapes, build one `ValidationIssue` per escape with
     `severity="error"`, `artifact_type="drg"`, `artifact_id=escape.node`, `file=str(pack_drg_fragment(pack_dir))`,
     `message=escape.message`, `category="body_path_escape"`.
  3. Call it from `validate_pack` immediately after `_validate_org_fragment` returns a fragment (skip
     when it returns `None`), so it runs beside the asset leg in every validation.
  4. Keep the function short and single-purpose; no branching beyond the `None` guard.
- **Files**: `src/charter/offering/packs/pack_validator.py`.
- **Notes**: do not restyle the asset leg. Ruff/mypy strict must pass.

### Subtask T010 – Targeted validation

- **Steps**:
  1. `uv run pytest tests/charter/packs/test_pack_validator_body_path_escape.py -q`
  2. `uv run pytest tests/charter/packs tests/charter_offering/drg/test_org_body_path_escapes.py tests/charter_offering/assets/test_org_asset_path_escapes.py -q`
  3. `uv run mypy --strict src/charter/offering/packs/pack_validator.py`
  4. `uv run ruff check src/charter/offering/packs/pack_validator.py tests/charter/packs/test_pack_validator_body_path_escape.py`
- **Files**: none (validation only).
- **Parallel?**: Yes, after T009.
- **Notes**: no full-suite sweep. Record commands and counts in the WP history.

## Test Strategy

- Mandatory: T006–T008, all through `validate_pack` and the `charter org validate` CLI.
- Fixtures: a minimal single-node pack builder shared by all cases (escaping and contained).
- Typed sources: `mypy --strict` on the changed module.

## Risks & Mitigations

- **Judging a discovered node** → the predicate excludes them; T008(c) pins the premise.
- **Double-reporting an asset fault** → the new leg only reads authored fragment nodes; the asset
  leg is untouched.
- **Message drift from doctor** → print the predicate's message; never rebuild it.
- **Slow `--help`** → lazy import of the predicate, as elsewhere in the module.

## Review Guidance

- Confirm the red→green transition for each new test.
- Confirm the finding is structured (category/artifact_type/artifact_id/file/message) and that no
  existing category changed meaning.
- Confirm the new leg runs for a pack that also has asset faults (both findings present).
- Confirm `mypy --strict` and ruff were run on the touched files.

## Progress & Status

Progress, history and status live in the status event log (`status.events.jsonl`), never in this
file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
