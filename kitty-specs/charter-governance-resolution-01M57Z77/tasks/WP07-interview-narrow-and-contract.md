---
work_package_id: WP07
title: Interview --narrow-activation, charter command contract text and CLI reference docs
dependencies:
- WP06
requirement_refs:
- FR-013
- FR-014
- C-003
planning_base_branch: issue-6404-charter-governance-resolution-work
merge_target_branch: issue-6404-charter-governance-resolution-work
branch_strategy: Planning artifacts for this mission were generated on issue-6404-charter-governance-resolution-work. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6404-charter-governance-resolution-work unless the human explicitly redirects the landing branch.
subtasks:
- T031
- T032
- T033
- T034
phase: Phase 3 - Delivery and activation
history:
- at: '2026-10-18T17:40:00Z'
  actor: claude-code/opus
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/interview.py
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/cli/commands/charter/interview.py
- packs/built-in/missions/mission-steps/software-dev/charter/prompt.md
- docs/api/cli-commands.md
- docs/api/charter-commands.md
- tests/specify_cli/cli/commands/test_charter_interview_promotion.py
- tests/specify_cli/cli/commands/test_charter_interview_org_prefill.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Interview --narrow-activation, charter command contract text and CLI reference docs

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
- **Tests**: run the WP's own test files plus the owning subsystem directory (`tests/charter/` and, for `src/charter/offering/**`, `tests/charter_offering/`). Subsystem sweeps are large (`tests/charter/` ≈ 3,900 tests): always run them with `-n auto --dist loadfile` (pytest-xdist is installed), never `--dist load`. Do not run `make test-full` or the whole `tests/architectural/` directory; run only the named gate files.
- **Terminology**: "Mission", never the retired term. Run `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q` when touching prose or `src/charter/offering/`.
- **Commits**: conventional types (`fix`, `feat`, `test`, `refactor`, `docs`); end every commit message with the session attribution lines given to you.
- Diagnostic wording for unknown selected ids is fixed Mission-wide (WP02 defines the constant `UNKNOWN_SELECTION_DIAGNOSTIC` in `resolver.py`): `"Unknown selected {kind} '{token}' dropped: not found in built-in, org packs (charter_packs.org.packs) or .kittify/charter-packs/; see 'spec-kitty charter list'."`
- Stay inside `owned_files`; a small out-of-map edit is acceptable only with a one-line rationale in the commit message and `add-history` note.

## Objectives & Success Criteria

