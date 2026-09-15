"""Tests for `spec-kitty events tail` (mission event-push-watch-channel, WP04).

This is the CLI SHELL test suite -- see
``kitty-specs/event-push-watch-channel-01M1K6W2/tasks/WP04-cli-shell-events-tail.md``
for the full subtask breakdown. Per the corrected architecture (FR-011/NFR-001/
NFR-002), ``src/specify_cli/cli/commands/events.py`` is a THIN shell: it owns no
poll loop and no direct ``time.sleep`` call of its own. It is a plain ``for``-loop
consumer of WP01-03's core (``poll_once``/``tail_events``/``validate_resume_cursor``,
all in ``src/specify_cli/status/tail_reader.py``).

Deterministic termination (NFR-001's CLI-shell half, restated per this WP's own
Context section): every ``CliRunner`` invocation in this module passes ONLY
``--once`` or a small ``--max-events N`` -- **never** a bare unbounded
``events tail`` invocation, anywhere, ever. This is what makes every test in this
file terminate without a wall-clock timeout.

Marker/CI discipline (C-008/SK-144): every test in THIS file is fast/mocked-
resolution and carries the module-level ``pytestmark = [pytest.mark.fast]``
(collected by ``fast-tests-cli``, which selects
``tests/cli/ tests/specify_cli/cli/ -m "fast and not windows_ci"`` per
``.github/workflows/ci-quality.yml``). The one real-fixture end-to-end test
(real git repo, real ``meta.json``, no mocking) lives in the SIBLING file
``tests/cli/test_events_tail_real_fixture.py``, whose own module-level
``pytestmark = [pytest.mark.integration, pytest.mark.git_repo]`` carries NO
``fast`` marker -- it is a *separate file*, not a per-function override,
because pytest marks stack (a function inheriting a module-level ``fast``
mark cannot un-mark itself with a function-level decorator alone). That file
is collected by ``integration-tests-cli``, which selects
``tests/cli/ tests/specify_cli/cli/ -m 'not windows_ci and (git_repo or
integration)'``. Both filters re-verified live against the workflow file
(WP04 Context section); the file-split pattern mirrors existing dedicated
git_repo-only modules in this repo, e.g.
``tests/cli/commands/test_agent_mission_commit_to_branch.py``.

Typer single-command-app CliRunner gotcha (mirrors ``tests/docs/test_docs_query_cli.py``'s
own comment): ``events.app`` currently registers exactly ONE command (``tail``).
Typer's CliRunner collapses a *standalone* single-command Typer app into that command
directly, so invoking it bare with ``["tail", ...]`` would treat "tail" as if it were
an argument rather than a subcommand name. Production always mounts ``events.app`` via
``app.add_typer(events_module.app, name="events")`` (T027), which preserves "tail" as
an explicit subcommand -- so every test here mirrors that exact mounting via a
throwaway root Typer app, exactly like ``test_docs_query_cli.py`` does for `docs query`.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands import events as events_cli
from specify_cli.context.mission_resolver import ResolvedMission

pytestmark = [pytest.mark.fast]

runner = CliRunner()

MISSION_SLUG = "001-events-tail-fixture"
MISSION_ID = "01EVENTSTAILFIXTURE0000000"

# Mirrors test_docs_query_cli.py's exact mounting pattern -- a standalone
# single-command Typer app is collapsed by CliRunner unless mounted under a
# named group, so every invocation below goes through this wrapper, matching
# how `register_commands` mounts `events.app` in production (T027).
_root_app = typer.Typer()
_root_app.add_typer(events_cli.app, name="events")


def _invoke(*args: str) -> object:
    return runner.invoke(_root_app, ["events", *args])


def _resolved(feature_dir: Path) -> ResolvedMission:
    return ResolvedMission(
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
        mid8=MISSION_ID[:8],
        feature_dir=feature_dir,
    )


def _write_events(feature_dir: Path, events: list[dict]) -> Path:
    feature_dir.mkdir(parents=True, exist_ok=True)
    log_path = feature_dir / "status.events.jsonl"
    with log_path.open("w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event) + "\n")
    return log_path


def test_events_tail_once_emits_all_pre_existing_events_in_order(tmp_path: Path) -> None:
    """T021 (ATDD, red-first): User Story 1 AC1.

    Drives `spec-kitty events tail --mission <slug> --json --once` against a
    pre-populated `status.events.jsonl` (N=3 events) and asserts: exit code 0,
    exactly N lines on stdout, each a `json.loads`-able dict, and the events
    appear in file order.

    Run against WP03's final commit (before this WP's `events.py` exists), this
    test's failure mode is a plain import-time `ModuleNotFoundError`/collection
    error for `specify_cli.cli.commands.events` -- NOT a more specific assertion
    failure. This is a deliberately coarser RED than WP02/WP03's precise
    non-import failures, because the whole CLI shell is new in this WP: the
    `from specify_cli.cli.commands import events as events_cli` import at module
    scope above fails at COLLECTION time, before any test body runs.
    """
    feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
    events = [
        {"event_id": "evt-1", "wp_id": "WP01", "seq": 1},
        {"event_id": "evt-2", "wp_id": "WP01", "seq": 2},
        {"event_id": "evt-3", "wp_id": "WP02", "seq": 3},
    ]
    _write_events(feature_dir, events)

    with patch.object(events_cli, "resolve_mission_handle", return_value=_resolved(feature_dir)):
        result = _invoke("tail", "--mission", MISSION_SLUG, "--json", "--once")

    assert result.exit_code == 0, result.output
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    parsed = [json.loads(line) for line in lines]
    # Exact ordered identity (a cardinality-only `len(lines) == 3`
    # would pass on any 3 lines, wrong content included -- this asserts the
    # real contract: these three event_ids, in this order, none more) also
    # proves the count.
    assert [p["event_id"] for p in parsed] == ["evt-1", "evt-2", "evt-3"]


def test_from_invariant_without_from_offset_is_usage_error() -> None:
    """T023 (FR-004): --from-invariant without --from-offset is rejected before
    any read begins -- non-zero exit, empty stdout (no Tail envelope emitted for
    the invocation), and the "usage_error" code on stderr's JSON body.

    Mission resolution is never even reached (no mock/real fixture needed) --
    this check runs first, before any file/mission access.
    """
    result = _invoke(
        "tail",
        "--mission",
        "does-not-matter",
        "--json",
        "--once",
        "--from-invariant",
        "deadbeef",
    )

    assert result.exit_code != 0
    assert result.stdout == ""
    stderr_body = json.loads(result.stderr)
    assert stderr_body["error"] == "usage_error"


def test_unresolvable_mission_slug_mocked_resolution_fails_closed() -> None:
    """T024 (FR-009): a mocked resolve_mission_handle that raises SystemExit(2)
    (its own contract on an unresolvable handle) propagates as a non-zero exit
    with no stdout Tail envelope. Patch target is the IMPORTING module
    (specify_cli.cli.commands.events.resolve_mission_handle), never
    specify_cli.cli.selector_resolution.resolve_mission_handle.
    """
    with patch.object(events_cli, "resolve_mission_handle", side_effect=SystemExit(2)):
        result = _invoke("tail", "--mission", "whatever", "--json", "--once")

    assert result.exit_code != 0
    assert result.stdout == ""


def test_unresolvable_mission_slug_real_repo_root_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T024 (FR-009): a genuinely bad slug against a real (tmp-path) repo root,
    without mocking resolution -- asserts the canonical typed JSON envelope
    on stdout end-to-end. SPECIFY_REPO_ROOT pins locate_project_root() to this
    tmp_path deterministically (Tier 1 of its resolution order), avoiding a
    chdir.
    """
    (tmp_path / "kitty-specs").mkdir()
    (tmp_path / ".kittify").mkdir()
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))

    result = _invoke("tail", "--mission", "no-such-mission-slug", "--json", "--once")

    assert result.exit_code != 0
    assert result.stderr == ""
    body = json.loads(result.stdout)
    assert body["success"] is False
    assert body["error_code"] == "MISSION_NOT_FOUND"
    assert body["handle"] == "no-such-mission-slug"


