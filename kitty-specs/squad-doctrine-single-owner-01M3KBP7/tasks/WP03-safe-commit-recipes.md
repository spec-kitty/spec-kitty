---
work_package_id: WP03
title: Printed commit recipes use safe-commit (#5078 code)
dependencies: []
requirement_refs:
- FR-018
planning_base_branch: claude/squad-doctrine-single-owner-rzqpvw
merge_target_branch: claude/squad-doctrine-single-owner-rzqpvw
branch_strategy: Planning artifacts for this mission were generated on claude/squad-doctrine-single-owner-rzqpvw. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/squad-doctrine-single-owner-rzqpvw unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-squad-doctrine-single-owner-01M3KBP7
base_commit: 96d9f4028797cfacb25adc7ea78bb311b0199c03
created_at: '2026-09-28T07:28:31.228098+00:00'
subtasks:
- T011
- T012
- T013
- T014
phase: Phase 1 - Foundations
history:
- at: '2026-09-28T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks (fold-in revision)
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- src/specify_cli/cli/commands/_commit_recipes.py
- tests/specify_cli/cli/commands/test_commit_recipes.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/cli/commands/agent/workflow_executor.py
- src/specify_cli/cli/commands/implement.py
- src/specify_cli/cli/commands/agent/tasks_parsing_validation.py
- src/specify_cli/cli/commands/charter/_synthesis.py
- src/specify_cli/cli/commands/agent/mission_setup_plan.py
- src/specify_cli/cli/commands/_commit_recipes.py
- tests/specify_cli/cli/commands/test_commit_recipes.py
- tests/agent/test_build_implement_prompt_lines.py
- tests/specify_cli/cli/commands/test_implement_writeside.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Printed commit recipes use safe-commit (#5078 code)

## ⚡ Do This First: Load Agent Profile

FIRST run `spec-kitty agent profile show python-pedro` (add `--all` if it reports the profile as not activated in this repo) and `spec-kitty charter context --action implement --json`. Apply the resolved initialization, boundaries, directives and tactics, then state which ones you applied.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Branch Strategy

- **Planning base branch**: `claude/squad-doctrine-single-owner-rzqpvw`
- **Merge target branch**: `claude/squad-doctrine-single-owner-rzqpvw`
- Execution worktrees are allocated per computed lane from `lanes.json`. Work only in the workspace that `spec-kitty implement WP03` resolves.

## Mission-wide rules (read before editing)

- **Charter**: `.kittify/charter/charter.md`. **Spec**: `kitty-specs/squad-doctrine-single-owner-01M3KBP7/spec.md`. **Plan**: `plan.md`. **Grounding evidence**: `research.md` R-7..R-11.
- **Epic rule (#5218)**: one owner states each rule. Every other artifact references the owner by id and does not restate it. This is not wholesale merging: directive = rule, tactic = how, styleguide = format, procedure = workflow, paradigm = worldview.
- **Delivery-risk rule**: when you trim a copy that was the only delivery path for an owner, record in the Activity Log which DRG edge WP09 must add. Content WPs do NOT edit edges, graphs or the extractor.
- **Generated files are owned by WP09 only**:
  - `packs/built-in/*.graph.yaml`
  - `packs/built-in/pack-manifest.yaml`
  - `src/charter/offering/drg/migration/{extractor,hand_authored_overlay}.py`
  - `src/charter/activation/packs/{default,minimal}.yaml`
  - `packs/built-in/missions/*/actions/*/index.yaml`
  - the DRG goldens

  In a content WP, `spec-kitty doctrine regenerate-graph --check` and the manifest-freshness tests are EXPECTED to be stale. Do not regenerate or hand-edit those files. Record the edges or activation changes WP09 must make in your Activity Log under a heading `### Handoff to WP09`.
- **Pinned ids (plan.md "Pinned successor ids")**:
  - `bdd-scenario-formulation` (tactic, `tactics/testing/`);
  - `boring-code-review` (styleguide; same id, new kind);
  - `supply-chain-install-safety` stays the ONE supply-chain tactic, made ecosystem-neutral, with its JS/TS steps moved to the `javascript-supply-chain` toolguide;
  - `tracker-backlog-iterative-deepening` (internal tactic).

  Do not invent other ids.
- **Pack prose**:
  - no `#NNNN` issue references (see `tests/architectural/_builtin_pack_provenance_baseline.yaml` and `test_builtin_pack_provenance_ratchet.py`; counts may only go down);
  - no version numbers;
  - the terminology canon applies: Mission, never Feature, and canonical `status commit`.
- **Validate every edited artifact loads**, through its repository (`from charter.offering.service import DoctrineService`) or the kind's schema tests. `procedure.schema.yaml` and most schemas are `additionalProperties: false`.
- **ATDD / red-first**: commit a failing test that pins the new doctrine shape BEFORE the content change, as its own commit.
- **Ownership map**: stay inside `owned_files`. A small out-of-map edit is allowed only with a one-line rationale in the Activity Log (no-overlap is the real guard).
- **No full heavy suites** (`NO_FULL_HEAVY_SUITES_IN_MISSION`): run targeted files and the named gate files only.
- **Commit** with `spec-kitty safe-commit <files> -m "<msg>" --to-branch <your lane branch>`. Lane branches are not protected. If safe-commit refuses, stop and report the refusal verbatim in the Activity Log; do not bypass it with raw git or `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`. Never commit on `main`.
- **Lane-local CLI (mandatory).** The global `spec-kitty` on PATH is an editable install of the ROOT checkout. Inside a lane worktree it reads the root's packs and code, not yours. For every doctrine or charter command in a lane (`doctrine regenerate-graph`, `charter context|generate|sync|synthesize`, `agent profile show`, upgrade/migration runs), invoke:
  `PYTHONPATH=$PWD/src SPEC_KITTY_PACKS_ROOT=$PWD/packs python -m specify_cli <args>`
  from the lane worktree root. pytest is already lane-local (`pytest.ini` sets `pythonpath = src`).
- **Handoff channel.** Handoff notes for later WPs (edges, activation, pinned tests) go in the **body of your final commit**, under a line `Handoff-to-WP09:` (or `Handoff-to-WP10:` / `Handoff-to-WP11:`), and are mirrored in your Activity Log. Downstream WPs read them with `git log --format=%B` over the merged dependency lanes.
- **Expected-red list.** Content WPs leave the generated graph and manifest stale on purpose. In your final commit body, under `Expected-red-until-WP09:`, list the exact test node ids that are red in your lane only because regeneration is deferred. Typical: `regenerate-graph --check`, `test_doctrine_regenerate_graph_roundtrip`, `test_pack_manifest_no_author_edit`, `test_shipped_graph_is_fresh_and_byte_identical`, reachability, census. Reviewers treat those as expected; WP09's reviewer verifies the whole union is green.
- **Before handoff**, run every red-first test of the WPs you depend on, so you never break a predecessor's pin.

## Objectives & Success Criteria

Operator decision (#5078): **safe-commit is consumer doctrine.** Every commit recipe the CLI prints for an agent to run becomes `spec-kitty safe-commit <files> -m "<msg>" --to-branch <branch>`. `safe_commit_cmd.py` and `git/commit_helpers.py:994-1060` stage and commit only the named paths, and they refuse protected destinations unless configured.

Printed recipes are at (research R-8; verify the lines):
- `workflow_executor.py:1378,1455,1514`
- `implement.py:424`
- `tasks_parsing_validation.py:337,339,537,567,661`
- `charter/_synthesis.py:749`
- `mission_setup_plan.py:137`

Confirm the real module paths with `grep -rn "git commit" src/specify_cli --include=*.py`. **Only change strings printed as instructions for an agent or user.** Leave code that actually runs git.

## Subtasks & Detailed Guidance

### T011 – Red-first test (own commit, RED)

`tests/specify_cli/cli/commands/test_commit_recipes.py` (markers `unit, fast`):
- An AST/string scan of **all of `src/specify_cli`** finds no printed `git commit` recipe outside a named allowlist of files with a rationale each. Include `core/mission_creation.py:871` if it is a printed recipe; if it is, fix it here as an out-of-map edit. Pin the base count found at the planning base in a comment. Detect string constants and f-strings containing `git commit`, excluding subprocess argv lists.
- The helper renders a safe-commit recipe with `--to-branch`.
- The protected-primary hint is present when the target is a protected branch.
- Positive control: the scan flags a fixture string `'git commit -m "feat(WP01): x"'`.

### T012 – A single recipe helper

- Create `src/specify_cli/cli/commands/_commit_recipes.py` (or reuse an existing helper if grep finds one) with a small function, e.g. `safe_commit_recipe(files: Sequence[str], message: str, branch: str | None) -> str`.
- Add a constant for the protected-primary hint text. The hint names the supported path: plan on a topic branch, or configure `protection.protected_branches` in `.kittify/config.yaml`. It never suggests `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`, per the charter.
- Hoist any literal repeated ≥ 3 times (Sonar S1192).

### T013 – Replace the recipes

- Use the helper at every site.
- For `implement.py:424` (planning artifacts; the old recipe used `git add -f`): safe-commit already force-adds named paths, so drop `-f`, and add the protected-primary hint.

### T014 – Update pinned output tests

Update the tests that pin the old strings: `tests/agent/test_build_implement_prompt_lines.py`, `tests/specify_cli/cli/commands/test_implement_writeside.py`, plus any found by `grep -rln "git commit -m" tests`. Assert the new safe-commit recipe instead.

## Test Strategy

```bash
pytest tests/specify_cli/cli/commands/test_commit_recipes.py tests/agent/test_build_implement_prompt_lines.py tests/specify_cli/cli/commands/test_implement_writeside.py -q
pytest tests/agent -q -k "workflow or implement or tasks" ; pytest tests/specify_cli/cli/commands -q -k "implement or setup_plan or synthesis"
make test-fast   # baseline
ruff check <files> && ruff format --check <files> && mypy <src files>
```

## Review Guidance

- No executed git call changed.
- The protected-branch wording follows the charter.
- Complexity ≤ 15 in the touched functions; extract helpers where needed.

## Activity Log

- 2026-09-28T09:00:00Z – system – Prompt created (fold-in revision).
- 2026-09-28 – claude (python-pedro, sonnet) – Implemented on lane-c; the orchestrator recorded this entry on the planning branch.
  - Commits:
    - `9e51fcb6`: red scanner and helper. 24 base hits, 11 of them genuine printed recipes.
    - `92c7ce9f`: all 11 sites converted.
  - Two sites now use the lane's own branch, `workspace.branch_name`.
  - The kitty-specs cleanup recipe omits `--to-branch`.
  - 13 allowlisted residue sites.
  - Out-of-map test re-pins: `test_workflow_review_lane_gate.py`, `test_review_validation_unit.py`.
  - Tests:
    - targeted: 26 passed
    - `tests/agent` subset: 186 passed
    - `tests/specify_cli/cli/commands` subset: 312 passed
    - `make test-fast`: 2106 passed, 1 failed (`TestFreshnessShortCircuitOSErrorFallthrough`, baseline-red per the implementer)
    - `test_charter_synthesize_cli`: 6 failed, baseline-red (linked-worktree charter-write guard)
  - Moved to for_review.
