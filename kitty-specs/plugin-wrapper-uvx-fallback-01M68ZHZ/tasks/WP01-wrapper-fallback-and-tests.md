---
work_package_id: WP01
title: Wrapper fallback fix and its tests
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- C-002
- C-003
- SC-001
- SC-002
- SC-003
- SC-004
- SC-005
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Fix the generated bootstrap
history:
- at: '2026-10-31T12:45:00Z'
  actor: planner-priti
  action: Prompt generated via spec-kitty tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/tool_surface/bundles/
create_intent: []
execution_mode: code_change
model: claude-sonnet
owned_files:
- src/specify_cli/tool_surface/bundles/claude_wrapper.py
- tests/specify_cli/tool_surface/bundles/test_claude_wrapper.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Wrapper fallback fix and its tests

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the
frontmatter, and behave according to its guidance before parsing the rest of this
prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best
match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via
  `spec-kitty agent tasks status`).
- Address all feedback before declaring the work complete.

---

## Objectives & Success Criteria

Two generated bootstrap scripts — `bin/spec-kitty-wrapper` (bash) and
`bin/spec-kitty-wrapper.cmd` (cmd.exe) — currently delegate to
`uvx "spec-kitty-cli==<version>"`. `uvx <requirement>` runs the executable named after
the *distribution*, and the distribution ships only `spec-kitty`, so the fallback exits
1 without ever running the CLI. Fix both, and make the wrapper's choice of CLI
deliberate:

1. The fallback invokes `uvx --from "<requirement>" spec-kitty …` (FR-001, FR-002).
2. A `spec-kitty` on PATH is used only when its reported version is inside the pinned
   build's `<major>.<minor>` series (FR-004); otherwise the pinned path wins.
3. If the exact pin cannot be resolved by uvx (an unpublished build version), retry with
   `spec-kitty-cli>=<pinned>,<<next-minor>` before giving up (FR-003).
4. The terminal error names the uv/pipx remedy, not `pip install spec-kitty-cli` (FR-005).

Success: SC-001 through SC-005 in `../spec.md`.

## Context & Constraints

- Defect and reproduction: `../research.md` (D-01) and `../spec.md` "Problem Statement".
- Current implementation: `src/specify_cli/tool_surface/bundles/claude_wrapper.py`
  (`_BASH_WRAPPER_TEMPLATE`, `_CMD_WRAPPER_TEMPLATE`, `wrapper_bash_content`,
  `wrapper_cmd_content`).
- Call sites that must keep working unchanged:
  `src/specify_cli/tool_surface/bundles/claude.py:244-247` and
  `src/specify_cli/tool_surface/bundles/projection.py:943-945`.
- Constraints: no new console script (C-002); no gate weakening (C-003); bundle layout
  untouched (C-001); rendering stays offline and deterministic (NFR-004).
- `spec-kitty --version` prints `spec-kitty-cli version 4.0.0rc8` — the version token is
  the last whitespace-separated token, not the whole line.

## Branch Strategy

- **Strategy**: single_branch
- **Planning base branch**: main
- **Merge target branch**: main

> These fields are populated by `spec-kitty agent mission finalize-tasks`. Do not change
> them manually.

## Subtasks & Detailed Guidance

### Subtask T001 – Version→series helper

- **Purpose**: One authority for "which versions may this bundle run".
- **Steps**: Add a pure helper next to the templates that derives the supported series
  (`<major>.<minor>`) and the uvx requirements from the build version:
  the exact spec (`spec-kitty-cli==<version>`) and the series range
  (`spec-kitty-cli>=<version>,<<major>.<minor+1>`). An unparseable version yields the
  exact spec only — never a guessed range. Expose it for the template renderers (and for
  tests) without widening `__all__` beyond what the module already exports unless the
  renderers need it.
- **Files**: `src/specify_cli/tool_surface/bundles/claude_wrapper.py`
- **Parallel?**: No — T002/T003 consume it.
- **Notes**: Prefer `re.fullmatch`-style anchoring over substring search so
  `4.0.0rc8` yields `4.0` and `unknown` yields nothing.

### Subtask T002 – POSIX template rewrite

- **Purpose**: The reported broken path.
- **Steps**:
  1. Keep the shebang, `set -euo pipefail`, and `VERSION="<pinned>"`.
  2. PATH probe: run `spec-kitty --version` once, extract the first
     `<digits>.<digits>` token with `awk`, and delegate (`exec spec-kitty "$@"`) only when
     it equals the embedded series. A missing binary, a failing probe or an unparseable
     version falls through — do not abort under `set -e`.
  3. uvx path: for each requirement from T001 (pinned, then range), probe
     `uvx --from "<req>" spec-kitty --version`; on success `exec uvx --from "<req>"
     spec-kitty "$@"`. Only a resolution failure moves to the next requirement — a CLI
     that ran is never retried against another version.
  4. Terminal error: exit 1 with a message naming `uv tool install spec-kitty-cli` /
     `pipx install spec-kitty-cli` (or `uvx`), and no `pip install spec-kitty-cli`.
