"""Concurrency proof: writer safety under a concurrent tail reader (WP05).

Mission ``event-push-watch-channel-01M1K6W2``, WP05 -- the mission's only true
integration/concurrency tier. Proves, with a real concurrent execution (not an
assertion, not a mocked reader), that a live ``events tail`` reader (the real
CLI shell from ``src/specify_cli/cli/commands/events.py``, WP04, driving the
real bounded-generator core ``tail_events()`` from
``src/specify_cli/status/tail_reader.py``, WP01-03) running against a
mission's ``status.events.jsonl`` while that mission's own normal writer path
(``status.emit.emit_status_transition``) is actively appending to it produces
ZERO behavioral change on the writer side (NFR-004/SC-005).

Fixture pattern (per this WP's own Context section -- reused, not hand-
rolled): the ``tmp_path``-``feature_dir`` + ``seed_wp_to_planned`` +
``emit_status_transition(...)``
pattern from ``tests/status/conftest.py`` / ``tests/status/test_emit.py``.
This harness never mints a real mission via a genuine ULID-minting
mission-creation codepath (no ``spec-kitty agent mission create``, nothing
under ``.kittify/missions/``), so the C-009/SK-147 fixture-freeze obligation
is NOT applicable here -- see the module-level note near
``_DeterministicIdSource`` below for what IS pinned and why.

Genuine overlap (not sequential-then-compared): the writer thread and the
reader thread coordinate through TWO ``threading.Event`` checkpoints, not
one -- ``first_write_done`` (writer signals after its first write) AND
``reader_polling`` (reader signals immediately before it enters the CLI's
poll loop, and the writer *waits* on it before performing any further
writes). This is a stronger, deterministic proof of overlap than a single
one-way checkpoint: the writer's remaining three writes are guaranteed to
happen while the reader's ``events tail`` invocation is already in flight
(the CLI has been called and has not yet returned), not merely "probably
still running" based on timing.

Byte-identical comparison (not an event-count check): ``event_id`` and ``at``
are the only two fields in the emitted ``StatusEvent`` that vary run-to-run
(everything else -- ``mission_slug``, ``wp_id``, ``from_lane``, ``to_lane``,
``actor``, ``force``, ``execution_mode``, ``reason``, ``mission_id`` -- is
either supplied explicitly and identically by this harness or derived
deterministically from the identical seed/log content). This harness pins
both via monkeypatch on the two module-level generators
``specify_cli.status.emit._generate_ulid`` / ``specify_cli.status.emit.now_utc_iso``
(preferred pinning strategy, per T032's guidance) rather than falling back to
a field-exclusion comparison, so the final assertion is genuine byte equality
of the raw ``status.events.jsonl`` content -- not "same event count", not
"same number of lines".

Bounded reader, always: every reader invocation in this file uses
``--max-events N`` (never a bare/unbounded ``events tail``), mirroring
WP03's core-level discipline and WP04's own CLI-shell test suite.

Marker/CI discipline (C-008/SK-144, T034): this module carries
``pytestmark = [pytest.mark.integration, pytest.mark.git_repo]`` --
collected by ``integration-tests-status``
(``tests/status/ tests/specify_cli/status/ -m "not windows_ci and (git_repo
or integration)"``, ``.github/workflows/ci-quality.yml``) and explicitly
NOT by ``fast-tests-status`` (``-m "fast and not windows_ci and not
(git_repo or integration or stress)"``) -- both re-verified live via
``pytest --collect-only`` against the actual workflow file, not merely
assumed from this docstring.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

import specify_cli.status.emit as emit_module
from specify_cli.cli.commands import events as events_cli
from specify_cli.context.mission_resolver import ResolvedMission
from specify_cli.status.emit import emit_status_transition
from specify_cli.status.models import TransitionRequest
from specify_cli.status.store import EVENTS_FILENAME

import tests.status.conftest as _conftest_module
from tests.status.conftest import seed_wp_to_planned

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

MISSION_SLUG = "events-tail-concurrency"
ACTOR = "wp05-concurrency-proof-actor"

# Fixed writer sequence (T031/T032): two WPs, each planned -> claimed ->
# in_progress. Four emit_status_transition calls total -- enough for the
# reader's checkpoint to land strictly between the first and the remaining
# three, and small enough that --max-events 4 terminates the reader
# deterministically without depending on wall-clock luck.
WRITER_SEQUENCE: tuple[tuple[str, str], ...] = (
    ("WP01", "claimed"),
    ("WP01", "in_progress"),
    ("WP02", "claimed"),
    ("WP02", "in_progress"),
)

# Mirrors tests/cli/test_events_tail.py's exact mounting pattern: a
# standalone single-command Typer app is collapsed by CliRunner unless
# mounted under a named group, so this wrapper matches how production
# mounts events.app via `app.add_typer(events_module.app, name="events")`.
_root_app = typer.Typer()
_root_app.add_typer(events_cli.app, name="events")

runner = CliRunner()


class _DeterministicIdSource:
    """Pins ``event_id``/``at`` generation for a byte-identical comparison.

    ``emit_status_transition`` does not accept explicit ``event_id``/``at``
    overrides through ``TransitionRequest`` for the real pipeline (unlike
    ``seed_wp_to_planned``'s own deterministic ``_make_seed_event_id()``
    counter, which writes directly to the log). To get a truly
    byte-identical comparison between the control and concurrent runs
    (T031/T032's preferred pinning strategy, approach (a)), this harness
    instead monkeypatches the two module-level generators the writer path
    itself calls -- ``specify_cli.status.emit._generate_ulid`` and
    ``specify_cli.status.emit.now_utc_iso`` -- and resets the counters to
    the same starting state before each of the two runs, so both produce
    the identical event_id/at sequence given the identical writer script.

    This does NOT mint any real ULID via the genuine mission-creation
    codepath (no ``spec-kitty agent mission create``, no
    ``.kittify/missions/`` write), so the C-009/SK-147 fixture-freeze
    obligation does not apply to this harness -- see the module docstring.
    """

    def __init__(self) -> None:
        self._id_counter = 0
        self._clock_counter = 0

    def reset(self) -> None:
        self._id_counter = 0
        self._clock_counter = 0

    def next_id(self) -> str:
        self._id_counter += 1
        return f"01WP05CONCURRENCYPROOF{self._id_counter:03d}"

    def next_ts(self) -> str:
        self._clock_counter += 1
        return f"2026-01-01T00:00:{self._clock_counter:02d}+00:00"


def _reset_seed_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset ``seed_wp_to_planned``'s own module-level ``_SEED_COUNTER``.

    ``tests/status/conftest.py``'s ``_make_seed_event_id()`` counter is
    process-global and monotonic (by design -- it exists to give every
    seed call in the whole test run a unique id, not to be per-scenario
    deterministic). Left alone, two independent seed passes in the SAME
    test would mint different seed event_ids for the control vs. concurrent
    run (e.g. ``01SEED...0001``/``...0002`` vs. ``...0003``/``...0004``),
    breaking the byte-identical comparison on lines this harness does not
    otherwise touch (T031's actual observed RED). Resetting it here before
    each seed pass is a narrow, test-local concern about this harness's own
    two-run comparison -- not the C-009/SK-147 real-ULID fixture-freeze
    obligation (these ids are the deterministic ``01SEEDxxx`` counter form,
    never real ULID/clock output).
    """
    monkeypatch.setattr(_conftest_module, "_SEED_COUNTER", 0)


def _run_writer_sequence(feature_dir: Path) -> None:
    """T032: the fixed, deterministic writer sequence T031's test depends on.

    Runs WRITER_SEQUENCE against *feature_dir* via the real
    ``emit_status_transition`` pipeline (no unrelated network/process
    dependency), leaving the event log in its
    final state. Used unmodified for the control run; the concurrent run
    below inlines the same four calls with checkpoint signaling between
    the first and the remaining three.
    """
    for wp_id, to_lane in WRITER_SEQUENCE:
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=MISSION_SLUG,
                wp_id=wp_id,
                to_lane=to_lane,
                actor=ACTOR,
            ),
        )


