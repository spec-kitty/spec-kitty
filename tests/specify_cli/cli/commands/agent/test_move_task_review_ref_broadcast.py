"""RED-first e2e regression tests for #3954 (F-46): bound legacy-prose
``review_ref`` at the WPStatusChanged wire projection.

Drives the REAL ``move-task`` CLI entry point (Typer ``CliRunner``) and the
REAL ``emit_status_transition`` seam across the four transition families the
plan names -- approval, completion (multi-hop), rejection/rework, and direct
emission -- and observes the offered Zeitgeist moment through the shared
``OfferRecorder`` (tests/status/test_zeitgeist_moment_handler.py).

Before the fix, a ``review_ref`` over 240 UTF-8 bytes made the pinned events
codec (``spec_kitty_events.zeitgeist_attrs``) raise
``ZeitgeistAttrsOverflowError``, and ``zeitgeist_bridge._broadcast_moment``
turned that into a whole-moment drop (0 offers) -- silent data loss on the
wire, even though the canonical local ``status.events.jsonl`` always kept the
full note. These tests assert the bounded broadcast instead: a wire
``review_ref`` collapsed to one line and truncated to <=240 UTF-8 bytes, the
moment offered exactly once, and the full local note preserved byte-for-byte.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks import app
from specify_cli.status import adapters
from specify_cli.status.emit import emit_status_transition
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event, read_events
from specify_cli.zeitgeist_client import resolution as resolution_module
from tests.mocked_env import setup_mocked_env
from tests.status.test_zeitgeist_moment_handler import OfferRecorder, _credential

if TYPE_CHECKING:
    from click.testing import Result

pytestmark = [pytest.mark.integration, pytest.mark.fast]

runner = CliRunner()

_MISSION = "review-ref-bound-3954"

#: >240 UTF-8 bytes, single record, genuine multi-line prose review_ref
#: content. T1 proves the collapse-before-truncate ordering: a raw newline
#: would otherwise trip the codec's own control-character guard
#: independently of the byte bound.
_LONG_PROSE_NOTE = (
    "Reviewed the WP03 implementation against every acceptance criterion in the plan and confirmed the "
    "bounded review_ref helper collapses whitespace before truncation, matches the codec byte budget, and "
    "never splits a multi-byte codepoint at the 240-byte boundary.\n"
    "Second line: this note deliberately carries a genuine newline character so the collapse-before-truncate "
    "ordering is exercised end to end, and the persisted local copy must still read back byte for byte."
)
assert len(_LONG_PROSE_NOTE.encode("utf-8")) > 240
assert "\n" in _LONG_PROSE_NOTE


def _build_wp_file(tmp_path: Path, mission_slug: str, wp_id: str) -> Path:
    """Seed a minimal, production-shaped WP file + mission scaffold."""
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify").mkdir(exist_ok=True)
    wp_file = tasks_dir / f"{wp_id}-test.md"
    wp_file.write_text(
        f"---\n"
        f"work_package_id: {wp_id}\n"
        f"title: Test {wp_id}\n"
        f"execution_mode: doc_change\n"
        f"agent: testbot\n"
        f"subtasks: []\n"
        f"owned_files:\n  - src/{wp_id.lower()}/**\n"
        f"authoritative_surface: src/{wp_id.lower()}/\n"
        f"---\n\n# {wp_id}\n\n## Activity Log\n",
        encoding="utf-8",
    )
    return feature_dir


def _seed_wp_in_lane(tmp_path: Path, *, mission_slug: str, wp_id: str, lane: str) -> Path:
    """Seed a feature dir with ``wp_id`` at ``lane`` in the canonical event log."""
    feature_dir = _build_wp_file(tmp_path, mission_slug, wp_id)
    append_event(
        feature_dir,
        StatusEvent(
            event_id=f"seed-{wp_id}-{lane}",
            mission_slug=mission_slug,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane(lane),
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
            reason=f"seed to {lane}",
        ),
    )
    return feature_dir


def _invoke(tmp_path: Path, mission_slug: str, args: list[str]) -> Result:
    with setup_mocked_env(
        tmp_path,
        mission_slug=mission_slug,
        workspace_resolution=FileNotFoundError,
        extra_patches={
            "_validate_ready_for_review": (True, []),
            "_check_unchecked_subtasks": [],
        },
    ):
        return runner.invoke(app, args, catch_exceptions=False)


def _persisted_events(feature_dir: Path, wp_id: str) -> list[StatusEvent]:
    return [e for e in read_events(feature_dir) if e.wp_id == wp_id]


@pytest.fixture(autouse=True)
def _zeitgeist_only_registry() -> None:
    """Isolate every test to the Zeitgeist handlers as the sole fan-out wiring."""
    adapters.reset_handlers()
    adapters.ensure_zeitgeist_moment_handlers()
    yield
    adapters.reset_handlers()
    adapters.ensure_zeitgeist_moment_handlers()


@pytest.fixture
def offer_recorder(monkeypatch: pytest.MonkeyPatch) -> OfferRecorder:
    """Install the shared ``OfferRecorder`` and resolve credentials/focus deterministically."""
    monkeypatch.setattr(resolution_module, "resolve_credentials", lambda cwd, **kwargs: _credential())
    monkeypatch.setattr(resolution_module, "resolve_focus_lease", lambda *a, **k: None)
    return OfferRecorder().install(monkeypatch)


@pytest.mark.regression
def test_approval_with_overlong_prose_broadcasts_bounded_and_persists_full_note(
    tmp_path: Path, offer_recorder: OfferRecorder, caplog: pytest.LogCaptureFixture
) -> None:
    """#3954 T1: an approval carrying a >240-byte multi-line prose
    ``review_ref`` (F-46) broadcasts bounded instead of being dropped whole.
    The wire value is single-line, <=240 UTF-8 bytes, and ends with the
    ellipsis marker; an INFO log names the truncation, but the log is NOT the
    proof -- the full multi-line note must still read back byte-for-byte off
    the canonical ``status.events.jsonl``."""
    caplog.set_level(logging.INFO, logger="specify_cli.status.zeitgeist_bridge")
    feature_dir = _seed_wp_in_lane(tmp_path, mission_slug=_MISSION, wp_id="WP01", lane="in_review")

    result = _invoke(
        tmp_path,
        _MISSION,
        [
            "move-task",
            "WP01",
            "--to",
            "approved",
            "--note",
            _LONG_PROSE_NOTE,
            "--mission",
            _MISSION,
            "--no-auto-commit",
        ],
    )

    assert result.exit_code == 0, f"move-task failed:\n{result.output}"

    moments = offer_recorder.moment_offers()
    assert len(moments) == 1, f"expected exactly one moment offer, got {len(moments)}: {moments}"
    wire_review_ref = moments[0][1]["attrs"]["review_ref"]
    assert len(wire_review_ref.encode("utf-8")) <= 240
    assert "\n" not in wire_review_ref
    assert wire_review_ref.endswith("…")

    # The INFO log is an ADDITIONAL assertion, never the pass condition on its own.
    assert "review_ref" in caplog.text
    assert "truncated" in caplog.text.lower()

    persisted = _persisted_events(feature_dir, "WP01")
    assert persisted, "no persisted events for WP01"
    full_note_events = [e for e in persisted if e.review_ref == _LONG_PROSE_NOTE]
    assert full_note_events, (
        f"expected the full multi-line note preserved byte-for-byte in the canonical local log; persisted review_refs were: {[e.review_ref for e in persisted]}"
    )


@pytest.mark.regression
def test_multihop_transition_offers_exactly_once_per_emitted_event(tmp_path: Path, offer_recorder: OfferRecorder) -> None:
    """#3954 T2: a genuine multi-hop ``move-task`` call (walking several lane
    hops in one invocation) offers exactly one moment PER emitted status
    event -- not exactly one overall. Before the fix, the hop whose
    review_ref carried the operator's overlong prose note silently dropped
    while the other hops offered fine, so offers fell short of the event
    count."""
    feature_dir = _seed_wp_in_lane(tmp_path, mission_slug=_MISSION, wp_id="WP01", lane="in_progress")

    result = _invoke(
        tmp_path,
        _MISSION,
        [
            "move-task",
            "WP01",
            "--to",
            "approved",
            "--note",
            _LONG_PROSE_NOTE,
            "--mission",
            _MISSION,
            "--no-auto-commit",
        ],
    )

    assert result.exit_code == 0, f"move-task failed:\n{result.output}"

    persisted = _persisted_events(feature_dir, "WP01")
    emitted_this_call = [e for e in persisted if e.event_id != "seed-WP01-in_progress"]
    assert len(emitted_this_call) > 1, f"expected a genuine multi-hop call (>1 emitted event), got {len(emitted_this_call)}"

    moments = offer_recorder.moment_offers()
    assert len(moments) == len(emitted_this_call), f"expected one offer per emitted event ({len(emitted_this_call)}), got {len(moments)}"


@pytest.mark.regression
def test_rejection_from_in_review_with_overlong_note_broadcasts_bounded(tmp_path: Path, offer_recorder: OfferRecorder) -> None:
    """#3954 T3: the ``in_review -> in_progress`` review-rejection edge
    threads the operator's ``--note`` into the wire ``review_ref`` (the
    shared wire contract requires one on this edge); an over-240-byte note
    must not drop the moment."""
    _seed_wp_in_lane(tmp_path, mission_slug=_MISSION, wp_id="WP01", lane="in_review")

    result = _invoke(
        tmp_path,
        _MISSION,
        [
            "move-task",
            "WP01",
            "--to",
            "doing",
            "--note",
            _LONG_PROSE_NOTE,
            "--mission",
            _MISSION,
            "--no-auto-commit",
        ],
    )

    assert result.exit_code == 0, f"move-task failed:\n{result.output}"

    moments = offer_recorder.moment_offers()
    assert len(moments) == 1, f"expected exactly one moment offer, got {len(moments)}: {moments}"
    wire_review_ref = moments[0][1]["attrs"]["review_ref"]
    assert len(wire_review_ref.encode("utf-8")) <= 240


@pytest.mark.regression
def test_direct_emission_with_overlong_prose_broadcasts_bounded(tmp_path: Path, offer_recorder: OfferRecorder) -> None:
    """#3954 T4: calling ``emit_status_transition`` directly (bypassing the
    ``move-task`` CLI's guard chain entirely, with a clock-derived occurrence
    time) still bounds an over-long prose ``review_ref`` before the wire."""
    feature_dir = _seed_wp_in_lane(tmp_path, mission_slug=_MISSION, wp_id="WP01", lane="planned")

    emit_status_transition(
        feature_dir,
        wp_id="WP01",
        to_lane="claimed",
        actor="robert",
        mission_slug=_MISSION,
        review_ref=_LONG_PROSE_NOTE,
    )

    moments = offer_recorder.moment_offers()
    assert len(moments) == 1, f"expected exactly one moment offer, got {len(moments)}: {moments}"
    wire_review_ref = moments[0][1]["attrs"]["review_ref"]
    assert len(wire_review_ref.encode("utf-8")) <= 240
    assert "\n" not in wire_review_ref
