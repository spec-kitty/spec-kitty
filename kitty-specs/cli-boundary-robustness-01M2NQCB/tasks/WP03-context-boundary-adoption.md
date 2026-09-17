---
work_package_id: WP03
title: Context command adoption and resolved defaults
dependencies:
- WP02
requirement_refs:
- FR-005
- FR-007
- FR-008
- FR-009
- FR-011
- FR-012
planning_base_branch: fix/cli-boundary-robustness
merge_target_branch: fix/cli-boundary-robustness
branch_strategy: Planning artifacts for this mission were generated on fix/cli-boundary-robustness. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/cli-boundary-robustness unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cli-boundary-robustness-01M2NQCB
base_commit: 325aa2113f0903c6d020aa4e2dacfa539db21d70
created_at: '2026-09-16T20:49:55.378955+00:00'
subtasks:
- T011
- T012
- T013
- T014
- T015
phase: Phase 2 - Parallel command adoption
history:
- at: '2026-09-16T20:02:57Z'
  actor: codex
  action: Prompt generated via mission tasks workflow
authoritative_surface: src/specify_cli/cli/commands/context.py
create_intent:
- tests/specify_cli/cli/commands/test_context_boundary_contract.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/context.py
- tests/specify_cli/cli/commands/test_context_boundary_contract.py
tags: []
tracker_refs:
- '#4597'
- '#4601'
---

# Work Package Prompt: WP03 – Context command adoption and resolved defaults

## Objective

Make the context command family consume WP02’s shared JSON seam on all owned exit paths and eliminate the bare-command OptionInfo leak so `spec-kitty context` behaves exactly like `spec-kitty context info`.

## Context and constraints

- Depends on WP02; import the shared contract/helper rather than defining a local envelope.
- #4597 is an old-style Typer default leakage at the `invoke_without_command=True` callback.
- Fix the callback/call site with concrete resolved values. Do not add sentinel coercion throughout the callee.
- Preserve every existing successful JSON payload; only transport and error shape change.
- The post-spec census identifies prose-before-JSON, bare `print(json.dumps(...))`, and repeated Rich error prefixes in this one owned file. Fold only replacements that directly serve JSON stream discipline.
- WP06 owns the cross-command OptionInfo class guard; this WP supplies context-specific behavior.

## Branch strategy

- Planning base / final merge target: `fix/cli-boundary-robustness`.
- Runtime selects a lane worktree after WP02 through `lanes.json`.
- Start with: `spec-kitty agent action implement WP03 --agent <name>`
- WP04 and WP05 may proceed in parallel because ownership is disjoint.

## Owned-file boundary

Modify only `context.py` and the new context boundary test. Do not edit the shared helper, architectural gate, agent context commands, or mission planning files.

## Subtasks and detailed guidance

### T011 – RED: context acceptance surface

Create `test_context_boundary_contract.py` and first capture the defects:

- Bare `spec-kitty context` and explicit `spec-kitty context info` have identical output and exit code for the same initialized-project/no-worktree fixture.
- Neither stream contains `OptionInfo`, `ArgumentInfo`, or the framework placeholder repr.
- `context info --workspace <missing> --json` emits parseable canonical error JSON only on stdout.
- Not-in-project JSON opts into WP02’s helper.
- Non-JSON error paths retain human-readable output.

Tie the first two to #4597 and the error cases to #4601 in test names/docstrings.

### T012 – Resolve callback defaults explicitly

Inspect the no-subcommand callback and the delegated `context info` function signature. When no subcommand was invoked, call the underlying behavior with actual Python defaults rather than forwarding Typer’s `OptionInfo` object.

Acceptance points:

- Bare and explicit command outputs match for content and exit code.
- Explicit flags continue to bind normally.
- No callee-wide type/sentinel workaround is introduced.
- Help/subcommand routing is unchanged.

### T013 – Adopt canonical JSON failures

Route every context-owned JSON error branch through WP02’s contract and console seam, including:

- unresolved workspace / missing worktree;
- project-root discovery;
- any sibling error path in this file that currently prints prose before JSON or returns a divergent mapping.

