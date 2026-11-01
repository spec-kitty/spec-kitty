---
work_package_id: WP02
title: Two paths, one answer — parity guard, CLI proof and record
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- NFR-003
- C-003
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6278-human-slug-handle-parity
merge_target_branch: issue-6278-human-slug-handle-parity
branch_strategy: Planning artifacts for this mission were generated on issue-6278-human-slug-handle-parity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6278-human-slug-handle-parity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-human-slug-handle-parity-01M6BV06
base_commit: e2689fa73f08a40db9daa2c9592e4df74058842e
created_at: '2026-11-01T16:33:43.199800+00:00'
subtasks:
- T004
- T005
- T006
- T007
phase: Phase 2 - Parity and record
history:
- at: '2026-11-01T15:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/cli/commands/test_selector_resolution.py
create_intent:
- tests/specify_cli/cli/commands/agent/test_implement_mission_handle.py
- docs/changelog/unreleased/6278-human-slug-handle-parity.fixed.md
execution_mode: code_change
model: ''
owned_files:
- tests/specify_cli/cli/commands/test_selector_resolution.py
- tests/specify_cli/cli/commands/agent/test_implement_mission_handle.py
- src/specify_cli/cli/commands/implement.py
- docs/api/cli-commands.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6278'
---

# Work Package Prompt: WP02 – Two paths, one answer

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: claude

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (``spec-kitty agent tasks status --mission human-slug-handle-parity-01M6BV06`) and address every item before handing back.

## Objectives & Success Criteria

WP01 fixed the identity resolver. This WP proves the operator-visible half and stops the two
resolution paths from drifting again:

- **FR-004 / SC-002**: `implement WP01 --mission <human-slug>` resolves the Mission. The command
  resolves through `implement_phases.py::detect_mission_context` → `resolve_mission_handle`; pin that
  entry point, not the helper it calls.
- **FR-005 / SC-004**: one test asserts that `resolve_mission_handle` and the read-path bare-modern
  fold (`resolve_mission_dir_with_bare_modern_fold`, which wraps
  `mission_runtime.placement_seam(...).read_dir(PRIMARY_METADATA)`) return the **same mission
  directory** for every handle form the issue tabulates: human slug, composed slug, mid8. Plus a
  committed directory named exactly like the human slug (legacy), which must win at the
  exact-directory rung on both paths.
- **SC-003**: two Missions sharing a human slug produce the ambiguity outcome on both paths — the
  same rendered refusal with both candidates — and neither silently picks one.
- **T006/T007**: the user-facing surfaces say what they now do: `implement --mission`'s help text
  (today it reads "Mission slug (for example, 001-my-feature)", which describes the retired
  `NNN-` shape) and the changelog.

## Context

Read first:

1. `src/specify_cli/cli/selector_resolution.py` — `resolve_mission_handle` (the identity path) and
   `resolve_mission_dir_with_bare_modern_fold` (the #4723 read-path wrapper). Both render ambiguity
   into the same CLI envelope: `AmbiguousHandleError` from the ladder,
   `MissionSelectorAmbiguous` from the read path. **Assert on the rendered CLI outcome and the
   resolved directory, never on the exception class** — the two paths legitimately differ there, and
   pinning the class would pin an implementation detail instead of the operator contract.
2. `src/specify_cli/missions/_read_path_resolver.py::resolve_bare_modern_mission_dir_name` — the
   other path's fold: it globs `kitty-specs/<slug>-*/meta.json`, requires a valid mid8 tail, and
   raises on more than one match.
3. `src/specify_cli/cli/commands/implement_phases.py::detect_mission_context` — the implement entry
   point (`--mission` → `resolve_mission_handle` → `(mission_number, slug)`).
4. `tests/specify_cli/cli/commands/test_selector_resolution.py` — the existing CLI harness style
   (`CliRunner`, `setup_mocked_env`, `tmp_path` fixtures) and
   `tests/specify_cli/cli/commands/test_bare_modern_slug_ambiguity_cli.py` for the read-path
   ambiguity convention.
5. `docs/changelog/CHANGELOG.md` — the `[Unreleased]` section's entry style.

**C-003**: the issue's "Also seen" note about `--owned-checkout` status reads is out of scope. If
your parity test shows this WP's change already fixes that read, note it in the hand-back and in
the PR body; do not widen the diff to chase it.

## Subtasks

### T004 — CLI-level red first: `implement` accepts the human slug

New test file `tests/specify_cli/cli/commands/agent/test_implement_mission_handle.py` (or the
closest existing implement command test file if one already covers `detect_mission_context` — check
`tests/specify_cli/cli/commands/agent/` before adding a file).

Fixture: a temp project whose `kitty-specs/smoke-test-01M6BTQX/meta.json` carries
`mission_id: 01M6BTQX…`, `mission_slug: smoke-test-01M6BTQX`, `mission_type: software-dev`,
`target_branch: main`, `topology: lanes`.

- `detect_mission_context("smoke-test", repo_root)` returns `(None, "smoke-test-01M6BTQX")` — the
  composed slug, not the handle the operator typed.
- The same call with `"01M6BTQX"` and with `"smoke-test-01M6BTQX"` returns the identical tuple.
- A second Mission sharing the human slug makes the call raise `AmbiguousHandleError` (the
  non-CLI path reports the typed error; the CLI-level envelope is already covered by the
  existing selector-resolution tests).

Keep the test at the function seam: this file must not shell out to a real `spec-kitty implement`
run — the full command needs a git repo, a charter and a claim, and none of that is what this WP
is pinning. If an existing test already drives the `implement` Typer app against a temp project,
reuse that harness for the human-slug case instead of mocking.

### T005 — The two-path parity matrix

Add one parametrized test to `tests/specify_cli/cli/commands/test_selector_resolution.py` that, for
each handle form, resolves through both paths on the same `tmp_path` project and asserts the two
directories are equal:

| handle | fixture |
| --- | --- |
| `smoke-test` | `smoke-test-01M6BTQX` (mid8 `01M6BTQX`) — the reported defect |
| `smoke-test-01M6BTQX` | same |
| `01M6BTQX` | same |
| `083-foo-bar` and `foo-bar` | legacy `NNN-` mission, no mid8 tail |
| `plain` | a Mission directory named exactly `plain` (exact-directory rung on both paths) |

Then a second test for the ambiguity case: two Missions sharing `smoke-test`, asserting both paths
refuse and name both composed slugs, and that neither returns a directory.

`resolve_mission_dir_with_bare_modern_fold` prints and `sys.exit`s on refusal; assert the exit code
and the rendered message rather than the exception type (see Context §1). Use `capsys` or the
existing console capture helper in that file rather than letting output leak.

### T006 — `implement --mission` help text

`src/specify_cli/cli/commands/implement.py` declares
`--mission` as `help="Mission slug (for example, 001-my-feature)"`. That example is the retired
`NNN-` shape and is part of why operators do not know which handles work. Change the help to name
the accepted forms in one short line — the Mission's slug, its human slug (the slug without the
`-<mid8>` suffix), the `mid8`, or the full mission id — following the wording already used by
`src/specify_cli/cli/commands/mission_type.py` ("Mission handle: mission_id (ULID), mid8, or slug.")
so the two agree. If that help text is mirrored in a generated docs page under `docs/api/`, do not
regenerate the whole reference: check whether the page is generated, and if it is, say so in the
hand-back instead of rebuilding it (see the brief's shared-cache warning).

### T007 — `[Unreleased]` changelog entry

`docs/changelog/CHANGELOG.md` (the root `CHANGELOG.md` is a symlink to it). One entry, impact-first
bold lead with `(#6278)`, then before/after, under 1,200 characters, in the section's existing
style. Say what changes for an operator: `implement --mission <human-slug>` now resolves the same
Mission `agent tasks status` resolves, and two Missions sharing a human slug still fail loudly.

## Definition of Done

- T004's and T005's human-slug assertions are red before WP01's fix and green with it — if WP01 has
  already landed on this branch, prove the redness by reverting the rung locally, running the test,
  and restoring it (do not commit the revert).
- `uv run pytest tests/specify_cli/cli/commands/test_selector_resolution.py tests/specify_cli/cli/commands/agent/test_implement_mission_handle.py -q` is green.
- `uv run ruff check` and `uv run mypy` clean on every file you touched.
- The changelog entry passes whatever changelog guard the repo runs
  (`uv run pytest tests/ -k changelog` or the docs-lint target you find in `Makefile` — name the
  one you ran).
- No test asserts on a private helper, an exception class across the two paths, or a mock of the
  resolver; the assertions are about resolved directories and rendered refusals.
