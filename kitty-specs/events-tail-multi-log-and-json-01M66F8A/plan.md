# Implementation Plan: events tail multi-log selector and a meaningful --json

**Branch**: `issue-6611-events-tail-multi-log-and-json` | **Date**: 2026-10-30 | **Spec**: `spec.md`
**Input**: Mission specification from `kitty-specs/events-tail-multi-log-and-json-01M66F8A/spec.md` (issue spec-kitty/spec-kitty#6611)

## Summary

`spec-kitty events tail` — ADR 2026-10-13-2 D-2's local subscriber — gains a
`--log <kind>` selector over the canonical ledger kinds (`status` default,
`decisions`, `mission`, `run`, `glossary`, `ops`, `canonical`), and its dead
`--json` flag becomes meaningful: human-readable one-line summaries by default,
`--json` opts into today's byte-identical JSON-lines envelope (the
`docs query --json` precedent). The core reader (`status/tail_reader.py`) is
already path-generic and stays untouched; the change is confined to the CLI
shell plus a small private helper module for kind resolution and rendering.

Primary requirement source: spec.md FR-001…FR-007; technical grounding in
`research.md` (verified writer paths for every kind).

## Technical Context

**Language/Version**: Python 3.11+ (repo standard; `src/` layout, uv-managed).
**Primary Dependencies**: Typer (CLI shell, already used by `events.py`), the
existing resolution seams — `resolve_mission_handle`,
`resolve_surface_dir_or_typed_error`, `locate_project_root` — and the core
reader `status/tail_reader.py` (`poll_once`, `tail_events`,
`validate_resume_cursor`, `TailCursor`). No new dependencies.
**Storage**: N/A — the mission only reads existing JSON-lines ledgers.
**Testing**: pytest + Typer `CliRunner` on the mounted `events.app` (the exact
pattern of `tests/cli/test_events_tail.py`: a throwaway root Typer app, because
CliRunner collapses a standalone single-command app). New fast/mocked tests in a
new sibling file; red-first through the CLI entry point.
**Target Platform**: the `spec-kitty` CLI (POSIX + Windows; plain `print`
output, no Rich markup on stdout in human mode).
**Project Type**: single (CLI command surface in `src/specify_cli/cli/`).
**Performance Goals**: N/A — a subscriber poll loop at the core's fixed 0.25 s
interval; run-journal matching scans at most the runs directory once at startup.
**Constraints**: shell gains no poll loop and no direct `time.sleep` (NFR-001);
`--json` output byte-identical to main for the status kind (NFR-004); human
rendering deterministic (NFR-003).
**Scale/Scope**: one command module, one new private helper module, one new
test file, changelog + one docs page touch. Small mission, single lane.

### Design decisions (from research.md)

1. **Kind registry in a new private helper** —
   `src/specify_cli/cli/commands/_events_tail_logs.py` holds the closed kind
   enum, the per-kind path resolution and the human renderer. `events.py`
   stays the thin shell (flag surface, dispatch). Mirrors the
   `cli/commands/_<name>.py` private-helper convention. The core stays
   path-generic and untouched (C-004).
2. **Resolution rules** (all joins, no new resolution code, C-002):
   - `status` (default): resolved status surface dir + `status.events.jsonl`
     (unchanged — `mission_event_log_path`).
   - `decisions`: the same resolved surface dir + `decisions.events.jsonl`
     (both streams are COORD-partition; the existing shell docstring
     anticipates joining onto the same resolution).
   - `mission`: `resolved.feature_dir` + `mission-events.jsonl` (Mission v1).
   - `run`: scan `<repo_root>/.kittify/runtime/runs/*/state.json` for
     `mission_id` (fallback `mission_slug` for legacy rows), take the most
     recently modified `run.events.jsonl` among matches; skip unreadable
     state.json; typed `run_log_unavailable` refusal (stderr envelope, exit 1)
     when no run belongs to the mission. Never tail another mission's run.
   - `glossary`: `<repo_root>/.kittify/events/glossary/<mission_id>.events.jsonl`.
   - `ops`: `<repo_root>/kitty-ops/lifecycle.jsonl` (Op lifecycle log).
   - `canonical`: `<repo_root>/.kittify/canonical-events.jsonl`.
   - Unknown kind: Typer choice validation (usage error, exit 2) before any
     file access.
3. **Output modes**: `--json` flips from a default-True no-op to a
   default-False opt-in. Human mode (default) renders one plain-`print` line
   per event: `<timestamp|at|-> <event_type|type|-> <compact sorted payload>`;
   reader-injected `tail_offset`/`tail_invariant` keys are omitted;
   `log_truncated` signals render as `log truncated (<reason>) at offset <n> —
   resynced from offset 0`. JSON mode prints exactly today's
   `print(json.dumps(event))` lines (cursor keys included).
4. **Resume carry-over**: `--from-offset`/`--from-invariant` validate against
   the selected log's path — the existing `validate_resume_cursor` call, fed a
   different path; refusal envelopes unchanged.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — pass. The kind registry is the one owner of
  the selector vocabulary; path joins reuse the existing resolution seams
  rather than re-deriving surfaces (no second source of truth for where a
  ledger lives — each rule cites its writer in `research.md`).
- **Architectural alignment / core-vs-shell** — pass. The loop-owning core is
  untouched; the shell gains only flags, resolution joins and rendering
  (NFR-001 keeps the shell loop-free).
