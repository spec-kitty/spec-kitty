---
work_package_id: WP06
title: Home-folder command writer scoped to configured agents
dependencies:
- WP05
requirement_refs:
- FR-011
- NFR-003
planning_base_branch: issue-6475-6470-command-skill-names
merge_target_branch: issue-6475-6470-command-skill-names
branch_strategy: Planning artifacts for this mission were generated on issue-6475-6470-command-skill-names. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6475-6470-command-skill-names unless the human explicitly redirects the landing branch.
subtasks:
- T022
- T023
- T024
- T025
phase: Phase 3 - Home folder
history:
- at: '2026-10-20T20:01:05Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/runtime/agent_commands.py
create_intent:
- tests/specify_cli/runtime/test_agent_commands_scope.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/runtime/agent_commands.py
- tests/specify_cli/runtime/test_agent_commands.py
- tests/specify_cli/runtime/test_agent_commands_freshness_precheck_shape.py
- tests/specify_cli/runtime/test_agent_commands_scope.py
- tests/performance/test_cli_startup_agent_commands_freshness.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Home-folder command writer scoped to configured agents

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and
behave according to its guidance before parsing the rest of this prompt. If the skill is not
available, read `packs/built-in/agent_profiles/python-pedro.agent.yaml` and adopt it.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status --mission command-skill-names-and-antigravity-01M5DBWT` and the event log `review_ref` before
starting; address every feedback item and record each with
`spec-kitty agent tasks add-history WP06 --note "..." --mission command-skill-names-and-antigravity-01M5DBWT`.

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

- The CLI startup writer installs global slash-command files only for slash agents configured in
  the current project (none outside a project); `~/.agent/workflows` is never written; Spec
  Kitty-owned `spec-kitty.*.md` there are removed with proof; warm startup stays within NFR-003
  (+≤50 ms vs base).
- The WP01 #6470 repro turns fully green: remove its `p0_repro` marker in this WP (convert it into
  an ordinary test, keep it in place).

## Subtasks & Detailed Guidance

### Subtask T022 – Startup scope

- Read `runtime/agent_commands.py` fully (`ensure_global_agent_commands`,
  `assess_global_agent_commands`, `_freshness_short_circuit`, stamps) and the startup call in
  `src/specify_cli/__init__.py:146-155`. **Avoid editing `specify_cli/__init__.py`** (repo rule:
  `__init__.py` edits require a version bump); prefer making the no-argument startup call resolve
  the scope inside `agent_commands.py` (find all callers of `ensure_global_agent_commands()` with no
  args first: if startup is the only one, change the default; otherwise add an explicit keyword and
  ask before touching `__init__.py`).
- Scope resolution: locate the project root cheaply from CWD (reuse the existing project-root
  locator used by startup, no heavy YAML import if avoidable — measure), read configured agents via
  `load_agent_config`/`get_configured_agents`, filter with `configured_slash_agents()` (WP05). No
  project or no config → `()` meaning **none**; never let `()` mean "all".
- `agent config add <slash agent>` (WP05 file `cli/commands/agent/config.py`) must call
  `ensure_global_agent_commands(agent_keys=(key,))` for that agent — verify it already does
  (`_command_surface_doctor.py:189-191` precedent) and add it if not (out-of-map edit, rationale).

### Subtask T023 – Freshness stamp per key

- Today `_freshness_short_circuit` returns None for any `agent_keys is not None` and the stamp is
  written only for full-fleet calls; exact key equality. Change to: the stamp stores
  `{cli_version, template_source_signature, healthy_keys: [...], schema: 2}`; scoped calls write it
  (union with prior healthy keys when version+signature match, replace otherwise); short-circuit
  when every requested key ∈ `healthy_keys` and the destination-health check passes for the
  requested keys. A stamp without `schema: 2` is "not fresh" (forces one build that also runs the
  cleanup in T024).
- Keep the SK-243 immunity property (no `AssetPreparation` on the short-circuit path) and the
  existing concurrency lock; update the docstrings that describe the full-fleet-only contract.
- `_VERSION_FILENAME` / all-agent stamp: keep writing it only for genuine full-fleet calls; make sure
  nothing on startup depends on it after the change.

### Subtask T024 – `~/.agent/workflows` cleanup

- Inside `_build`, for a hard-coded `Path.home() / ".agent" / "workflows"` (never via
  `get_global_command_dir`, which would KeyError): if it is a real directory (refuse symlink /
  outside-home resolution), `observe(..., role="destination_probe")`, then for each child named
  `spec-kitty.*.md` call `prepared.retire(child)` (inventory proof). For a child with no inventory
  entry, remove only on the exact **current**-version marker line AND byte equality with a render
  from a frozen private antigravity config row (`{"dir": ".agent/workflows", "ext": "md",
  "arg_format": "$ARGUMENTS"}` kept as a private constant for this purpose only). Never use
  `_is_canonical_predecessor`'s different-version branch as deletion proof (R-M5). Never remove the
  directory. Record the cleanup as done via the stamp schema so warm runs skip it.

### Subtask T025 – Tests

- New `tests/specify_cli/runtime/test_agent_commands_scope.py`: configured `claude` only → no other
  agent dir created in a temp HOME; outside a project → nothing written; `()` ≠ all; scoped stamp
  short-circuits on the second call (assert no `AssetPreparation` constructed — monkeypatch);
  schema-1 stamp forces a build; cleanup removes inventory-owned and current-marker+bytes files,
  keeps a user file, keeps an edited marked file, refuses a symlinked `~/.agent/workflows`.
- Update the existing freshness tests (`test_agent_keys_mismatch_forces_rerender` etc.) to the new
  contract — judge each test: stale → re-pin with rationale.
- Startup timing: run `tests/performance/test_cli_startup_agent_commands_freshness.py` before and
  after (base vs head) and record the numbers in the trace; keep within +50 ms.

## Test Strategy

`.venv/bin/python -m pytest tests/specify_cli/runtime tests/runtime/test_upgrade_preview_bootstrap.py tests/runtime/test_generic_asset_scope.py tests/runtime/test_check_assets_membership_tolerance.py tests/runtime/test_doctor_command_file_health.py tests/runtime/test_startup_torn_read_escalation.py -q`,
the performance file explicitly, the WP01 6470 test, `make test-fast`.

## Definition of Done

- Scoped startup, per-key freshness, safe cleanup, 6470 repro green and unmarked, timing recorded.

## Review Guidance

Reviewer checks no deletion path relies on the marker alone and that warm startup does no
`iterdir` of `~/.agent/workflows`.

## Context & Constraints

- Read first: `kitty-specs/command-skill-names-and-antigravity-01M5DBWT/spec.md`, `plan.md` (the **Post-plan squad dispositions**
  table overrides the concern text where they disagree), `research.md`, `data-model.md`,
  `occurrence_map.yaml`, and `.kittify/charter/charter.md`.
- Operator rulings (decision `01M5DBXJ05DSF4322SXVPNPZZ1` + 2026-10-20 answers): name
  `spec-kitty-<cmd>`; clean break; keep hand-edited dotted skills with a warning; slash-command files
  of the 13 command agents keep `spec-kitty.<cmd>` (C-001, #6471); pack sources keep
  `/spec-kitty.<cmd>` and skill bodies are rewritten at render time; `builtin:spec-kitty.<cmd>` is an
  accepted input alias; Antigravity workflow files are archived, not deleted; a user folder at a
  canonical path is skipped with a warning.
- **Stop and ask the operator** (C-006) on anything these rulings do not cover. Do not guess.
- Code rules: ruff + `ruff format --force-exclude <files>` + mypy clean, complexity ≤15, no new
  `# noqa`/`# type: ignore` without an inline rationale, repeated literals hoisted to constants,
  new branches covered by focused tests in the same commit.
