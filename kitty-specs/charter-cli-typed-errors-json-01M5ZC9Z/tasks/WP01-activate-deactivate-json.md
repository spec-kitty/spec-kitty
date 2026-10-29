---
work_package_id: WP01
title: 'Activate/deactivate: report extraction and --json (#6525 local slice)'
dependencies: []
requirement_refs:
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- FR-011
- FR-012
- NFR-001
- NFR-003
- NFR-004
- C-001
- C-005
- SC-002
- SC-003
- SC-005
planning_base_branch: issue-6557-charter-cli-typed-errors-json
merge_target_branch: issue-6557-charter-cli-typed-errors-json
branch_strategy: Planning artifacts for this mission were generated on issue-6557-charter-cli-typed-errors-json. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6557-charter-cli-typed-errors-json unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-cli-typed-errors-json-01M5ZC9Z
base_commit: cee88ac24e26d8f5a08585b121da33a49ac27b3d
created_at: '2026-10-27T19:24:27.877147+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Activate / deactivate
history:
- at: '2026-10-27T19:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/
create_intent:
- src/specify_cli/cli/commands/charter/_activation_report.py
- tests/specify_cli/cli/commands/charter/test_activation_text_golden.py
- tests/specify_cli/cli/commands/charter/test_activation_json_6525.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/charter/activate.py
- src/specify_cli/cli/commands/charter/deactivate.py
- src/specify_cli/cli/commands/charter/_activation_report.py
- tests/specify_cli/cli/commands/charter/test_activation_text_golden.py
- tests/specify_cli/cli/commands/charter/test_activation_json_6525.py
- tests/specify_cli/cli/commands/charter/snapshots/activation_json/**
- tests/architectural/test_json_contract_enumeration.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Activate/deactivate: report extraction and --json (#6525 local slice)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission charter-cli-typed-errors-json-01M5ZC9Z`). If present, address every item first and record progress with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

Positional `spec-kitty charter activate KIND ID [--cascade SCOPE [--include-deactivated]] [--only] --json`
and `spec-kitty charter deactivate KIND ID [--cascade SCOPE] --json`:

- On success, stdout is exactly one JSON document: the **ActivationChangeReport** of
  `kitty-specs/charter-cli-typed-errors-json-01M5ZC9Z/data-model.md` / `contracts/cli-json.md`
  (`schema_version: "1.0.0"`, snake_case).
- On refusal, stdout is exactly one canonical error `{"ok": false, "error": {"code", "message", ...}}`
  (via `render_coded_error`), and the exit code equals the exit code of the same invocation without `--json`.
- Without `--json`, the human output is **byte-identical** to `origin/main` on every success path, and
  refusals print `Error (<CODE>): <message>` (the only intended text change).
- `--json` with `--preset` keeps today's preset behaviour unchanged.

Requirements: FR-004, FR-005, FR-006, FR-007, FR-008, FR-011, FR-012, NFR-001, NFR-003, NFR-004, C-001, C-005.

## Context & Constraints

- Charter: `.kittify/charter/charter.md` (tidy-first SO#2, ATDD-first, complexity ≤ 15, no new `noqa`/`type: ignore`).
- Plan / decisions: `kitty-specs/charter-cli-typed-errors-json-01M5ZC9Z/plan.md`, `research.md` §4, `data-model.md`, `contracts/cli-json.md`.
- **C-001**: codes are LOCAL UPPER_SNAKE. Never use or imitate the spec-kitty-charter contract codes (`artifact_required`, `activation_invalid`, …). No `revision` field. Do not close #6525.
- **Seam**: do not change `src/charter/**`. Report types live in the CLI layer (`_activation_report.py`). Keep the
  existing imports pattern of `activate.py`/`deactivate.py`; add no new `charter.activation.<internal>` import
  beyond those already present in these files (the boundary gate is shrink-only).
- Envelope: `src/specify_cli/cli/json_contract.py::json_error` via `src/specify_cli/cli/commands/charter/_coded_errors.py::render_coded_error`.
  Do not modify `_coded_errors.py` (WP02 does not either; it is shared and stable).

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `issue-6557-charter-cli-typed-errors-json`
- **Merge target branch**: `issue-6557-charter-cli-typed-errors-json`

> Execution worktrees are allocated per computed lane from `lanes.json`. Start with
> `spec-kitty agent action implement WP01 --agent <name> --mission charter-cli-typed-errors-json-01M5ZC9Z`.

## Commit sequence (mandatory, reviewer checks it)

1. `test(charter): pin activate/deactivate text output` — T001 only; green on the base.
2. `refactor(charter): build activation report before rendering` — T002; T001 still green, no other test changed.
3. `test(charter): red acceptance tests for activate/deactivate --json (#6525)` — T003; red.
4. Implementation commits for T004–T005 (T003 turns green).
5. `test(charter): snapshot activation JSON; classify deactivate in JSON gate` — T006.

## Subtasks & Detailed Guidance

### Subtask T001 – Golden-text ratchet

- **Purpose**: prove the tidy step (T002) and the `--json` wiring change nothing in the human output.
- **Steps**:
  1. Create `tests/specify_cli/cli/commands/charter/test_activation_text_golden.py` (`pytestmark = [pytest.mark.fast]` if it runs in < 1 s per test, otherwise no tier marker beyond what neighbours use).
  2. Reuse fixture patterns from `tests/specify_cli/cli/commands/charter/test_charter_deactivate_commands.py`
     and `test_org_cascade_chain.py` (a tmp project with `.kittify/config.yaml`, org pack under `org-packs/` when needed;
     invoke `charter_app` via `CliRunner` with the hidden `--repo-root`). Use `--no-compile` to keep runs fast and deterministic.
  3. Cover, as separate cases, the text output of:
     - direct activate (no cascade): `Activated:` line + the no-cascade referenced-artifacts warning;
     - activate `--cascade all` reaching ≥ 1 cascaded target, ≥ 1 out-of-scope (use a narrowed scope such as `--cascade tactic`), a kind-filtered node (template/asset) if the fixture graph has one;
     - activate `--cascade all` with a deactivated child (skipped, deactivated + unreached + hint) and the same with `--include-deactivated` (reinstated line);
     - activate `--only` (`No longer in force (...)` line);
     - deactivate direct; deactivate `--cascade all` with an exclusive child, a shared child, an absent-allow-list child (`still active (no allow-list…)`), and a required child (`skipped (required by …)`).
  4. Assert the full `result.output` against inline expected strings (normalize the tmp path only). Capture the
     expected strings by running on the base before T002. If a case is impossible to construct from existing fixtures, note it in the test docstring and in `add-history`.
- **Files**: new test file only.
- **Notes**: Rich wraps at terminal width; set `COLUMNS`/`env={"COLUMNS": "200"}` in `runner.invoke` to avoid wrap-dependent goldens.

### Subtask T002 – Tidy-first report extraction (behaviour-preserving)

- **Purpose**: today `_activate_cascade_targets`, `_render_cascade_activation`, `_cascade_child`,
  `_render_cascade_deactivation` and the command bodies mutate and print in the same loop. Separate them so a
  single report value feeds both the text renderer and (T005) the JSON serializer.
- **Steps**:
  1. Create `src/specify_cli/cli/commands/charter/_activation_report.py` with `__all__` and frozen dataclasses:
     - `ArtifactRef(kind: str, id: str, urn: str | None)` (kind = operator token, id = stored config-stem spelling);
     - `CascadeOutcome` entries where extra data is needed: `FailedRef(ref, message)`, `DeactivatedSkip(ref, required_by: tuple[str, ...])`,
       `SharedSkip(ref, referenced_by: str)`, `RequiredSkip(ref, packs: tuple[str, ...])` — or one `CascadeEntry(ref, detail: dict)`; choose the simpler typed form;
     - `CascadeReport(source_urn, scope, cascaded, reinstated, failed, skipped_out_of_scope, skipped_deactivated, unreached_behind_deactivated, skipped_kind_filtered, skipped_shared, skipped_required, still_active_unrestricted, zero_activatable: bool)`;
     - `ActivationChangeReport(command, kind, id, changed, no_longer_in_force, warnings, referenced_not_cascaded, cascade)`;
     - `to_json()` methods (T005 uses them; write them now, they are pure) returning the contract shape with `schema_version: "1.0.0"`.
  2. Refactor activate: `_activate_cascade_targets` returns the cascaded / failed lists instead of printing;
     `_render_cascade_activation` becomes `_cascade_activation_report(...) -> CascadeReport` plus a pure
     `render_cascade_activation(report)` that prints exactly the lines printed today **in the same order**
     (cascaded and warning lines interleave in sorted kind/id order today — preserve that: record events in an ordered
     list if needed, or render failures in their original position). `_render_no_cascade_warning` similarly yields refs + renderer.
  3. Refactor deactivate the same way (`_cascade_child` → returns an outcome; `_render_cascade_deactivation` → report + renderer). Keep `_warn_mission_default_binding` calls at the same points of the output.
  4. Keep every function ≤ complexity 15; keep public names that tests import (grep `tests/` for each name you rename; prefer keeping names and changing bodies).
  5. Run T001 + the existing activate/deactivate tests (see Test Strategy). All green, untouched.
- **Files**: `activate.py`, `deactivate.py`, `_activation_report.py`.
- **Parallel?**: no.

### Subtask T003 – Red acceptance tests for `--json`

- **Steps**: new `tests/specify_cli/cli/commands/charter/test_activation_json_6525.py`, same fixtures as T001. Cases:
  1. `activate KIND ID --json` → exit 0, `json.loads(result.stdout)` succeeds (NFR-001: assert the whole stdout parses), `schema_version == "1.0.0"`, `command == "activate"`, `changed` non-empty, `cascade is None`, `referenced_not_cascaded` lists the refs the text warning lists.
  2. `activate ... --cascade all --json` → `cascade.source_urn`, every touched artifact with `kind`/`id`/`urn`, outcome lists populated per fixture; reinstated case with `--include-deactivated`.
  3. `deactivate ... --cascade all --json` → `skipped_shared` (with `referenced_by`), `skipped_required` (with `packs`), `still_active_unrestricted`, `cascaded`.
  4. Refusals with `--json` (each asserts canonical shape, the code, exit code == same invocation without `--json`, and **no change under `.kittify/`** — snapshot the tree bytes before/after for NFR-003):
     `ACTIVATION_KIND_UNKNOWN` (kind `nonsense`), `CASCADE_SCOPE_INVALID` (`--cascade bogus-kind`),
     `ACTIVE_CHARTER_CONFIG_INVALID` (malformed charter-pack config, see `test_status_sk16_config_guard.py` / existing activate config tests for the fixture),
     `DEACTIVATION_REFUSED_REQUIRED` (org-required id; `error.requiring_packs == ["acme"]`),
     `CHARTER_WRITE_ROOT_INVALID` (linked worktree — reuse the existing linked-worktree fixture from the write-root tests; grep `LinkedWorktreeCharterWriteError` in tests),
     `ACTIVATION_FAILED` (unknown artifact id → `ValueError` from the manager).
  5. Text-mode refusal prints `Error (ACTIVATION_KIND_UNKNOWN): Unknown kind 'nonsense'. Valid kinds: …`.
  6. `activate --preset missing --json` unchanged (existing behaviour; one regression assertion).
  7. Usage error stays exit 2: `deactivate --json` with `--include-deactivated`? (not an option there) — use `activate KIND ID --include-deactivated --json` without `--cascade` → exit 2.
- Commit red.

### Subtask T004 – Local codes + coded rendering

- **Steps**:
  1. In `activate.py`, add module constants (and export through `__all__` only if another module imports them; `deactivate.py` already imports from `activate.py`):
     `ACTIVATION_KIND_UNKNOWN`, `CASCADE_SCOPE_INVALID`, `CHARTER_WRITE_ROOT_INVALID`, `DEACTIVATION_REFUSED_REQUIRED`, `ACTIVATION_FAILED`. `ACTIVE_CHARTER_CONFIG_INVALID` comes from the exception's own `.code`.
  2. Route every refusal in both commands through one helper, e.g. `_refuse(code, message, *, json_output, payload=None) -> NoReturn` that calls `render_coded_error(...)` and raises `typer.Exit(1)`.
     Replace `console.print(f"[red]Error:[/red] ...")` and `render_pack_config_error` in the positional paths. `render_pack_config_error` already prints `Error (CODE): body` — keep it for any remaining caller or replace its body with `render_coded_error(exc.code, exc.body, json_output=False)`; text must stay identical.
  3. `resolve_write_root_or_exit` gains a `json_output: bool = False` parameter (preset path passes its own flag; text unchanged except the coded prefix).
  4. `DeactivationRefused` → `DEACTIVATION_REFUSED_REQUIRED` only for the required subclass (`reason == "required"`); payload `{"requiring_packs": [entry.pack ...]}`. Any other `DeactivationRefused` reason → `ACTIVATION_FAILED` (future-proof, no contract code).
  5. Mission-type validation / step-removal `ValueError` and `DRGLoadError` → `ACTIVATION_FAILED`.

### Subtask T005 – `--json` wiring

- **Steps**:
  1. activate: change the `--json` help to "Output JSON (positional form: change report; --preset: applied preset)."; drop `json_output` from `_PRESET_ONLY_OPTIONS` (keep `--pack`, `--force` preset-only). Update `_check_preset_flags` accordingly.
  2. deactivate: add `json_output: bool = typer.Option(False, "--json", help="Output the change report as JSON.")`.
  3. In JSON mode run the mutation + cascade + `recompile_or_notify` + `reproject_pack_skills` inside `with console.capture():` (pattern: `_activate_preset`), but render refusals **outside** the capture (a refusal inside raises out of the `with`; make the refusal helper emit after the capture exits, e.g. by catching `typer.Exit` around the captured block only for the non-zero coded path, or by structuring: validate+mutate (may refuse, not captured) → captured render-only/recompile block). A failing `recompile_or_notify` with `typer.Exit(!=0)` in JSON mode → `RESYNTHESIS_FAILED`-style coded error is NOT in scope; mirror `_activate_preset`: emit the existing `_RESYNTHESIS_FAILED` code with the report as payload.
  4. Emit `console.emit_json(report.to_json())` once at the end.
  5. Tension warnings (`_render_tension_warnings`) must also land in `warnings` in JSON mode: split it into collect + render like T002.
- **Notes**: stdout must contain nothing but the JSON document — assert in tests via `result.stdout`.

### Subtask T006 – Snapshots + enumeration gate

- **Steps**:
  1. Store canonical payloads under `tests/specify_cli/cli/commands/charter/snapshots/activation_json/` (one file per case: `activate_direct.json`, `activate_cascade.json`, `deactivate_cascade.json`). Compare after normalizing tmp paths; regenerate only with an explicit env flag (follow an existing snapshot helper in the repo if one exists — grep `snapshot` in `tests/`; else a tiny helper in the test module).
  2. `tests/architectural/test_json_contract_enumeration.py`: move `"charter activate"` from `PARSEABLE` to `ADOPTED` (keep `(("--preset", "missing"), 1, "outside")` only if that arm now yields the canonical envelope — check; otherwise use a positional arm, e.g. `(("nonsense", "x"), 1, "outside")`), and add `"charter deactivate": (("nonsense", "x"), 1, "outside")` to `ADOPTED`. Run the gate file.

## Test Strategy

Run (record commands + counts in `add-history`):

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/charter/test_activation_text_golden.py tests/specify_cli/cli/commands/charter/test_activation_json_6525.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/charter/ -q -k "activate or deactivate or cascade or preset" 
uv run --frozen pytest tests/charter/test_tension_cascade_exclusion.py tests/charter/test_activation_preserves_effective_4253.py tests/charter/test_skill_activation.py tests/charter/test_glossary_pack_activation.py -q
uv run --frozen pytest tests/architectural/test_json_contract_enumeration.py tests/architectural/test_runtime_charter_activation_boundary.py -q
uv run --frozen ruff check src/specify_cli/cli/commands/charter tests/specify_cli/cli/commands/charter
uv run --frozen ruff format --check --force-exclude <changed files>
uv run --frozen mypy --strict src/specify_cli/cli/commands/charter/activate.py src/specify_cli/cli/commands/charter/deactivate.py src/specify_cli/cli/commands/charter/_activation_report.py
```

Do not run `make test-full` or the full `tests/architectural/` directory.

## Risks & Mitigations

- **Output order drift** in the refactor → T001 goldens; render from an ordered event list if the original interleaving cannot be reproduced from bucketed lists.
- **Refusal swallowed by `console.capture()`** → refusals rendered outside the capture; T003 asserts stdout JSON for every refusal.
- **Existing tests import renamed helpers** → grep before renaming; keep names.
- **Complexity creep** in `activate_cmd` (already long) → move JSON/text branching into small helpers.

## Review Guidance

- Verify the commit sequence (golden green on base; refactor commit changes no test; red tests before implementation).
- Diff the golden expectations against `origin/main` output (re-run T001 on a base checkout).
- Confirm no contract-shaped code (snake_case) or `revision` field; codes match `contracts/cli-json.md`.
- Confirm `--json` stdout parses for every case, exit codes match non-JSON runs, nothing written on refusal.
- Confirm mypy --strict and ruff/format pass on changed files.

## Progress & Status

- `spec-kitty agent tasks add-history WP01 --note "..."`
- `spec-kitty agent tasks move-task WP01 --to <status>`
- `spec-kitty agent tasks status --mission charter-cli-typed-errors-json-01M5ZC9Z`