- **Files**: `src/specify_cli/tool_surface/bundles/claude_wrapper.py`
- **Parallel?**: No.
- **Notes**: The probe adds one process on the installed-CLI path and none on the
  delegate path after it (NFR-001). Keep `"$@"` forwarding intact.

### Subtask T003 – CMD template rewrite

- **Purpose**: Windows parity for the same resolution order.
- **Steps**: Mirror T002 with cmd.exe constructs: `where` probes, a `GOTO`-based flow, an
  installed-version capture via `FOR /F` plus a `delims=.` split compared against the
  embedded series, `uvx --from` with **quoted** requirements (`>=`/`<` are redirection
  operators), `%*` forwarding, and `EXIT /B %ERRORLEVEL%` never inside a parenthesized
  block (#623). The remedy lines match T002.
- **Files**: `src/specify_cli/tool_surface/bundles/claude_wrapper.py`
- **Parallel?**: No.
- **Notes**: Keep every new label defined and reachable; keep the existing no-
  parenthesized-`IF` invariant that the test suite pins.

### Subtask T004 – Red-first tests

- **Purpose**: Prove the defect and pin each half of the fix independently.
- **Steps**:
  1. First, against the *current* template: rewrite
     `test_bash_falls_back_to_uvx_when_path_shim_is_unreachable` to assert the fixed argv
     (`uvx --from spec-kitty-cli==9.9.9 spec-kitty mission list`) and add the series-gate
     runtime tests. Run them and record the red.
  2. Then implement T001–T003 and re-run.
  3. Runtime tests must use a temp `PATH` with stub `uvx` / `spec-kitty` executables:
     - no `spec-kitty`, `uvx` present → `--from` pinned argv (SC-001);
     - PATH CLI reporting the bundle series → direct delegation, `uvx` never invoked;
     - PATH CLI reporting another series → uvx path taken, PATH binary not executed
       (SC-003);
     - pinned resolution failing, range resolution succeeding → range argv
       (FR-003);
     - neither available → non-zero exit, uv/pipx remedy, no `pip install spec-kitty-cli`
       (FR-005).
  4. Content pins: both rendered wrappers contain `uvx --from`, contain no bare
     `uvx "spec-kitty-cli` / `uvx spec-kitty-cli` invocation (SC-002), and the `.cmd`
     keeps its #623 invariants.
- **Files**: `tests/specify_cli/tool_surface/bundles/test_claude_wrapper.py`
- **Parallel?**: Can be drafted alongside T001.
- **Notes**: Hermetic — no network, no reliance on the developer's real `uvx` or an
  installed `spec-kitty`. Keep the module markers (`unit`, `fast`) and skip POSIX shell
  tests on Windows.

## Test Strategy

- Mandatory: the rewritten `tests/specify_cli/tool_surface/bundles/test_claude_wrapper.py`.
- Commands:
  - `uv run pytest tests/specify_cli/tool_surface/bundles/test_claude_wrapper.py -q -p no:randomly`
  - `uv run pytest tests/specify_cli/tool_surface/bundles -q`
- Lint/type: `uv run ruff check src/specify_cli/tool_surface/bundles/claude_wrapper.py tests/specify_cli/tool_surface/bundles/test_claude_wrapper.py`
  and the project's configured type check for the touched module.
- A helper-only assertion is not sufficient evidence: at least one test must execute the
  rendered script.

## Risks & Mitigations

- `set -e` aborting on a failed probe → guard the probe in an `if`/`|| true`.
- cmd.exe parse-time `%ERRORLEVEL%` expansion → keep `EXIT /B` outside parentheses.
- Unquoted `>`/`<` in the CMD range requirement → quote the whole requirement.
- Flaky tests from a real `uvx` → stub executables only.

## Review Guidance

- Verify the generated argv, not only the template text.
- Verify each half independently: revert the `--from` change and confirm the fallback
  test goes red; revert the series gate and confirm the gate test goes red.
- Confirm no `pip install spec-kitty-cli` remains in generated output.
- Confirm the diff does not touch bundle layout or manifests (#6479).

## Progress & Status

Progress and status live in the status event log (`status.events.jsonl`).

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
