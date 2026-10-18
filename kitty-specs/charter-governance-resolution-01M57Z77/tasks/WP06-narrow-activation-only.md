---
work_package_id: WP06
title: 'Opt-in narrow activation: charter activate --only and frozen-list warnings'
dependencies: []
requirement_refs:
- FR-012
- FR-014
- C-001
subtasks:
- T026
- T027
- T028
- T029
- T030
phase: Phase 3 - Delivery and activation
agent: claude
history:
- at: '2026-10-18T17:40:00Z'
  actor: claude-code/opus
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/activation_engine.py
create_intent:
- tests/specify_cli/cli/commands/charter/test_activate_only_6408.py
execution_mode: code_change
model: sonnet
owned_files:
- src/charter/activation/activation_engine.py
- src/charter/activation/pack_manager.py
- src/charter/activation/org_charter.py
- src/specify_cli/cli/commands/charter/activate.py
- tests/specify_cli/cli/commands/charter/test_activate_only_6408.py
- tests/charter/test_activation_engine.py
- tests/charter/test_pack_manager.py
- tests/charter/test_activation_preserves_effective_4253.py
- tests/charter/activation/test_promotion_fail_closed.py
- tests/charter/activation/test_org_charter_union.py
- tests/specify_cli/cli/commands/charter/test_activate_preserve.py
- tests/specify_cli/cli/commands/charter/test_activate_preset.py
- tests/specify_cli/test_charter_activate_vendored_click.py
role: implementer
task_type: implement
---

# Work Package Prompt: WP06 – Opt-in narrow activation: charter activate --only and frozen-list warnings

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt. Then load action doctrine: `spec-kitty charter context --action implement --mission-type software-dev --no-mark-loaded`.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission charter-governance-resolution-01M57Z77`). Address every feedback item; record progress with `spec-kitty agent tasks add-history <WPID> --note "..."`.

---

## Branch Strategy

- **Strategy**: populated by `finalize-tasks`
- **Planning base branch**: `issue-6404-charter-governance-resolution-work`
- **Merge target branch**: `issue-6404-charter-governance-resolution-work`

Execution worktrees are allocated per computed lane from `lanes.json`. Start with:

```bash
spec-kitty agent action implement <WPID> --agent claude --mission charter-governance-resolution-01M57Z77
```

Never construct a workspace path by hand.

## Shared Rules (every WP)

- **Red first** (ADR 2026-07-17-1): write the issue-pinned failing test(s) for the WP's acceptance scenarios and commit them on their own *before* the fix commit (`test: red repro for #NNNN ...`). After the fix, keep them as focused tests (not left marked `regression`).
- **Non-vacuity**: every absence/refusal assertion is paired with a positive control on the same fixture (tactic `acceptance-criteria-non-vacuity`).
- **Quality gates** (NFR-001): `uv run --frozen ruff check <changed files>`, `uv run --frozen ruff format --check --force-exclude <changed files>`, `uv run --frozen mypy --strict <changed src files>`; cyclomatic complexity ≤ 15; no new `# noqa` / `# type: ignore`.
- **Tests**: run the WP's own test files plus the owning subsystem directory (`tests/charter/` and, for `src/charter/offering/**`, `tests/charter_offering/`). Do not run `make test-full` or the whole `tests/architectural/` directory; run only the named gate files.
- **Terminology**: "Mission", never the retired term. Run `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q` when touching prose or `src/charter/offering/`.
- **Commits**: conventional types (`fix`, `feat`, `test`, `refactor`, `docs`); end every commit message with the session attribution lines given to you.
- Stay inside `owned_files`; a small out-of-map edit is acceptable only with a one-line rationale in the commit message and `add-history` note.

## Objectives & Success Criteria

