---
work_package_id: WP02
title: Truthful discovery prompt, aligned guidance, e2e contract test
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-008
- FR-012
- FR-013
planning_base_branch: claude/project-thread-silj7c
merge_target_branch: claude/project-thread-silj7c
branch_strategy: Planning artifacts for this mission were generated on claude/project-thread-silj7c. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/project-thread-silj7c unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-truthful-discovery-step-01M3KABP
base_commit: f338859f0a6e1cd2647979a2cd6d29efb3fa9206
created_at: '2026-09-28T07:14:19.354718+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - Implementation
history:
- at: '2026-09-28T06:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: packs/built-in/missions/mission-steps/software-dev/research/
create_intent:
- tests/next/test_discovery_step_contract.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- packs/built-in/missions/mission-steps/software-dev/research/**
- packs/built-in/missions/mission-steps/software-dev/plan/prompt.md
- src/charter/offering/skills/spk-mission-research/**
- src/charter/offering/skills/spk-start-command-map/references/command-map.md
- docs/api/slash-commands.md
- docs/changelog/CHANGELOG.md
- tests/next/test_discovery_step_contract.py
- tests/next/test_prompt_file_invariant.py
- packs/built-in/pack-manifest.yaml
- tests/architectural/_builtin_pack_provenance_baseline.yaml
- docs/context/spec-driven.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Truthful discovery prompt, aligned guidance, e2e contract test

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

- An agent following only the prompt `spec-kitty next` issues for the software-dev `discovery` step (source: `packs/built-in/missions/mission-steps/software-dev/research/prompt.md`, aliased discovery→research at `src/runtime/next/decision.py:465`) meets every instruction before any spec or plan exists (SC-001).
- The same prompt, rendered as `/spec-kitty.research` for every mission type (`src/specify_cli/skills/command_installer.py:79-86`), states when `spec-kitty research --mission <handle>` applies (mission types that ship research templates, e.g. research, after their plan is filled) and that it creates nothing for types without templates (FR-012).
- All agent-facing research guidance agrees (FR-013). The plan prompt says to extend an existing `research.md` (FR-004).

## Context & Constraints

- Decision DM-01M3KAD2G6HZMB6TF4W049WCB9: no software-dev research scaffold; the plan step owns `research.md`/`data-model.md` structure (C-001).
- Edit sources only (C-002): the prompt under `packs/built-in/missions/mission-steps/`, `src/charter/offering/skills/spk-mission-research/SKILL.md` (:14 says "only after plan"), `src/charter/offering/skills/spk-start-command-map/references/command-map.md` (:6 says "Research before specification"), `docs/api/slash-commands.md` (:331-345, syntax lacks `--mission`). Never the generated `.claude/`, `.agents/` copies.
- Current prompt defects to remove: "Location Pre-flight Check" that STOPs on `main` (planning runs on the target branch, which may be `main`); "What This Command Creates" (false for software-dev); "Before this: /spec-kitty.plan calls this as Phase 0" (false; the plan prompt never calls it); bare `spec-kitty research` without `--mission`; success criteria requiring CSVs and data-model.md the agent was told a no-op creates.
- Discovery requires no artifacts (`packs/built-in/missions/software-dev/expected-artifacts.yaml` ~:25-27; research.md/data-model.md optional ~:95-110). Discovery findings go into `kitty-specs/<mission>/research.md` (create or extend; never truncate existing content). Name the step `discovery` wherever it could be confused with specify's discovery interview.
- WP01 result: the research command now scaffolds all four artifacts for research-type missions via the canonical resolver; software-dev still gets none.

## Subtasks & Detailed Guidance

### Subtask T006 – Red-first end-to-end contract test
- New `tests/next/test_discovery_step_contract.py`, `@pytest.mark.regression` pinned to #5254 first. Pattern: `tests/next/test_next_command_integration.py` (~:293) drives `next` in a temp git repo. Steps: create a fresh software-dev mission (no `plan.md`), query `next` → preview/step `discovery`, obtain the issued prompt text (prompt_file), extract every `spec-kitty ...` invocation from fenced code blocks and inline code (substitute `<handle>`/`<mission_slug>` placeholders with the mission slug; skip explicit "do not run" examples), run each through the CLI and assert exit 0 and that every required option is present (e.g. `research` requires `--mission`). Then show `next` advances past `discovery` via the supported path (no `--result success` shortcut that bypasses guards; if advancing requires reporting the step done, do so only after the assertions, exactly as an agent would). Also assert every success-criteria bullet names only artifacts the prompt tells the agent to author. Commit RED against today's prompt, record the failure, then convert to a focused test (drop the marker) at the end. Keep runtime < 30 s (NFR-004).

### Subtask T007 – Rewrite the research prompt
- Keep frontmatter/description style. New structure: goal (capture discovery findings before specify); where (`kitty-specs/<mission_slug>/research.md`, create or extend; optional evidence under `kitty-specs/<mission_slug>/research/`); what to record (decisions, rationale, evidence, open questions feeding specify/plan); location check that does not stop on the primary branch (point at `spec-kitty agent mission branch-context --json` if any check is needed); a short "Research mission scaffolds" section: `spec-kitty research --mission <handle>` scaffolds from the mission type's templates after its plan is filled; for mission types without research templates (software-dev) it creates nothing and is not needed; truthful success criteria. Every command shown must include required options.

### Subtask T008 – Plan prompt Phase 0 wording
- In `plan/prompt.md` Phase 0 (~:320-353): "Consolidate findings in `research.md`: extend the file if discovery already created it; do not replace existing content." Add a text-invariant assertion (in `test_discovery_step_contract.py` or `test_prompt_file_invariant.py`).

### Subtask T009 – Align guidance surfaces
- Skill `spk-mission-research/SKILL.md`, command map row, `docs/api/slash-commands.md` `/spec-kitty.research` section: same ordering and invocation as the new prompt. If the doctrine manifest/graph hashes skills, run `spec-kitty doctrine regenerate-graph` and commit the regenerated files (do not hand-edit `pack-manifest.yaml`).

### Subtask T010 – Changelog and gates
- `docs/changelog/CHANGELOG.md` `[Unreleased]`: bold impact-first lead with `(#5254)`, then before → after, including WP01's resolver tier change (reads `.kittify/overrides/templates/`, org packs, package default; no longer reads `.kittify/missions/<type>/templates/` or project-root `templates/`). A separate short line for #5233 (tech debt, no behaviour change). No version bump.
- Run `pytest tests/architectural/test_no_legacy_terminology.py`, `tests/doctrine/test_builtin_cli_command_references.py`, the doctrine regen/manifest gates if the skill changed, and `scripts/docs/check_docs_freshness.py --ci` if the doc change needs it.

## Test Strategy

```
pytest tests/next/test_discovery_step_contract.py tests/next/test_prompt_file_invariant.py tests/next/test_next_command_integration.py -q
pytest tests/doctrine/test_builtin_cli_command_references.py tests/architectural/test_no_legacy_terminology.py -q
pytest tests/doctrine/ -q -k "manifest or regenerate or skill"   # if the skill changed
make test-fast
ruff check . && ruff format --check . && mypy <changed .py files>
```

## Risks & Mitigations

- Invocation extraction from prose is brittle: restrict to code spans starting with `spec-kitty `; unit-test the extractor with a positive and a negative sample.
- `next` state mutation in the test repo: use isolated temp repos and HOME.

## Review Guidance

- Read the rendered prompt as an agent on a fresh software-dev mission on `main`: is every instruction executable? Does `/spec-kitty.research` on a research mission still lead to the scaffold?
- Confirm the e2e test goes RED when the old prompt is restored (non-vacuity).

## Post-tasks squad folds (binding)

- **Provenance ratchet:** `tests/architectural/test_builtin_pack_provenance_ratchet.py` pins counts in `tests/architectural/_builtin_pack_provenance_baseline.yaml` (research prompt `repo_paths: 4`; plan prompt 6 / provenance 2). Counts may only go down: minimise `kitty-specs/` literals in the rewrite (prefer `<mission_dir>` phrasing) and never put `#NNNN` issue references in pack prose. Run the ratchet test.
- **Conditional invocation:** fence the `spec-kitty research --mission <handle>` instruction in a clearly marked "Research-type missions only" section that the T006 extractor skips for software-dev. Add a second T006 case: research-type fixture with a filled plan → that invocation exits 0 and creates 4 non-empty files (tests FR-012).
- **Driving `next` (T006):** query mode returns a preview without a prompt file. The supported path is `spec-kitty next --agent A --mission M --result success --json`, which issues `discovery` with its `prompt_file`; a second `--result success` completes it and advances to `specify` (discovery has no required artifacts). This is the legitimate path, not a bypass. The advancing mode runs the charter preflight: stub `run_preflight_or_abort` as `tests/contract/test_next_no_implicit_success.py` does. The issued file is header + governance + template (`prompt_builder.py:142-147`): extract commands from the template body only, reusing `_COMMAND_PATTERN` from `tests/doctrine/test_builtin_cli_command_references.py`.
- **Non-vacuity text asserts:** prompt names `research.md` as create-or-extend (FR-001); no STOP / "NOT main" location instruction (FR-002); at least one extracted invocation; FR-013 phrase invariant over the skill, command map, `docs/api/slash-commands.md` and `docs/context/spec-driven.md:189` (which also falsely says plan prompts to run `spec-kitty research` — fix it in T009).

## Branch Strategy

- Planning base branch and merge target: `claude/project-thread-silj7c` (the PR head branch; the PR targets `main`).
- Execution worktrees are allocated per computed lane from `lanes.json`. Use `spec-kitty implement WP02` and work only in the resolved workspace.

## Standing rules

- Charter first: read `.kittify/charter/charter.md`; load `spec-kitty charter context --action implement`.
- Red-first (ADR 2026-07-17-1): the issue-pinned `@pytest.mark.regression` test is committed RED before the fix (show the failing run in the Activity Log), then converted to a focused unit/integration test (no `regression` marker left) once green.
- New code: ruff, `ruff format --check`, mypy clean; no new suppressions; complexity ≤ 15; every new branch tested in the same commit.
- Never edit generated agent copies (`.claude/`, `.agents/`, ...). Never bump the version. Never push to `main`.
- Record exact test commands and pass/fail counts in the Activity Log.

## Activity Log

- 2026-09-28T06:40:00Z – system – Prompt created.
