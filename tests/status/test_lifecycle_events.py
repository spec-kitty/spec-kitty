"""Tests for the local-first canonical lifecycle event writer.

Covers issue #1067 (project + mission lifecycle events), #1068
(WPCreated immediate persistence), and the diagnostic
``has_non_bootstrap_status_history`` helper consumed by the merge
gate added for #1069.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _git_init(path: Path) -> None:
    """Minimal git init for test fixtures that need a real git root."""
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(path)],
        check=True,
        capture_output=True,
    )


import specify_cli.status.lifecycle_events as lifecycle
from specify_cli.status.lifecycle_events import (
    LIFECYCLE_EVENT_TYPES,
    MISSION_CREATED,
    PLAN_COMPLETED,
    PLAN_STARTED,
    PROJECT_INITIALIZED,
    REVIEWER_SELF_APPROVAL,
    SPECIFY_COMPLETED,
    TASKS_COMPLETED,
    WP_CREATED,
    append_lifecycle_event,
    emit_artifact_phase,
    emit_artifact_phase_local,
    emit_mission_created_local,
    emit_project_initialized,
    emit_reviewer_self_approval,
    emit_wp_created_local,
    has_lifecycle_event,
    has_non_bootstrap_status_history,
    mission_event_log_path,
    project_event_log_path,
    read_lifecycle_events,
    fanout_lifecycle_event_hosted,
    persist_lifecycle_event_local,
)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    _git_init(tmp_path)
    (tmp_path / ".kittify").mkdir()
    return tmp_path


@pytest.fixture()
def feature_dir(tmp_path: Path) -> Path:
    _git_init(tmp_path)
    fd = tmp_path / "kitty-specs" / "demo-mission"
    fd.mkdir(parents=True)
    return fd


# ---------------------------------------------------------------------------
# ProjectInitialized
# ---------------------------------------------------------------------------


def test_project_initialized_persists_and_dedupes(repo: Path) -> None:
    env1 = emit_project_initialized(
        repo,
        project_uuid="proj-123",
        project_slug="demo",
        actor="test",
    )
    env2 = emit_project_initialized(
        repo,
        project_uuid="proj-123",
        project_slug="demo",
        actor="test",
    )

    log = project_event_log_path(repo)
    assert log.exists(), "project event log was not created"
    assert env1 is not None and env1["event_type"] == PROJECT_INITIALIZED
    assert env2 is None, "duplicate ProjectInitialized for the same UUID must be skipped"

    entries = read_lifecycle_events(log)
    assert len(entries) == 1
    payload = entries[0]["payload"]
    assert payload["project_uuid"] == "proj-123"
    assert payload["project_slug"] == "demo"
    assert payload["actor"] == "test"


def test_project_initialized_writes_canonical_jsonl(repo: Path) -> None:
    emit_project_initialized(repo, project_uuid="abc", project_slug="x", actor="t")
    log = project_event_log_path(repo)
    raw = log.read_text(encoding="utf-8").strip().splitlines()
    assert len(raw) == 1
    payload = json.loads(raw[0])
    assert payload["event_type"] == PROJECT_INITIALIZED
    assert payload["aggregate_type"] == "Project"


# ---------------------------------------------------------------------------
# MissionCreated
# ---------------------------------------------------------------------------


def test_mission_created_local_appended_before_any_saas_fan_out(
    feature_dir: Path,
) -> None:
    envelope = emit_mission_created_local(
        feature_dir,
        mission_slug="demo-mission",
        mission_id="01ULID",
        mission_number=None,
        mission_type="software-dev",
        target_branch="main",
    )

    assert envelope is not None
    log = mission_event_log_path(feature_dir)
    entries = read_lifecycle_events(log)
    assert len(entries) == 1
    assert entries[0]["event_type"] == MISSION_CREATED
    assert entries[0]["aggregate_id"] == "01ULID"


def test_mission_created_dedupe_on_mission_slug(feature_dir: Path) -> None:
    emit_mission_created_local(
        feature_dir,
        mission_slug="demo-mission",
        mission_id=None,
        mission_number=None,
        mission_type="software-dev",
        target_branch="main",
    )
    second = emit_mission_created_local(
        feature_dir,
        mission_slug="demo-mission",
        mission_id=None,
        mission_number=None,
        mission_type="software-dev",
        target_branch="main",
    )
    assert second is None
    entries = read_lifecycle_events(mission_event_log_path(feature_dir))
    assert len(entries) == 1


def test_mission_created_payload_contains_required_fields(feature_dir: Path) -> None:
    """The MissionCreated payload must include all fields required by the
    canonical events 5.1.0 schema (``mission_type`` and ``wp_count`` are
    required). See issues #1190 and #1199.

    ``actor`` was payload-forbidden under #1190; spec-kitty-events 8.0.0 added
    it back as an optional WHO field and #75 makes the local emitter resolve
    it, so its presence is now asserted here rather than its absence."""
    envelope = emit_mission_created_local(
        feature_dir,
        mission_slug="demo-mission",
        mission_id="01J6XW9KQT7M0YB3N4R5CQZ2EX",
        mission_number=None,
        mission_type="software-dev",
        target_branch="main",
        wp_count=0,
        friendly_name="Demo Mission",
        purpose_tldr="Demo TLDR",
        purpose_context="Demo context paragraph.",
    )
    assert envelope is not None
    payload = envelope["payload"]
    # Required by the canonical schema (#1199).
    assert payload["mission_type"] == "software-dev"
    assert payload["wp_count"] == 0
    # Other expected keys are still present.
    assert payload["mission_slug"] == "demo-mission"
    assert payload["mission_id"] == "01J6XW9KQT7M0YB3N4R5CQZ2EX"
    assert payload["target_branch"] == "main"
    assert payload["friendly_name"] == "Demo Mission"
    # WHO is set by default (#75): an opaque identifier, never empty.
    assert isinstance(payload["actor"], str) and payload["actor"].strip()


# ---------------------------------------------------------------------------
# MissionCreated actor resolution (#75)
# ---------------------------------------------------------------------------


def _fake_git_config(monkeypatch: pytest.MonkeyPatch, *, stdout: str, error: bool = False):
    """Intercept ``git config`` probes; every other command runs for real."""

    real_run = subprocess.run
    calls: list[list[str]] = []

    def _run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[:3] != ["git", "config", "user.email"]:
            return real_run(cmd, **kwargs)
        calls.append(list(cmd))
        if error:
            raise FileNotFoundError("git binary missing")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", _run)
    return calls


def test_mission_created_local_resolves_actor_from_git_email(feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _fake_git_config(monkeypatch, stdout="robert@example.com\n")

    envelope = emit_mission_created_local(
        feature_dir,
        mission_slug="demo-mission",
        mission_id="01ULID",
        mission_number=None,
        mission_type="software-dev",
        target_branch="main",
    )

    assert envelope is not None
    assert envelope["payload"]["actor"] == "robert@example.com"
    assert calls and calls[0][:3] == ["git", "config", "user.email"]


@pytest.mark.parametrize("error", [False, True], ids=["unconfigured", "git-absent"])
def test_mission_created_local_actor_falls_back_to_cli(feature_dir: Path, monkeypatch: pytest.MonkeyPatch, error: bool) -> None:
    _fake_git_config(monkeypatch, stdout="", error=error)

    envelope = emit_mission_created_local(
        feature_dir,
        mission_slug="demo-mission",
        mission_id="01ULID",
        mission_number=None,
        mission_type="software-dev",
        target_branch="main",
    )

    assert envelope is not None
    assert envelope["payload"]["actor"] == "cli"


def test_mission_created_local_oversized_email_falls_back_to_cli(feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A resolved email over the zeitgeist attrs codec's 240-byte-per-value
    bound must degrade to ``"cli"`` at emit time (#74) — otherwise the value
    passes producer-time validation (no ``max_length`` on the contract) and
    ``to_zeitgeist_attrs`` only rejects it later, silently dropping the whole
    moment instead of just its WHO."""
    from spec_kitty_events.zeitgeist_attrs import ZEITGEIST_ATTRS_MAX_BYTES

    oversized_email = ("a" * (ZEITGEIST_ATTRS_MAX_BYTES + 10)) + "@example.com"
    calls = _fake_git_config(monkeypatch, stdout=f"{oversized_email}\n")

    envelope = emit_mission_created_local(
        feature_dir,
        mission_slug="demo-mission",
        mission_id="01ULID",
        mission_number=None,
        mission_type="software-dev",
        target_branch="main",
    )

    assert envelope is not None
    assert envelope["payload"]["actor"] == "cli"
    assert calls and calls[0][:3] == ["git", "config", "user.email"]