Use stable codes that name the domain condition (`workspace_not_found`, `no_worktree`, `repo_root_unresolved`, or the existing equivalent). JSON mode must not print a Rich prefix first.

### T014 – Route successful JSON through the transport seam

Replace owned bare `print(json.dumps(...))` output sites with the repository console JSON seam while keeping the parsed values exactly unchanged. Confirm serializer behavior for paths/enums already handled by surrounding code.

Do not redesign success envelopes, rename keys, or wrap a historically bare success object merely for symmetry.

### T015 – Parity and issue traceability

Complete the matrix across:

- bare callback versus explicit `info`;
- JSON success, JSON error, human success, and human error;
- initialized project without an active worktree;
- missing named workspace;
- outside-project root discovery.

Assert no traceback and no placeholder repr on any covered path. Keep issue numbers visible in regression identifiers so FR-012 is auditable.

## Test strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_context_boundary_contract.py -q
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_context_info.py tests/specify_cli/integration/test_context_lifecycle.py -q
ruff check src/specify_cli/cli/commands/context.py tests/specify_cli/cli/commands/test_context_boundary_contract.py
```

Also run the relevant whole-repo formatting/type gates before handoff.

## Definition of done

- Bare context is behaviorally identical to explicit context info.
- No placeholder reaches output or business logic.
- Every owned JSON error is canonical and stdout-clean.
- Existing success JSON parses to the same value as before.
- Human behavior and explicit options remain intact.
- Issue-pinned acceptance coverage is green.

## Risks and mitigations

- **Accidental success-shape change**: compare parsed old/new expectations, not desired symmetry.
- **Prose contamination**: assert raw stdout parses directly with `json.loads`.
- **Typer regression**: cover both bare callback and ordinary bound invocation.
- **Scope creep**: repeated errors may be consolidated only via the WP02 seam; do not refactor unrelated context resolution.

## Reviewer guidance

Inspect the callback invocation first. Then review every `json_output` branch in `context.py` for pre-output prose and bare print calls. Verify stable error codes and unchanged success values. Confirm the diff contains no local envelope constructor.

## Acceptance matrix

| Invocation | Fixture | Contract |
|---|---|---|
| `context` | initialized, no active worktree | identical to `context info`; no placeholder |
| `context info` | same fixture | existing human result |
| `context info --workspace missing --json` | initialized project | canonical error JSON only |
| `context info --json` | outside project | canonical root error JSON only |
| `context info --json` | resolvable context | unchanged success value |
| `context info` | error case | useful human stderr, historical exit |

## Stable-code guidance

- Reuse an existing machine code when it already names the same domain condition.
- Do not derive codes from exception class names.
- Keep code strings lowercase snake case.
- Message text may be human-readable but must not be the only branching signal.
- Do not expose absolute temporary paths unless the existing UX already requires them.

## Implementation evidence to retain

- Captured bare/explicit invocation output comparison.
- Raw stdout for each JSON error test.
- Parsed success payload comparison against the pre-change expectation.
- Test identifiers linking #4597 and #4601.
- Focused regression and existing context suite results.

## Explicit non-goals

- Do not redesign workspace resolution.
- Do not change agent-context commands in the sibling package.
- Do not standardize successful payloads across unrelated commands.
- Do not add an AST or signature-style policy test.
- Do not catch arbitrary exceptions and translate them to JSON.
- Do not change help text or subcommand registration unless required for parity.
- Do not edit WP02's helper or WP06's architectural gate.

## Self-review checklist

- [ ] Callback forwards concrete Python values.
- [ ] No sentinel coercion was added to the info callee.
- [ ] No JSON branch prints prose before the payload.
- [ ] No direct `print(json.dumps(...))` remains in an adopted path.
- [ ] Error codes are stable domain slugs.
- [ ] Success payload keys and nesting are unchanged.
- [ ] Human errors still make sense.
- [ ] Only owned files changed.

## Activity log

### 2026-09-16 – Prompt generated

Context adoption isolated into its own post-seam parallel lane.
