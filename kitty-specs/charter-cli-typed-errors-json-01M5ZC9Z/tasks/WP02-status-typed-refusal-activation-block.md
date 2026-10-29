---
work_package_id: WP02
title: 'Status: typed broken-charter refusal, canonical envelope, activation block (#6557, #6526 local slice)'
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-009
- FR-010
- FR-011
- FR-012
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- C-002
- C-003
- C-004
- C-005
- C-006
- SC-001
- SC-002
- SC-004
- SC-005
planning_base_branch: issue-6557-charter-cli-typed-errors-json
merge_target_branch: issue-6557-charter-cli-typed-errors-json
branch_strategy: Planning artifacts for this mission were generated on issue-6557-charter-cli-typed-errors-json. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6557-charter-cli-typed-errors-json unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-cli-typed-errors-json-01M5ZC9Z
base_commit: f1cfa3a59a9a62a40141f9e946b65053aa011cfb
created_at: '2026-10-27T22:07:44.175738+00:00'
subtasks:
- T007
- T008
- T009
- T010
- T011
- T012
phase: Phase 2 - Status
history:
- at: '2026-10-27T19:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/
create_intent:
- tests/specify_cli/cli/commands/charter/test_status_broken_charter_6557.py
- tests/specify_cli/cli/commands/charter/test_status_activation_block_6526.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/charter/status.py
- src/specify_cli/cli/commands/charter/_status_collectors.py
- tests/specify_cli/cli/commands/charter/test_status_broken_charter_6557.py
- tests/specify_cli/cli/commands/charter/test_status_activation_block_6526.py
- tests/specify_cli/cli/commands/charter/snapshots/status_activation/**
- tests/specify_cli/cli/commands/charter/test_status_sk16_config_guard.py
- tests/specify_cli/cli/commands/charter/test_status_json_safe.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Status: typed broken-charter refusal, canonical envelope, activation block

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission charter-cli-typed-errors-json-01M5ZC9Z`); address every item first.

---

## Objectives & Success Criteria

1. **#6557**: `spec-kitty charter status` on an unparseable, list-rooted, or empty `.kittify/charter/charter.yaml`
   exits 1 with `ACTIVE_CHARTER_CONFIG_INVALID`, naming the file, the problem and the remedy
   (`… re-run spec-kitty charter generate --from-interview`), never "Unexpected", never the bundle-schema
   "run upgrade" message. Text: `Error (ACTIVE_CHARTER_CONFIG_INVALID): …`. JSON: canonical envelope.
2. **Envelope (operator decision 01M5ZCANVH16B2ANT1BJ115S8R)**: every `charter status --json` error is
   `{"ok": false, "error": {"code", "message"}}`; the legacy `{result, success, error, code}` error shape is gone for this command.
   The **success** payload keeps its existing keys (`result: "success"`, …) — only errors change.
3. **#6526 local slice**: `charter status --json` adds an `activation` block (data-model.md "ActivationBlock"; snake_case; `schema_version: "1.0.0"`).
   Text (non-JSON) output of `charter status` is unchanged on every success path.

Requirements: FR-001, FR-002, FR-003, FR-004, FR-009, FR-010, FR-011, FR-012, NFR-001..004, C-002..C-005.

## Context & Constraints

- Gate to reuse (C-004): `src/specify_cli/cli/commands/charter/_charter_yaml_gate.py::assert_charter_yaml_sound(repo_root)` (PR #6555). It raises `ActiveCharterConfigError` (`KittyInternalConsistencyError`, `.code`, `.body`). Absent `charter.yaml` passes.
- Rendering: `src/specify_cli/cli/commands/charter/_coded_errors.py::render_coded_error` (do not modify it).
- Activation reads (C-003, ADR 2026-10-19-1): only through `charter.activation.api`: `load_activation_ledger`,
  `required_not_in_force`, `read_org_required_provenance`, `ActiveCharterConfigError`. Check `ArtifactKind` import path used elsewhere in `specify_cli` (prefer the offering/activation public seam that existing charter CLI modules already use). No new `charter.activation.<internal>` import.
- C-001: local codes only; snake_case block; no camelCase contract fields, no `revision`. Do not close #6526.
- Test patterns: `tests/specify_cli/cli/commands/charter/test_synthesize_charter_soundness.py` (#6415 — module-scoped generated-project template copied per test; `_BROKEN_YAML`; nothing-written assertion). Reuse that approach (copy the helper shape, do not import across test modules unless the repo already does).
- WP01 already reclassified `charter activate`/`deactivate` in the enumeration gate; build on its branch state.

## Branch Strategy

- **Planning base branch**: `issue-6557-charter-cli-typed-errors-json`
- **Merge target branch**: `issue-6557-charter-cli-typed-errors-json`
- Lane allocated by finalize-tasks; start with `spec-kitty agent action implement WP02 --agent <name> --mission charter-cli-typed-errors-json-01M5ZC9Z`.

## Commit sequence

1. `test(charter): red tests for status broken-charter refusal (#6557)` — T007.
2. `fix(charter): status refuses an unsound charter.yaml with a typed code (#6557)` — T008 + T009.
3. `test(charter): red tests for status activation block (#6526)` — T010.
4. `feat(charter): activation block in charter status --json (#6526)` — T011.
5. `test(charter): snapshot status activation block; status JSON errors adopted` — T012.

## Subtasks & Detailed Guidance

### Subtask T007 – Red #6557 tests

- New `tests/specify_cli/cli/commands/charter/test_status_broken_charter_6557.py` (markers like the #6415 file: `regression`, `non_sandbox`, `git_repo`).
- Cases (each: exit 1; nothing under `.kittify/` changed, byte-compare before/after):
  1. Unparseable YAML (`_BROKEN_YAML`) — text: contains `Error (ACTIVE_CHARTER_CONFIG_INVALID):`, `.kittify/charter/charter.yaml`, `spec-kitty charter generate --from-interview`; does not contain `Unexpected`.
  2. Same with `--json` — `json.loads(result.stdout)` is exactly `{"ok": False, "error": {"code": "ACTIVE_CHARTER_CONFIG_INVALID", "message": <str containing the file + remedy>}}` (allow extra keys inside `error` only if render adds none — it doesn't).
  3. List root (`- a\n- b\n`) text and JSON — same code; output does not contain `Bundle schema version` nor `spec-kitty upgrade`.
  4. Empty / comment-only file — same code, message mentions "no content".
  5. Positive control on the same fixture: sound charter → exit 0, JSON success payload has `result == "success"`.

### Subtask T008 – Status gate + envelope + codes

- In `status.py`:
  1. Immediately after `repo_root = _charter_pkg.find_repo_root()`, call `assert_charter_yaml_sound(repo_root)` — **before** `_assert_bundle_compatible`.
     Note `_charter_pkg` patching shim: tests patch `specify_cli.cli.commands.charter.X`; importing the gate directly is fine.
  2. Replace the except-chain with coded rendering via a small helper (keep `status` ≤ complexity 15 — it already carries `# noqa: C901`; do not add new suppressions; consider moving the text rendering body into helpers so the noqa can be dropped, as a campsite improvement, only if behaviour stays byte-identical):
     - `KittyInternalConsistencyError` → `render_coded_error(e.code, e.body or e.code, json_output=…)`.
     - `ConfigShapeError` → `CHARTER_CONFIG_SHAPE_INVALID`, message `str(e)`.
     - `TaskCliError` → `CHARTER_STATUS_FAILED`, message `str(e)`.
     - `Exception` → `INTERNAL_ERROR`, message `f"Unexpected error: {e}"` (keeps the word for real crashes only).
     - All `raise typer.Exit(code=1) from e`.
  3. JSON success path: keep `print(json.dumps(payload, indent=2))` as is (shape unchanged except the new block in T011).
- Remove the now-unused `_emit_error` import from `status.py` only (do not touch `_common.py`).

### Subtask T009 – Update existing status error tests

- `tests/specify_cli/cli/commands/charter/test_status_sk16_config_guard.py` and `test_status_json_safe.py` assert the legacy error envelope. Re-pin them to the canonical envelope + `CHARTER_CONFIG_SHAPE_INVALID` / the relevant code. This is a stale-pin re-pin justified by operator decision `01M5ZCANVH16B2ANT1BJ115S8R` (SO#4 "stale → re-pin"); say so in the commit body.
- Grep for other status error-shape assertions: `grep -rn "charter.*status" tests | grep -n "\"success\"\] is False\|\[\"error\"\]"`. If one lies outside `owned_files` (e.g. `tests/charter/test_presence_gate_bundle_authority.py`), re-pin it with a one-line rationale in `add-history` (ownership-map leeway).

### Subtask T010 – Red activation-block tests

- New `tests/specify_cli/cli/commands/charter/test_status_activation_block_6526.py`. Fixtures:
  - **ledger**: a project whose `.kittify/charter/activation.yaml` exists with `activated_directives: [A]`, `deactivated_directives: [B]`, `mission_type_activations: [software-dev]` (use the existing ledger fixtures in `tests/charter/activation/` or `tests/charter/conformance/test_activation_ledger_conformance.py` for valid shapes).
  - **legacy**: an unmigrated project (legacy activation keys in `charter.yaml`/`config.yaml`, no ledger) — follow how `tests/charter/activation/` builds an unmigrated project; assert `source == "legacy"` and `path` names that legacy file.
  - **required**: an org pack (`org-packs/acme` + `org-charter.yaml` with `required_directives: [R]`, configured in `.kittify/config.yaml` per the existing org-pack fixtures, e.g. `test_activate_preset.py` ORG/ORG_DIR) with (a) `activated_directives` omitting R → `{"kind": "directive", "id": "R", "in_force": false, "packs": ["acme"]}`, (b) absent allow list → `in_force: true`.
- Assert the block keys exactly: `schema_version, source, path, exists, selected, deactivated, mission_types, activated_kinds, required`. `selected[<plural>]` is `null` for an absent allow list and a list otherwise; `deactivated` lists only present deny keys.
- Text-mode `charter status` output unchanged (compare against the output with the block code path disabled is not possible — instead assert the text has no "activation" section and equals a captured golden for the ledger fixture made on the base).

### Subtask T011 – Collector + payload

- In `_status_collectors.py` add `_collect_activation_status(repo_root: Path) -> dict[str, Any]`:
  1. `ledger = load_activation_ledger(repo_root, report_stray=False)` (check the signature; it takes `legacy_loader`/`report_stray`).
  2. `selected = {kind.plural: (list(ids) if ids is not None else None) for kind, ids in ledger.allow}` — include every activatable kind present in `ledger.allow`; decide and document whether absent kinds are omitted or `null` (prefer: every activatable kind listed, `null` when absent, so consumers see the full key set; snapshot pins it).
  3. `deactivated = {kind.plural: list(ids) for kind, ids in ledger.deny if ids}`.
  4. `mission_types = list(ledger.mission_type_activations) if not None else None`; same for `activated_kinds`.
  5. Required: for each org-requirable kind, `read_org_required_provenance(repo_root, kind, strict=False)` → `{stem: packs}`; `not_in_force = {(o.kind, o.artifact_id) for o in required_not_in_force(repo_root, ledger, strict=False)}`; entries sorted by (kind, id) with `packs` from `RequiringPack.pack` (dedup, first-seen).
  6. `path`: repo-relative POSIX when inside `repo_root`.
  7. On `ActiveCharterConfigError` / `KittyInternalConsistencyError` during these reads → return `{"schema_version": "1.0.0", "error": {"code": e.code, "message": e.body or e.code}}` (status still succeeds for the other sections; design decision recorded in traces/design-decisions.md — keep it).
- In `status.py` add `"activation": _collect_activation_status(repo_root)` to the payload (JSON only; do not render it in text mode — FR-011).
- NFR-002: time `charter status --json` on the ledger fixture before/after (`time.perf_counter` in a throwaway script, not a test); note the delta in `add-history`.

### Subtask T012 – Snapshot + gate

- Snapshot the ledger-fixture `activation` block under `tests/specify_cli/cli/commands/charter/snapshots/status_activation/ledger.json` (normalize tmp paths).
- `tests/architectural/test_json_contract_enumeration.py` (owned by WP01 — out-of-map edit, record rationale "status errors adopted canonical envelope per decision 01M5ZCANVH16B2ANT1BJ115S8R"): move `"charter status": ((), 1, "outside")` from `PARSEABLE` to `ADOPTED`. Run the gate file.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/charter/test_status_broken_charter_6557.py tests/specify_cli/cli/commands/charter/test_status_activation_block_6526.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/charter/ -q -k "status"
uv run --frozen pytest tests/agent/cli/commands/test_charter_status_cli.py tests/specify_cli/cli/commands/charter/test_synthesize_charter_soundness.py tests/charter/test_presence_gate_bundle_authority.py -q
uv run --frozen pytest tests/architectural/test_json_contract_enumeration.py tests/architectural/test_runtime_charter_activation_boundary.py tests/architectural/test_charter_activation_api_reexport.py -q
uv run --frozen ruff check <changed>; uv run --frozen ruff format --check --force-exclude <changed>
uv run --frozen mypy --strict src/specify_cli/cli/commands/charter/status.py src/specify_cli/cli/commands/charter/_status_collectors.py
```

## Risks & Mitigations

- Legacy-envelope consumers break → accepted by operator; WP03 adds the CHANGELOG note.
- `_status_collectors` reached via `_charter_pkg` patch shim in tests → add the new collector name to the package re-export list only if a test needs to patch it.
- Legacy fixture construction is fiddly → mirror an existing unmigrated-project test exactly.

## Review Guidance

- Red→green proof for T007/T010 (commit order).
- Gate called before `_assert_bundle_compatible`; list-root case no longer says "upgrade".
- No "Unexpected" except the INTERNAL_ERROR path; success payload keys unchanged.
- Activation read only via `charter.activation.api`; `required` semantics match `required_not_in_force`.

## Progress & Status

- `spec-kitty agent tasks add-history WP02 --note "..."` · `spec-kitty agent tasks move-task WP02 --to <status>`