def test_mission_created_local_boundary_length_email_is_kept(feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An email exactly at the byte bound is still a valid actor — only
    strictly-over-bound values fall back."""
    from spec_kitty_events.zeitgeist_attrs import ZEITGEIST_ATTRS_MAX_BYTES

    boundary_email = "a" * (ZEITGEIST_ATTRS_MAX_BYTES - len("@example.com")) + "@example.com"
    assert len(boundary_email.encode("utf-8")) == ZEITGEIST_ATTRS_MAX_BYTES
    _fake_git_config(monkeypatch, stdout=f"{boundary_email}\n")

    envelope = emit_mission_created_local(
        feature_dir,
        mission_slug="demo-mission",
        mission_id="01ULID",
        mission_number=None,
        mission_type="software-dev",
        target_branch="main",
    )

    assert envelope is not None
    assert envelope["payload"]["actor"] == boundary_email


def test_mission_created_local_explicit_actor_wins_without_identity_probe(feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A pinned actor bypasses resolution entirely (other git use is fine —
    the write lock legitimately shells out to git around the append)."""
    calls = _fake_git_config(monkeypatch, stdout="", error=True)

    envelope = emit_mission_created_local(
        feature_dir,
        mission_slug="demo-mission",
        mission_id="01ULID",
        mission_number=None,
        mission_type="software-dev",
        target_branch="main",
        actor="agent:sk-impl-spec-kitty-75",
    )

    assert envelope is not None
    assert envelope["payload"]["actor"] == "agent:sk-impl-spec-kitty-75"
    assert calls == []


# ---------------------------------------------------------------------------
# Artifact phases (Specify / Plan / Tasks)
# ---------------------------------------------------------------------------


def test_artifact_phase_completed_dedupes_on_artifact_path(feature_dir: Path) -> None:
    e1 = emit_artifact_phase(
        feature_dir,
        event_type=SPECIFY_COMPLETED,
        mission_slug="demo-mission",
        actor="test",
        artifact_path="kitty-specs/demo-mission/spec.md",
    )
    e2 = emit_artifact_phase(
        feature_dir,
        event_type=SPECIFY_COMPLETED,
        mission_slug="demo-mission",
        actor="test",
        artifact_path="kitty-specs/demo-mission/spec.md",
    )
    assert e1 is not None
    assert e2 is None


def test_artifact_phase_rejects_unknown_event_type(feature_dir: Path) -> None:
    with pytest.raises(ValueError):
        emit_artifact_phase(
            feature_dir,
            event_type="NotARealPhase",
            mission_slug="demo-mission",
        )


def test_artifact_phase_records_optional_metadata(feature_dir: Path) -> None:
    emit_artifact_phase(
        feature_dir,
        event_type=TASKS_COMPLETED,
        mission_slug="demo-mission",
        mission_number=7,
        artifact_path="kitty-specs/demo-mission/tasks.md",
        summary="Created three work packages",
        wp_count=3,
    )

    payload = read_lifecycle_events(mission_event_log_path(feature_dir))[0]["payload"]
    assert payload["mission_number"] == 7
    assert payload["artifact_path"] == "kitty-specs/demo-mission/tasks.md"
    assert payload["summary"] == "Created three work packages"
    assert payload["wp_count"] == 3


def test_local_artifact_phase_persists_started_without_hosted_fanout(
    feature_dir: Path,
) -> None:
    from specify_cli.status import adapters

    adapters.reset_handlers()
    captured: list[dict[str, object]] = []
    adapters.register_lifecycle_saas_fanout_handler(lambda **kwargs: captured.append(dict(kwargs)))
    try:
        envelope = emit_artifact_phase_local(
            feature_dir,
            event_type=PLAN_STARTED,
            mission_slug="demo-mission",
            actor="test",
            artifact_path="kitty-specs/demo-mission/plan.md",
        )

        assert envelope is not None
        entries = read_lifecycle_events(mission_event_log_path(feature_dir))
        assert entries == [envelope]
        assert entries[0]["payload"]["artifact_path"] == ("kitty-specs/demo-mission/plan.md")
        assert captured == []
    finally:
        adapters.reset_handlers()


def test_local_artifact_phase_persists_completed_without_hosted_fanout(
    feature_dir: Path,
) -> None:
    from specify_cli.status import adapters

    adapters.reset_handlers()
    captured: list[dict[str, object]] = []
    adapters.register_lifecycle_saas_fanout_handler(lambda **kwargs: captured.append(dict(kwargs)))
    try:
        envelope = emit_artifact_phase_local(
            feature_dir,
            event_type=PLAN_COMPLETED,
            mission_slug="demo-mission",
            actor="test",
            artifact_path="kitty-specs/demo-mission/plan.md",
            summary="Plan generated",
        )

        assert envelope is not None
        assert read_lifecycle_events(mission_event_log_path(feature_dir)) == [envelope]
        assert envelope["payload"]["summary"] == "Plan generated"
        assert captured == []
    finally:
        adapters.reset_handlers()


def test_local_artifact_phase_retains_strict_event_type_validation(
    feature_dir: Path,
) -> None:
    with pytest.raises(ValueError, match="Unsupported artifact phase event_type"):
        emit_artifact_phase_local(
            feature_dir,
            event_type="NotARealPhase",
            mission_slug="demo-mission",
        )

    with pytest.raises(ValueError):
        emit_artifact_phase_local(
            feature_dir,
            event_type=PLAN_STARTED,
            mission_slug="demo-mission",
            mission_number="not-an-integer",  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# WPCreated
# ---------------------------------------------------------------------------


def test_wp_created_persists_immediately_and_dedupes(feature_dir: Path) -> None:
    env1 = emit_wp_created_local(
        feature_dir,
        mission_slug="demo-mission",
        wp_id="WP01",
        wp_title="Set up scaffolding",
        depends_on=[],
    )
    env2 = emit_wp_created_local(
        feature_dir,
        mission_slug="demo-mission",
        wp_id="WP01",
        wp_title="Set up scaffolding",
        depends_on=[],
    )
    assert env1 is not None
    assert env2 is None  # idempotent on (mission_slug, wp_id)

    entries = read_lifecycle_events(mission_event_log_path(feature_dir))
    assert [e["event_type"] for e in entries] == [WP_CREATED]
    assert entries[0]["aggregate_id"] == "WP01"


def test_wp_created_full_roster_writes_one_event_per_wp(feature_dir: Path) -> None:
    for wp_id, title in [("WP01", "Alpha"), ("WP02", "Beta"), ("WP03", "Gamma")]:
        emit_wp_created_local(
            feature_dir,
            mission_slug="demo-mission",
            wp_id=wp_id,
            wp_title=title,
        )
    entries = [e for e in read_lifecycle_events(mission_event_log_path(feature_dir)) if e["event_type"] == WP_CREATED]
    assert sorted(e["aggregate_id"] for e in entries) == ["WP01", "WP02", "WP03"]


def test_reviewer_self_approval_persists_and_dedupes(feature_dir: Path) -> None:
    env1 = emit_reviewer_self_approval(
        feature_dir,
        mission_slug="demo-mission",
        wp_id="WP01",
        implementing_actor="codex:gpt-5:implementer",
        intended_reviewer="claude:sonnet:reviewer",
        failure_reason="reviewer exited 1",
    )
    env2 = emit_reviewer_self_approval(
        feature_dir,
        mission_slug="demo-mission",
        wp_id="WP01",
        implementing_actor="codex:gpt-5:implementer",
        intended_reviewer="claude:sonnet:reviewer",
        failure_reason="reviewer exited 1",
    )

    assert env1 is not None
    assert env1["event_type"] == REVIEWER_SELF_APPROVAL
    assert env2 is None
    entries = read_lifecycle_events(mission_event_log_path(feature_dir))
    assert len(entries) == 1
    assert entries[0]["aggregate_id"] == "WP01"
    assert entries[0]["payload"]["intended_reviewer"] == "claude:sonnet:reviewer"
    assert entries[0]["payload"]["fallback_approved"] is True


def test_wp_created_records_optional_metadata(feature_dir: Path) -> None:
    emit_wp_created_local(
        feature_dir,
        mission_slug="demo-mission",
        mission_number=7,
        wp_id="WP09",
        wp_title="Document replay recovery",
        wp_path="kitty-specs/demo-mission/tasks/WP09.md",
    )

    payload = read_lifecycle_events(mission_event_log_path(feature_dir))[0]["payload"]
    assert payload["mission_number"] == 7
    assert payload["wp_path"] == "kitty-specs/demo-mission/tasks/WP09.md"


# ---------------------------------------------------------------------------
# Merge guard: has_non_bootstrap_status_history
# ---------------------------------------------------------------------------


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(e, sort_keys=True) for e in entries) + "\n",
        encoding="utf-8",
    )


