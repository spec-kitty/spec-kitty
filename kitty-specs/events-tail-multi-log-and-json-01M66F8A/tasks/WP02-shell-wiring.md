---
work_package_id: WP02
title: Shell wiring --log selector and a meaningful --json
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-004
- FR-005
- FR-006
- FR-007
planning_base_branch: issue-6611-events-tail-multi-log-and-json
merge_target_branch: issue-6611-events-tail-multi-log-and-json
branch_strategy: Planning artifacts for this mission were generated on issue-6611-events-tail-multi-log-and-json. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6611-events-tail-multi-log-and-json unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
history:
- at: '2026-10-30T13:30:00Z'
  actor: maintainer-c
  event: created
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- tests/cli/test_events_tail_log_selector.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/events.py
- tests/cli/test_events_tail_log_selector.py
- tests/cli/test_events_tail_status_surface.py
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

Wire WP01's helper into the `events tail` CLI shell (#6611): add the `--log`
choice flag (default `status`), map `RunLogUnavailable` to the typed
`run_log_unavailable` stderr envelope, validate resume cursors against the
selected log, and flip `--json` from an accepted-but-unused flag to a real
opt-in — human-readable one-line summaries by default, byte-identical JSON
lines with `--json`. Red-first through the CLI entry point.

This WP touches ONLY `src/specify_cli/cli/commands/events.py` and the new
`tests/cli/test_events_tail_log_selector.py`.

## Context

- Spec: `kitty-specs/events-tail-multi-log-and-json-01M66F8A/spec.md`
  (FR-001/004/005/006/007; NFR-001..004; C-003, C-005).
- Contract: same dir, `contracts/cli-contract.md` — the authoritative option
  table, output shapes, refusal envelopes and the 9-row behavioral table.
- WP01 (dependency): `src/specify_cli/cli/commands/_events_tail_logs.py`
  exports the kind registry, `resolve_log_path`, `latest_run_journal` +
  `RunLogUnavailable`, and `render_event_line`.
- The existing command: `src/specify_cli/cli/commands/events.py` — read its
  full docstring first; the mission must preserve its architecture invariants
  (shell owns no loop and no direct `time.sleep`; errors via `_refuse` on
  STDERR; `--mission` only, C-003).
- Existing test pattern: `tests/cli/test_events_tail.py` — mounted-app
  CliRunner (`_root_app.add_typer(events_cli.app, name="events")`), autouse
  surface-mocking fixture, `--once`/`--max-events` termination discipline.
- `docs query`'s `--json` (`src/specify_cli/cli/commands/docs.py:184`) is the
  precedent for the flag semantics: default human, `--json` machine.

## Detailed guidance

### T005 — Red-first (write these tests BEFORE touching events.py)

In the new `tests/cli/test_events_tail_log_selector.py`
(`pytestmark = [pytest.mark.fast]`, mounted app, autouse surface fixture —
copy the shape from `test_events_tail.py`, do not import from it):

1. `--log decisions --once --json` on a fixture mission whose resolved
   surface has a `decisions.events.jsonl` with rows → expect the rows as JSON
   lines, exit 0. RED today: `--log` is an unknown option (exit 2).
2. Default output differs from `--json` output for the same log → RED today:
   the flag is a no-op, both outputs are identical JSON lines.

