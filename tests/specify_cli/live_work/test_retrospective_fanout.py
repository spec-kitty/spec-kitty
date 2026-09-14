"""The retrospective seam's folded-#4267 live frames — machine-tested.

``retrospective/lifecycle_events.py`` records captured/failed/skipped
locally; #4268 folds #4267's lifecycle continuity in by publishing each
outcome as a live relay frame *after* the local append — the same
fire-and-forget posture the decision seam uses. The publish is
monkeypatched here (the socket path itself is covered in
``test_publisher.py``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.retrospective import lifecycle_events as retro
from specify_cli.retrospective.schema import GenRetrospectiveRecord

pytestmark = pytest.mark.fast


@pytest.fixture
def captured_calls(monkeypatch):
    calls: list[list] = []
    from specify_cli.live_work import publisher as publisher_module

    def _fake_publish(observations, *, cwd, report=None):
        calls.append(list(observations))
        report_obj = report if report is not None else publisher_module.PublishReport()
        for observation in observations:
            report_obj.sent.append(observation.kind.value)
        return report_obj

    monkeypatch.setattr(publisher_module, "publish_observations", _fake_publish)
    # The retrospective seam imports the function inside the helper, so
    # patch the name the helper resolves as well.
    import specify_cli.live_work

    monkeypatch.setattr(specify_cli.live_work, "publish_observations", _fake_publish)
    return calls


@pytest.fixture
def mission_repo(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    mission_dir = root / "kitty-specs" / "080-demo"
    mission_dir.mkdir(parents=True)
    mission_id = "01J" + "23456789ABCDEFGHJKMNPQRST"[:23]
    (mission_dir / "meta.json").write_text(json.dumps({"mission_id": mission_id, "mission_slug": "080-demo"}), encoding="utf-8")
    # resolve_retrospective_home / the status lock need a git repo.
    import subprocess

    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/acme/repo.git"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(exist_ok=True)
    return root


def _record(mission_id: str) -> GenRetrospectiveRecord:
    return GenRetrospectiveRecord(
        schema_version=1,
        mission_id=mission_id,
        mission_slug="080-demo",
        generator_version="test",
        findings_status="ran_no_findings",
        proposals=[],
        evidence_refs=[],
        policy_source={"source": "test"},
    )


def test_emit_captured_publishes_the_live_frame_after_local_append(mission_repo: Path, captured_calls) -> None:
    mission_id = "01J" + "23456789ABCDEFGHJKMNPQRST"[:23]
    retro.emit_captured(
        _record(mission_id),
        mission_repo,
        provenance_kind="runtime_post_completion",
        actor=retro.Actor(kind="runtime", id="test"),
    )
    assert len(captured_calls) == 1
    observation = captured_calls[0][0]
    assert observation.kind.value == "lifecycle.retrospective_captured"
    assert observation.mission is not None
    assert observation.mission.mission_id == mission_id
    # The local record landed first — the frame is beside it, not instead of it.
    log = mission_repo / "kitty-specs" / "080-demo" / "status.events.jsonl"
    assert log.exists() and "RetrospectiveCaptured" in log.read_text(encoding="utf-8")


def test_emit_capture_failed_publishes_failure_with_inline_text(mission_repo: Path, captured_calls) -> None:
    mission_id = "01J" + "23456789ABCDEFGHJKMNPQRST"[:23]
    retro.emit_capture_failed(
        mission_id,
        "080-demo",
        mission_repo,
        failure_category="generator_exception",
        failure_message="generator crashed",
        remediation_hint=None,
        policy_source={"source": "test"},
        attempted_provenance_kind="runtime_post_completion",
        missing_artifacts=None,
        actor=retro.Actor(kind="runtime", id="test"),
    )
    observation = captured_calls[0][0]
    assert observation.kind.value == "lifecycle.retrospective_failed"
    assert observation.text and "generator crashed" in observation.text


def test_emit_skipped_publishes_skip_with_inline_text(mission_repo: Path, captured_calls) -> None:
    mission_id = "01J" + "23456789ABCDEFGHJKMNPQRST"[:23]
    retro.emit_skipped(
        mission_id,
        "080-demo",
        mission_repo,
        skip_reason="operator bypassed",
        skip_reason_source="cli_flag",
        policy_source={"source": "test"},
        actor=retro.Actor(kind="human", id="op"),
    )
    observation = captured_calls[0][0]
    assert observation.kind.value == "lifecycle.retrospective_skipped"
    assert observation.text and "operator bypassed" in observation.text


def test_moment_handler_kill_switch_silences_the_frame(mission_repo: Path, captured_calls, monkeypatch) -> None:
    monkeypatch.setenv("SPEC_KITTY_NO_MOMENT_HANDLERS", "1")
    mission_id = "01J" + "23456789ABCDEFGHJKMNPQRST"[:23]
    retro.emit_captured(
        _record(mission_id),
        mission_repo,
        provenance_kind="runtime_post_completion",
        actor=retro.Actor(kind="runtime", id="test"),
    )
    assert captured_calls == []
    # The local record still landed — the switch only silences the frame.
    log = mission_repo / "kitty-specs" / "080-demo" / "status.events.jsonl"
    assert "RetrospectiveCaptured" in log.read_text(encoding="utf-8")