def test_resume_structurally_invalid_offset_is_refused(tmp_path: Path) -> None:
    """T025 (FR-013, structural): an out-of-range --from-offset is refused
    before any streaming begins -- non-zero exit, empty stdout, and the
    "invalid_resume_offset" code on stderr. Exercises validate_resume_cursor()
    directly against a crafted tmp-path file (no mocking).
    """
    feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
    _write_events(feature_dir, [{"event_id": "evt-1"}])

    with patch.object(events_cli, "resolve_mission_handle", return_value=_resolved(feature_dir)):
        result = _invoke(
            "tail",
            "--mission",
            MISSION_SLUG,
            "--json",
            "--once",
            "--from-offset",
            "999999",
        )

    assert result.exit_code != 0
    assert result.stdout == ""
    stderr_body = json.loads(result.stderr)
    assert stderr_body["error"] == "invalid_resume_offset"


def test_resume_content_mismatch_is_refused(tmp_path: Path) -> None:
    """T025 (FR-013, content): a structurally-valid offset whose supplied
    content invariant does not match the actual bytes is refused -- non-zero
    exit, empty stdout, and the "resume_content_mismatch" code on stderr.
    """
    feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
    log_path = _write_events(feature_dir, [{"event_id": "evt-1"}])
    offset = log_path.stat().st_size

    with patch.object(events_cli, "resolve_mission_handle", return_value=_resolved(feature_dir)):
        result = _invoke(
            "tail",
            "--mission",
            MISSION_SLUG,
            "--json",
            "--once",
            "--from-offset",
            str(offset),
            "--from-invariant",
            "0" * 64,
        )

    assert result.exit_code != 0
    assert result.stdout == ""
    stderr_body = json.loads(result.stderr)
    assert stderr_body["error"] == "resume_content_mismatch"