def test_has_non_bootstrap_status_history_false_when_only_bootstrap(
    feature_dir: Path,
) -> None:
    log = mission_event_log_path(feature_dir)
    _write_jsonl(
        log,
        [
            {
                "event_id": "01H1",
                "wp_id": "WP01",
                "from_lane": None,
                "to_lane": "planned",
                "force": True,
                "actor": "finalize-tasks",
                "at": "2026-01-01T00:00:00Z",
                "mission_slug": "demo-mission",
            },
            {
                "event_id": "01H2",
                "wp_id": "WP02",
                "from_lane": "planned",
                "to_lane": "planned",
                "force": True,
                "actor": "finalize-tasks",
                "at": "2026-01-01T00:00:01Z",
                "mission_slug": "demo-mission",
            },
        ],
    )
    assert has_non_bootstrap_status_history(feature_dir) is False


def test_has_non_bootstrap_status_history_false_for_genesis_seed(
    feature_dir: Path,
) -> None:
    """#1775 review M6: the canonical post-FSM seed is genesis -> planned with
    force=False. The merge guard must still recognise it as bootstrap (not real
    history), otherwise every seeded log looks like it has advanced past planned.
    """
    log = mission_event_log_path(feature_dir)
    _write_jsonl(
        log,
        [
            {
                "event_id": "01H1",
                "wp_id": "WP01",
                "from_lane": "genesis",
                "to_lane": "planned",
                "force": False,
                "actor": "finalize-tasks",
                "at": "2026-01-01T00:00:00Z",
                "mission_slug": "demo-mission",
            },
        ],
    )
    assert has_non_bootstrap_status_history(feature_dir) is False


