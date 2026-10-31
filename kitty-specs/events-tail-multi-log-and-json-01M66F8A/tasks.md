# Tasks: events tail multi-log selector and a meaningful --json

**Mission**: `events-tail-multi-log-and-json-01M66F8A` | **Branch**: `issue-6611-events-tail-multi-log-and-json` (coord topology)
**Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md) | **Issue**: spec-kitty/spec-kitty#6611

2 work packages. WP01 builds the private helper (kind registry, path
resolution incl. latest-run selection, human renderer) with unit tests; WP02
wires it into the `events tail` shell — the `--log` flag and the flipped
`--json` — red-first through the CLI entry point. WP02 depends on WP01; both
edit disjoint files, so the split has no `owned_files` overlap.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Kind registry + `resolve_log_path`: the seven kinds joined over existing resolution seams | WP01 | |
| T002 | Latest-run resolution: runs-dir scan, `mission_id`/slug match, mtime ordering, `RunLogUnavailable` typed refusal | WP01 | [P] |
| T003 | Human renderer: deterministic one-line rendering, cursor-key omission, `log_truncated` warning | WP01 | [P] |
| T004 | Unit tests for registry, run resolution and renderer (fast, `tmp_path` fixtures) | WP01 | |
| T005 | Red-first CLI tests: `--log` rejected as unknown option today; default output differs from `--json` today | WP02 | |
| T006 | `--log` flag + dispatch in `events.py`; `run_log_unavailable` stderr envelope; resume validation against the selected log | WP02 | |
| T007 | `--json` flip in `events.py`: human default via renderer, `--json` byte-identical JSON lines; flag help + docstring refresh | WP02 | |
| T008 | CLI test battery: table-driven kind paths, run selection/refusal, missing-log wait, resume refusal, unknown kind, byte-stability pin | WP02 | |

## WP01 — Log-kind helper module (`_events_tail_logs.py`)

**Goal**: Build `src/specify_cli/cli/commands/_events_tail_logs.py` — the
closed kind registry, per-kind path resolution (including latest-run
selection with its typed refusal) and the deterministic human renderer — with
unit tests. The shell (WP02) consumes only this module; the core reader stays
untouched.
**Priority**: P1 (MVP — the selector vocabulary and resolution rules everything else uses).
**Independent test**: unit tests resolve every kind against `tmp_path`
fixtures to the exact canonical paths in `data-model.md`; run selection picks
the newest matching journal and refuses typed when none matches; the renderer
is deterministic and omits cursor keys.
**Dependencies**: none.
**Requirement refs**: FR-001, FR-002, FR-003, FR-004, FR-007.
**Prompt**: [tasks/WP01-log-kind-helper.md](tasks/WP01-log-kind-helper.md) (~300 lines)

T001 Kind registry + `resolve_log_path` (WP01)
T002 Latest-run resolution + `RunLogUnavailable` (WP01)
T003 Human renderer (WP01)
T004 Unit tests (WP01)

## WP02 — Shell wiring: `--log` selector and a meaningful `--json`

**Goal**: Wire the helper into `spec-kitty events tail`: the `--log` choice
flag (default `status`), the `run_log_unavailable` refusal envelope, resume
validation against the selected log, and the `--json` flip — human-readable
default output, `--json` opting into today's byte-identical JSON lines.
Red-first through the CLI entry point.
**Priority**: P1 (the user-visible fix for both halves of #6611).
**Independent test**: `events tail --mission <s> --log decisions --once --json`
streams decision rows (red on main: no `--log` option); the same invocation
without `--json` prints human lines; `--log status --json` output is
byte-identical to the pre-change command.
**Dependencies**: WP01 (consumes the helper module).
**Requirement refs**: FR-001, FR-004, FR-005, FR-006, FR-007.
**Prompt**: [tasks/WP02-shell-wiring.md](tasks/WP02-shell-wiring.md) (~330 lines)

## Mission close-out (driver-owned, NOT a WP)

After both WPs merge into the mission branch, the mission driver owns these
concrete drift surfaces — no WP may edit them (finding 4 of the post-tasks
review):

1. `CHANGELOG.md` — `[Unreleased]` entry for the `--json` default flip
   (C-005, High): before/after behavior and the migration (`--json` opts
   back into machine output).
2. `docs/api/cli-commands.md` — the GENERATED CLI reference pins the
   current `--json` help ("no observable effect either way …
   [default: True]") and lacks `--log`; regenerate via
   `scripts/docs/build_cli_reference.py` (the HELP-DRIFT gate
   `scripts/docs/check_cli_reference_freshness.py` and
   `tests/architectural/test_docs_cli_reference_parity.py` will go red
   otherwise). Check `docs/api/agent-subcommands.md` too if it carries the
   tail help.
3. `docs/context/system-events.md` — the "Tail envelope" glossary entry
   says "One JSON line emitted on stdout"; now true only in `--json` mode.
   Update the wording (this is the canonical terminology directory).
4. `docs/architecture/event-ledger-writers-and-readers.md` — gap-table row
   G-10 tracks this exact issue; close it.
5. The PR body names the deferred log kinds (C-001 scope note).
