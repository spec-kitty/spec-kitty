---
work_package_id: WP17
title: S11 core command skills, stale-lane CLI remedy, skill-text guard, CLAUDE.md
dependencies:
- WP07
- WP08
- WP10
- WP12
- WP14
- WP15
requirement_refs:
- FR-090
- FR-091
- FR-093
- FR-059
- SC-011
- C-001
planning_base_branch: issue-7276-lane-worktree-hardening
merge_target_branch: issue-7276-lane-worktree-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-7276-lane-worktree-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7276-lane-worktree-hardening unless the human explicitly redirects the landing branch.
subtasks:
- T107
- T108
- T109
- T110
- T111
phase: Phase 7 - S11 text that follows behaviour
history:
- at: '2026-11-06T08:51:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/skills/
create_intent:
- tests/charter_offering/test_command_skill_text_guard.py
- tests/lanes/test_stale_remediation_cli_command.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/offering/skills/spec-kitty-implement-review/SKILL.md
- src/charter/offering/skills/spec-kitty-git-workflow/SKILL.md
- src/charter/offering/skills/spec-kitty-program-orchestrate/SKILL.md
- src/charter/offering/skills/spec-kitty-mission-review/SKILL.md
- src/charter/offering/skills/spk-gate-consolidate/SKILL.md
- src/charter/offering/skills/spk-run-blocked-recovery/SKILL.md
- src/specify_cli/lanes/stale_check.py
- tests/charter_offering/test_command_skill_text_guard.py
- tests/lanes/test_stale_remediation_cli_command.py
- CLAUDE.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP17 - S11 core command skills, stale-lane CLI remedy, skill-text guard, CLAUDE.md

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Address every item; record progress with `spec-kitty agent tasks add-history WP17 --note "..."`.

---

## Implementation command

```bash
cd /home/user/spec-kitty
spec-kitty agent action implement WP17 --agent claude --mission lane-worktree-model-hardening-01M6QY1M
```

## Objectives & Success Criteria

S11 (#7285), the core-repository text that ships with this Mission's behaviour:

- FR-090: the six core command skills teach the shipped model: `consolidate`, never `merge`, for lane consolidation; status read through the CLI (`spec-kitty agent tasks status`); no manual stale-lane recipe; no hand status commits; cleanup as consolidation's last step (Removed / Kept / Retained report; `spec-kitty doctor workspaces --prune` as the remedy only where WP16's behaviour has landed, else withheld); the for_review gate counts commits on the lane branch (no checkout needed); pointers for `DESTROYED_LANE` / `LANE_WORK_TIP_UNKNOWN` (follow the command the CLI prints).
- FR-091: `lanes/stale_check.py::_stale_remediation` (`:117`) prints a `spec-kitty` command (the A-10 re-entry path `spec-kitty agent action implement <WP> --mission <handle>`, which refreshes a stale lane through auto-rebase), never `cd .worktrees/...` and never `git merge`.
- FR-093: a guard test `tests/charter_offering/test_command_skill_text_guard.py` with planted strings fails on: `spec-kitty merge`, manual stale-lane recipes (`cd .worktrees/` + `git merge`/`git rebase`), advice to hand-commit status files, and lease-behaviour text (the lease is not shipped, C-007).
- FR-059 (CLAUDE.md half): CLAUDE.md "Execution Workspace Strategy" and "Consolidation" paragraphs describe the size default (topology settled at the first `finalize-tasks`), the Mission topic branch, that the coordination branch shares the Mission branch's name, the status read door, lane checkouts without status files, and cleanup as the last step. Also fix the stale orchestrator-api contract version prose (1.10.0 -> live value; tracer friction).
- SC-011 (core half): 0 occurrences of the forbidden texts.

## Context & Constraints