def test_has_non_bootstrap_status_history_true_for_real_transition(
    feature_dir: Path,
) -> None:
    log = mission_event_log_path(feature_dir)
    _write_jsonl(
        log,
        [
            {
                "event_id": "01H1",
                "wp_id": "WP01",
                "from_lane": None,
                "to_lane": "planned",
                "force": True,
                "actor": "finalize-tasks",
            },
            {
                "event_id": "01H2",
                "wp_id": "WP01",
                "from_lane": "planned",
                "to_lane": "in_progress",
                "force": False,
                "actor": "claude",
            },
        ],
    )
    assert has_non_bootstrap_status_history(feature_dir) is True


def test_has_non_bootstrap_status_history_false_when_lifecycle_event_present_without_real_transition(
    feature_dir: Path,
) -> None:
    emit_mission_created_local(
        feature_dir,
        mission_slug="demo-mission",
        mission_id=None,
        mission_number=None,
        mission_type="software-dev",
        target_branch="main",
    )
    assert has_non_bootstrap_status_history(feature_dir) is False


def test_has_non_bootstrap_status_history_false_for_lifecycle_plus_bootstrap(
    feature_dir: Path,
) -> None:
    emit_mission_created_local(
        feature_dir,
        mission_slug="demo-mission",
        mission_id=None,
        mission_number=None,
        mission_type="software-dev",
        target_branch="main",
    )
    _write_jsonl(
        mission_event_log_path(feature_dir),
        [
            *read_lifecycle_events(mission_event_log_path(feature_dir)),
            {
                "event_id": "01H1",
                "wp_id": "WP01",
                "from_lane": "planned",
                "to_lane": "planned",
                "force": True,
                "actor": "finalize-tasks",
            },
        ],
    )
    assert has_non_bootstrap_status_history(feature_dir) is False


