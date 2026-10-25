"""Parity between CLI materialization and the shared diary reducer."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest

from specify_cli.status import EVENTS_FILENAME, materialize
from spec_kitty_events.status import reduce as reduce_shared_state

pytestmark = pytest.mark.fast

_FIXTURE_ROOT = files("spec_kitty_events") / "conformance/fixtures/status_diary/replay"
_DIARY_SUFFIX = ".jsonl"
_DIARY_PREFIX = "status_diary_"
# #6605: every replay fixture the installed package ships, not a hand-picked subset, so a new upstream
# fixture (for example seed_lane_authority) is replayed against the CLI as soon as the lock resolves it.
# #4990's concurrent_reject_beats_approve stays pinned by name below as a floor.
_FIXTURE_NAMES = tuple(
    sorted(
        entry.name[len(_DIARY_PREFIX) : -len(_DIARY_SUFFIX)]
        for entry in _FIXTURE_ROOT.iterdir()
        if entry.name.startswith(_DIARY_PREFIX) and entry.name.endswith(_DIARY_SUFFIX)
    )
)


def test_every_packaged_replay_fixture_is_replayed() -> None:
    """The glob is non-vacuous and still holds the fixtures this test used to name."""
    assert {"fresh_mission", "every_lane", "out_of_order_duplicates", "unknown_kinds", "concurrent_reject_beats_approve"} <= set(_FIXTURE_NAMES)
    for name in _FIXTURE_NAMES:
        assert (_FIXTURE_ROOT / f"{_DIARY_PREFIX}{name}_output.json").is_file(), f"replay fixture {name!r} ships no _output.json golden"


@pytest.mark.parametrize("fixture_name", _FIXTURE_NAMES)
def test_written_snapshot_matches_shared_reducer(
    fixture_name: str,
    tmp_path: Path,
) -> None:
    """The committed snapshot is the shared reducer's state plus CLI extras."""
    diary_text = (_FIXTURE_ROOT / f"status_diary_{fixture_name}.jsonl").read_text(encoding="utf-8")
    golden_text = (_FIXTURE_ROOT / f"status_diary_{fixture_name}_output.json").read_text(encoding="utf-8")
    diary_rows = [json.loads(line) for line in diary_text.splitlines()]

    golden = json.loads(golden_text)
    # Each fixture names its own Mission; meta.json must agree or the snapshot's identity fields differ.
    feature_dir = tmp_path / golden["mission_slug"]
    feature_dir.mkdir()
    (feature_dir / EVENTS_FILENAME).write_text(diary_text, encoding="utf-8")
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_number": int(golden["mission_number"]),
                "mission_slug": golden["mission_slug"],
                "mission_type": golden["mission_type"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    materialize(feature_dir)
    written: dict[str, Any] = json.loads((feature_dir / "status.json").read_text(encoding="utf-8"))
    shared_state = reduce_shared_state(diary_rows).to_dict()

    assert shared_state == golden
    written.pop("retrospective", None)
    # #4786 archive-freeze fix: a brand-new mission (this fixture's tmp_path
    # feature_dir has no pre-existing status.json) always materializes at the
    # current schema, which stamps this CLI-only marker -- same pattern as
    # the other CLI-only extras popped below/above.
    written.pop("schema_version", None)
    for wp_state in written["work_packages"].values():
        if wp_state["lane"] == "canceled":
            wp_state.pop("cancellation_reason", None)
            wp_state.pop("reason_source", None)
        # WP04 (#4786): the read-root implementer-attribution projection
        # (reducer._project_implementer_attribution) is another CLI-only
        # extra layered atop the shared reducer's state — same pattern as
        # the cancellation-provenance extras above.
        wp_state.pop("implementer_of_record", None)
    assert written == shared_state