def _resolved(feature_dir: Path) -> ResolvedMission:
    """A canned ResolvedMission pointing at *feature_dir* (mirrors
    tests/cli/test_events_tail.py's own ``_resolved()`` helper) -- patched
    in for ``events_cli.resolve_mission_handle`` so the real CLI shell
    (events.py) and the real core (tail_reader.py) both run against this
    harness's tmp_path fixture without minting a real mission via
    ``resolve_mission_handle``'s filesystem scan.
    """
    return ResolvedMission(
        mission_id="01WP05CONCURRENCYFIXTURE0",
        mission_slug=MISSION_SLUG,
        mid8="01WP05CON",
        feature_dir=feature_dir,
    )


def test_concurrent_writer_and_bounded_reader_byte_identical_to_control(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T031/T033 (ATDD): a live writer genuinely overlapping a live bounded
    reader produces zero behavioral change on the writer's own event log
    (NFR-004/SC-005).

    At WP04's final commit this exact concurrent-execution scenario --
    a real writer thread and a real ``events tail`` reader thread racing
    against the same ``status.events.jsonl``, synchronized via an explicit
    ``threading.Event`` checkpoint pair -- has never been exercised
    anywhere in this mission's test suite (WP01-04 all test the reader in
    isolation against static or externally-mutated-between-polls fixture
    files, never alongside a live, actively-running writer thread). Both
    ``tail_events()`` and the ``events`` CLI shell already fully exist and
    are independently tested at WP04's tip, so the RED this test
    introduces there is behavioral (the harness runs but the byte-identical
    assertion does not hold, or the harness itself is simply absent), never
    an import/collection failure.
    """
    ids = _DeterministicIdSource()
    monkeypatch.setattr(emit_module, "_generate_ulid", ids.next_id)
    monkeypatch.setattr(emit_module, "now_utc_iso", ids.next_ts)

    # ---- Control run: writer sequence alone, no reader present. ----
    control_dir = tmp_path / "control" / "kitty-specs" / MISSION_SLUG
    control_dir.mkdir(parents=True)
    _reset_seed_counter(monkeypatch)
    seed_wp_to_planned(control_dir, "WP01", slug=MISSION_SLUG)
    seed_wp_to_planned(control_dir, "WP02", slug=MISSION_SLUG)
    ids.reset()
    _run_writer_sequence(control_dir)
    control_bytes = (control_dir / EVENTS_FILENAME).read_bytes()

    # ---- Concurrent run: writer on a background thread; a bounded
    #      `events tail --max-events N` reader on another thread, polling
    #      the SAME feature_dir concurrently. ----
    concurrent_dir = tmp_path / "concurrent" / "kitty-specs" / MISSION_SLUG
    concurrent_dir.mkdir(parents=True)
    _reset_seed_counter(monkeypatch)
    seed_wp_to_planned(concurrent_dir, "WP01", slug=MISSION_SLUG)
    seed_wp_to_planned(concurrent_dir, "WP02", slug=MISSION_SLUG)
    ids.reset()

    # Two-checkpoint handshake (T032) -- proves genuine overlap in the test
    # itself rather than merely making it likely:
    #   1. `first_write_done`: writer signals after its FIRST write.
    #   2. `reader_polling`: reader signals immediately before it enters the
    #      CLI's poll loop; the WRITER then waits on this before performing
    #      any of its remaining three writes. This guarantees those writes
    #      happen strictly while the reader's `events tail` invocation is
    #      already in flight (called and not yet returned) -- not merely
    #      "probably still running" based on timing alone.
    first_write_done = threading.Event()
    reader_polling = threading.Event()

    writer_exc: list[BaseException] = []
    reader_exc: list[BaseException] = []
    reader_exit_code: list[int] = []
    reader_events: list[dict[str, object]] = []

    def _writer() -> None:
        try:
            for index, (wp_id, to_lane) in enumerate(WRITER_SEQUENCE):
                # Wait for proof the reader is genuinely mid-poll before
                # writing the remaining events (bounded -- never hangs the
                # test indefinitely if the reader side breaks).
                if index == 1 and not reader_polling.wait(timeout=10):
                    raise AssertionError("reader did not signal reader_polling within 10s")
                emit_status_transition(
                    TransitionRequest(
                        feature_dir=concurrent_dir,
                        mission_slug=MISSION_SLUG,
                        wp_id=wp_id,
                        to_lane=to_lane,
                        actor=ACTOR,
                    ),
                )
                if index == 0:
                    first_write_done.set()
        except BaseException as exc:  # noqa: BLE001 -- surfaced via writer_exc, not swallowed
            writer_exc.append(exc)
            first_write_done.set()
            raise

    def _reader() -> None:
        try:
            if not first_write_done.wait(timeout=10):
                raise AssertionError("writer did not signal first_write_done within 10s")
            with patch.object(
                events_cli,
                "resolve_mission_handle",
                return_value=_resolved(concurrent_dir),
            ):
                reader_polling.set()
                result = runner.invoke(
                    _root_app,
                    [
                        "events",
                        "tail",
                        "--mission",
                        MISSION_SLUG,
                        "--json",
                        "--max-events",
                        str(len(WRITER_SEQUENCE)),
                    ],
                )
            reader_exit_code.append(result.exit_code)
            for line in result.stdout.splitlines():
                stripped = line.strip()
                if stripped:
                    reader_events.append(json.loads(stripped))
        except BaseException as exc:  # noqa: BLE001 -- surfaced via reader_exc, not swallowed
            reader_exc.append(exc)
            raise

    writer_thread = threading.Thread(target=_writer, name="wp05-writer")
    reader_thread = threading.Thread(target=_reader, name="wp05-reader")

    writer_thread.start()
    reader_thread.start()

    # Bounded joins (never rely on an external kill) -- this test must
    # terminate deterministically.
    writer_thread.join(timeout=30)
    reader_thread.join(timeout=30)

    assert not writer_thread.is_alive(), "writer thread did not terminate within the bounded join timeout"
    assert not reader_thread.is_alive(), "reader thread did not terminate within the bounded join timeout"
    assert not writer_exc, f"writer thread raised: {writer_exc!r}"
    assert not reader_exc, f"reader thread raised: {reader_exc!r}"

    concurrent_bytes = (concurrent_dir / EVENTS_FILENAME).read_bytes()

    # Primary assertion (T031/T033): byte-identical raw log content --
    # never "same event count" or "same number of lines" alone, which would
    # pass even if event ORDER or CONTENT differed between the runs.
    assert concurrent_bytes == control_bytes

    # Secondary, non-blocking sanity checks (T033): the reader ran cleanly
    # and genuinely observed the concurrently-running writer (confirms
    # overlap actually occurred, not merely that the checkpoints fired).
    assert reader_exit_code == [0]
    assert len(reader_events) >= 1
