---
work_package_id: WP02
title: Shared JSON contract seam
dependencies: []
requirement_refs:
- FR-005
- FR-007
- FR-008
- FR-012
- NFR-004
- NFR-006
planning_base_branch: fix/cli-boundary-robustness
merge_target_branch: fix/cli-boundary-robustness
branch_strategy: Planning artifacts for this mission were generated on fix/cli-boundary-robustness. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/cli-boundary-robustness unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cli-boundary-robustness-01M2NQCB
base_commit: 325aa2113f0903c6d020aa4e2dacfa539db21d70
created_at: '2026-09-16T20:20:29.821465+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - Independent boundary foundations
history:
- at: '2026-09-16T20:02:57Z'
  actor: codex
  action: Prompt generated via mission tasks workflow
authoritative_surface: src/specify_cli/cli/
create_intent:
- src/specify_cli/cli/json_contract.py
- tests/specify_cli/cli/commands/test_json_contract_boundary.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/json_contract.py
- src/specify_cli/cli/commands/_doctor_shared.py
- src/specify_cli/cli/helpers.py
- tests/specify_cli/cli/commands/test_json_contract_boundary.py
- tests/specify_cli/cli/test_helpers.py
tags: []
tracker_refs:
- '#4532'
- '#4601'
---

# Work Package Prompt: WP02 – Shared JSON contract seam

## Objective

Promote the frozen #4242 JSON error envelope into a single shared authority, preserve doctor compatibility through re-export, and make shared project-root/git-resolution failures capable of honoring `--json` without changing existing human callers.

## Context and authoritative decisions

- Read `contracts/json-envelope-contract.md` in full before coding.
- Error shape is exactly `{"ok": false, "error": {"code": <slug>, "message": <text>}}`.
- Empty success is not defined here as one universal payload; commands retain their own successful shapes.
- A JSON error uses the same exit code as the corresponding non-JSON condition. Never homogenize to exit 2.
- `CliConsole.emit_json`/`print_json` is the stdout transport seam; prose belongs on stderr.
- NFR-004 permits exactly one error-envelope definition. `_doctor_shared.py` re-exports; it must not retain a competing implementation.
- `get_project_root_or_exit` gains a defaulted `json_output: bool = False`, so all unmodified callers remain source- and behavior-compatible.

## Branch strategy

- Planning base and merge target: `fix/cli-boundary-robustness`.
- Runtime allocates the dependency lane/worktree from `lanes.json`.
- Start with: `spec-kitty agent action implement WP02 --agent <name>`
- WP01 is independent and may execute concurrently.

## Owned-file boundary

Only the shared contract, doctor compatibility module, CLI helper module, the new focused test file, and the existing helper contract test may change. The existing helper test is owned here because `exit_git_resolution_failure` intentionally changes from its legacy flat stderr shape to the canonical nested stdout envelope. Do not adopt individual commands here; WP03–WP05 own their call sites.

## Subtasks and detailed guidance

### T006 – RED: freeze the shared contract and helper behavior

Create `tests/specify_cli/cli/commands/test_json_contract_boundary.py` before implementation. Capture:

- Error envelope value and nesting, including `error` as an object rather than a string.
- Stable, non-empty code/message validation.
- JSON-aware `get_project_root_or_exit` outside a project: valid JSON on stdout, no prose contamination, existing exit 1.
- Default/human invocation: existing prose and exit behavior unchanged.
- `exit_git_resolution_failure` uses the same canonical shape under JSON.
- The known doctor consumers can still import their envelope helper from `_doctor_shared`.

Use existing `test_doctor_json_not_in_project.py` as authority. Do not rewrite or own that frozen test.

### T007 – Create `cli/json_contract.py`

Move/promote the existing doctor-private envelope definition into this new shared module. Keep the API small and explicit: construction of the canonical error mapping and, if justified by existing usage, a helper that emits it through the console seam.

Required properties:

- One constructor/authority for error shape.
- Stable `code` and human `message` are caller supplied.
- No broad command knowledge or command-specific exit code policy in the module.
- No success-payload normalization.
- Types are concrete enough for mypy; no blanket ignores.

### T008 – Re-export through `_doctor_shared.py`

Replace the old doctor-local definition with an import/re-export from `cli/json_contract.py`. Update the module docstring/import-boundary declaration called out by the post-spec squad so it truthfully names the new shared dependency.