- Tests: run the targeted files you touch plus the owning directory
  (`tests/specify_cli/skills`, `tests/specify_cli/upgrade/migrations`, init tests) and the specific
  architectural gate files implicated. **Never** `make test-full` or a bare `tests/architectural/`
  sweep (NO_FULL_HEAVY_SUITES_IN_MISSION). Use `.venv/bin/python -m pytest ... -q`.
- Harness env leaks: containers export `SPEC_KITTY_NO_NAG`, `SPEC_KITTY_NO_UPGRADE_CHECK`,
  `SPEC_KITTY_NON_INTERACTIVE`; delete them test-locally when a test needs them unset.
- Append dated entries to `kitty-specs/command-skill-names-and-antigravity-01M5DBWT/traces/*.md` at each significant decision or
  friction point (that file is planning surface; editing it is allowed).
- Commit with a conventional message ending with:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_0113JBRFGzV5iEZ6QwgwijcB`. Never push.

## Branch Strategy

- **Strategy**: single_branch (no lanes; work in the repository root checkout)
- **Planning base branch**: issue-6475-6470-command-skill-names
- **Merge target branch**: issue-6475-6470-command-skill-names

## Progress & Status

Progress lives in the status event log. Record notes with
`spec-kitty agent tasks add-history <WPID> --note "..."`, move with
`spec-kitty agent tasks move-task <WPID> --to <lane>`, mark subtasks with
`spec-kitty agent tasks mark-status <Txxx...> --status done`.

Implementation command:

```bash
spec-kitty agent action implement WP06 --agent claude --mission command-skill-names-and-antigravity-01M5DBWT
```
