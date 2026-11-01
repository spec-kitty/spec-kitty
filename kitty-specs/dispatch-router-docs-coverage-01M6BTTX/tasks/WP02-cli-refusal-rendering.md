---
work_package_id: WP02
title: Human-readable dispatch refusal on the console
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
- T010
- T014
phase: Phase 2 - CLI
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/dispatch.py
- tests/specify_cli/invocation/cli/test_dispatch.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Human-readable dispatch refusal on the console

## ⚡ Do This First: Load Agent Profile

Load the agent profile in the frontmatter (`python-pedro`) before reading the rest of
this prompt, and behave according to its guidance.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Mode**: red-first.

---

## Objectives & Success Criteria

`spec-kitty dispatch` without `--json` now renders a refusal a human can act on (error
code, up to three candidate profiles, and the `--profile <id>` remedy) and exits 1 — on
the real (Op-opening) path, the `--dry-run` path, and the unknown-`--profile` refusal —
while the `--json` envelope keeps its five keys and shape (FR-007, FR-008). This WP also
carries the **CLI-level proof of the issue's own request** (FR-001), because a router
unit test alone does not exercise the command a user runs (T014).

Requirements: FR-001 (CLI proof), FR-004, FR-005, FR-006 (rendered), FR-007, FR-008.

## Context & Constraints

- **Authority file**: `src/specify_cli/cli/commands/dispatch.py` —
  `_emit_routing_error_and_exit`, `_dispatch_impl` (dry-run branch and real branch),
  `_render_dry_run_ambiguous_rich`, `_render_payload_capsule`.
- **The router decides, the CLI renders** (C-004). Do not recompute candidates, do not
  re-rank, do not re-derive a suggestion: read `e.error_code`, `e.candidates`,
  `e.suggestion` and print them.
- `--json` behaviour is contractual: the `routing_failed` envelope on stderr keeps
  `error`, `error_code`, `message`, `candidates`, `suggestion` and its exit code
  (FR-008). Adding fields is out of scope; changing a key is forbidden.
- The `ROUTER_AMBIGUOUS` **dry-run** path is exit 0 with a payload (FR-009 of that
  earlier mission) — do not change its exit code; only make sure the human rendering of
  the error paths is legible and consistent.
- **No new dependency** for console output: `rich`'s `console` is already imported in the
  module; reuse it rather than adding tabs/tables libraries.
- **No suppressions** (C-005).

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> Populated by `finalize-tasks`.

## Subtasks & Detailed Guidance

### Subtask T008 – RED: a refusal prints a raw JSON blob without `--json`

- **Purpose**: pin the readability defect through the CLI entry point.
- **Steps**: in `tests/specify_cli/invocation/cli/test_dispatch.py`, add a test that runs
  `dispatch "<no-match request>"` **without** `--json` against a registry fixture
  (reuse `_make_mock_registry` / `_run_with_registry`) and asserts: exit code 1; the
  output does **not** parse as a `routing_failed` JSON envelope; the output contains the
  error code, the candidate profile id and a `--profile` remedy; and the same holds for
  `--dry-run` without `--json`. Add the unknown-`--profile` case
  (`dispatch "x" --profile nonexistent` without `--json`) with the same three
  assertions. Add the sibling assertion that with `--json` the envelope still has exactly
  the five keys and `candidates` is populated.
- **Files**: `tests/specify_cli/invocation/cli/test_dispatch.py`.
- **Validation**: the non-`--json` assertions MUST fail before T009.

### Subtask T009 – Human rendering for every refusal path