def test_has_non_bootstrap_status_history_false_when_log_absent(
    tmp_path: Path,
) -> None:
    assert has_non_bootstrap_status_history(tmp_path / "absent") is False


def test_has_non_bootstrap_status_history_tolerates_noise_and_detects_planned_repair(
    feature_dir: Path,
) -> None:
    log = mission_event_log_path(feature_dir)
    log.write_text(
        "\n"
        "not-json\n"
        '["not", "an", "event"]\n'
        + json.dumps(
            {
                "event_id": "01H3",
                "wp_id": "WP01",
                "from_lane": "approved",
                "to_lane": "planned",
                "force": False,
                "actor": "repair",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    assert has_non_bootstrap_status_history(feature_dir) is True


def test_has_non_bootstrap_status_history_false_when_log_read_fails(feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission_event_log_path(feature_dir).write_text("{}", encoding="utf-8")

    def _raise(*args, **kwargs):  # noqa: ANN002, ANN003
        raise OSError("boom")

    monkeypatch.setattr(Path, "read_text", _raise)
    assert has_non_bootstrap_status_history(feature_dir) is False


# ---------------------------------------------------------------------------
# Sanity checks on the public surface
# ---------------------------------------------------------------------------


def test_lifecycle_event_types_complete() -> None:
    assert {
        PROJECT_INITIALIZED,
        MISSION_CREATED,
        SPECIFY_COMPLETED,
        TASKS_COMPLETED,
        WP_CREATED,
        REVIEWER_SELF_APPROVAL,
    } <= LIFECYCLE_EVENT_TYPES


def test_has_lifecycle_event_matches_dedup_keys(feature_dir: Path) -> None:
    log = mission_event_log_path(feature_dir)
    append_lifecycle_event(
        log,
        WP_CREATED,
        {
            "mission_slug": "demo-mission",
            "wp_id": "WP07",
            "wp_title": "demo",
            "depends_on": [],
            "actor": "test",
        },
        aggregate_id="WP07",
        aggregate_type="WorkPackage",
        dedup_keys={"mission_slug": "demo-mission", "wp_id": "WP07"},
    )
    assert has_lifecycle_event(log, event_type=WP_CREATED, dedup_keys={"mission_slug": "demo-mission", "wp_id": "WP07"})
    assert not has_lifecycle_event(log, event_type=WP_CREATED, dedup_keys={"mission_slug": "demo-mission", "wp_id": "WP99"})


def test_read_lifecycle_events_tolerates_unreadable_and_malformed_logs(feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = mission_event_log_path(feature_dir)
    log.write_text(
        "\nnot-json\n" + json.dumps({"event_type": WP_CREATED, "payload": {"wp_id": "WP01"}}) + "\n",
        encoding="utf-8",
    )
    assert len(read_lifecycle_events(log)) == 1

    def _raise(*args, **kwargs):  # noqa: ANN002, ANN003
        raise OSError("boom")

    monkeypatch.setattr(Path, "read_text", _raise)
    assert read_lifecycle_events(log) == []


def test_has_lifecycle_event_ignores_non_mapping_payload(feature_dir: Path) -> None:
    log = mission_event_log_path(feature_dir)
    _write_jsonl(log, [{"event_type": WP_CREATED, "payload": ["not", "a", "mapping"]}])

    assert not has_lifecycle_event(log, event_type=WP_CREATED, dedup_keys={"mission_slug": "demo-mission"})


def test_append_lifecycle_event_rejects_unknown_type(feature_dir: Path) -> None:
    assert (
        append_lifecycle_event(
            mission_event_log_path(feature_dir),
            "NotARealLifecycleEvent",
            {},
            aggregate_id="x",
            aggregate_type="Unknown",
        )
        is None
    )


def test_append_lifecycle_event_returns_none_when_write_fails(feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(path: Path, line: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(lifecycle, "_atomic_append", _raise)

    assert (
        append_lifecycle_event(
            mission_event_log_path(feature_dir),
            WP_CREATED,
            {"mission_slug": "demo-mission", "wp_id": "WP01"},
            aggregate_id="WP01",
            aggregate_type="WorkPackage",
        )
        is None
    )


def test_persist_local_then_explicit_hosted_fanout_uses_same_envelope(
    feature_dir: Path,
) -> None:
    from specify_cli.status import adapters

    adapters.reset_handlers()
    captured: list[dict[str, object]] = []
    adapters.register_lifecycle_saas_fanout_handler(lambda **kwargs: captured.append(dict(kwargs)))
    log_path = mission_event_log_path(feature_dir)
    try:
        envelope = persist_lifecycle_event_local(
            log_path,
            WP_CREATED,
            {"mission_slug": "demo-mission", "wp_id": "WP01"},
            aggregate_id="WP01",
            aggregate_type="WorkPackage",
            mission_slug="demo-mission",
        )

        assert envelope is not None
        assert read_lifecycle_events(log_path) == [envelope]
        assert captured == []

        fanout_lifecycle_event_hosted(envelope, log_path=log_path)

        assert captured == [{"envelope": envelope, "log_path": log_path}]
        assert captured[0]["envelope"] is envelope
        assert read_lifecycle_events(log_path) == [envelope]
    finally:
        adapters.reset_handlers()


def test_append_lifecycle_event_composes_local_write_and_hosted_fanout(
    feature_dir: Path,
) -> None:
    from specify_cli.status import adapters

    adapters.reset_handlers()
    captured: list[dict[str, object]] = []
    adapters.register_lifecycle_saas_fanout_handler(lambda **kwargs: captured.append(dict(kwargs)))
    log_path = mission_event_log_path(feature_dir)
    try:
        envelope = append_lifecycle_event(
            log_path,
            WP_CREATED,
            {"mission_slug": "demo-mission", "wp_id": "WP01"},
            aggregate_id="WP01",
            aggregate_type="WorkPackage",
            mission_slug="demo-mission",
        )

        assert envelope is not None
        assert read_lifecycle_events(log_path) == [envelope]
        assert captured == [{"envelope": envelope, "log_path": log_path}]
    finally:
        adapters.reset_handlers()


def test_local_write_failure_returns_none_without_hosted_fanout(
    feature_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.status import adapters

    adapters.reset_handlers()
    captured: list[dict[str, object]] = []
    adapters.register_lifecycle_saas_fanout_handler(lambda **kwargs: captured.append(dict(kwargs)))

    def fail_write(path: Path, line: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(lifecycle, "_atomic_append", fail_write)
    try:
        envelope = persist_lifecycle_event_local(
            mission_event_log_path(feature_dir),
            WP_CREATED,
            {"mission_slug": "demo-mission", "wp_id": "WP01"},
            aggregate_id="WP01",
            aggregate_type="WorkPackage",
            mission_slug="demo-mission",
        )

        assert envelope is None
        assert captured == []
    finally:
        adapters.reset_handlers()


def test_lifecycle_repo_root_resolution_handles_supported_logs(repo: Path) -> None:
    """FR-001 adoption: ``_repo_root_for_lifecycle_log`` routes to
    ``resolve_canonical_root`` so it is CWD-invariant (D-12).

    Any log path INSIDE a git repo resolves to the canonical root.  The old
    structural path-name filter (project vs mission log pattern check) is
    replaced by the public resolver, so ``unknown_log`` (a path inside the
    same git repo) also resolves correctly.  A path not inside any git repo,
    and ``None``, still returns ``None`` (fail-closed).
    """
    project_log = project_event_log_path(repo)
    mission_log = repo / "kitty-specs" / "demo-mission" / "status.events.jsonl"
    # Any path inside the same git repo resolves to the canonical root.
    other_log = repo / "other" / "status.events.jsonl"

    assert lifecycle._repo_root_for_lifecycle_log(None) is None
    assert lifecycle._repo_root_for_lifecycle_log(project_log) == repo
    assert lifecycle._repo_root_for_lifecycle_log(mission_log) == repo
    # After adoption: other paths inside the git repo also resolve (no path-name filter).
    assert lifecycle._repo_root_for_lifecycle_log(other_log) == repo


def test_lifecycle_repo_root_resolution_fails_closed_outside_git(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A path the resolver cannot anchor to a git root returns ``None``.

    Fail-closed branch: when ``resolve_canonical_root`` raises
    ``WorkspaceRootNotFound`` (path not inside any git repo), the helper
    swallows it and returns ``None`` rather than guessing a root.
    """
    from specify_cli.workspace.root_resolver import WorkspaceRootNotFound

    def _raise(_start: Path) -> Path:
        raise WorkspaceRootNotFound("no git root")

    monkeypatch.setattr(lifecycle, "resolve_canonical_root", _raise)
    assert lifecycle._repo_root_for_lifecycle_log(repo / "anywhere.jsonl") is None


def test_validate_lifecycle_payload_rejects_unexpected_extra_fields() -> None:
    """The canonical-conformance guard catches extra-property drift at
    emit time. This is the regression guard for issue
    Priivacy-ai/spec-kitty#1190 — the exact shape that previously
    sailed through the local validator and only failed at the SaaS
    jsonschema boundary."""
    bad_payload = {
        "mission_slug": "demo",
        "mission_number": None,
        "target_branch": "main",
        "mission_id": "01J6XW9KQT7M0YB3N4R5CQZ2EX",
        # extra — schema forbids it. NOT ``actor``: events 8.0.0 declared an
        # optional opaque ``actor`` on MissionCreated/MissionClosed, so the
        # drift probe uses a key that is still outside the contract.
        "emitted_by": "spec-kitty mission create",
        "created_at": "2026-05-20T00:00:00+00:00",
        "friendly_name": "Demo",
        "purpose_tldr": "tldr",
        "purpose_context": "context",
    }
    with pytest.raises(ValueError, match="emitted_by"):
        lifecycle._validate_lifecycle_payload("MissionCreated", bad_payload)


def test_validate_lifecycle_payload_passes_when_payload_matches_schema() -> None:
    """A fully-conformant MissionCreated payload passes the validator.

    The previous version of this test passed a payload missing
    ``mission_type`` and ``wp_count`` and asserted the validator
    tolerated them — that codified the bug from Priivacy-ai/spec-kitty#1199.
    The widened validator now requires both fields; the test reflects the
    correct canonical contract.
    """
    good_payload = {
        "mission_slug": "demo",
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "wp_count": 0,
        "mission_id": "01J6XW9KQT7M0YB3N4R5CQZ2EX",
        "created_at": "2026-05-20T00:00:00+00:00",
        "friendly_name": "Demo",
        "purpose_tldr": "tldr",
        "purpose_context": "context",
    }
    # Should not raise.
    lifecycle._validate_lifecycle_payload("MissionCreated", good_payload)


def test_validate_lifecycle_payload_rejects_missing_required_fields() -> None:
    """The widened validator catches missing-required-field drift, which
    the previous extras-only scope let through. Regression guard for
    Priivacy-ai/spec-kitty#1199 — without the widening, a payload
    missing ``mission_type`` would sail past the local guard and only
    fail at the SaaS jsonschema boundary."""
    bad_payload = {
        "mission_slug": "demo",
        "mission_number": None,
        # mission_type intentionally omitted — this was the #1199 drift
        "target_branch": "main",
        # wp_count also intentionally omitted
        "mission_id": "01J6XW9KQT7M0YB3N4R5CQZ2EX",
        "created_at": "2026-05-20T00:00:00+00:00",
        "friendly_name": "Demo",
        "purpose_tldr": "tldr",
        "purpose_context": "context",
    }
    with pytest.raises(ValueError, match="mission_type"):
        lifecycle._validate_lifecycle_payload("MissionCreated", bad_payload)


def test_validate_lifecycle_payload_falls_through_for_unknown_event_types() -> None:
    """Unknown event types (i.e. not yet known to the installed events
    package) must pass through quietly so adding a new event type
    upstream doesn't become a sudden hard failure for installed CLIs."""
    # Should not raise even for a completely-made-up event_type.
    lifecycle._validate_lifecycle_payload("NotARealEventType", {"foo": "bar"})


def test_validate_lifecycle_payload_strictly_validates_post_mission_types() -> None:
    """MISSION_REOPENED / FOLLOW_UP_RECORDED take the strict-validation path.

    ``spec_kitty_events`` 11.0.0 retired the local-only concept and removed
    ``LOCAL_ONLY_EVENT_TYPES`` (#6399), so the post-mission types are no longer
    exempt: a payload that is nowhere near canonical shape must now raise,
    like any other known lifecycle type.
    """
    from spec_kitty_events.conformance.validators import _EVENT_TYPE_TO_MODEL

    assert lifecycle.MISSION_REOPENED in _EVENT_TYPE_TO_MODEL
    assert lifecycle.FOLLOW_UP_RECORDED in _EVENT_TYPE_TO_MODEL
    malformed_payload = {"unexpected_field": "drift", "mission_slug": "demo"}
    for event_type in lifecycle.POST_MISSION_LIFECYCLE_EVENT_TYPES:
        with pytest.raises(ValueError, match="fails canonical contract"):
            lifecycle._validate_lifecycle_payload(event_type, malformed_payload)


def test_validate_lifecycle_payload_still_strict_for_delivery_path_types() -> None:
    """A known delivery-path event type validates strictly.

    MissionCreated still rejects a payload with extra/missing fields.
    """
    bad_payload = {
        "mission_slug": "demo",
        "mission_number": None,
        "target_branch": "main",
        "mission_id": "01J6XW9KQT7M0YB3N4R5CQZ2EX",
        # extra — schema forbids it (see the drift-probe note above: events
        # 8.0.0 declared an optional ``actor``, so probe with a foreign key).
        "emitted_by": "spec-kitty mission create",
        "created_at": "2026-05-20T00:00:00+00:00",
        "friendly_name": "Demo",
        "purpose_tldr": "tldr",
        "purpose_context": "context",
    }
    with pytest.raises(ValueError, match="emitted_by"):
        lifecycle._validate_lifecycle_payload(lifecycle.MISSION_CREATED, bad_payload)


_SAAS_KW = {
    "build_id": "build-1",
    "project_uuid": "proj-uuid",
    "project_slug": "demo",
    "node_id": "node-1",
    "lamport_clock": 1,
}


def test_build_saas_lifecycle_queue_event_returns_none_for_invalid_event_type_or_payload() -> None:
    """A non-queueable envelope (bad ``event_type``/``payload``) yields None."""
    # Non-str event_type.
    assert lifecycle.build_saas_lifecycle_queue_event({"event_type": None, "payload": {}}, **_SAAS_KW) is None
    # Non-Mapping payload.
    assert lifecycle.build_saas_lifecycle_queue_event({"event_type": "ProjectInitialized", "payload": "not-a-mapping"}, **_SAAS_KW) is None


def test_build_saas_lifecycle_queue_event_returns_none_for_invalid_aggregate_type() -> None:
    """A valid event_type+payload but non-str ``aggregate_type`` yields None."""
    assert (
        lifecycle.build_saas_lifecycle_queue_event(
            {"event_type": "ProjectInitialized", "payload": {}, "aggregate_type": None},
            **_SAAS_KW,
        )
        is None
    )
