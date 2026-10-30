# Research — events tail multi-log selector and a meaningful --json

Discovery findings for issue spec-kitty/spec-kitty#6611, recorded before
specification. All paths relative to the repository root unless absolute.

## Grounding: the issue is live on current main (512567eee7)

- `src/specify_cli/cli/commands/events.py` still tails only
  `status.events.jsonl` via `mission_event_log_path()` on the resolved status
  surface; there is no log selector.
- Its `--json` option is accepted but unused (`json_output` parameter carries
  `# noqa: ARG001 -- accepted-but-unused flag`); no human-readable mode exists.
- Nothing on main supersedes it: `git log -S "ARG001 -- accepted-but-unused"`
  over `events.py` shows only the original command commit (2870a1d2ec) and the
  #5466 surface fix (ffac51ce91). The changelog has no entry for a `--log`
  selector.
- Gap-table row G-10 in `docs/architecture/event-ledger-writers-and-readers.md`
  tracks exactly this ("Extend tail to the other logs once G-1 names them").

## Blocking dependencies are all resolved

- spec-kitty/spec-kitty#6603 (EventBridge port + writes gate) is closed: the
  gate `tests/architectural/test_event_log_writes_gate.py` now names the log
  families (`LOG_FAMILIES`), so the selector can list canonical kinds.
- The issue's 2026-10-27 "parked: WAIT for spec-kitty-events#92" note is
  discharged: spec-kitty/spec-kitty-events#92 (CloudEvents envelope, type
  registry, schemas) is closed.
- #5466 (tail reads the primary checkout's log on a coord mission) is closed;
  `events tail` already resolves through `resolve_surface_dir_or_typed_error`.
- The issue's cross-reference comment asks that #5466 stay a distinct bug; it
  is closed, and this mission builds on its resolver rather than reopening it.

## Evidence: where each canonical log lives on disk

Writers verified in `src/`:

| Kind | Canonical path | Writer evidence |
|------|----------------|------------------|
| status | `<resolved status surface>/status.events.jsonl` | `src/specify_cli/status/store.py` `EVENTS_FILENAME`; the tail's existing behavior |
| decisions | `<mission_dir>/decisions.events.jsonl` | `src/specify_cli/events/decision_log.py:144` (`mission_dir / "decisions.events.jsonl"`); COORD-partition like status (`src/mission_runtime/artifacts.py` `DECISION_LOG`) |
| mission (v1) | `<feature_dir>/mission-events.jsonl` | `src/runtime/next/runtime_bridge_composition.py:352` |
| run | `runs_root(repo_root)/<run_id>/run.events.jsonl` (`.kittify/runtime/runs/`) | `src/runtime/next/_internal_runtime/engine.py:108`; the runs dir comes from the canonical `src/runtime/next/run_index.py` `runs_root(repo_root)`; the sibling `state.json` `MissionRunSnapshot` carries `mission_id`/`mission_slug` (optional for legacy rows) |
| glossary | `.kittify/events/glossary/<mission_id>.events.jsonl` | writer: `src/glossary/events.py` (`get_event_log_path` → `sanitize_mission_id(mission_id)`); `ResolvedMission.mission_id` is a validated 26-char ULID on which sanitization is identity, so the join is exact. Do NOT reuse `get_event_log_path` in the reader: it has an `mkdir` side effect |
| ops | `kitty-ops/lifecycle.jsonl` | `src/specify_cli/invocation/lifecycle.py` `LIFECYCLE_LOG_RELATIVE_PATH` |
| canonical | `.kittify/canonical-events.jsonl` | `src/specify_cli/status/lifecycle_events.py` `PROJECT_EVENTS_FILENAME` |

`ResolvedMission` (`context/mission_resolver.py`) carries `mission_id`,
`mission_slug`, `feature_dir`, `mid8` — enough to join every mission-scoped
kind without new resolution code (C-002).

## Decisions reached

1. **Selector is a closed enum (`--log`), default `status`.** The kinds are
   exactly the ledger kinds the #6603 gate names that the issue's problem
   statement lists, plus the existing default. ops-index / op-closures /
   propagation-errors / policy-audit / archive-registry / encoding-provenance
   stay out of scope (proportionality; they are bookkeeping indexes more than
   subscriber streams). Deferred, named in the PR.