- **Purpose**: make the refusals legible without weakening the machine path (FR-007).
- **Steps**: split `_emit_routing_error_and_exit` into a JSON emitter (unchanged
  behaviour for `--json`) and a console renderer that prints, via `console.print`: the
  error code, one line per candidate (`id (action) — match_reason`), and the suggestion
  (which already carries the runnable `--profile` command). Keep exit code 1 in both
  modes. Route **three** call sites through the same renderer so they cannot drift: the
  dry-run `ROUTER_NO_MATCH` branch, the real-path `RouterAmbiguityError` handler, and
  `profile_not_found_routing` (an unknown `--profile` is a refused dispatch too, and it
  currently dumps raw JSON in human mode as well). Keep
  `_render_dry_run_ambiguous_rich` (exit-0 payload path) as it is, or align its wording
  with the new renderer — but do not change its exit code.
- **Files**: `src/specify_cli/cli/commands/dispatch.py`.
- **Validation**: T008 green (including its unknown-`--profile` case); the existing
  dispatch suite green.

### Subtask T010 – CLI-surface assertions for candidates and tied ids

- **Purpose**: prove the rendered remedy is the router's (FR-004, FR-005, FR-006).
- **Steps**: extend the CLI tests so that the rendered output for a no-match names the
  same ids the router reported, and that a tied fixture's `ROUTER_AMBIGUOUS` rendering
  (both `--json` and console) names every tied id with a `--profile` command for each.
  Assert the *envelope's* `candidates`/`suggestion` values, not a hard-coded sentence, so
  the test does not pin prose that lives in the router.
- **Files**: `tests/specify_cli/invocation/cli/test_dispatch.py`.
- **Validation**: all green.

### Subtask T014 – The issue's own request, through the command

- **Purpose**: FR-001/SC-001 are about `spec-kitty dispatch`, not about `route()`; prove
  the reported request end-to-end at the CLI.
- **Steps**: in `tests/specify_cli/invocation/cli/test_dispatch.py`, add a test that copies
  `packs/built-in/agent_profiles/*.agent.yaml` into `.kittify/profiles/` (the shipped-catalog
  pattern from `test_writing_comms_routing.py`), writes the configured-charter stub with the
  existing `_write_configured_charter` helper (without it the empty-charter fallback answers
  `generic-agent`), builds a **real** `ProfileRegistry(project)`, and runs
  `dispatch "mark ADR-0068 Accepted and regenerate the ADR index" --dry-run --json`.
  Assert: exit 0, `status == "dry_run"`, `profile_id == "curator-carla"`,
  `router_confidence == "domain_keyword"`, and `alternatives` is a list. Add the second
  assertion that `"index the invoice table"` through the same command still exits 1 with
  `ROUTER_NO_MATCH` (FR-002 at the CLI).
- **Files**: `tests/specify_cli/invocation/cli/test_dispatch.py`.
- **Validation**: the first assertion MUST fail (exit 1, `ROUTER_NO_MATCH`) before WP01's
  router change — this subtask depends on WP01; the invoice-table assertion is green before
  and after.

## Validation

```bash
uv run pytest tests/specify_cli/invocation/cli/test_dispatch.py -q
uv run pytest tests/specify_cli/invocation/cli/ -q
```

Also run the issue's request through the real command with the shipped catalog and paste
the output in the PR:

```bash
uv run spec-kitty dispatch "mark ADR-0068 Accepted and regenerate the ADR index" --dry-run
```

## Definition of Done

- T008 observed RED first (no-match, dry-run, and unknown-`--profile` cases).
- No `--json` refusal prints no JSON envelope and names code, candidates and remedy.
- `--json` envelope unchanged in keys/shape, `candidates` populated.
- Exit codes unchanged: 1 for both refusal kinds on the real and dry-run error paths and
  for an unknown `--profile`, 0 for the dry-run ambiguous payload.
- The reported request routes through `dispatch --dry-run --json` on the shipped catalog.
- No suppression, no new dependency, no unrelated refactor.

## Risks & Mitigations

- **Path drift** between the dry-run and real error handlers → one shared renderer.
- **Prose pinning** in tests → assert ids/values from the router, not sentences.
- **Rich markup leaking into `--json`** → the JSON path never touches `console`.
