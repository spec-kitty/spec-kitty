---
work_package_id: WP02
title: 'Governance resolution: declared ids, layer-aware selections, diagnostics'
dependencies:
- WP01
requirement_refs:
- FR-007
- FR-008
- FR-009
- FR-010
- FR-011
- NFR-004
subtasks:
- T006
- T007
- T008
- T009
- T010
- T011
phase: Phase 2 - Identity surfaces
agent: claude
history:
- at: '2026-10-18T17:40:00Z'
  actor: claude-code/opus
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/resolver.py
create_intent:
- tests/charter/org_pack_identity_support.py
execution_mode: code_change
model: sonnet
owned_files:
- src/charter/activation/resolver.py
- src/charter/activation/compact.py
- src/charter/activation/context_json.py
- src/charter/activation/context_contract.py
- src/charter/activation/context.py
- tests/charter/org_pack_identity_support.py
- tests/charter/test_resolver.py
- tests/charter/test_compact.py
- tests/charter/test_resolver_activation_gating.py
- tests/charter/test_charter_context_directives_source.py
- tests/charter/test_resolve_project_governance_single_authority.py
- tests/charter/test_context_schema_version_ledger.py
- tests/specify_cli/cli/commands/test_charter_org_directive_identity.py
role: implementer
task_type: implement
---

# Work Package Prompt: WP02 – Governance resolution: declared ids, layer-aware selections, diagnostics

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