Run them, capture the failures (these are the defect reproductions for
#6611), then implement T006/T007 and turn them green. Keep the failing
assertions in the final file (they become the regression battery).

### T006 — `--log` flag, dispatch and refusals

- Add `log: str = typer.Option("status", "--log", help=...)` with Typer's
  choice validation over the seven kinds (unknown value → usage error, exit
  2, before any file access — contract row 8). The help text lists the kinds
  and names the default.
- Dispatch order (finding 2 from the post-tasks review): usage check →
  repo root → mission resolve → KIND DISPATCH → surface resolution (only
  for `status`/`decisions`, via the existing `_resolve_event_log_dir`)
  → log path resolution (incl. the `run` kind's refusal) → resume
  validation → stream. A broken coordination surface must NOT block the
  project-scoped (`ops`, `canonical`, `glossary`) or primary-partition
  (`mission`, `run`) kinds: `_resolve_event_log_dir` runs only when the
  kind is `status` or `decisions`, and its result is passed as the optional
  `surface_dir` to WP01's `resolve_log_path(repo_root, resolved, log,
  surface_dir)`. `status` keeps the exact existing behaviour (NFR-004): the
  path is `mission_event_log_path(surface_dir)` as before.
- Wrap the `run` kind's resolution: catch `RunLogUnavailable` and `raise
  _refuse("run_log_unavailable", str(exc), 1)` — same envelope shape/channel
  as the existing refusals (contract row 5). Nothing on stdout.
- `--from-offset`/`--from-invariant` validation is unchanged code, but now
  validates against the SELECTED log's path (FR-006): the existing
  `validate_resume_cursor(log_path, ...)` call simply receives the kind's
  path. The FR-004 usage check stays first, before any file access.

### T007 — the `--json` flip

- Change `json_output` to `typer.Option(False, "--json", help=...)` — default
  off. Remove the `noqa: ARG001` comment (the flag is now used).
- In both the `--once` and stream paths, print per event:
  - `--json`: `print(json.dumps(event))` — EXACTLY today's line (cursor keys
    included). Do not reformat, reorder or re-serialize differently.
  - default: `print(render_event_line(event))` (WP01's renderer).
- Update the flag help ("JSON lines for machine consumption; default is a
  one-line human-readable summary") and refresh the module docstring: the
  C-001 scope-lock sentence and the `--json` mentions must describe the new
  surface (`--log` kinds, human default); keep the core/shell and
  stderr-envelope doctrine text intact.
- Finding 1 from the post-tasks review: `tests/cli/test_events_tail_status_surface.py`
  asserts JSON on stdout via its `_tail` helper WITHOUT passing `--json` —
  after the flip those lines are human-rendered. Minimally update that
  suite (its `_tail` helper gains `--json`) keeping every
  surface-resolution assertion intact; this file is in `owned_files`.
- The default flip is user-facing: changelog and docs are handled by the
  mission close-out (NOT this WP) — do not edit CHANGELOG.md here.

### T008 — CLI test battery (extend the T005 file)

Cover the contract's behavioral table (fast, mocked resolution, `--once` or
small `--max-events` only — never an unbounded stream):

- Table-driven: for each of the seven kinds, `--log <kind> --once --json`
  reads the expected canonical path (fixture writes rows at that path; assert
  the rows appear). For `status`, additionally assert byte-identical output
  to the pre-change shape (NFR-004 pin: same `json.dumps` lines).
- `run`: two run dirs (mtime ordering) → newest wins; runs only for another
  mission → `run_log_unavailable` envelope on stderr, exit 1, empty stdout.
- Missing log (`glossary`/`ops`/`canonical` absent) → `--once` prints
  nothing, exit 0.
- Lazy surface resolution: `--log ops` (or `glossary`/`canonical`/
  `mission`/`run`) with a surface resolver that fails closed still tails the
  log (no `status_surface_unavailable`); `--log status` with the same
  broken surface still refuses with `status_surface_unavailable`.
- Corrupt interior JSON line: NOT re-tested here — the core reader's
  raise-on-corruption contract is unchanged (spec Edge Cases; finding 8).
- `--log decisions --from-offset <out-of-range>` → `invalid_resume_offset`
  envelope, exit 2. `--from-invariant` alone (any kind) → `usage_error`,
  exit 2.
- `--log bogus` → Typer usage error, exit 2.
- Human mode: an envelope-shaped event renders via the renderer's shape
  (assert the exact line — determinism), `log_truncated` renders as the
  warning line, and `--json` output for the same fixture differs from human
  output (the T005 red assertion, now green).

## Test strategy

All tests fast/mocked (`tests/cli/` selection: `-m "fast and not
windows_ci"`). No real git fixtures needed — reuse `test_events_tail.py`'s
monkeypatching of the surface resolver. Locally run:
`uv run pytest tests/cli/test_events_tail_log_selector.py
tests/cli/test_events_tail.py tests/cli/test_events_tail_status_surface.py`
(existing suites stay green — `test_events_tail.py` untouched,
`test_events_tail_status_surface.py` after its minimal owned `--json`
update), plus ruff/format and the repo's fast
type-check path for the touched module. No heavy suites
(NO_FULL_HEAVY_SUITES_IN_MISSION).

## Definition of Done

- The T005 red tests now pass, plus the full T008 battery; the
  pre-existing `tests/cli/test_events_tail.py` and
  `tests/cli/test_events_tail_real_fixture.py` suites stay green unchanged,
  and `tests/cli/test_events_tail_status_surface.py` stays green after its
  minimal `--json` update (finding 1).
- `events.py` carries the `--log` flag, the `run_log_unavailable` refusal, the
  `--json` flip, and an updated docstring; no loop, no direct `time.sleep`,
  stderr-only refusals, `--mission` only.
- No edits outside the two `owned_files` paths (helper module belongs to
  WP01; changelog/docs belong to the mission close-out).

## Risks / reviewer guidance

- Byte-stability: the `--json` path must print the identical
  `json.dumps(event)` line as before — any reordering or key change breaks
  scripted subscribers' cursor contract (NFR-004).
- Ordering of checks: usage check → repo root → mission resolve → kind
  dispatch → surface resolution (`status`/`decisions` only) → run resolution
  → resume validation → stream. The `run_log_unavailable` refusal must
  precede resume validation.
- Default flip is deliberate (C-005) but must be visible in the changelog at
  close-out — reviewer confirms no changelog edit snuck into this WP.
