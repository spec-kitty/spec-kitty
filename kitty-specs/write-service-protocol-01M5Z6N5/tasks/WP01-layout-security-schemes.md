---
work_package_id: WP01
title: Contract layout admits a root security scheme
dependencies: []
requirement_refs:
- FR-007
- FR-008
- SC-001
planning_base_branch: issue-6675-write-service-protocol
merge_target_branch: issue-6675-write-service-protocol
branch_strategy: Planning artifacts for this mission were generated on issue-6675-write-service-protocol. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6675-write-service-protocol unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Foundation
history:
- at: '2026-10-27T18:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: contracts/tools/layout_check.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- contracts/tools/layout_check.py
- tests/contract/test_layout_check.py
- contracts/README.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Contract layout admits a root security scheme

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission write-service-protocol-01M5Z6N5`) and address every item before handing back.

## Objectives & Success Criteria

- A module's root `openapi.yaml` may carry `components` whose **only** key is `securitySchemes`
  (operator ruling `bearer_declaration`, 2026-10-27). Spec FR-007, FR-008.
- A root `components` with any other key (`schemas`, `responses`, ...) still fails with
  `TRACKED_BUNDLE`, and so does an empty `components` or a non-mapping one.
- The resolver, `bundle.py --bundle-only` and the Gradle `validate_*` / `validateBundle_*` tasks
  keep and accept the scheme (proved on a scratch module outside the repository).
- `contracts/README.md` states the rule with one example.

## Context & Constraints

- `contracts/tools/layout_check.py::check_bundles` refuses any root `components` today.
- `bundle.py` orders top-level keys `openapi, info, servers, tags, paths, components`; other keys
  (`security`) follow, key-sorted. `citation_check` reads only `components.schemas`.
- Do not touch `_shared/` (spec C-004). Do not widen the admitted set beyond `securitySchemes`.
- ATDD-first: commit T001's failing tests before T002.

## Branch Strategy

- **Strategy**: single_branch (set by finalize-tasks)
- **Planning base branch**: issue-6675-write-service-protocol
- **Merge target branch**: issue-6675-write-service-protocol

Implementation command: `spec-kitty agent action implement WP01 --agent claude --mission write-service-protocol-01M5Z6N5`

## Subtasks & Detailed Guidance

### Subtask T001 – Failing tests

- **Purpose**: pin the accepted and refused shapes before the code changes.
- **Steps**: in `tests/contract/test_layout_check.py`, beside
  `test_root_document_carrying_components_is_a_bundle`, add (tmp-path fixtures built from the
  `clean` fixture, like the neighbours):
  1. a root with `components: {securitySchemes: {writeToken: {type: http, scheme: bearer}}}` and a
     root `security: [{writeToken: []}]` → no finding;
  2. the same plus `schemas: {}` under `components` → exactly `["TRACKED_BUNDLE"]`;
  3. `components: {}` → `["TRACKED_BUNDLE"]`; `components: []` → `["TRACKED_BUNDLE"]`.
- **Validation**: the new accept case fails on the base (RED), the refuse cases pass already
  (they are the paired positive control). Commit as `test(layout): ...` first.

### Subtask T002 – Amend `check_bundles`

- **Steps**: admit the root `components` only when it is a non-empty mapping whose keys are
  exactly `{"securitySchemes"}`. Name the admitted key in one module constant
  (`ROOT_COMPONENTS_ADMITTED = frozenset({"securitySchemes"})`). Keep the message of the refusal
  specific: name the extra keys.
- **Validation**: T001 GREEN; the existing `v_tracked_bundle` case and the whole file pass.

### Subtask T003 – Prove the downstream tools keep the scheme

- **Steps**: copy `contracts/mission-status` to a scratch root outside the repository, add the
  scheme and a root `security`, run `layout_check.py`, `bundle.py --bundle-only` and, with a JDK
  21 and the pinned Gradle (`install_tools.py --only gradle`), the full `bundle.py`. Confirm the
  bundle carries `components.securitySchemes` and `security`, and the generator validation passes.
- **Notes**: no file is committed for this subtask; record the commands and outcome in the WP's
  history note. If a tool drops or rejects the scheme, stop and report: WP03 depends on it.

### Subtask T004 – README rule

- **Steps**: add a `## Security schemes` section to `contracts/README.md` after
  "Module version and the /api/v1 prefix": the root may declare `components.securitySchemes` and
  nothing else under `components`; operations reference it through `security`; `TRACKED_BUNDLE`
  for anything else. One YAML example. `structure_check.py` must still pass (it checks required
  headings only).

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q tests/contract/test_layout_check.py
.venv/bin/python contracts/tools/layout_check.py --root contracts
.venv/bin/python contracts/tools/structure_check.py --root contracts
.venv/bin/python contracts/tools/run_negative_cases.py --cases contracts/tools/negative_cases.json  # if it takes these args; see its --help
uv run --frozen ruff check contracts/tools/layout_check.py tests/contract/test_layout_check.py
uv run --frozen ruff format --check --force-exclude contracts/tools/layout_check.py tests/contract/test_layout_check.py
```

## Risks & Mitigations

- The generator rejects `security` on a 3.1 document: T003 catches it before WP03.
- Over-admitting: the frozenset makes the admitted set explicit; the paired refusal tests guard it.

## Review Guidance

- RED commit precedes the change; the refuse cases are positive controls.
- The admitted set is exactly `securitySchemes`.

## Progress & Status

Recorded through the status event log.