Make `resolve_project_governance` and `ActiveCharterService` use the identity index: the directive base shows declared ids (#6406), selections validate against every layer and an unknown id is dropped with a diagnostic instead of erasing governance (#6407), every service getter delivers stem ≠ id artifacts (sibling defect), and JSON context exposes `diagnostics`.

Done when, with the fixture org pack (`qa-003-no-fake-green` → `QA_003`, `qa-tactic-seven` → `qa-seven`):
- compact and JSON context list `QA_003` (source org pack), never `QA_003_NO_FAKE_GREEN`;
- `selected_directives: [QA_003]` and `[qa-003-no-fake-green]` both deliver `QA_003`, no "governance unresolved";
- `selected_directives: [QA_003, NOPE_999]` delivers everything plus a diagnostic naming `NOPE_999` in compact text and JSON `diagnostics`, exit 0, remediation pointing at org packs / `.kittify/charter-packs/` / `charter list`;
- an org paradigm in `selected_paradigms` is accepted; an unknown one is dropped with a diagnostic;
- `ActiveCharterService.tactics` (and every other kind's getter) includes `qa-seven` whether the list holds the stem or the declared id;
- the NFR-004 snapshot test from WP01 still passes unchanged.

Requirement refs: FR-007, FR-008, FR-009, FR-010, FR-011, NFR-004.

## Context & Constraints

- Depends on WP01 (`IdentityIndex`, generalised `resolve_artifact_urn`).
- `src/charter/activation/resolver.py`:
  - `_resolve_unmatched_directive_token` :144-163 (normaliser fallback with warning) — fold into index use.
  - `ActiveCharterService.__init__` :199; getters paradigms :214, procedures :223, agent_profiles :236, directives :253-287 (already URN-resolving), tactics :290, styleguides :299, toolguides :308, mission_step_contracts :317, glossary_packs :326, skills :335 — pattern `{k: v ... if k in pack_ctx.activated_X}` compares declared ids against stems.
  - `GovernanceResolution.diagnostics` :653; `_validate_paradigm_selection` :656-671 (raises, text "packs/built-in/paradigms/"); paradigm base :707-714, union :943-956.
  - `_resolve_directive_base` :800-853 (`base = sorted({_normalize_directive_id(d) ...})` :824; `valid_ids` :812-815 built-in + charter-local; raise :831-838 "add them to packs/built-in/directives/").
  - `_resolve_template_set_selection` :895-910 (remediation text only — FR-011; template-set layer awareness is out of scope).
  - `resolve_project_governance` :917 (loads `load_offering_catalog()` :946); duplicate `PackContext.from_config` calls at :707 and :818.
- `compact.py:311-338` `_resolve_governance_summary` catches `GovernanceResolutionError` (:320-324) and renders `(none)`; diagnostics already rendered (:267-268, merged :337).
- `context_json.py:135-170` `_load_project_directives_with_source` swallows errors (:155-159); `_project_directive_entries_with_source` :230 returns `(entries, directives_source)`.
- `context.py` entry points: `build_charter_context` :151, `build_charter_context_include` :360, `build_charter_context_json` :468 (payload :520-538).
- `context_contract.py`: `CONTEXT_SCHEMA_VERSION` :40 (1.3.0), `CONTEXT_CONTRACT_TOP_LEVEL_KEYS` :82-100.
- Callers that benefit automatically: `src/runtime/next/prompt_builder.py:536`, `src/specify_cli/runtime/doctor.py:142`, `collect_governance_diagnostics` (resolver.py:1064). Do not edit them; verify they still pass their tests.
- C-007: absent-key base membership (`resolver.py:819-822`, built-in catalog) unchanged.

## Subtasks & Detailed Guidance

### Subtask T006 – Fixture org pack + red tests

- **Steps**:
  1. Create a reusable fixture builder `tests/charter/org_pack_identity_support.py` (function `write_identity_org_pack(repo_root) -> Path` that writes an org pack with `qa-003-no-fake-green.directive.yaml` (`id: QA_003`, title "QA No Fake Green"), `qa-tactic-seven.tactic.yaml` (`id: qa-seven`), an org paradigm with stem ≠ id, and registers it in `.kittify/config.yaml` `charter_packs.org.packs`). Model it on `tests/specify_cli/cli/commands/test_charter_org_directive_identity.py`. WP03 and WP06 reuse it.
  2. Red tests (one file per surface, extending existing files):
     - `tests/charter/test_compact.py`: activated `qa-003-no-fake-green` → "Directive IDs" contains `QA_003`, not `QA_003_NO_FAKE_GREEN` (positive control: built-in `DIRECTIVE_001` still listed).
     - `tests/charter/test_resolver.py`: `selected_directives: [QA_003]` resolves; `[qa-003-no-fake-green]` resolves; `[QA_003, NOPE_999]` keeps `QA_003` and every activated directive and adds a diagnostic naming `NOPE_999`; the diagnostic text contains `.kittify/charter-packs` and not `packs/built-in/`; org paradigm accepted; unknown paradigm dropped with diagnostic; template-set error text no longer says "packs/built-in" / "built-in missions" only.
     - `tests/charter/test_resolver_activation_gating.py`: `ActiveCharterService(...).tactics` contains `qa-seven` for list `[qa-tactic-seven]` and for list `[qa-seven]` (ratchet control); parametrise over each getter kind with a stem ≠ id fixture.
     - `tests/charter/test_charter_context_directives_source.py` / `tests/specify_cli/cli/commands/test_charter_org_directive_identity.py`: CLI `charter context --action plan --mission-type software-dev --json --no-mark-loaded` → directive entries contain `{"id": "QA_003", "source": <org>}`; JSON has `diagnostics` (empty list when clean; contains `NOPE_999` when selected); exit 0.
  Commit red: `test: red repro for #6406 #6407 governance identity`.

### Subtask T007 – Directive base and selection validation through the index

- **Steps**: thread `identity: IdentityIndex | None = None` into `resolve_project_governance` (build once if `None`, from the same `PackContext`; build `PackContext` once and pass it to the paradigm and directive base helpers). In `_resolve_directive_base`:
  - activated base: `identity.declared_id(DIRECTIVE, t)`; for an unresolvable token keep today's normaliser-with-warning fallback (edge case: legacy tokens);
  - selections: `identity.selection_id(DIRECTIVE, s)`; unknown → drop + `diagnostics.append(...)` (do not raise). Charter-local `directives:` ids remain valid.
  - Remove `_resolve_unmatched_directive_token` if fully replaced (keep behaviour for activation lists).
- Return diagnostics through `GovernanceResolution.diagnostics`.

### Subtask T008 – Paradigm validation and remediation texts

- **Steps**: `_validate_paradigm_selection` uses `identity.knows/declared_id(PARADIGM, p)`; unknown → drop + diagnostic. Paradigm activated base and the union at :943-956 map through `declared_id`. `_resolve_template_set_selection` keeps raising (out of scope) but its text points at `charter list --show-available` / project overrides, not "packs/built-in". Introduce one module constant for the shared remediation sentence (Sonar S1192).

### Subtask T009 – Service getters for every kind

- **Steps**: add `identity` kwarg to `ActiveCharterService.__init__` (build lazily from its `pack_ctx` when absent). One helper `_activated_ids(kind) -> frozenset[str]` = `{identity.declared_id(kind, t) or t for t in tokens}`, memoised per kind on the instance; use it in all getters (paradigms, procedures, agent_profiles, tactics, styleguides, toolguides, mission_step_contracts, glossary_packs, skills). Directives getter: replace its private URN loop with the index (keep the #4240 warning behaviour for unknown tokens).

### Subtask T010 – Diagnostics in compact and JSON context

- **Steps**:
  1. `compact._resolve_governance_summary`: unknown ids now arrive in `resolution.diagnostics`; keep the `except GovernanceResolutionError` for genuine failures (template set).
  2. `context_json`: stop discarding the resolution's diagnostics; return them; `context.py` payload gains top-level `"diagnostics": [...]` (always present, list of strings).
  3. `context_contract.py`: add `"diagnostics"` to `CONTEXT_CONTRACT_TOP_LEVEL_KEYS`; bump `CONTEXT_SCHEMA_VERSION` to `1.4.0`; extend `tests/charter/test_context_schema_version_ledger.py` with the 1.4.0 entry and rationale.
  4. Build the index once per entry point in `context.py` (`build_charter_context`, `build_charter_context_json`, `build_charter_context_include`) and pass it to `resolve_project_governance`. WP03 adds the `identity=` keyword to the action-bundle loader and include renderers and wires those call sites in `context.py`.

### Subtask T011 – Verify

- **Steps**: run the snapshot test from WP01 (must pass unchanged), the red tests (now green), and the suites below. Confirm `tests/next/test_prompt_builder_unit.py` and `tests/runtime/test_doctor_unit.py` still pass (if present).

## Test Strategy

```bash
uv run --frozen pytest tests/charter/test_resolver.py tests/charter/test_compact.py tests/charter/test_resolver_activation_gating.py tests/charter/test_charter_context_directives_source.py tests/charter/test_resolve_project_governance_single_authority.py tests/charter/test_context_schema_version_ledger.py tests/charter/test_default_in_force_snapshot.py tests/specify_cli/cli/commands/test_charter_org_directive_identity.py -q
uv run --frozen pytest tests/charter/ tests/charter_offering/ -q -p no:randomly
uv run --frozen mypy --strict src/charter/activation/resolver.py src/charter/activation/compact.py src/charter/activation/context_json.py src/charter/activation/context_contract.py src/charter/activation/context.py
```

## Risks & Mitigations

- Schema bump ripples into tests that pin `1.3.0` → grep `1.3.0` under `tests/` and update only schema-version pins.
- Changing raise-to-drop could hide genuine errors → diagnostics must be visible in both renderings; tested.
- `resolver.py` complexity: extract helpers; keep each ≤ 15.

## Review Guidance

- No surface still guesses a directive id with the normaliser before consulting the index.
- Unknown-id diagnostics: compact text + JSON, exit 0, no `packs/built-in/` remediation.
- NFR-004 snapshot untouched.
