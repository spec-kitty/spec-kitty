---
work_package_id: WP01
title: Research command resolves shipped templates canonically
dependencies: []
requirement_refs:
- FR-005
- FR-006
- FR-007
planning_base_branch: claude/project-thread-silj7c
merge_target_branch: claude/project-thread-silj7c
branch_strategy: Planning artifacts for this mission were generated on claude/project-thread-silj7c. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/project-thread-silj7c unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-truthful-discovery-step-01M3KABP
base_commit: f338859f0a6e1cd2647979a2cd6d29efb3fa9206
created_at: '2026-09-28T06:28:48.992595+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Implementation
history:
- at: '2026-09-28T06:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/research.py
create_intent:
- tests/specify_cli/cli/commands/test_research_templates.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/research.py
- src/specify_cli/core/project_resolver.py
- src/specify_cli/core/__init__.py
- tests/specify_cli/cli/commands/test_research_preservation.py
- tests/specify_cli/cli/commands/test_research_templates.py
- tests/agent/test_commands.py
- tests/research/**
- tests/runtime/test_project_resolver.py
- tests/runtime/test_global_runtime_convergence_unit.py
- tests/specify_cli/cli/commands/test_research_read_surface.py
- tests/architectural/test_overwrite_ownership_routing.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Research command resolves shipped templates canonically

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

- For a research mission with a filled `plan.md`, `spec-kitty research --mission <handle>` creates `research.md`, `data-model.md`, `research/evidence-log.csv`, `research/source-register.csv`, each non-empty and equal to the resolved template (SC-002; today only the 2 CSVs, and only when `~/.kittify` is populated).
- For a software-dev mission: 0 files created, 0 overwritten, truthful "no template" report (SC-003, #4926).
- Template lookup goes through `specify_cli.runtime.resolver.resolve_template` (6-tier: `.kittify/overrides/templates/`, legacy `.kittify/templates/`, org packs, `~/.kittify/missions/<type>/templates/`, `~/.kittify/templates/`, package default). The legacy `specify_cli.core.project_resolver.resolve_template_path` is retired (its only caller is `research.py:76`).

## Context & Constraints

- Spec: `kitty-specs/truthful-discovery-step-01M3KABP/spec.md` (FR-005..007, NFR-001..003). Research: `research.md` Decision 2 (tier change is accepted and goes in the changelog, which WP02 writes; note it in the Activity Log for WP02).
- `research.py`: import at :20, `_write_research_asset` resolves via `resolve_template_path(project_root, mission_type, template_rel)` at :76; asset calls at :264-265 ask for `research.md`/`data-model.md`; the pack ships `packs/built-in/missions/research/templates/research-template.md` and `data-model-template.md`; CSVs at `templates/research/*.csv`.
- `guard_destructive_overwrite` (#4926, ~:80) and the "refuse to fabricate empty files" outcome must stay behaviourally identical.
- `resolve_template` raises `FileNotFoundError`; map it to the existing no-template outcome. Keep `mission=<mission_type>` keyed on the meta.json key (`software-dev`, `research`), not the display label.
- Removing `resolve_template_path` from `specify_cli/core/__init__.py` `__all__`: main is on an untagged rc (4.0.0rc5) so no version bump (C-003).

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first regression test
- Create `tests/specify_cli/cli/commands/test_research_templates.py` with a `@pytest.mark.regression` test pinned to #5254: temp git repo with a research-type mission (meta.json `mission_type: research`) and a `plan.md` that passes `validate_plan_filled(strict=True)` (see how `test_research_preservation.py` builds fixtures), isolated HOME (no `~/.kittify` templates), run the CLI command via typer `CliRunner`, assert `research.md` and `data-model.md` exist, non-empty, equal to the shipped template content. Commit it RED and record the failing output.

### Subtask T002 – Canonical resolver + destination→template table
- Replace the legacy call with `resolve_template(name, project_root, mission=mission_type)`; keep one module-level mapping `{Path("research.md"): "research-template.md", Path("data-model.md"): "data-model-template.md", Path("research/evidence-log.csv"): "research/evidence-log.csv", Path("research/source-register.csv"): "research/source-register.csv"}` used by both the md and CSV loops. Keep functions ≤ 15 complexity; extract a tiny `_resolve_research_template(...) -> Path | None` helper and unit-test it directly (found / not found).

### Subtask T003 – Retire the legacy resolver
- Delete `resolve_template_path` from `core/project_resolver.py` and its export in `core/__init__.py` (import + `__all__`). `git grep resolve_template_path` must only show unrelated `_resolve_template_path` helpers afterwards. Check `tests/architectural/` for any ledger listing it and update.

### Subtask T004 – Update tests pinning old behaviour
- `tests/agent/test_commands.py` (~:182, ~:217 monkeypatches `research_module.resolve_template_path`): repoint to the new seam / real resolver; keep asserting software-dev creates nothing.
- `tests/specify_cli/cli/commands/test_research_preservation.py` (~:36-40, :196-237 seed the legacy tier and assert "no template for ANY mission type"): update to the canonical tiers; justify each assertion change in the Activity Log (NFR-001).
- Run `tests/research/` too.

### Subtask T005 – #4926 guards, same-fixture controls
- In the new test module, on ONE shared fixture helper: positive control (research mission → created, non-empty) and negative controls (software-dev → nothing created; pre-existing authored `research.md` without `--force` → byte-identical after run). Then convert T001 to a focused test (drop the `regression` marker).

## Test Strategy

```
pytest tests/specify_cli/cli/commands/test_research_templates.py tests/specify_cli/cli/commands/test_research_preservation.py tests/specify_cli/cli/commands/test_research_read_surface.py tests/agent/test_commands.py tests/research/ -q
pytest tests/architectural/test_overwrite_ownership_routing.py tests/architectural/test_mutation_ownership_routing.py -q
make test-fast
ruff check src tests && ruff format --check src tests && mypy src/specify_cli/cli/commands/research.py src/specify_cli/core/
```

## Risks & Mitigations

- Tier change drops `.kittify/missions/<type>/templates/` and project-root `templates/`: accepted (research.md Decision 2); tell WP02 for the changelog.
- Home-dir leakage in tests: isolate HOME/`SPEC_KITTY_HOME` per existing fixtures so the package-default tier is what's exercised.

## Review Guidance

- Verify the half-by-half proof: reverting only the template-name table, or only the resolver switch, turns the positive-control test red (acceptance-criteria-non-vacuity).
- Verify `guard_destructive_overwrite` untouched and the negative controls share the positive control's fixture.

## Post-tasks squad folds (binding)

- **T003/T004 blast radius:** `tests/runtime/test_project_resolver.py` (:9-59) and `tests/runtime/test_global_runtime_convergence_unit.py` (:513-627) import `resolve_template_path` — delete or port those tests to `resolve_template` in the same commit as the retirement. `tests/specify_cli/cli/commands/test_research_read_surface.py:105-108` seeds `.kittify/templates/research.md` / `data-model.md` and asserts creation at :276-277 — re-seed with `research-template.md` / `data-model-template.md`.
- **Tier list correction:** `resolve_template` also has the mission-scoped override tier `.kittify/overrides/missions/<m>/templates/`; it returns a `ResolutionResult` — use `.path`.
- **Extra tests:** (a) an override at `.kittify/overrides/templates/research-template.md` wins over the pack default; (b) a typeless mission (`get_mission_type` returns `''`) short-circuits to "no template" without probing `missions//templates`.
- **Architectural pin:** `tests/architectural/test_overwrite_ownership_routing.py:284-295` allowlists qualname `_write_research_asset` and the token `shutil.copy2(template_path, dest_path)` — keep both, or update the allowlist deliberately and run that test.

## Branch Strategy

- Planning base branch and merge target: `claude/project-thread-silj7c` (the PR head branch; the PR targets `main`).
- Execution worktrees are allocated per computed lane from `lanes.json`. Use `spec-kitty implement WP01` and work only in the resolved workspace.

## Standing rules

- Charter first: read `.kittify/charter/charter.md`; load `spec-kitty charter context --action implement`.
- Red-first (ADR 2026-07-17-1): the issue-pinned `@pytest.mark.regression` test is committed RED before the fix (show the failing run in the Activity Log), then converted to a focused unit/integration test (no `regression` marker left) once green.
- New code: ruff, `ruff format --check`, mypy clean; no new suppressions; complexity ≤ 15; every new branch tested in the same commit.
- Never edit generated agent copies (`.claude/`, `.agents/`, ...). Never bump the version. Never push to `main`.
- Record exact test commands and pass/fail counts in the Activity Log.

## Activity Log

- 2026-09-28T06:40:00Z – system – Prompt created.