- **ATDD-first** — pass. Red tests through the CLI entry point precede the fix
  (DIRECTIVE_034); the repro targets a P3 defect, so no `p0_repro` marker.
- **Terminology canon** — pass. `--mission` only; kind names are the writers'
  own file names (`status`, `decisions`, `mission`, `run`, `glossary`, `ops`,
  `canonical`).
- **Locality / smallest viable diff** — pass. Two source files, one test file;
  no opportunistic refactors beyond the touched lines (DIRECTIVE_024/025
  tension resolved toward locality; `--json` flag semantics change is the issue
  itself, not scope creep).
- **No full heavy suites in mission** — pass. Fast CLI tests + targeted status
  tests only; CI owns the rest.
- Post-Phase-1 re-check: design adds no contract beyond the CLI surface in
  `contracts/cli-contract.md`; no new gates violated.

## Project Structure

### Documentation (this mission)

```
kitty-specs/events-tail-multi-log-and-json-01M66F8A/
├── plan.md              # This file
├── research.md          # Discovery + Phase 0 (extended, not replaced)
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── cli-contract.md  # Phase 1 output: the events tail CLI contract
└── tasks.md             # /spec-kitty.tasks output (later)
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/
├── events.py                 # Shell: --log flag, --json flip, dispatch (edited)
└── _events_tail_logs.py      # NEW: kind registry, path resolution, run
                              # matching, human renderer (private helper)

tests/cli/
└── test_events_tail_log_selector.py   # NEW: fast, mocked-resolution tests
                                        # (kinds, modes, run selection,
                                        # refusals, resume carry-over)

docs/
├── changelog/CHANGELOG.md    # [Unreleased] entry (user-facing)
└── (events tail docs page, if one exists — see quickstart.md)
```

**Structure Decision**: single-project CLI surface; the private helper follows
the `cli/commands/_<name>.py` convention (like `_event_logs_doctor.py`). The
new test file is a sibling of `test_events_tail.py`, keeping the WP04 file's
mission-scoped doctrine header untouched.

## Complexity Tracking

*No Charter Check violations — table empty.*

## Implementation Concern Map

### IC-01 — Log-kind registry and per-kind path resolution

- **Purpose**: Own the closed `--log` vocabulary and resolve each kind to its
  canonical ledger path, including latest-run selection and its typed refusal.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-007; C-001, C-002, C-004.
- **Affected surfaces**: `src/specify_cli/cli/commands/_events_tail_logs.py`
  (new), `src/specify_cli/cli/commands/events.py` (flag + dispatch),
  `tests/cli/test_events_tail_log_selector.py` (new).
- **Sequencing/depends-on**: none (first concern).
- **Risks**: run-journal matching must never pick another mission's run
  (typed refusal covers it); coordination-routed missions resolve `decisions`
  through the same surface resolver as `status` (reuse, do not re-derive).

### IC-02 — Output modes: human-readable default, `--json` opt-in

- **Purpose**: Make `--json` change the output — deterministic one-line human
  summaries by default, byte-identical JSON lines with `--json`.
- **Relevant requirements**: FR-004, FR-005; NFR-002, NFR-003, NFR-004; C-005.
- **Affected surfaces**: `src/specify_cli/cli/commands/events.py` (print
  sites), `src/specify_cli/cli/commands/_events_tail_logs.py` (renderer),
  `tests/cli/test_events_tail_log_selector.py`.
- **Sequencing/depends-on**: IC-01 (the renderer is exercised through kinds,
  but is independent of resolution; same files → same lane, sequential edits).
- **Risks**: default output flip is user-visible (changelog before/after);
  `--json` must stay byte-identical for scripted consumers (pinned by test).

### IC-03 — Resume and refusal semantics on every kind

- **Purpose**: `--from-offset`/`--from-invariant` validate against the
  selected log; existing refusal envelopes unchanged.
- **Relevant requirements**: FR-006.
- **Affected surfaces**: `src/specify_cli/cli/commands/events.py` (validate
  call site — path swap only), `tests/cli/test_events_tail_log_selector.py`.
- **Sequencing/depends-on**: IC-01 (needs the selected path).
- **Risks**: none beyond IC-01's; the core validator is path-generic.

## Phase 0 — Research

`research.md` was created at discovery and is complete for this mission's
scope: every kind's canonical path is verified against its writer, the
blocking dependencies (#6603, spec-kitty-events#92, #5466) are confirmed
resolved, and the design decisions (kind set, default flip, latest-run rule,
plain-print rendering) are recorded with rationale and alternatives. No
`[NEEDS CLARIFICATION]` markers remain. The Phase 0 addition is the
red-test plan (see `research.md` § Reproduction) — no further research tasks.

## Phase 1 — Design & Contracts

- `data-model.md`: the LogKind value object and its resolution rules; the
  unchanged core entities it feeds.
- `contracts/cli-contract.md`: the `events tail` CLI contract — options
  (incl. the new `--log` and the flipped `--json`), output shapes for both
  modes, stderr refusal envelopes (existing ones plus `run_log_unavailable`),
  exit codes, and the behavioral table.
- `quickstart.md`: how an operator follows each ledger kind and switches
  between human and JSON output; where each log lives.

No external API, webhook or integration surface is added — the CLI contract
is the only interface; `contracts/` therefore contains exactly one file.
