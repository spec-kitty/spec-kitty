---
work_package_id: WP01
title: Log-kind helper module (_events_tail_logs.py)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-007
planning_base_branch: issue-6611-events-tail-multi-log-and-json
merge_target_branch: issue-6611-events-tail-multi-log-and-json
branch_strategy: Planning artifacts for this mission were generated on issue-6611-events-tail-multi-log-and-json. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6611-events-tail-multi-log-and-json unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
history:
- at: '2026-10-30T13:30:00Z'
  actor: maintainer-c
  event: created
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- src/specify_cli/cli/commands/_events_tail_logs.py
- tests/cli/test_events_tail_logs_unit.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/_events_tail_logs.py
- tests/cli/test_events_tail_logs_unit.py
role: implementer
tags: []
tracker_refs:
- spec-kitty/spec-kitty#6611
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile:

```
/spk-charter-profile-load python-pedro
```

(or run `spec-kitty agent profile show python-pedro` and adopt its rules)
Adopt its directives and tactics (spec fidelity, locality, canonical-sources
reuse, close-defect-by-construction, anti-scaffold testing) for the whole WP.
State which you applied in your handoff note.

## Objective

Build `src/specify_cli/cli/commands/_events_tail_logs.py` — the private helper
behind `spec-kitty events tail`'s new `--log` selector (#6611): the closed
kind registry, per-kind path resolution (including latest-run journal
selection with its typed refusal), and the deterministic human-readable event
renderer. Plus fast unit tests for all of it.

This WP touches ONLY the new helper module and its unit tests. The CLI shell
(`events.py`) is WP02's; the core reader (`status/tail_reader.py`) is
untouched by the whole mission (spec C-004).

## Context

- Spec: `kitty-specs/events-tail-multi-log-and-json-01M66F8A/spec.md`
  (FR-001/002/003/004/007; constraints C-001, C-002, C-004).
- Plan: same dir, `plan.md` (design decisions 1–3) and `data-model.md` (the
  LogKind table — the authoritative resolution rules).
- CLI contract: same dir, `contracts/cli-contract.md` (kinds, paths, refusal
  envelopes, both output shapes).
- Research: same dir, `research.md` — every kind's path is verified against
  its writer; read the "Evidence" table before coding.