def test_resume_success_path_emits_only_events_at_or_after_offset(tmp_path: Path) -> None:
    """T025 (FR-013 SUCCESS path -- User Story 3 AC1's non-refusal branch).

    Not a mocked validate_resume_cursor -- a real tmp-path log, consumed via a
    real ``--once`` CLI invocation whose resume token (offset, invariant) is
    parsed out of that invocation's REAL STDOUT (the ``tail_offset``/
    ``tail_invariant`` sibling keys FR-004/plan.md's Tail Envelope & Cursor
    Schema require on every pass-through envelope) -- never ``log_path.stat()``
    and never a direct ``poll_once()`` call. A consumer-facing resume contract
    proven via an internal shortcut that bypasses the very stdout interface
    under test would not actually prove the contract holds (this is what let
    R4's severity-4 finding -- the reader never emitted those keys at all --
    through in the first place: see ``test_resume_round_trip_via_real_cli_stdout_cursor``
    below, which pins the same bug at its true failure point). Then further
    events are appended past that offset; asserts the resumed invocation emits
    exactly the events at/after O, in order, none duplicated, none of the
    pre-O events re-emitted.
    """
    feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
    log_path = _write_events(
        feature_dir,
        [{"event_id": "evt-1"}, {"event_id": "evt-2"}],
    )

    with patch.object(events_cli, "resolve_mission_handle", return_value=_resolved(feature_dir)):
        first = _invoke("tail", "--mission", MISSION_SLUG, "--json", "--once")
    assert first.exit_code == 0, first.output
    first_lines = [line for line in first.stdout.splitlines() if line.strip()]
    # Exact ordered identity (a cardinality-only `len(first_lines)
    # == 2` would pass on any 2 lines, wrong content included -- this asserts
    # the real contract: exactly these two event_ids, in this order) also
    # proves the count.
    assert [json.loads(line)["event_id"] for line in first_lines] == ["evt-1", "evt-2"]
    last_envelope = json.loads(first_lines[-1])
    resume_offset = last_envelope["tail_offset"]
    resume_invariant = last_envelope["tail_invariant"]

    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"event_id": "evt-3"}) + "\n")
        fh.write(json.dumps({"event_id": "evt-4"}) + "\n")

    with patch.object(events_cli, "resolve_mission_handle", return_value=_resolved(feature_dir)):
        resumed = _invoke(
            "tail",
            "--mission",
            MISSION_SLUG,
            "--json",
            "--from-offset",
            str(resume_offset),
            "--from-invariant",
            resume_invariant,
            "--max-events",
            "2",
        )

    assert resumed.exit_code == 0, resumed.output
    resumed_lines = [line for line in resumed.stdout.splitlines() if line.strip()]
    parsed = [json.loads(line) for line in resumed_lines]
    assert [p["event_id"] for p in parsed] == ["evt-3", "evt-4"]