`charter interview --narrow-activation` promotes the selected directives, tactics and paradigms as selection plus org-required ids (replacing the key) and reports what stops being in force, including in JSON; the `/spec-kitty.charter` command contract explains how selections and activation lists behave and how to keep activation narrow (#6408).

Done when:
- `charter interview --defaults --narrow-activation --selected-directives DIRECTIVE_001 --json` → `activated_directives` holds only `001-architectural-integrity-standard` plus org-required directives; JSON `narrowed` lists the dropped directive ids;
- without `--narrow-activation` the result is identical to today (assert against the effective-set count computed on the same fixture, never a hard-coded 38) and JSON `narrowed` is `{}`;
- `--defaults` fills `selected_paradigms` from the profile defaults, so `--narrow-activation` also narrows paradigms to those defaults — intended; pinned by a test and shown in the output;
- CLI reference docs regenerated: `docs/api/cli-commands.md` via `scripts/docs/build_cli_reference.py` (covers WP06's `--only` and this WP's flag; `scripts/docs/check_cli_reference_freshness.py` clean) and the interview flag table in `docs/api/charter-commands.md:64-73` gains `--narrow-activation`;
- a kind with an empty selection is not narrowed;
- the contract text at `packs/built-in/missions/mission-steps/software-dev/charter/prompt.md` (:83 and :305-307) explains: selections are additive; the first explicit activation list is frozen; use `charter activate <kind> <id> --only`, `charter interview --narrow-activation` or `charter activate --preset minimal` to stay narrow.

Requirement refs: FR-013, FR-014, C-003.

## Context & Constraints

- Depends on WP06 (`promote_activations(narrow_bases=...)`, `org_required_stems`).
- `src/specify_cli/cli/commands/charter/interview.py`: `_promote_interview_selections` :44-130 (directives/tactics/paradigms :78-82; promoted only when a selection resolves :112-113; seeds absent keys :120-127 via `promote_activations(..., effective_sets=resolve_effective_sets(repo_root, absent))`); `interview()` :134 (has `# noqa: C901` — do not add complexity there, add a helper); `apply_org_charter_to_interview` (:207) runs first and already writes org-required ids, so narrow mode must replace, not append; JSON payload :338-355 (keys `result, success, interview_path, mission, profile, selected_paradigms, selected_directives, available_tools, org_prefill_messages, org_prefill_warning, promotion_warnings`).
- `tests/architectural/test_json_contract_enumeration.py` only exercises the error envelope — no change needed; `promotion_warnings` also referenced in `tests/specify_cli/cli/commands/test_charter_ambiguous_directives.py`.
- Contract file: the vendor clean-tree digest ignores `missions/` (verified), but run `spec-kitty charter pack regenerate-graph --check` and `tests/architectural/test_doctrine_regenerate_graph_roundtrip.py`; gates reading the prompt: `tests/charter_offering/test_builtin_cli_command_references.py` (every `spec-kitty …` command path in a code span must resolve), `tests/charter_offering/missions/test_prompt_emptiness.py`, `test_software_dev_prompt_walk.py`, `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py:520`. Source upstream is `spec-kitty-open-packs` — note a follow-up to port the edit there in the PR (not in this WP).
- C-003: this prompt is the only `packs/built-in/` file this Mission edits; nothing in `packs/internal/`.

## Subtasks & Detailed Guidance

### Subtask T031 – Red tests

- `tests/specify_cli/cli/commands/test_charter_interview_promotion.py`: narrow vs default on the same fixture (exact list + `narrowed` payload); empty selection kind untouched; org-required stays (use the WP02 fixture org pack builder or an org-charter requiring a directive) — extend `test_charter_interview_org_prefill.py` for the org case.
Commit red: `test: red repro for #6408 interview narrow activation`.

### Subtask T032 – `--narrow-activation`

- Add the option to `interview()`; pass `narrow: bool` into `_promote_interview_selections` (extract a `_narrow_bases(...)` helper: per selected kind, selection stems ∪ `org_required_stems(repo_root, plural, warnings)`); call `promote_activations(..., narrow_bases=...)`; return `(warnings, dropped)`; JSON gains `"narrowed": {key: [dropped]}` (always present). Non-JSON output prints "No longer in force (N) for <key>: ..." lines.

### Subtask T033 – Contract text

- Rewrite `prompt.md:83` and `:305-307` (and any adjacent sentence they depend on) to state the additive/frozen semantics and the three narrow paths with exact commands. Keep wording concise; Mission terminology.

### Subtask T034 – Gates

- Run `spec-kitty charter pack regenerate-graph --check`, `spec-kitty charter pack vendor --check` (if available), and the prompt gates listed above.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/test_charter_interview_promotion.py tests/specify_cli/cli/commands/test_charter_interview_org_prefill.py tests/specify_cli/cli/commands/test_charter_ambiguous_directives.py tests/charter_offering/test_builtin_cli_command_references.py tests/charter_offering/missions/ tests/architectural/test_doctrine_regenerate_graph_roundtrip.py tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/charter/ -q -n auto --dist loadfile
uv run --frozen mypy --strict src/specify_cli/cli/commands/charter/interview.py
```

## Risks & Mitigations

- Interview order (org prefill first) → narrow replaces; tested with an org-required id.
- Contract text referencing a non-existent command path fails the CLI-reference gate → only real commands.

## Review Guidance

- Default interview output byte-identical except the new `narrowed: {}` key.
- Contract text matches shipped behaviour.
