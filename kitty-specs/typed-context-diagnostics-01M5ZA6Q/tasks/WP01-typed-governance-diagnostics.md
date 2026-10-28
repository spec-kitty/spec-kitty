---
work_package_id: WP01
title: Typed governance diagnostics contract
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
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
planning_base_branch: issue-6460-typed-context-diagnostics
merge_target_branch: issue-6460-typed-context-diagnostics
branch_strategy: Planning artifacts for this mission were generated on issue-6460-typed-context-diagnostics. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6460-typed-context-diagnostics unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-typed-context-diagnostics-01M5ZA6Q
base_commit: a543272f22db83d2b0ac36a83eb7c604f28205dc
created_at: '2026-10-27T18:42:28.871928+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
phase: Phase 1 - Contract
history:
- at: '2026-10-27T18:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- tests/charter/test_context_diagnostics_typed.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/_diagnostics.py
- src/charter/activation/ERROR_CODES.md
- src/charter/activation/resolver.py
- src/charter/activation/context_json.py
- src/charter/activation/context.py
- src/charter/activation/context_contract.py
- src/charter/activation/compact.py
- src/charter/activation/api.py
- src/runtime/next/prompt_builder.py
- src/specify_cli/runtime/doctor.py
- docs/api/charter-commands.md
- docs/changelog/CHANGELOG.md
- tests/charter/test_context_diagnostics_typed.py
- tests/charter/test_*.py
- tests/charter/fixtures/*_in_force_snapshot.json
- tests/acceptance/fixtures/unmigrated_context_golden.json
- tests/runtime/test_doctor_unit.py
- tests/next/test_prompt_builder_unit.py
- tests/architectural/test_charter_activation_api_reexport.py
- tests/specify_cli/cli/commands/test_charter_org_directive_identity.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Typed governance diagnostics contract

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address every feedback item; record progress with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

Close #6460 and #6461 item 1 (docs only; the code of #6461 item 3 is WP02).

- `GovernanceResolution.diagnostics` is `list[GovernanceDiagnostic]`; each entry has `code: GovernanceDiagnosticCode` and `message: str`.
- `charter context --json` emits `diagnostics` as a list of `{"code": ..., "message": ...}` objects; `context_schema_version` stays `"1.4.0"`.
- Codes (closed set, JSON-stable strings): `UNKNOWN_SELECTION_DROPPED`, `CATALOG_DEFAULT_APPLIED`, `FALLBACK_APPLIED`, `SELECTION_MERGED`, `UNRESOLVED_REFERENCE`. Mapping: `data-model.md`.
- `doctor`'s governance check warns iff an entry has code `UNKNOWN_SELECTION_DROPPED`; no prefix matching anywhere (SC-003: `grep -rn "_UNKNOWN_SELECTION_PREFIX\|startswith(_UNKNOWN" src` is empty).
- Compact context and the runtime prompt show the same message text as before (SC-004).
- `docs/api/charter-commands.md` documents the `{code, message}` shape with all five codes and the interview JSON `narrowed` field; the rc8 changelog entry (`docs/changelog/CHANGELOG.md`, the #6407 line in `[Unreleased] - 4.0.0rc8`) is reworded to the typed shape.
- Requirements: FR-001..FR-006, NFR-001..NFR-003, C-001..C-003.

## Context & Constraints

- Read `kitty-specs/typed-context-diagnostics-01M5ZA6Q/{spec,plan,research,data-model}.md` and `contracts/context-json-diagnostics.md`.
- Charter: `.kittify/charter/charter.md` (ATDD-first C-011: the red tests are their own commit **before** any implementation commit; `__all__` convention C-007; no new `noqa` / `type: ignore`; complexity <= 15).
- Architecture: `specify_cli` must import charter symbols through `charter.activation.api` (not `charter.activation.resolver`) for new imports. Note `doctor.py` currently also imports from `charter.activation.resolver`; leave that existing import alone except what you must change.
- Out of scope (C-003): `charter generate --json` `diagnostics` (`src/specify_cli/cli/commands/charter/generate.py`, compiler diagnostics) stays `list[str]`.
- Do NOT bump `CONTEXT_SCHEMA_VERSION`.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: issue-6460-typed-context-diagnostics
- **Merge target branch**: issue-6460-typed-context-diagnostics

> Populated by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; use `spec-kitty agent action implement WP01 --agent claude --mission typed-context-diagnostics-01M5ZA6Q`.

## Subtasks & Detailed Guidance

### Subtask T001 – Red ATDD tests (commit first, alone)

- **Purpose**: pin the user-observable contract before implementation.
- **File**: `tests/charter/test_context_diagnostics_typed.py` (new). Mark tests `fast`/`unit` per the conventions of neighbouring files (check `tests/charter/test_charter_context_directives_source.py` for the CLI-runner fixture it uses to render `charter context --json`, and reuse it).
- **Tests**:
  1. `test_context_json_diagnostics_are_typed_objects`: render context JSON for a bare project (the same setup the directives-source test uses). Assert `payload["context_schema_version"] == "1.4.0"`, `payload["diagnostics"]` non-empty, every entry is a `dict` with keys exactly `{"code", "message"}`, every `code` in the five-value set.
  2. `test_unknown_selected_directive_has_drop_code`: charter selects `NOPE_999` (reuse the setup in `test_charter_context_directives_source.py:112-124`). Assert one entry with `code == "UNKNOWN_SELECTION_DROPPED"` whose message contains `NOPE_999`.
  3. Per-code resolver mapping (unit, through `resolve_project_governance`): a bare project yields `CATALOG_DEFAULT_APPLIED` (paradigms, directives) and `FALLBACK_APPLIED` (tools, template set); a charter selection beyond the base yields `SELECTION_MERGED`. Reuse fixtures from `tests/charter/test_resolver.py`.
  4. Doctor (in `tests/runtime/test_doctor_unit.py`, next to the existing test at ~`:394`): (a) a stubbed resolution whose `UNKNOWN_SELECTION_DROPPED` entry has a **reworded** message (e.g. `"Selection NOPE_999 was discarded"`) → warning, message listed; (b) negative control: an entry with code `CATALOG_DEFAULT_APPLIED` whose message starts with `"Unknown selected "` → no dropped-selection warning.
  5. `UNRESOLVED_REFERENCE` on the profile path: `resolve_governance_for_profile` with a profile/interview that references an unknown directive (see existing coverage in `tests/charter/test_resolver.py`), assert the entry code.
- Run them; confirm RED for the right reason (strings instead of objects / ImportError of the new names). Commit: `test(charter): pin typed {code, message} context diagnostics (#6460)` with trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

### Subtask T002 – Code enum and value object

- **File**: `src/charter/activation/_diagnostics.py`. Update the module docstring (it now holds charter-encoding codes AND governance-resolution codes). Add:
  ```python
  class GovernanceDiagnosticCode(StrEnum):
      UNKNOWN_SELECTION_DROPPED = "UNKNOWN_SELECTION_DROPPED"
      CATALOG_DEFAULT_APPLIED = "CATALOG_DEFAULT_APPLIED"
      FALLBACK_APPLIED = "FALLBACK_APPLIED"
      SELECTION_MERGED = "SELECTION_MERGED"
      UNRESOLVED_REFERENCE = "UNRESOLVED_REFERENCE"

  @dataclass(frozen=True)
  class GovernanceDiagnostic:
      code: GovernanceDiagnosticCode
      message: str
      def to_json(self) -> dict[str, str]:
          return {"code": self.code.value, "message": self.message}
  ```
  with docstrings; add both to `__all__`.
- **File**: `src/charter/activation/ERROR_CODES.md`: add a third part "Governance resolution diagnostic codes" (source of truth: `_diagnostics.py` `GovernanceDiagnosticCode`), one `##` per code with "When it fires", "JSON stability" and example message; update the intro ("This file has three parts"). Keep the NFR-008 note scoped to part 1.
- **File**: `src/charter/activation/api.py`: re-export `GovernanceDiagnostic`, `GovernanceDiagnosticCode` (follow the existing `X as X` pattern and `__all__`); add matching rows to `tests/architectural/test_charter_activation_api_reexport.py`.

### Subtask T003 – Producers emit typed entries

- **File**: `src/charter/activation/resolver.py`.
- `GovernanceResolution.diagnostics: list[GovernanceDiagnostic]`.
- Every `diagnostics: list[str]` parameter in the producer helpers becomes `list[GovernanceDiagnostic]`; each `append` wraps its existing f-string unchanged in `GovernanceDiagnostic(<code>, <same text>)`. Mapping (lines on origin/main `581b5c46`): `_drop_unknown` (`:647`) → UNKNOWN_SELECTION_DROPPED; `:703`, `:834` → CATALOG_DEFAULT_APPLIED; `:745`, `:913` → FALLBACK_APPLIED; `:742`, `:786`, `:788`, `:889`, `:891` → SELECTION_MERGED; `:1027` → UNRESOLVED_REFERENCE.
- Keep `UNKNOWN_SELECTION_DIAGNOSTIC` as the message template (still used by `_drop_unknown` and tests).
- `collect_governance_diagnostics` keeps returning `list[str]`: `[d.message for d in resolution.diagnostics]` (it also returns uncoded `GovernanceResolutionError.issues`). Note this in its docstring.
- Watch complexity (<= 15) of any function you touch.

### Subtask T004 – Context JSON serialisation

- **File**: `src/charter/activation/context_json.py:150-179`. Build `list[dict[str, str]]` from the resolution: `[d.to_json() for d in diagnostics if isinstance(d, GovernanceDiagnostic)]`. A duck-typed stub without `diagnostics` (or non-list) still yields `[]`. Fix the return annotation(s) and docstring of `_load_project_directives_with_diagnostics` and its callers (`:278-292`, `context.py:580-597`) so mypy --strict is clean.
- Decide and document what a stub entry that is not a `GovernanceDiagnostic` does (recommended: dropped, since production always yields typed entries; if a seam test feeds strings, update that test instead of adding a string branch).
- **File**: `src/charter/activation/context_contract.py:76-81`: reword the `diagnostics` ledger comment: a list of `{code, message}` objects, codes closed set (name them), consumers match on `code`; still 1.4.0 (unshipped, redefined before rc8). Check `tests/charter/test_context_schema_version_ledger.py` still passes (no version change).

### Subtask T005 – Doctor by code

- **File**: `src/specify_cli/runtime/doctor.py:139-170`. Remove `_UNKNOWN_SELECTION_PREFIX` and the `UNKNOWN_SELECTION_DIAGNOSTIC` import; import `GovernanceDiagnosticCode` from `charter.activation.api`; `unknown = [d.message for d in resolution.diagnostics if d.code is GovernanceDiagnosticCode.UNKNOWN_SELECTION_DROPPED]`. Message text of the warning unchanged.
- `charter.activation.api` then has no `src/` caller of `UNKNOWN_SELECTION_DIAGNOSTIC`: remove its re-export (and `__all__` entry, and the row in `test_charter_activation_api_reexport.py`) so `tests/architectural/test_no_dead_symbols.py` stays green. Grep `src/` first to confirm no other caller.

### Subtask T006 – Text renderers

- `src/charter/activation/compact.py:310-339`: `_resolve_governance_summary` keeps a `list[str]` of display lines; extend with `d.message for d in resolution.diagnostics`. The `governance unresolved/unavailable (...)` lines stay as they are.
- `src/runtime/next/prompt_builder.py:552-553`: join `d.message`.
- Assert in existing tests (`tests/charter/test_compact.py:156-167`, `tests/next/test_prompt_builder_unit.py:552-560`) that the rendered text is unchanged.

### Subtask T007 – Existing assertions and goldens

- Run: `uv run --frozen pytest tests/charter tests/runtime tests/next tests/specify_cli/cli/commands/test_charter_org_directive_identity.py tests/acceptance -q -x -p no:cacheprovider` (narrow further if slow) and fix every failure caused by the shape change:
  - assertions like `TEMPLATE.format(...) in resolution.diagnostics` → compare against `[d.message for d in ...]` or assert the typed entry;
  - JSON assertions `... in data["diagnostics"]` → match `{"code": ..., "message": ...}`;
  - goldens: `tests/charter/fixtures/default_in_force_snapshot.json`, `synthesized_in_force_snapshot.json` (produced via `asdict(resolution)`, so entries become `{code, message}` objects; regenerate with the regeneration path the test documents, never hand-edit content beyond the shape), and `tests/acceptance/fixtures/unmigrated_context_golden.json` (`:19`).
- Every changed test must still fail if the product regressed to strings (no vacuous loosening).
- If a failing test lies outside `owned_files`, fix it anyway with a one-line rationale in `add-history` (ownership-map leeway).

### Subtask T008 – Docs and changelog

- `docs/api/charter-commands.md:344-348`: replace "list of strings" with the `{code, message}` shape, a table of the five codes with when each fires, "match on `code`; `message` may be reworded", schema 1.4.0.
- Same file, `## spec-kitty charter interview` section: document `--json` key `narrowed`: object mapping an activation key (e.g. `activated_directives`) to the list of ids that stopped being in force because of `--narrow`-style promotion; `{}` when nothing was narrowed. Verify semantics against `src/specify_cli/cli/commands/charter/interview.py:140-220,464-512` (read the flag name from the code; do not guess).
- `docs/changelog/CHANGELOG.md:78` (rc8 section, #6407 entry): say the `diagnostics` list holds `{code, message}` objects with the five codes; add `#6460` to the issue refs. No new duplicate entry.
- Run `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q` (prose touched).

## Test Strategy

- Red-first (T001) then green. Blast radius per CLAUDE.md §Test policy: the new test file; `tests/charter/` and `tests/charter_offering/` are owning subsystems for charter changes → run `tests/charter/` (fast tier) and the directly touched tests in `tests/runtime/`, `tests/next/`, `tests/specify_cli/cli/commands/test_charter_*.py`, `tests/acceptance` goldens; architectural gate files: `test_charter_activation_api_reexport.py`, `test_no_dead_symbols.py`, `test_layer_rules.py`, `test_no_legacy_terminology.py`. Plus `make test-fast`. No whole `tests/architectural/` sweep.
- Static: `uv run --frozen ruff check <files>`, `uv run --frozen ruff format --check --force-exclude <files>`, `uv run --frozen mypy --strict <touched src files>`.
- Record commands and counts with `add-history`.

## Risks & Mitigations

- Hidden consumers of `resolution.diagnostics` as strings: `grep -rn "\.diagnostics" src` (filter to GovernanceResolution) before finishing.
- Golden churn: only shape changes; content identical.
- `asdict` of a StrEnum keeps the enum instance; check JSON dumping in the snapshot tests serialises it as the plain string.

## Review Guidance

- Verify red→green: T001 commit red on the planning base, green at the WP tip.
- Verify no prefix/wording-based classification remains (SC-003) and text surfaces unchanged (SC-004).
- Verify schema stays 1.4.0, docs list exactly five codes, mypy --strict clean, no new suppressions.

## Progress & Status

Use `spec-kitty agent tasks add-history`, `move-task`, `status`; never edit history here.