def test_resume_round_trip_via_real_cli_stdout_cursor(tmp_path: Path) -> None:
    """R4 severity-4 fix (issue #3841): the consumer-facing resume contract,
    proven end-to-end through the REAL public interface -- stdout -- with no
    internal shortcut anywhere in this test.

    Before this fix, ``poll_once()``'s pass-through envelopes never carried
    ``tail_offset``/``tail_invariant`` (only the unrelated ``log_truncated``
    signal did), even though spec.md FR-004 and plan.md's Tail Envelope &
    Cursor Schema require them on EVERY envelope so a real consumer can
    persist both and supply them back on restart (FR-013). A test that
    obtains its resume token via ``log_path.stat()``/``poll_once()`` directly
    (the shape the sibling test above used to take) cannot catch that defect,
    because it never goes through the interface the defect is in.

    This test:
      1. runs ``spec-kitty events tail --once`` against a real log and parses
         the cursor out of actual parsed stdout JSON (never internal state),
      2. appends more events,
      3. restarts with ``--from-offset``/``--from-invariant`` taken from that
         parsed stdout,
      4. asserts the resume is accepted (exit 0) and every resumed event is
         emitted exactly once -- none duplicated, none lost.

    It fails against the pre-fix reader with a ``KeyError: 'tail_offset'``
    (the pass-through envelope's stdout JSON has no such key to parse), and
    passes once ``poll_once()`` injects both sibling keys on every
    pass-through line.
    """
    feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
    log_path = _write_events(
        feature_dir,
        [{"event_id": "evt-1"}, {"event_id": "evt-2"}],
    )

    with patch.object(events_cli, "resolve_mission_handle", return_value=_resolved(feature_dir)):
        first = _invoke("tail", "--mission", MISSION_SLUG, "--json", "--once")
    assert first.exit_code == 0, first.output
    first_lines = [line for line in first.stdout.splitlines() if line.strip()]
    first_parsed = [json.loads(line) for line in first_lines]
    assert [p["event_id"] for p in first_parsed] == ["evt-1", "evt-2"]

    # The resume cursor comes ONLY from the parsed stdout of the invocation
    # above -- no `log_path.stat()`, no direct `poll_once()`/`tail_reader`
    # import, no internal state of any kind.
    cursor_source = first_parsed[-1]
    resume_offset = cursor_source["tail_offset"]
    resume_invariant = cursor_source["tail_invariant"]

    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"event_id": "evt-3"}) + "\n")
        fh.write(json.dumps({"event_id": "evt-4"}) + "\n")

    with patch.object(events_cli, "resolve_mission_handle", return_value=_resolved(feature_dir)):
        resumed = _invoke(
            "tail",
            "--mission",
            MISSION_SLUG,
            "--json",
            "--from-offset",
            str(resume_offset),
            "--from-invariant",
            resume_invariant,
            "--max-events",
            "2",
        )

    assert resumed.exit_code == 0, resumed.output
    resumed_lines = [line for line in resumed.stdout.splitlines() if line.strip()]
    resumed_parsed = [json.loads(line) for line in resumed_lines]
    resumed_ids = [p["event_id"] for p in resumed_parsed]

    # Accepted resume, and every resumed event exactly once -- none
    # duplicated (no repeat of evt-1/evt-2), none lost (both evt-3/evt-4
    # present).
    assert resumed_ids == ["evt-3", "evt-4"]
    assert len(resumed_ids) == len(set(resumed_ids))


