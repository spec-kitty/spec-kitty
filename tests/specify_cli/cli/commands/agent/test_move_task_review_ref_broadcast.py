"""RED-first e2e regression tests for #4327: ``review_ref`` is pointer-only.

Drives the REAL ``move-task`` CLI entry point (Typer ``CliRunner``) and the
REAL ``emit_status_transition`` seam across the four transition families the
issue names -- approval, completion (multi-hop), rejection/rework, and direct
emission -- and observes the offered Zeitgeist moment through the shared
``OfferRecorder`` (tests/status/test_zeitgeist_moment_handler.py).

Before the fix, ``move-task`` fell back to the operator's ``--note`` prose
when filling the approval/rejection reference, so a >240-byte note landed in
the wire ``review_ref`` attr and the #3954 interim had to truncate it at the
bridge. Now the fallbacks are gone: the reference slot takes the real
pointer (``--approval-ref``, the review-cycle pointer) or a synthetic marker
token (``auto-approval:<WP>:<date>`` / ``approval:<WP>`` / ``review:<WP>``),
the operator's prose stays whole in the durable local ``reason`` (which the
codec keeps off the wire), and the moment broadcasts without any bridge-side
bounding -- the maintainer acceptance bar for this issue: "a long review note
still broadcasts (no >240-byte moment drop, per #3954) while ``review_ref``
carries only a pointer."
"""

from __future__ import annotations

import logging
import re
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

#: >240 UTF-8 bytes, single record, genuine multi-line prose review-note
#: content. With #4327's pointer-only ``review_ref`` this prose never reaches
#: the wire attr at all -- it stays whole in the durable local ``reason``.
_LONG_PROSE_NOTE = (
    "Reviewed the WP03 implementation against every acceptance criterion in the plan and confirmed the "
    "pointer-only review_ref fix removes the note fallback at every producer, keeps the codec's own "
    "240-UTF-8-byte attr bound as the single wire authority, and preserves the operator prose whole.\n"
    "Second line: this note deliberately carries a genuine newline character so the prose-preserved-in-"
    "reason guarantee is exercised end to end, and the persisted local copy must still read back byte "
    "for byte."
)
assert len(_LONG_PROSE_NOTE.encode("utf-8")) > 240
assert "\n" in _LONG_PROSE_NOTE

#: The synthetic marker tokens ``move-task`` mints when no real pointer
#: exists (#4327): ``auto-approval:<WP>:<date>`` (approval facts),
#: ``approval:<WP>`` (durable approval cycle) and ``review:<WP>`` (rejection).
_POINTER_SHAPED_RE = re.compile(r"^((auto-)?approval:WP\d+(:\d{8})?|review:WP\d+)$")


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
def test_approval_with_overlong_prose_broadcasts_pointer_ref_and_persists_full_note(
    tmp_path: Path, offer_recorder: OfferRecorder, caplog: pytest.LogCaptureFixture
) -> None:
    """#4327 T1: an approval carrying a >240-byte multi-line prose ``--note``
    broadcasts with a POINTER-SHAPED ``review_ref`` (the ``--approval-ref``
    value or a synthetic ``approval:<WP>``/``auto-approval:<WP>:<date>``
    token -- never the note), the moment is offered exactly once with no
    bridge-side truncation, and the full multi-line note is preserved
    byte-for-byte in the durable local ``reason``."""
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
    assert _POINTER_SHAPED_RE.match(wire_review_ref), f"wire review_ref must be a pointer or synthetic token, got: {wire_review_ref!r}"
    assert _LONG_PROSE_NOTE not in wire_review_ref
    assert len(wire_review_ref.encode("utf-8")) <= 240
    assert "\n" not in wire_review_ref

    # The interim's bridge-side truncation is gone: nothing logs a truncation.
    assert "truncated" not in caplog.text.lower()

    persisted = _persisted_events(feature_dir, "WP01")
    assert persisted, "no persisted events for WP01"
    note_reason_events = [e for e in persisted if e.reason == _LONG_PROSE_NOTE]
    assert note_reason_events, (
        f"expected the full multi-line note preserved byte-for-byte in the canonical local reason; persisted reasons were: {[e.reason for e in persisted]}"
    )
    # Pointer-only on the durable record too: no persisted event carries the
    # prose in its review_ref slot.
    assert not [e for e in persisted if e.review_ref == _LONG_PROSE_NOTE], (
        f"note prose must never fill a persisted review_ref; persisted review_refs were: {[e.review_ref for e in persisted]}"
    )


@pytest.mark.regression
def test_multihop_transition_offers_exactly_once_per_emitted_event(tmp_path: Path, offer_recorder: OfferRecorder) -> None:
    """#4327 T2: a genuine multi-hop ``move-task`` call (walking several lane
    hops in one invocation) offers exactly one moment PER emitted status
    event -- not exactly one overall. Before the fix, the hop whose
    review_ref carried the operator's overlong prose note silently dropped
    while the other hops offered fine, so offers fell short of the event
    count; with pointer-only refs every hop offers."""
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
def test_rejection_from_in_review_with_overlong_note_broadcasts_pointer_ref(tmp_path: Path, offer_recorder: OfferRecorder) -> None:
    """#4327 T3: the ``in_review -> in_progress`` review-rejection edge
    requires a ``review_ref`` on the wire; with a >240-byte ``--note`` and no
    review-feedback pointer, the slot takes the synthetic ``review:<WP>``
    token (never the note) and the moment still broadcasts."""
    feature_dir = _seed_wp_in_lane(tmp_path, mission_slug=_MISSION, wp_id="WP01", lane="in_review")

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
    assert _POINTER_SHAPED_RE.match(wire_review_ref), f"wire review_ref must be the review pointer or synthetic review:<WP> token, got: {wire_review_ref!r}"
    assert _LONG_PROSE_NOTE not in wire_review_ref

    persisted = _persisted_events(feature_dir, "WP01")
    # Pre-existing behavior (unchanged by #4327): the backward hop prefixes the
    # reason with "backward rewind: in_review -> in_progress: " -- the note is
    # preserved whole after that prefix.
    assert [e for e in persisted if e.reason and e.reason.endswith(_LONG_PROSE_NOTE)], (
        f"expected the full note preserved in reason; persisted reasons were: {[e.reason for e in persisted]}"
    )


@pytest.mark.regression
def test_direct_emission_with_overlong_prose_review_ref_fails_loud_not_silent(
    tmp_path: Path, offer_recorder: OfferRecorder, caplog: pytest.LogCaptureFixture
) -> None:
    """#4327 T4 / no-silent-drop gate: calling ``emit_status_transition``
    directly with an explicit over-240-byte PROSE ``review_ref`` (the one
    remaining way prose can reach the slot -- the operator typed it into the
    pointer slot themselves) rides verbatim to the codec, which drops the
    moment LOUDLY: a logged WARNING naming ``review_ref``, never a silent
    drop and never a bridge-side truncation. The canonical local log keeps
    the value exactly as written."""
    caplog.set_level(logging.WARNING, logger="specify_cli.status.zeitgeist_bridge")
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
    assert moments == [], f"an over-bound review_ref must not broadcast, got: {moments}"
    assert "not broadcast" in caplog.text
    assert "review_ref" in caplog.text

    persisted = _persisted_events(feature_dir, "WP01")
    assert [e for e in persisted if e.review_ref == _LONG_PROSE_NOTE], "the canonical local log keeps the explicitly-written review_ref verbatim"
