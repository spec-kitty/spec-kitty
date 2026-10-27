---
work_package_id: WP03
title: doctor event-logs command and docs (#6610)
dependencies:
- WP02
requirement_refs:
- FR-006
- FR-012
- C-003
- C-004
- SC-004
- NFR-002
- NFR-003
planning_base_branch: issue-6610-local-event-log-retention
merge_target_branch: issue-6610-local-event-log-retention
branch_strategy: Planning artifacts for this mission were generated on issue-6610-local-event-log-retention. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6610-local-event-log-retention unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-local-event-log-retention-01M5ZCJP
base_commit: e6d24ca48bc1754eb36b6c560f41aacc02abc89a
created_at: '2026-10-27T21:43:19.732080+00:00'
subtasks:
- T011
- T012
- T013
- T014
phase: Phase 3 - Command
history:
- at: '2026-10-27T19:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/_event_logs_doctor.py
create_intent:
- src/specify_cli/cli/commands/_event_logs_doctor.py
- tests/cli/commands/test_doctor_event_logs.py
- docs/guides/how-to/clean-up-local-event-logs.md
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/_event_logs_doctor.py
- tests/cli/commands/test_doctor_event_logs.py
- docs/api/cli-commands.md
- docs/changelog/CHANGELOG.md
- docs/guides/how-to/clean-up-local-event-logs.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – `doctor event-logs` command and docs (#6610)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` via `spec-kitty agent tasks status`; address every item; record with `spec-kitty agent tasks add-history WP03 --note "..."`.

---

## Objectives & Success Criteria

`spec-kitty doctor event-logs [--apply] [--json]` exposes the WP02 engine. Preview is the default and changes nothing (FR-006); `--apply` deletes; the report lists every candidate and kept item with its reason; exit codes per FR-012 (0 preview / clean apply, 1 any failed deletion, 2 config or usage error). The CLI reference, a how-to page and the changelog document it (C-004).

## Context & Constraints

- Contract: `kitty-specs/local-event-log-retention-01M5ZCJP/contracts/doctor-event-logs.md` (JSON shape and exit codes — authoritative). Quickstart: `quickstart.md`.
- **C-003: do not edit `src/specify_cli/cli/commands/doctor.py`** (closed shim). Self-register via a sibling `src/specify_cli/cli/commands/_event_logs_doctor.py` exposing `register(app)`; `doctor._auto_discover_doctor_siblings()` imports every `_*_doctor.py`. Template: `_run_index_doctor.py`.
- Conventions: `--json` option text `"Machine-readable JSON output"`; shared `console` from `_doctor_shared`; project root via `_doctor_shared.resolve_project_root_or_exit(locate_project_root, json_output)`; JSON via `console.print_json(json.dumps(payload, indent=2))`.
- Docs rules (charter): one Divio quadrant per page declared in frontmatter, `updated: 2026-10-27`, plain language, Mission (never feature). Mirror the frontmatter of a neighbouring `docs/how-to/*.md` page; if `docs/` keeps an index/toc or page inventory (e.g. `docs/development/page-inventory.yaml`, `toc.yml`, `docs-retrieval-index.yaml`) that a docs test checks, add the page there too — run `tests/docs` to find out.
- Test placement: `tests/cli/commands/` (per-PR `cli` module). Not `tests/specify_cli/cli/commands/` (nightly only).

## Branch Strategy

- **Planning base branch**: `issue-6610-local-event-log-retention`
- **Merge target branch**: `issue-6610-local-event-log-retention`

Implement with `spec-kitty agent action implement WP03 --agent claude --mission local-event-log-retention-01M5ZCJP`.

## Subtasks & Detailed Guidance

### Subtask T011 – Red-first CLI tests (own commit)

`tests/cli/commands/test_doctor_event_logs.py`, using typer's `CliRunner` against the root app (find how neighbouring `tests/cli/commands/*doctor*` tests invoke `doctor` subcommands and reuse their project fixture). Reuse/extract the WP02 fixture builder if it lives in a shared helper; otherwise build a small fixture (one completed Mission with 2 old runs and `keep_runs: 1` / `max_age_days: 0`... note `max_age_days: 0` makes everything older than 0 days eligible — use explicit config to keep fixtures small).
1. Preview human output lists the candidate path and the word "Preview" (or equivalent) and the kept reasons; exit 0; tree unchanged.
2. `--json` preview: payload keys exactly as the contract (`applied`, `limits`, `candidates`, `kept`, `deleted`, `failed`, `removed_index_entries`); `applied` false; lists of dicts with `surface`, `kind`, `path`, `mission`, `age_days`, `reason`.
3. `--apply --json`: `applied` true, `deleted` holds the candidate paths, run dir gone, exit 0.
4. Invalid config (`keep_runs: -1`) → exit 2, nothing deleted, error names the key; with `--json`, an error payload (follow the doctor family's JSON error convention — check `_doctor_shared`).
5. A failed deletion (monkeypatch the engine delete helper to raise `OSError`) → exit 1, `failed` populated.
6. Nothing to clean → exit 0 and a clear "nothing to remove" line.
7. `spec-kitty doctor --help` lists `event-logs`.
Commit: `test(doctor): pin the doctor event-logs preview/apply contract (#6610)`.

### Subtask T012 – The subcommand

```python
def register(app: typer.Typer) -> None:
    @app.command(name="event-logs")
    def event_logs_command(
        apply: Annotated[bool, typer.Option("--apply", help="Delete the listed candidates (default: preview only)")] = False,
        json_output: Annotated[bool, typer.Option("--json", help="Machine-readable JSON output")] = False,
    ) -> None:
        """Preview, then prune, local run journals, event logs and caches past retention (ADR 2026-10-13-2 D-3).

        Reads ledger.retention (keep_runs, max_age_days) from .kittify/config.yaml.
        Committed ledgers, lock files, open or unknown Missions and locked items are never removed.

        Examples:
            spec-kitty doctor event-logs
            spec-kitty doctor event-logs --json
            spec-kitty doctor event-logs --apply
        """
```
- Body: resolve root → `load_retention_limits` (catch `RetentionConfigError` → print error, `typer.Exit(2)`) → `scan` → if `apply`: `apply_plan` → render → exit per FR-012.
- Split rendering into small helpers (`_render_human`, `_payload`) to stay ≤ complexity 15. Human output: a table or bullet list of candidates (path, surface, age, reason), a count line of kept items grouped by reason (list each kept item only with `--json`, or show them all if the list is short — your call, but every kept reason must be visible), and in preview a closing hint `Run with --apply to delete these N item(s).`
- Module docstring mirroring `_run_index_doctor.py`'s (what, how registered, that it mutates only with `--apply`). `__all__ = ["register"]`.

### Subtask T013 – CLI reference and generated surfaces

- `docs/api/cli-commands.md`: add `## spec-kitty doctor event-logs` in alphabetical position (between `env-file` and `identity`), same shape as neighbours (help output block). Run `tests/architectural/test_docs_cli_reference_parity.py`.
- Run `tests/architectural/test_completion_manifest_freshness.py`; if a completion manifest or help snapshot needs regenerating, use the repo's documented regeneration command (search the test's failure message / docstring) — never hand-edit generated files.
- `tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py` (nightly) may pin the doctor subcommand list; run it and update the golden via its documented regeneration path if it does.
- `tests/architectural/test_json_contract_enumeration.py` may require JSON-emitting commands to be enumerated; run it and follow its instructions.

### Subtask T014 – How-to and changelog

- `docs/guides/how-to/clean-up-local-event-logs.md` (add it to `docs/guides/how-to/` toc/index files too): Divio how-to; reader = an operator whose `.kittify/runtime/` has grown. Steps: preview, read reasons, tune `ledger.retention`, apply. A "What is never removed" list. Link ADR 2026-10-13-2.
- `docs/changelog/CHANGELOG.md` `[Unreleased]` → `### Added`: `- **\`spec-kitty doctor event-logs\` previews and prunes local run journals, event logs and caches past retention** (#6610, #5212). **Before:** ... **After:** ... **What to do:** ...` — and mention the per-surface cleanup policy in the state registry. Match the existing entry style exactly.

## Test Strategy

```bash
uv run --frozen pytest tests/cli/commands/test_doctor_event_logs.py -q
uv run --frozen pytest tests/architectural/test_docs_cli_reference_parity.py tests/architectural/test_completion_manifest_freshness.py tests/architectural/test_json_contract_enumeration.py tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py tests/specify_cli/cli/commands/test_run_index_doctor.py -q
uv run --frozen pytest tests/docs -q
make test-fast
```

## Risks & Mitigations

- Doctor's "1 = findings" convention differs from FR-012 (preview exits 0 even with candidates) — operator-confirmed; state it in the help text if helpful.
- Generated snapshots: regenerate, never hand-edit.

## Review Guidance

- `doctor.py` unchanged.
- JSON matches the contract exactly; exit codes per FR-012.
- Docs carry frontmatter + `updated`; changelog entry in `[Unreleased]`.

## Progress & Status

`spec-kitty agent tasks add-history WP03 --note "..."`; `spec-kitty agent tasks mark-status T011 --status done`.