def test_events_tail_registered_on_the_real_top_level_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T027: proof the registration in
    src/specify_cli/cli/commands/__init__.py actually wires `events tail`
    into the REAL top-level `spec-kitty` app -- not just that events.py's own
    module-level `app` works in isolation (every test above uses a throwaway
    `_root_app` wrapper, not the production registration path). Mirrors
    tests/architectural/test_docs_cli_reference_parity.py's own
    `_build_live_app()` discovery pattern: `register_commands(app)` on the
    real `specify_cli.app` singleton, with `sys.argv` pinned so none of
    `register_commands`'s fast-path early-returns fire.

    ``force_wide_help_console`` (house precedent:
    ``tests/specify_cli/cli/commands/_help_snapshot.py``) pins Typer's
    *own* rich_utils help console to a fixed, wide, colourless size. Without
    it, an ambient colour terminal (``FORCE_COLOR`` set, as CI's runner
    does) makes Rich's option highlighter emit a style-reset between the
    two leading hyphens of a long option name (``--mission`` renders as
    two separate spans, ``-`` then ``-mission``, with an ANSI reset
    in between), which breaks a plain ``"--mission" in result.output``
    substring check even though the option is genuinely present and
    correctly spelled. This is unrelated to the app's own
    ``specify_cli.cli.console`` singleton pin (``tests/conftest.py``'s
    ``_plain_cli_console_seam``), which does not reach Typer's internal
    help-rendering console.
    """
    import sys

    from specify_cli import app as top_level_app
    from specify_cli.cli.commands import register_commands
    from tests.specify_cli.cli.commands._help_snapshot import (
        force_wide_help_console,
    )

    force_wide_help_console(monkeypatch)

    saved_argv = sys.argv[:]
    sys.argv = ["spec-kitty", "--help"]
    try:
        register_commands(top_level_app)
    finally:
        sys.argv = saved_argv

    result = runner.invoke(top_level_app, ["events", "--help"])
    assert result.exit_code == 0, result.output
    assert "tail" in result.output

    result = runner.invoke(top_level_app, ["events", "tail", "--help"])
    assert result.exit_code == 0, result.output
    assert "--mission" in result.output
    assert "--once" in result.output


def test_no_write_syscall_reachable_on_any_code_path(tmp_path: Path) -> None:
    """T030 (FR-010): events tail is a pure reader. Spy on Path.open and assert
    no call anywhere opens status.events.jsonl/status.json/any mission artifact
    in a write mode ("w", "a", "x", or any "+" variant) -- across every code
    path exercised by this WP's own tests, including the error/refusal paths
    (usage error, mission-not-found, resume-refused), not just the happy path.
    """
    write_modes = {"w", "a", "x", "w+", "a+", "x+", "r+", "wb", "ab", "xb", "rb+", "wb+", "ab+", "xb+"}
    opened_for_write: list[tuple[str, str]] = []
    real_open = Path.open

    def spying_open(self: Path, mode: str = "r", *args: object, **kwargs: object) -> object:
        if mode in write_modes:
            opened_for_write.append((str(self), mode))
        return real_open(self, mode, *args, **kwargs)

    feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
    _write_events(feature_dir, [{"event_id": "evt-1"}])
    resolved = _resolved(feature_dir)

    with patch.object(Path, "open", spying_open):
        # Happy path.
        with patch.object(events_cli, "resolve_mission_handle", return_value=resolved):
            _invoke("tail", "--mission", MISSION_SLUG, "--json", "--once")
        # Usage-error path (FR-004).
        _invoke(
            "tail",
            "--mission",
            MISSION_SLUG,
            "--json",
            "--once",
            "--from-invariant",
            "deadbeef",
        )
        # Mission-not-found path (FR-009), mocked resolution.
        with patch.object(events_cli, "resolve_mission_handle", side_effect=SystemExit(2)):
            _invoke("tail", "--mission", "whatever", "--json", "--once")
        # Resume-refused path (FR-013, structural).
        with patch.object(events_cli, "resolve_mission_handle", return_value=resolved):
            _invoke(
                "tail",
                "--mission",
                MISSION_SLUG,
                "--json",
                "--once",
                "--from-offset",
                "999999",
            )

    assert opened_for_write == []


# NOTE: the real-fixture end-to-end test (real git repo, real meta.json, no
# mocking of the core or of resolve_mission_handle) lives in the sibling file
# tests/cli/test_events_tail_real_fixture.py, marked integration+git_repo
# (NOT fast) -- see this module's docstring for why it is a separate file
# rather than a function-level marker override.
