---
work_package_id: WP04
title: Compile wiring - from-interview re-derives languages; tool diagnostics
dependencies:
- WP03
requirement_refs:
- FR-011
- FR-012
- FR-013
- NFR-004
planning_base_branch: issue-5283-tech-agnostic-language-fallback
merge_target_branch: issue-5283-tech-agnostic-language-fallback
branch_strategy: Planning artifacts for this mission were generated on issue-5283-tech-agnostic-language-fallback. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5283-tech-agnostic-language-fallback unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-tech-agnostic-language-fallback-01M3NP53
base_commit: a2060146a75be1a4f614a859d5a86433924f4a3d
created_at: '2026-09-29T06:13:07.509757+00:00'
subtasks:
- T021
- T022
- T023
- T024
- T025
phase: Phase 4 - Charter compile (lane B)
history:
- at: '2026-09-29T06:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/charter/activation/compiler.py
create_intent:
- tests/charter/test_regenerate_rederives_languages.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/charter/activation/compiler.py
- src/charter/activation/doctrine_service_builder.py
- src/charter/activation/charter_yaml_io.py
- src/specify_cli/cli/commands/charter/generate.py
- tests/charter/test_regenerate_rederives_languages.py
- tests/charter/test_compiler.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP04 – Compile wiring - from-interview re-derives languages; tool diagnostics

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill (canonical: `spk-doctrine-profile-load`) to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Reviewers load `reviewer-renata` (reviewer ≠ implementer).

---

## ⛔ HARD RULE — NO_FULL_HEAVY_SUITES_IN_MISSION (verbatim, binding for implementer AND reviewer)

During implement and every WP review, you must NEVER run full or heavy suites:
- no whole `tests/architectural/`, no e2e or full-integration suites, no performance/stress/timing suites;
- no `make test-full`, no whole-repo pytest.

Per WP, run only:
- the test files covering the files the WP touches;
- the owning module's fast tier;
- the specific NAMED architectural gate files the change implicates.

Leave broad sweeps to the END of the mission (closeout) or to CI.

---

## ⚠️ Post-tasks squad corrections (BINDING — supersede any conflicting guidance further below)

- **Reference ids carry a kind prefix (BLOCKER B4):** e.g. `STYLEGUIDE:python-conventions`, `TOOLGUIDE:python-review-checks`, `AGENT_PROFILE:python-pedro`. Case 5 must read `charter.yaml` (not "or the rendered list") and assert `not any(i.split(":",1)[-1].startswith("python-") for i in ids)`; the Python positive control expects `STYLEGUIDE:python-conventions`.
- Half-by-half ENFORCED by the reviewer: revert T023 only → case 1 red; revert T024 only → case 5 red. If case 5 stays green with T024 reverted, T024 is dead or the test is vacuous — reject.
- Case 7 (tools): use the default languages answer and assert `languages` is **absent** (not zig, not `[unknown]`). Add an "N/A" placeholder case (→ absent) and a "Python and Zig" case (→ `["python"]`) at CLI level (US2 AS3a/AS3b).
- `_sanitize_catalog_selection` (`compiler.py:945`) has a single caller (`available_tools`, `:442`) — the per-label parameter is still the cleanest seam but "other callers unchanged" is moot; alternatively change the message directly with a clear docstring.
- The mypy fix is in `charter_yaml_io.py::_activation_keys()` (`:468`). `generate.py` helper is defined at `:28`. The 4908 test invokes activate as `charter_app ["activate","--repo-root", …]` (`:100-105`); there is no pack invocation there — find `pack.py`'s CLI entry for the pack-preserve case or cover it at the `compile_charter` call level with `rederive_languages` defaulting False.
- Consider keying the flag on the effective interview source (`interview_source == "interview"`) rather than the raw `from_interview` flag if `generate` falls back to defaults when `answers.yaml` is missing — document the choice.
- **Red→green proof (reviewer, mandatory):** re-run the new tests after `git checkout <base> -- src/charter/activation/compiler.py src/charter/activation/doctrine_service_builder.py src/specify_cli/cli/commands/charter/generate.py` (then `git checkout HEAD -- src/charter/activation/compiler.py src/charter/activation/doctrine_service_builder.py src/specify_cli/cli/commands/charter/generate.py`): they must be RED for the intended reason (an assertion, never an ImportError/collection error) and GREEN again at the tip. Base = the **WP03 tip** (against the planning base the tests are trivially red because WP03 is missing).
- **Red-first labelling:** in the red-first commit, every test is labelled in its docstring either `RED (pins the fix)` or `GREEN control (pins unchanged behaviour)`. Controls may pass on the base; only RED tests must fail. New names that do not exist on the base are imported function-locally (or referenced as literals) so the base can still collect the module.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks and use language identifiers in code blocks.

---

## Objectives & Success Criteria

Closes #4614 end-to-end and FR-011:

- `spec-kitty charter generate --from-interview` (the DEFAULT for `charter generate`) derives `catalog.languages` from the current interview instead of reading back the previously compiled list: from a stale `catalog.languages: [python]` seed, a Zig answer → `[unknown]`; a Rust answer → `[rust]`; the shipped default / a placeholder answer → field ABSENT (not `[python]`, not `[unknown]`).
- The same regenerate resolves its doctrine references under the re-derived languages (split-brain fix): after the Zig regenerate, `charter.yaml` contains no `python-*` reference ids.
- `charter generate --no-from-interview`, `charter activate …` and pack recompiles keep the recorded `catalog.languages` (compiled-first, unchanged).
- The unregistered-tool diagnostic for `available_tools` names the entry as a tool id, e.g. `available_tools: 'zig' is not a registered tool id; ignored (tool ids are validated separately from project languages)`; other labels keep their existing `Ignored unknown <label>: …` message; the registry is NOT widened.
- Campsite: fix the pre-existing mypy `no-any-return` at `charter_yaml_io.py:468` (without `# type: ignore`).

## Context & Constraints

- Charter (binding): `.kittify/charter/charter.md` — ATDD/red-first (C-011): the failing test is committed as its own commit BEFORE the fix; reviewer verifies red on the planning base and green at the WP tip.
- Mission docs: `kitty-specs/tech-agnostic-language-fallback-01M3NP53/{spec.md,plan.md,research.md,data-model.md,contracts/cli-outputs.md,quickstart.md}`; tracer files under `traces/` — append a dated 1–3 sentence entry for any tooling friction, approach change, or design decision you make.
- Operator policy (#2330 decision): Spec Kitty doctrine is tech-agnostic; default implementation profile `implementer-ivan`; unknown languages → advise extending the local charter; NEVER fix by adding languages one by one; NEVER suggest Python files/layouts/tools to a non-Python project.
- Sibling-owned, do NOT edit: `src/specify_cli/consolidation/**`, `tests/integration/**`, golden/snapshot fixtures (`tests/specify_cli/skills/__snapshots__/**`, `tests/cli/__snapshots__/**`, `tests/consolidation/merge_driver_goldens/**`, `tests/contract/snapshots/**`), doctor/decision surfaces, `review/arbiter.py`, move-task override, built-in software-dev guidelines (#5202).
- Code quality: `ruff check`, `ruff format --check`, `mypy` (strict) clean on touched files; cyclomatic complexity ≤15; no new `# noqa`/`# type: ignore`; every new branch/helper gets a focused test in the same commit; modules under `src/charter/**` keep `__all__` and every exported name needs a caller in `src/` (dead-symbol gate).
- Terminology canon: Mission, never "feature", in any new prose/identifier.
- In a lane worktree always run tools via `uv run --frozen ...` or the worktree's own interpreter so the LANE `src/` is imported (bare `python`/`pytest` may import the primary checkout).

### Grounded seams

- `compiler.py:376-385` `compile_charter(*, mission, interview, template_set=None, doctrine_catalog=None, doctrine_service=None, repo_root=None, pack_context=None)`; languages at `:424` `infer_repo_languages(repo_root, interview=interview)`; stamp at `~:688` (None → absent field, list → copied).
- Tool validation: `compiler.py:442-447` `_sanitize_catalog_selection(values=interview.available_tools, allowed=set(DEFAULT_TOOL_REGISTRY), label="available_tools", ...)`; message at `:969` `f"Ignored unknown {label}: ..."` (shared by other labels). `DEFAULT_TOOL_REGISTRY` in `resolver.py:96`.
- Callers of `compile_charter`: `specify_cli/cli/commands/charter/generate.py:489` (the only one that should pass `rederive_languages=from_interview`), `activate.py:566`, `pack.py:216` (both keep the default False — do not edit them).
- `generate.py:352-363`: with `--no-from-interview` a shipped `default_interview` is passed (not None). `generate.py:377`: `--from-interview/--no-from-interview` default True. `generate.py:29` `_build_doctrine_service_with_org_layer(repo_root)` → `charter.activation.doctrine_service_builder.build_activation_aware_doctrine_service` (`:244`) → `_build_doctrine_service` (`:92`) → `infer_repo_languages(repo_root)` at `:134` via the patch seam `charter.activation.context`.
- Test helpers: `tests/charter/test_active_languages_idempotency.py:70` `_invoke_generate` (CLI) and the seeded-`charter.yaml` pattern at `:196`; `tests/agent/cli/commands/test_charter_cli.py:225` (generate) — do NOT edit that file (owned by nobody here; WP05 uses its own module too).

## Branch Strategy

- **Strategy**: lanes (no coordination branch)
- **Planning base branch**: issue-5283-tech-agnostic-language-fallback
- **Merge target branch**: issue-5283-tech-agnostic-language-fallback

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; prepare yours with `spec-kitty agent action implement WP04 --agent claude`.

## Subtasks & Detailed Guidance

### Subtask T021 – Campsite (own commit FIRST)

- Fix `charter_yaml_io.py:468` `Returning Any from function declared to return "tuple[str, ...]"` by narrowing/validating the value (e.g. `tuple(str(x) for x in value)` after an `isinstance` check) — behaviour-preserving; add/extend a focused test if the branch is untested (find the covering test via `grep -rn "<function name>" tests/`). Commit `refactor(charter): campsite charter_yaml_io no-any-return`.

### Subtask T022 – Red-first CLI tests (own commit, RED)

New module `tests/charter/test_regenerate_rederives_languages.py`, driving the real `charter generate` typer command on a tmp project (`spec-kitty init`-equivalent fixture used by `test_active_languages_idempotency.py`):
1. Seed `.kittify/charter/charter.yaml` with `catalog.languages: [python]` (use the existing seeding helper pattern), write `answers.yaml` with the Zig answer, run `generate --from-interview --force` → `catalog.languages == ["unknown"]`.
2. Same seed + "Rust with cargo" → `["rust"]`.
3. Same seed + default answers (`interview --defaults`-equivalent) → `languages` key absent/None.
4. Same seed + Zig answer + `--no-from-interview` → still `["python"]`.
5. Reference parity: after (1), no `catalog.references[*].id` (or rendered reference list) starts with `python-`; positive control: a Python answer regenerate DOES include `python-conventions` (or whichever python-scoped id the shipped packs provide — discover it, don't guess).
6. Activate/pack preserve: seed `[python]`, run the activate path used by `tests/specify_cli/cli/commands/charter/test_recompile_preserves_mission_4908.py` (read it for the invocation) → `catalog.languages` still `["python"]`.
7. Tool message: `available_tools: [git, spec-kitty, zig]` → diagnostics contain `available_tools: 'zig' is not a registered tool id` and do NOT contain `Ignored unknown available_tools`; `zig` not in `catalog.languages`.
- Must fail now (except 4 and 6, which are positive controls and pass today — keep them in the same commit, clearly labelled). Commit `test(charter): red-first regenerate re-derives languages (#4614)`.

### Subtask T023 – compile_charter kwarg

- Add keyword-only `rederive_languages: bool = False`; pass `prefer_interview=rederive_languages` to the `:424` `infer_repo_languages` call. Update the docstring (why only generate sets it).

### Subtask T024 – Doctrine-service builder kwargs (split-brain fix)

- `build_activation_aware_doctrine_service(repo_root, *, agent_profile_overlay_dir=None, interview=None, prefer_interview=False)` and the internal `_build_activation_aware_doctrine_service` / `_build_doctrine_service` forward `interview`/`prefer_interview` to the ONE `infer_repo_languages` call (keep the patch-seam import). Only pass the kwargs through when set, preserving byte-identical kwargs for existing callers/stubs (follow the file's existing "only pass when set" pattern).
- `generate.py`: `_build_doctrine_service_with_org_layer(repo_root, *, interview=None, prefer_interview=False)`; in the generate flow pass `interview=interview_data, prefer_interview=from_interview` to it and `rederive_languages=from_interview` to `compile_charter`.
- Do not change `specify_cli/doctrine_service_factory.py` (thin re-export) unless mypy requires the signature to match; if so, forward the kwargs there too with a one-line rationale in the Activity Log.

### Subtask T025 – available_tools message

- Give `_sanitize_catalog_selection` an optional `missing_message: Callable[[list[str]], str] | None = None`; the `available_tools` call supplies the new wording (one message per call listing all missing ids, e.g. `available_tools: 'a', 'b' are not registered tool ids; ignored (tool ids are validated separately from project languages)` — pick one exact phrasing and pin it in the test); other callers unchanged. Unit-test the helper in `tests/charter/test_compiler.py`.

## Test Strategy

- `uv run --frozen pytest tests/charter/test_regenerate_rederives_languages.py tests/charter/test_compiler.py tests/charter/test_active_languages_idempotency.py tests/charter/test_doctrine_service_builder_unification.py -q`
- Neighbours (run these files only): `tests/specify_cli/cli/commands/charter/test_recompile_preserves_mission_4908.py`, `tests/agent/cli/commands/test_charter_cli.py`, any test importing `build_activation_aware_doctrine_service` (`grep -rl build_activation_aware_doctrine_service tests/ --include=*.py`).
- Named arch gates: `tests/architectural/test_layer_rules.py`.
- ruff check/format + mypy on the four touched src files.

## Risks & Mitigations

- Forgetting the builder kwargs leaves references resolved under the stale language → T022 case 5.
- Passing the kwargs from activate/pack would wipe recorded languages → case 6.

## Definition of Done

- [ ] Campsite commit, red commit, then fixes.
- [ ] T022 cases 1–7 green; activate/pack/no-from-interview preserve.
- [ ] mypy clean on `charter_yaml_io.py` (no-any-return gone) and all touched files; ruff/format clean; complexity ≤15.

## Review Guidance

Verify only `generate` passes the new flags; verify reference parity case; verify the tool message is label-specific; verify red→green. Targeted commands only (HARD RULE).

## Activity Log

> Append entries at the END, oldest first: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>` (UTC now: `date -u "+%Y-%m-%dT%H:%M:%SZ"`).

- 2026-09-29T06:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status; record subtasks with `spec-kitty agent tasks mark-status <Txxx> --status done`.