Verify existing doctor imports and frozen tests remain green. Avoid a circular import: the shared module must not import doctor command code.

### T009 – JSON-aware shared failures

Update `get_project_root_or_exit` in `cli/helpers.py`:

- Add `json_output: bool = False`.
- On failure with JSON requested, emit the canonical `not_in_project` envelope on stdout and use the pre-existing exit code.
- With the default, preserve exact human behavior.
- Keep all existing callers compiling; WP03–WP05 will opt in their owned commands.

Converge `exit_git_resolution_failure` in the same file onto the shared envelope for its JSON path. Preserve its existing code/message semantics and non-JSON behavior.

Do not fold the unrelated empty `except Exception: pass` notifier nearby.

### T010 – Exit, stream, and compatibility verification

Complete tests for:

- stdout is exactly one parseable JSON value on JSON error paths.
- Optional human diagnostics, if retained, are on stderr.
- Default helper callers get their historical prose and exit status.
- Doctor’s three exit-2 exceptions remain exit 2 through their existing command layer; ordinary root failure stays exit 1.
- There is no second literal/constructor for the canonical error mapping in owned source.

## Test strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_json_contract_boundary.py -q
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_doctor_json_not_in_project.py tests/specify_cli/cli/commands/test_doctor_shared.py -q
ruff check src/specify_cli/cli/json_contract.py src/specify_cli/cli/helpers.py src/specify_cli/cli/commands/_doctor_shared.py tests/specify_cli/cli/commands/test_json_contract_boundary.py
```

Use the whole-repository format check from `quickstart.md` before handoff.

## Definition of done

- Exactly one shared error-envelope authority exists.
- Doctor imports remain compatible through re-export.
- Shared root/git failures honor JSON streams and command-specific exit codes.
- Human mode is unchanged by default.
- Tests demonstrate shape, parseability, stream discipline, and exit fidelity.
- No command-adoption files or unrelated helper debt were touched.

## Risks and mitigations

- **Import cycle**: keep the contract module dependency-light and command-agnostic.
- **Shape drift**: compare parsed values and exact nested types in tests.
- **Exit drift**: the constructor never chooses an exit code; callers retain control.
- **Unintended caller changes**: use a defaulted flag and preserve the old branch verbatim.

## Reviewer guidance

Search the owned files for competing envelope literals, verify `_doctor_shared` only re-exports, inspect stdout/stderr assertions, and compare the root-failure exit code to the non-JSON invocation. Reject any attempt to normalize successful command payloads in this foundational WP.

## Contract examples

Canonical error value:

```json
{"ok": false, "error": {"code": "not_in_project", "message": "Not inside a Spec Kitty project"}}
```

The constructor owns the nested mapping only. It does not own:

- whether the caller exits 1 or 2;
- a command's successful payload;
- whether a human diagnostic is additionally useful on stderr;
- command discovery or enumeration policy;
- conversion of arbitrary exceptions into public errors.

## Acceptance matrix

| Surface | JSON requested | Expected stdout | Expected exit |
|---|---:|---|---:|
| project-root helper outside project | yes | canonical `not_in_project` object | existing 1 |
| project-root helper outside project | no | historical human prose | existing 1 |
| git resolution failure | yes | canonical domain error object | existing code |
| doctor compatibility import | n/a | no output; import succeeds | n/a |
| command success | yes | caller-owned existing payload | caller-owned |

## Implementation evidence to retain

- Red/green output from the new focused test.
- Existing frozen doctor test results.
- Search evidence showing one constructor in the owned surface.
- Paired human/JSON exit values for root failure.
- Raw captured stdout demonstrating direct `json.loads` success.
- Import smoke test for `_doctor_shared` consumers.

## Self-review checklist

- [ ] `json_contract.py` does not import command modules.
- [ ] `_doctor_shared.py` re-exports rather than wraps a duplicate mapping.
- [ ] `json_output` defaults to `False` on the shared helper.
- [ ] Human mode is byte/behavior compatible where frozen.
- [ ] JSON mode emits exactly one value on stdout.
- [ ] Caller exit codes are not centralized or homogenized.
- [ ] No successful payload was wrapped or renamed.
- [ ] Only owned files changed.

## Activity log

### 2026-09-16 – Prompt generated

Shared seam isolated from command adoption to unlock three parallel downstream packages.