- Existing shell to study (do NOT edit): `src/specify_cli/cli/commands/events.py`
  — note `_resolve_event_log_dir`'s docstring: it returns the directory "so a
  later log selector (#6611) can join another log name onto the same
  resolution".
- Existing test pattern to study (do NOT edit here):
  `tests/cli/test_events_tail.py` — mounted-app CliRunner, autouse
  surface-mocking fixture.

## Detailed guidance

### T001 — Kind registry and `resolve_log_path`

- A module-level frozen mapping `LOG_KINDS` (or a `StrEnum`/`frozenset` +
  resolver) holding exactly: `status`, `decisions`, `mission`, `run`,
  `glossary`, `ops`, `canonical` (spec C-001 — closed set; no more, no less).
- `resolve_log_path(repo_root: Path, resolved: ResolvedMission, kind: str,
  surface_dir: Path) -> Path`:
  - `status` → `mission_event_log_path(surface_dir)` (reuse the existing
    helper from `specify_cli.status`; do not re-spell the filename).
  - `decisions` → `surface_dir / "decisions.events.jsonl"` (same resolved
    surface — both streams are COORD-partition; see
    `events/decision_log.py:144` for the writer's join).
  - `mission` → `resolved.feature_dir / "mission-events.jsonl"`.
  - `glossary` → `repo_root / ".kittify" / "events" / "glossary" /
    f"{resolved.mission_id}.events.jsonl"`.
  - `ops` → `repo_root / "kitty-ops" / "lifecycle.jsonl"`.
  - `canonical` → `repo_root / ".kittify" / "canonical-events.jsonl"`.
  - `run` → delegate to the T002 helper.
  - Unknown kind → `ValueError` (the shell's Typer choice already rejects it
    earlier; this is defense in depth, not the usage-error path).
- No new resolution code: every rule is a join over `repo_root`,
  `resolved`, or the caller-provided `surface_dir` (C-002). The helper takes
  `surface_dir` as a parameter precisely so the shell keeps owning the
  topology-aware surface resolution and its failure modes.

### T002 — Latest-run resolution and the typed refusal

- `latest_run_journal(repo_root: Path, resolved: ResolvedMission) -> Path`
  raising `RunLogUnavailable` (a small local exception carrying a
  human-readable detail) when no run belongs to the mission.
- Scan `<repo_root>/.kittify/runtime/runs/*/`: for each run dir, read
  `state.json` (the `MissionRunSnapshot` shape — see
  `runtime/next/_internal_runtime/engine.py`); a run matches when its
  `mission_id` equals `resolved.mission_id`, OR (legacy rows where
  `mission_id` is null/absent) its `mission_slug` equals
  `resolved.mission_slug`. Among matching run dirs that have a
  `run.events.jsonl`, return the one whose `run.events.jsonl` has the most
  recent mtime. Skip unreadable/missing `state.json` silently (edge case in
  the spec: skipped, never fatal). Missing runs dir or no matches → raise
  `RunLogUnavailable` naming the mission and the runs dir.
- Never return a journal belonging to another mission (spec FR-007).

### T003 — Human renderer

- `render_event_line(event: Mapping[str, Any]) -> str` — deterministic,
  plain text (no Rich, no ANSI):
  - timestamp: first present of `timestamp`, `at`, else `-`.
  - kind: first present of `event_type`, `type`, else `-`.
  - remainder: the event's `payload` if it is a mapping, else the event minus
    the consumed keys (`timestamp`, `at`, `event_type`, `type`) — rendered as
    `json.dumps(..., sort_keys=True, default=str)`.
  - Always omit the reader-injected cursor keys `tail_offset` and
    `tail_invariant` (they are cursor plumbing, not content).
  - A `log_truncated` signal (type == `"log_truncated"`) renders as
    `log truncated (<reason>) at offset <detected_at_offset> — resynced from offset 0`.
  - Truncate long lines at 400 characters with a trailing `...` so a huge
    payload cannot flood a terminal (keep it generous; the JSON mode is the
    machine channel).
- Determinism is an NFR: same dict in, same string out.

### T004 — Unit tests (`tests/cli/test_events_tail_logs_unit.py`)

- New file, `pytestmark = [pytest.mark.fast]`, mirroring the sibling CLI test
  files' marker discipline (collected by `fast-tests-cli`).
- Table-driven: for every kind, a `tmp_path` fixture mission resolves to the
  exact canonical path from `data-model.md` (build a fake `ResolvedMission`
  and surface dir; no CLI, no mocking of resolution — the helper takes them
  as parameters).
- Run resolution: two matching run dirs (older/newer mtime via
  `os.utime`), a legacy run dir matched only by `mission_slug`, a foreign
  mission's run dir (must NOT be selected), an unreadable `state.json`
  (skipped), empty runs dir and missing runs dir (both raise
  `RunLogUnavailable`).
- Renderer: envelope-shaped event (`event_type`/`timestamp`/`payload`),
  status-shaped event (`type`/`at`), cursor-key omission, `log_truncated`
  line, determinism (render twice, assert equal), long-line truncation.
- Anti-scaffold: assert on real behaviour (paths, raised types, rendered
  strings), never on `called_once` mocks.

## Test strategy

Unit tests only in this WP (fast, `tmp_path`, no git fixtures). The
end-to-end CLI battery is WP02's. Do not run heavy suites
(NO_FULL_HEAVY_SUITES_IN_MISSION); `uv run pytest tests/cli/test_events_tail_logs_unit.py`
plus `uv run ruff check src/specify_cli/cli/commands/_events_tail_logs.py tests/cli/test_events_tail_logs_unit.py`
and `uv run mypy src/specify_cli/cli/commands/_events_tail_logs.py` (if the
repo's mypy config covers this path) are enough locally.

## Definition of Done

- `_events_tail_logs.py` exists with the closed registry, `resolve_log_path`,
  `latest_run_journal` + `RunLogUnavailable`, and `render_event_line`, each
  documented with a docstring citing its writer/contract (the repo's
  docstring density is a house style — see `events.py`).
- `tests/cli/test_events_tail_logs_unit.py` green; ruff/format clean.
- No edits outside the two `owned_files` paths.
- No changes to `events.py` or `status/tail_reader.py`.

## Risks / reviewer guidance

- Biggest risk: inventing a second resolution authority. Reviewer: every path
  join must trace to a writer named in `research.md`; no `Path.cwd()` use
  (repo_root is a parameter); no re-derivation of the status surface.
- Run matching: confirm a foreign mission's journal can never be returned and
  that `mission_id` takes precedence over the slug fallback.
- Renderer: confirm no Rich import and no ANSI escape can reach the string.