- Read: spec User Story 9, FR-090 to FR-093, Rule 8 ("Text follows behaviour"), C-001, C-002, C-007; `research.md` R-11; `upstream/doctrine-and-write-service-adr-map.md` (K1-K9 rows; it lists which skill gets which edit); tracer friction "S11 review (open-packs PR #128) found core follow-ups" (`spec-kitty context cleanup` clears every orphaned context; `DESTROYED_LANE` no-tip variant; `LANE_WORK_TIP_UNKNOWN` should suggest `--dry-run` first) - fold in only if small and only where behaviour exists.
- **Text never ships before its behaviour (FR-093)**: before writing a sentence, confirm the behaviour is on the topic branch (the dependencies WP07, WP08, WP10, WP12, WP14, WP15 are approved). Sentences about WP16 behaviour (pr-mode cleanup, prune backstop for Mission lanes) are withheld unless WP16 has landed; if it lands later, it adds them.
- C-002: do NOT edit `packs/built-in/`, `packs/internal/` or generated agent directories (`.claude/`, `.agents/` ...). Pack doctrine is WP18's patch. Core skills live in `src/charter/offering/skills/` (not in packs).
- Editing `src/charter/offering/**` and prose: run `tests/architectural/test_no_legacy_terminology.py` before pushing (CLAUDE.md). Terminology: say `consolidate`; name senses of "primary"/"merge"/"routing"/"residue".
- Internal code names (`LANE_BRANCH_MISSING`, `STATUS_WRITE_TARGETS_LANE_CHECKOUT`, ...) are final unless review renamed them (data-model §7): check the code before quoting them.
- Changes to skill files may trip the skills manifest / pack regen gates: if `spec-kitty charter pack regenerate-graph` or a skills hash test fails, follow its instruction; do not hand-edit manifests.
- C-011 red-first for the guard and the CLI message.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-7276-lane-worktree-hardening; completed changes must merge back into issue-7276-lane-worktree-hardening.
- **Planning base branch**: issue-7276-lane-worktree-hardening
- **Merge target branch**: issue-7276-lane-worktree-hardening

## Subtasks & Detailed Guidance

### Subtask T107 - Red-first tests

- `tests/lanes/test_stale_remediation_cli_command.py`:
  - `test_stale_remediation_has_no_git_merge_or_worktrees_cd`: build a stale lane; the remediation text contains `spec-kitty agent action implement` and neither `cd .worktrees` nor `git merge`.
  - `test_reentry_refreshes_stale_lane` (A-10 verification): re-running `spec-kitty agent action implement <WP>` on a stale lane rebases it (auto-rebase). If this test is red for reasons outside this WP's scope, stop and report: FR-091 must not name a path that does not work.
- `tests/charter_offering/test_command_skill_text_guard.py`: scan the six SKILL.md files; forbidden patterns as module constants; planted-string self-tests (one per pattern) in `tmp_path`; a floor asserting six files scanned.

### Subtask T108 - Stale remediation

- `_stale_remediation(lane, lane_branch, mission_branch)`: print `spec-kitty agent action implement <WP> --mission <handle>` (and the `consolidate` wording where relevant). Keep complexity <= 15; repeated literals as constants.

### Subtask T109 - Six SKILL.md edits [P]

- Apply K1-K9 from `upstream/doctrine-and-write-service-adr-map.md` to: `spec-kitty-implement-review`, `spec-kitty-git-workflow`, `spec-kitty-program-orchestrate`, `spec-kitty-mission-review`, `spk-gate-consolidate`, `spk-run-blocked-recovery`. Keep each skill's frontmatter and structure; change only the sentences that teach the old model.

### Subtask T110 - CLAUDE.md [P]

- Update "Execution Workspace Strategy (2.x)" (create-time topology paragraph: default = topic branch only, settled at first finalize by size; `lanes` / `coord` explicit-only; `single_branch` approval windows) and the "Consolidation & Preflight Patterns" intro (cleanup last; kept/retained report; exit 0 after a verified landing). Keep the house style (dense, precise; cite ADR `2026-11-06-2`/`-3`). Do not touch unrelated sections.

### Subtask T111 - Quality gates and blast radius

See Validation.

## Validation

```bash
cd <workspace>
uv run --frozen pytest tests/charter_offering/test_command_skill_text_guard.py tests/lanes/test_stale_remediation_cli_command.py -q
uv run --frozen pytest tests/charter_offering tests/charter tests/lanes -q -n auto --dist loadfile
uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_tests_stale_check.py -q     # out-of-matrix dir
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
make test-fast
uv run --frozen ruff check <touched py> && uv run --frozen ruff format --check --force-exclude <touched py>
uv run --frozen mypy --strict src/specify_cli/lanes/stale_check.py
```

Never `make test-full` or a bare `tests/architectural/` sweep.

## Tracer files

Return tracer lines in your completion summary (`- **[YYYY-MM-DD][implement WP17] ...**`, naming the trace file); the orchestrator appends them. List any withheld sentence and why.

## Risks & Mitigations

- Text ahead of behaviour: check each sentence against merged code.
- Manifest/hash gates on skill edits: follow their regen instruction.

## Review Guidance

- Guard non-vacuous; CLI remedy is a working `spec-kitty` command (A-10 test); no lease text; CLAUDE.md accurate; no `packs/` or generated agent dir edits.

## Definition of Done

- T107-T111 done; tests green; tracer lines returned.

## Progress & Status

- `spec-kitty agent tasks mark-status T107 T108 T109 T110 T111 --status done --mission lane-worktree-model-hardening-01M6QY1M`
- `spec-kitty agent tasks move-task WP17 --to for_review --mission lane-worktree-model-hardening-01M6QY1M`