2. **`decisions` joins onto the same resolved status surface as `status`.**
   The existing shell docstring anticipates this ("Returns the directory
   rather than the file so a later log selector (#6611) can join another log
   name onto the same resolution"), and both streams are COORD-partition.
3. **`run` resolves the mission's latest run journal** by scanning
   `.kittify/runtime/runs/*/state.json` for a `mission_id` (or legacy
   `mission_slug`) match and taking the most recently modified
   `run.events.jsonl`; a no-match is a typed `run_log_unavailable` refusal,
   never a silent tail of another mission's run. No `--run-id` flag in this
   mission (proportionality; latest-run is the natural subscriber default).
4. **`--json` flips to opt-in with a human-readable default**, following the
   `docs query --json` precedent (`cli/commands/docs.py`: default table,
   `--json` plain-print JSON). Accepted pre-GA (4.0.0rc); the default flip is
   called out in the changelog. `--json` output stays byte-identical to
   today's (cursor contract: `tail_offset`/`tail_invariant` remain).
5. **Human rendering is plain `print`, deterministic** — timestamp, event
   type, compact sorted payload; reader-injected cursor keys omitted;
   `log_truncated` rendered as a visible warning line. No Rich markup on
   stdout (NFR-002, mirrors the `docs query` piped-output contract).
6. **The core (`status/tail_reader.py`) is untouched.** It is already
   path-generic; the mission only feeds it different paths (C-004).

## Open questions resolved during specification

- Default output flip vs keeping JSON default: resolved to flip (issue asks
  for a human-readable mode so `--json` means something; `docs query`
  precedent; pre-GA window).
- Multiple runs per mission: resolved to latest-by-mtime with typed refusal
  on no match (see decision 3).

## Reproduction (red-first target)

The pre-existing entry point is `spec-kitty events tail --mission <slug>` (the
Typer command in `cli/commands/events.py`, mounted as `events tail`).
Red tests, through `CliRunner` on the mounted app (the pattern of
`tests/cli/test_events_tail.py`):

- `--log decisions --once --json` on a fixture mission with a decision log —
  fails today (no such option).
- default (no `--json`) human output differs from `--json` output — fails
  today (flag is a no-op).

## Phase 0 addendum (plan step, 2026-10-30)

- No new research tasks: every unknown named in the spec's Technical Context
  is discharged by the discovery findings above (verified writer paths,
  resolved dependencies, recorded design decisions). No `[NEEDS CLARIFICATION]`
  markers remain.
- Red-test plan confirmed: extend the WP04 test pattern
  (`tests/cli/test_events_tail.py`'s mounted-app CliRunner) in a new sibling
  file `tests/cli/test_events_tail_log_selector.py`; the first red assertions
  are the `--log` option's existence (unknown-option failure today) and the
  default-vs-`--json` output difference (no-op flag today).
- Supply-chain: no dependency is added, upgraded or removed — the
  supply-chain planning section does not apply.

## Post-tasks review round (2026-10-30, reviewer-renata squad) — accepted findings

All eight findings accepted and folded into the artifacts. Recorded decisions:

- **Run resolution vs the RunIndex (finding 3).** The runs dir comes from the
  canonical `src/runtime/next/run_index.py` `runs_root(repo_root)` — no
  literal re-spelling of the join. The mission→run relationship is derived by
  scanning each run dir's `state.json` rather than reading
  `feature-runs.json`: the index records the CURRENT run per mission, while
  this subscriber wants the most recently modified journal across ALL runs of
  the mission (including historical ones). Divergence policy: where the two
  disagree (an older run whose journal was touched last), latest-by-mtime
  wins — the subscriber follows writes, not the index's current-run pointer.
- **Lazy status-surface resolution (finding 2).** Only the `status` and
  `decisions` kinds consume the resolved status surface; project-scoped and
  primary-partition kinds must not fail because a coordination surface is
  broken. The shell dispatches on kind first; `resolve_log_path` takes
  `surface_dir: Path | None` and only those two kinds read it.
- **`test_events_tail_status_surface.py` (finding 1).** That suite asserts
  JSON on stdout without passing `--json`; after the default flip it needs a
  minimal update (its `_tail` helper gains `--json`), owned by WP02 with the
  surface-resolution assertions intact.
- **Changelog/docs obligations (finding 4)** are concretely owned by the
  mission close-out (driver-owned, see tasks.md): CHANGELOG `[Unreleased]`,
  regenerating `docs/api/cli-commands.md` via
  `scripts/docs/build_cli_reference.py` (HELP-DRIFT gate +
  `tests/architectural/test_docs_cli_reference_parity.py`), the Tail-envelope
  wording in `docs/context/system-events.md`, and gap-table row G-10 in
  `docs/architecture/event-ledger-writers-and-readers.md`.
- **Glossary writer (finding 5):** `src/glossary/events.py`; sanitization is
  identity on a validated ULID; `get_event_log_path` is not reused (mkdir
  side effect in a read path).
- **Renderer truncation (finding 7)** is now part of the CLI contract
  (human-mode lines truncate at 400 chars with a trailing `...`).
- **Corrupt-line edge (finding 8):** declared unchanged core contract;
  explicitly not re-tested in this mission.