Add an opt-in narrow activation path: `charter activate <kind> <id> --only` sets the kind's list to the id plus that kind's org-required ids and prints exactly what stops being in force; the default (no `--only`) is unchanged, and its warning now says the materialised list is frozen (#6408, operator decision 2026-10-18).

Done when:
- fresh project: `charter activate toolguide gherkin --only` → `activated_toolguides: [gherkin]`; output lists every other formerly effective toolguide under "No longer in force (N): ...";
- a present list + `--only` → replaced; a following plain `charter activate toolguide <other>` appends;
- an org pack requiring a toolguide/tactic whose stem ≠ declared id → the required artifact stays in force (written as its stem);
- `--only --preset ...` → exit 2 with a clear message;
- no `--only`: written list identical to today; warnings "Initialized from N ..." and "Preserved N ..." keep their prefixes and add the frozen-list sentence naming `--only`;
- `--only` with `--cascade`: only the named kind narrows; cascaded kinds append.

Requirement refs: FR-012, FR-014, C-001.

## Context & Constraints

- Engine (`src/charter/activation/activation_engine.py`): `ActivationPlan.deactivated` :191 (exists, unused by activate); `plan_activation` :220-363 (absent-key materialisation :334-343; "Initialized from" text :338-342); `_plan_promotion` :550-584 ("Preserved N" text :568); `promote_activations` :587-661.
- Manager (`src/charter/activation/pack_manager.py`): `_preservation_set` :429-476; `ActivationResult.deactivated` :502; `ActiveCharterManager.activate` :685-772 (seed :752, `plan_activation(..., effective_ids=preserved, ...)` :757-766, `commit_plan` + `restamp_bundle_hash` :770-771).
- Org-required: `load_org_charter_policies(repo_root)` → `getattr(policy, f"required_{plural}")` (`org_charter.py:705`, `REQUIRED_KIND_FIELDS` :100) are **declared ids**; converter `_normalize_required_ids` :294-336 (via `resolve_selected_id_to_stem`). Do not reuse `preset_application._org_required` (refuses, returns raw ids).
- CLI (`src/specify_cli/cli/commands/charter/activate.py`): `_check_preset_flags` :768-783 (exit 2 via `ctx.fail`; keep `ctx.fail`, vendored-click path pinned by `tests/specify_cli/test_charter_activate_vendored_click.py`); `activate_cmd` :852 **already complexity 15**; `manager.activate(...)` :983-990; render :994-997; cascade loop :269-292.
- Tests that substring-match warning prefixes: `tests/charter/test_pack_manager.py:250` ("had no explicit activation set"), `tests/charter/activation/test_promotion_fail_closed.py:50` ("Preserved 2 effective entries").
- `skill` kind: `--only` narrows the explicit list like any kind. `mission-type`: org-required base is empty.

## Subtasks & Detailed Guidance

### Subtask T026 – Red tests

- New `tests/specify_cli/cli/commands/charter/test_activate_only_6408.py` (CLI via `CliRunner`, fresh `spec-kitty init`-style fixture as in `test_activate_preserve.py`): scenarios 1-4 and 6 of US4 (fresh `--only`; present-list replace then plain append; `--only --preset` exit 2; cascade narrows only the named kind; exact dropped-id list asserted against the same fixture's effective set as positive control).
- `tests/charter/test_activation_engine.py`: `plan_activation(..., narrow_base=[...], previous_ids=[...])` → `new_list` and `deactivated` exact.
- `tests/charter/activation/test_org_charter_union.py`: `org_required_stems` maps a declared id with stem ≠ id to its stem; unknown id kept raw with a warning.
- Warning text: extend `tests/charter/test_pack_manager.py` / `test_activation_preserves_effective_4253.py` to assert the frozen-list sentence and `--only`.
Commit red: `test: red repro for #6408 narrow activation`.

### Subtask T027 – Engine `narrow_base`

- `plan_activation(..., narrow_base: Iterable[str] | None = None, previous_ids: Iterable[str] = ())`: when `narrow_base` is not None, skip absent-key materialisation; `new_list = dedupe(narrow_base) + [id]` (dedup); `deactivated = [i for i in previous_ids if i not in new_list]`. `_plan_promotion` / `promote_activations` accept `narrow_bases: Mapping[str, Sequence[str]] | None` with the same rule (WP07 uses it); return dropped ids per key.
- Append the frozen-list sentence to both warnings, e.g. `" This list is now explicit: artifacts shipped later are not activated automatically; use 'spec-kitty charter activate <kind> <id> --only' to keep activation narrow."` — one module constant.

### Subtask T028 – `org_required_stems`

- Public `org_required_stems(repo_root, kind_plural, warnings: list[str]) -> list[str]` in `org_charter.py` wrapping `load_org_charter_policies` + `_normalize_required_ids` (same pattern as :406-430). Returns `[]` for kinds outside `REQUIRED_KIND_FIELDS`.

### Subtask T029 – Manager `only=`

- `ActiveCharterManager.activate(..., only: bool = False)`: previous = present list, else the preserved set; base = `org_required_stems(...)`; call `plan_activation(..., narrow_base=base, previous_ids=previous)`; populate `ActivationResult.deactivated`.

### Subtask T030 – CLI `--only`

- Add `only: bool = typer.Option(False, "--only", help="Replace this kind's activation list with this id plus org-required ids (prints what stops being in force).")`; refuse with `--preset` in `_check_preset_flags`; extract `_render_activation_result(result, registration)` (keeps `activate_cmd` ≤ 15) printing "No longer in force (N): a, b, ...". Cascade loop unchanged.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/charter/test_activate_only_6408.py tests/specify_cli/cli/commands/charter/test_activate_preserve.py tests/specify_cli/cli/commands/charter/test_activate_preset.py tests/specify_cli/test_charter_activate_vendored_click.py tests/charter/test_activation_engine.py tests/charter/test_pack_manager.py tests/charter/test_activation_preserves_effective_4253.py tests/charter/activation/ -q
uv run --frozen pytest tests/charter/ tests/specify_cli/cli/commands/charter/ -q -p no:randomly
uv run --frozen pytest tests/architectural/test_json_contract_enumeration.py -q
uv run --frozen mypy --strict src/charter/activation/activation_engine.py src/charter/activation/pack_manager.py src/charter/activation/org_charter.py src/specify_cli/cli/commands/charter/activate.py
```

## Risks & Mitigations

- `activate_cmd` complexity ceiling → extraction is mandatory; check with `uv run --frozen ruff check --select C901`.
- Default path regression → existing preserve tests must stay green unchanged except for the appended warning sentence.

## Review Guidance

- Without `--only` the persisted list is byte-identical to `main` for the same fixture.
- Dropped-id output exact, not approximate.
