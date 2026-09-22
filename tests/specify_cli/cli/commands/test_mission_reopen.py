"""ATDD coverage for ``spec-kitty mission reopen`` (WP02 / FR-002, NFR-004).

These tests pin the binding contract in
``kitty-specs/.../contracts/mission-lifecycle-commands.md``:

* re-open clears ``merged_*`` from ``meta.json`` AND appends a ``MissionReopened``
  lifecycle event (WP01 helper) so ``derive_mission_lifecycle`` reports the
  ``reopened``/actionable surface_state — the load-bearing assertion, since
  clearing ``merged_*`` alone is a no-op for the classifier (D-A2);
* fail-closed on an unrecoverable mission (meta.json absent/corrupt OR the
  mission branch resolves in neither the local repo nor any configured remote):
  exit non-zero, no event, no metadata change (NFR-004);
* a missing worktree directory ALONE is recoverable — NOT fail-closed;
* fail-closed (#1926): a mission that has NOT reached completion (no merge
  marker and no terminal WPs) cannot be re-opened — exit non-zero, no event,
  no metadata change;
* an ambiguous handle surfaces ``MISSION_AMBIGUOUS_SELECTOR`` (no silent slug guess).
"""

from __future__ import annotations

import json
import subprocess
from kernel.clock import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands import mission_type
from specify_cli.status.lifecycle import derive_mission_lifecycle, is_mission_completed
from specify_cli.status.lifecycle_events import (
    MISSION_REOPENED,
    mission_event_log_path,
    read_lifecycle_events,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

runner = CliRunner()

_ULID = "01KV0S99ABCDEFGHJKMNPQRSTV"
_MID8 = _ULID[:8]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".kittify").mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "seed")
    return repo


def _make_merged_mission(
    repo: Path,
    *,
    slug: str = "demo-mission",
    mission_id: str = _ULID,
    create_branch: bool = True,
) -> Path:
    feature_dir = repo / "kitty-specs" / f"{slug}-{_MID8}"
    feature_dir.mkdir(parents=True)
    branch = f"kitty/mission-{slug}-{_MID8}-{_MID8}"
    meta = {
        "slug": f"{slug}-{_MID8}",
        "mission_slug": f"{slug}-{_MID8}",
        "friendly_name": "Demo Mission",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00+00:00",
        "mission_id": mission_id,
        "mid8": _MID8,
        "mission_branch": branch,
        "merged_at": "2026-02-01T00:00:00+00:00",
        "merged_by": "operator",
        "merged_into": "main",
        "merged_strategy": "merge",
        "merged_commit": "deadbeef",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # A terminal WP chain in the event log so the classifier sees a completed
    # mission (no active WPs) — re-open actionability must come from the event,
    # not from clearing merged_* (D-A2). Each line is a reducer-valid StatusEvent.
    log = feature_dir / "status.events.jsonl"
    chain = [
        ("genesis", "planned"),
        ("planned", "claimed"),
        ("claimed", "in_progress"),
        ("in_progress", "for_review"),
        ("for_review", "in_review"),
        ("in_review", "approved"),
        ("approved", "done"),
    ]
    lines = []
    for idx, (frm, to) in enumerate(chain):
        lines.append(
            json.dumps(
                {
                    "event_id": f"01HXYZDONEEVENT{idx:010d}",
                    "mission_slug": f"{slug}-{_MID8}",
                    "mission_id": mission_id,
                    "wp_id": "WP01",
                    "from_lane": frm,
                    "to_lane": to,
                    "at": f"2026-01-1{idx}T00:00:00+00:00",
                    "actor": "claude",
                    "force": frm == "genesis",
                    "execution_mode": "worktree",
                    "reason": None,
                    "review_ref": None,
                    "evidence": None,
                }
            )
        )
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if create_branch:
        _git(repo, "branch", branch)
    return feature_dir


def _invoke(repo: Path, *args: str):
    return runner.invoke(mission_type.app, list(args), env={"PWD": str(repo)})


def _select_completion_alternative(feature_dir: Path, mode: str) -> None:
    """Leave exactly one of the two documented completion proofs present."""
    if mode == "marker_only":
        mission_event_log_path(feature_dir).unlink()
        return
    if mode == "terminal_wps_only":
        meta_path = feature_dir / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta = {key: value for key, value in meta.items() if not key.startswith("merged_")}
        meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return
    raise AssertionError(f"unknown completion mode: {mode}")


def test_reopen_clears_merged_and_emits_event_and_is_actionable(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path)
    feature_dir = _make_merged_mission(repo)
    monkeypatch.chdir(repo)

    result = _invoke(repo, "reopen", _MID8, "--reason", "residual fix")

    assert result.exit_code == 0, result.output

    # merged_* cleared
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    for key in ("merged_at", "merged_by", "merged_into", "merged_strategy", "merged_commit"):
        assert key not in meta, f"{key} should be cleared on re-open"

    # MissionReopened event appended (the authority for actionability)
    events = read_lifecycle_events(mission_event_log_path(feature_dir))
    reopened = [e for e in events if e.get("event_type") == MISSION_REOPENED]
    assert len(reopened) == 1
    payload = reopened[0]["payload"]
    assert payload["reason"] == "residual fix"
    assert payload["mission_id"] == _ULID

    # derive_mission_lifecycle now reports the reopened/actionable surface_state
    lifecycle = derive_mission_lifecycle(feature_dir, now=datetime(2026, 3, 1, tzinfo=UTC))
    assert lifecycle.state == "reopened"
    assert lifecycle.surface_state == "reopened"


@pytest.mark.parametrize("completion_mode", ["marker_only", "terminal_wps_only"])
def test_reopen_supports_each_completion_alternative_without_losing_proof(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, completion_mode: str) -> None:
    """#4870: either documented proof must survive until its reopen audit fact exists."""
    repo = _init_repo(tmp_path)
    feature_dir = _make_merged_mission(repo)
    _select_completion_alternative(feature_dir, completion_mode)
    before_meta = (feature_dir / "meta.json").read_bytes()
    before = json.loads(before_meta)
    monkeypatch.chdir(repo)

    assert is_mission_completed(feature_dir) is True

    result = _invoke(
        repo,
        "reopen",
        _MID8,
        "--reason",
        f"exercise {completion_mode}",
        "--json",
    )

    assert result.exit_code == 0, result.output
    response = json.loads(result.output)
    assert response["result"] == "reopened"

    events = read_lifecycle_events(mission_event_log_path(feature_dir))
    reopened = [event for event in events if event.get("event_type") == MISSION_REOPENED]
    assert len(reopened) == 1
    assert reopened[0]["payload"]["cleared_merge"] == ({key: value for key, value in before.items() if key.startswith("merged_")} or None)

    after = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert not [key for key in after if key.startswith("merged_")]
    assert derive_mission_lifecycle(feature_dir).state == "reopened"


def test_reopen_requires_reason(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path)
    _make_merged_mission(repo)
    monkeypatch.chdir(repo)

    result = _invoke(repo, "reopen", _MID8)
    assert result.exit_code != 0


def test_reopen_does_not_mutate_wp_lanes(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path)
    feature_dir = _make_merged_mission(repo)
    monkeypatch.chdir(repo)

    before = (feature_dir / "status.events.jsonl").read_text(encoding="utf-8").splitlines()
    before_status = [line for line in before if "to_lane" in line]

    result = _invoke(repo, "reopen", _MID8, "--reason", "x")
    assert result.exit_code == 0

    after = (feature_dir / "status.events.jsonl").read_text(encoding="utf-8").splitlines()
    after_status = [line for line in after if "to_lane" in line]
    assert before_status == after_status, "re-open must NOT append WP-lane events"


def test_reopen_fail_closed_when_meta_missing(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path)
    feature_dir = _make_merged_mission(repo)
    (feature_dir / "meta.json").unlink()
    monkeypatch.chdir(repo)

    result = _invoke(repo, "reopen", f"{feature_dir.name}", "--reason", "x")
    assert result.exit_code != 0
    # No event written.
    events = read_lifecycle_events(mission_event_log_path(feature_dir))
    assert not [e for e in events if e.get("event_type") == MISSION_REOPENED]


def test_reopen_fail_closed_when_branch_in_neither_local_nor_remote(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path)
    feature_dir = _make_merged_mission(repo, create_branch=False)
    # No branch exists locally, and there is no configured remote.
    monkeypatch.chdir(repo)

    result = _invoke(repo, "reopen", _MID8, "--reason", "x")
    assert result.exit_code != 0, result.output

    # No event written, merged_* unchanged.
    events = read_lifecycle_events(mission_event_log_path(feature_dir))
    assert not [e for e in events if e.get("event_type") == MISSION_REOPENED]
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("merged_at") == "2026-02-01T00:00:00+00:00"


def test_reopen_recoverable_when_only_worktree_missing(tmp_path: Path, monkeypatch) -> None:
    # Missing worktree dir ALONE is recoverable (branch present) — NOT fail-closed.
    repo = _init_repo(tmp_path)
    feature_dir = _make_merged_mission(repo, create_branch=True)
    monkeypatch.chdir(repo)

    result = _invoke(repo, "reopen", _MID8, "--reason", "x")
    assert result.exit_code == 0, result.output
    events = read_lifecycle_events(mission_event_log_path(feature_dir))
    assert len([e for e in events if e.get("event_type") == MISSION_REOPENED]) == 1


def _make_uncompleted_mission(repo: Path) -> Path:
    """A mission with no merge marker and only active (non-terminal) WPs.

    Such a mission has NOT reached completion, so a re-open must be rejected
    fail-closed (#1926).
    """
    slug = "wip-mission"
    feature_dir = repo / "kitty-specs" / f"{slug}-{_MID8}"
    feature_dir.mkdir(parents=True)
    branch = f"kitty/mission-{slug}-{_MID8}-{_MID8}"
    meta = {
        "slug": f"{slug}-{_MID8}",
        "mission_slug": f"{slug}-{_MID8}",
        "friendly_name": "WIP Mission",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00+00:00",
        "mission_id": _ULID,
        "mid8": _MID8,
        "mission_branch": branch,
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # A WP still in progress — not terminal — so the mission is not completed.
    log = feature_dir / "status.events.jsonl"
    chain = [("genesis", "planned"), ("planned", "claimed"), ("claimed", "in_progress")]
    lines = []
    for idx, (frm, to) in enumerate(chain):
        lines.append(
            json.dumps(
                {
                    "event_id": f"01HXYZWIPEVENT0{idx:09d}",
                    "mission_slug": f"{slug}-{_MID8}",
                    "mission_id": _ULID,
                    "wp_id": "WP01",
                    "from_lane": frm,
                    "to_lane": to,
                    "at": f"2026-01-1{idx}T00:00:00+00:00",
                    "actor": "claude",
                    "force": frm == "genesis",
                    "execution_mode": "worktree",
                    "reason": None,
                    "review_ref": None,
                    "evidence": None,
                }
            )
        )
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _git(repo, "branch", branch)
    return feature_dir


def test_reopen_rejected_when_mission_not_completed(tmp_path: Path, monkeypatch) -> None:
    # #1926: a re-open is only valid once a mission has reached completion. A WIP
    # mission (no merge marker, active WPs) must be rejected fail-closed: non-zero
    # exit, no MissionReopened event, and meta.json left untouched.
    repo = _init_repo(tmp_path)
    feature_dir = _make_uncompleted_mission(repo)
    before_meta = (feature_dir / "meta.json").read_text(encoding="utf-8")
    monkeypatch.chdir(repo)

    result = _invoke(repo, "reopen", _MID8, "--reason", "premature")
    assert result.exit_code != 0, result.output
    # Rich may wrap the message across lines; match on a contiguous fragment.
    assert "cannot re-open" in result.output

    events = read_lifecycle_events(mission_event_log_path(feature_dir))
    assert not [e for e in events if e.get("event_type") == MISSION_REOPENED]
    after_meta = (feature_dir / "meta.json").read_text(encoding="utf-8")
    assert before_meta == after_meta, "meta.json must be untouched on rejection"


def test_second_reopen_blocked_until_recompletion(tmp_path: Path, monkeypatch) -> None:
    # #1926 self-correcting invariant: after a re-open clears merged_* and flips
    # the state to reopened/active, the mission is NOT completed again — so a
    # second re-open (and any follow-up) is blocked until it is re-completed.
    repo = _init_repo(tmp_path)
    feature_dir = _make_merged_mission(repo)
    monkeypatch.chdir(repo)

    first = _invoke(repo, "reopen", _MID8, "--reason", "first reopen")
    assert first.exit_code == 0, first.output

    # State is now reopened/active and merged_at is cleared → not completed.
    lifecycle = derive_mission_lifecycle(feature_dir, now=datetime(2026, 3, 1, tzinfo=UTC))
    assert lifecycle.state == "reopened"

    second = _invoke(repo, "reopen", _MID8, "--reason", "second reopen")
    assert second.exit_code != 0, second.output
    assert "cannot re-open" in second.output

    follow = _invoke(repo, "follow-up", _MID8, "--pr", "99")
    assert follow.exit_code != 0, follow.output
    assert "cannot record follow-up" in follow.output

    # Only the first re-open is recorded; the blocked attempts wrote nothing.
    events = read_lifecycle_events(mission_event_log_path(feature_dir))
    assert len([e for e in events if e.get("event_type") == MISSION_REOPENED]) == 1


def test_format_post_mission_events_renders_reopen_and_follow_up(
    tmp_path: Path,
) -> None:
    # T009: the views.py renderer produces human-readable history lines.
    # Build the input via the CANONICAL emit path (emit_* → read back the
    # persisted envelopes) rather than hand-rolling event dicts, so the test
    # fixture stays in lock-step with the producer contract.
    from specify_cli.status.lifecycle_events import (
        emit_follow_up_recorded,
        emit_mission_reopened,
        mission_event_log_path,
        read_lifecycle_events,
    )
    from specify_cli.status.views import format_post_mission_events

    feature_dir = tmp_path / "kitty-specs" / f"demo-{_MID8}"
    feature_dir.mkdir(parents=True)
    # The mission must be completed for the emit helpers to accept post-mission
    # events (#1926): a merge marker satisfies the precondition.
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "slug": feature_dir.name,
                "mission_slug": feature_dir.name,
                "friendly_name": "Demo",
                "mission_type": "software-dev",
                "target_branch": "main",
                "created_at": "2026-01-01T00:00:00+00:00",
                "mission_id": _ULID,
                "mid8": _MID8,
                "merged_at": "2026-02-01T00:00:00+00:00",
                "merged_into": "main",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    emit_mission_reopened(
        feature_dir,
        mission_id=_ULID,
        mission_slug=feature_dir.name,
        reason="residual fix",
        reopened_by="operator",
        reopened_at="2026-03-01T00:00:00+00:00",
    )
    emit_follow_up_recorded(
        feature_dir,
        mission_id=_ULID,
        mission_slug=feature_dir.name,
        follow_up_type="pr",
        pr_number=42,
        recorded_by="claude",
        recorded_at="2026-03-02T00:00:00+00:00",
    )

    events = read_lifecycle_events(mission_event_log_path(feature_dir))
    lines = format_post_mission_events(events)
    assert any("re-opened by operator" in line and "residual fix" in line for line in lines)
    assert any("follow-up PR #42 by claude" in line for line in lines)
    assert format_post_mission_events([]) == []


def test_reopen_post_emit_clear_failure_is_a_clean_recoverable_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A post-emit ``clear_merge_metadata`` failure must not surface as an
    unhandled traceback.

    The ``MissionReopened`` event is emitted (and durably appended) BEFORE the
    trailing ``clear_merge_metadata`` call. If that trailing call raises
    (documented ``FileNotFoundError`` / concurrent-delete), the event is
    already on disk claiming markers were cleared while ``meta.json`` still
    carries them. The command must surface this as a clean, retryable error
    (not crash) and tell the operator to re-run ``reopen`` to complete the
    marker cleanup — re-running heals it, since the still-present markers keep
    ``is_mission_completed`` true.
    """
    repo = _init_repo(tmp_path)
    feature_dir = _make_merged_mission(repo)
    monkeypatch.chdir(repo)

    def _boom(_feature_dir: Path) -> dict[str, str]:
        raise FileNotFoundError("meta.json vanished mid-clear")

    monkeypatch.setattr("specify_cli.mission_metadata.clear_merge_metadata", _boom)

    result = _invoke(repo, "reopen", _MID8, "--reason", "residual fix")

    assert result.exit_code == 1, result.output
    # A clean, handled exit is a `typer.Exit`-raised `SystemExit` — anything
    # else (e.g. the raw `FileNotFoundError` propagating unhandled) means the
    # failure surfaced as an uncaught traceback rather than a structured error.
    assert type(result.exception) is SystemExit, (
        f"a post-emit clear failure must be handled cleanly (typer.Exit), not raised as an unhandled exception: {result.exception!r}"
    )
    assert "mission_reopen_clear_failed" in result.output or "reopen" in result.output.lower()
    assert "spec-kitty mission reopen" in result.output

    # The audit event is already durably recorded (emit happened before the
    # failing clear) — the divergence is legible, not silent.
    events = read_lifecycle_events(mission_event_log_path(feature_dir))
    reopened = [e for e in events if e.get("event_type") == MISSION_REOPENED]
    assert len(reopened) == 1

    # The clear itself failed, so the markers are still present in meta.json —
    # recoverable by re-running the same command.
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("merged_at") == "2026-02-01T00:00:00+00:00"


def test_reopen_ambiguous_handle_emits_structured_error(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path)
    # Two missions whose mission_id shares the same mid8 prefix → ambiguous handle.
    _make_merged_mission(repo, slug="alpha", mission_id=_MID8 + "AAAAAAAAAAAAAAAAAA")
    second = repo / "kitty-specs" / f"beta-{_MID8}b"
    second.mkdir(parents=True)
    meta = {
        "slug": f"beta-{_MID8}b",
        "mission_slug": f"beta-{_MID8}b",
        "friendly_name": "Beta",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00+00:00",
        "mission_id": _MID8 + "BBBBBBBBBBBBBBBBBB",
        "mid8": _MID8,
    }
    (second / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    monkeypatch.chdir(repo)

    result = _invoke(repo, "reopen", _MID8, "--reason", "x")
    assert result.exit_code != 0
    assert "MISSION_AMBIGUOUS_SELECTOR" in result.output


def test_reopen_ambiguous_handle_emits_json_envelope(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path)
    # Two missions whose mission_id shares the same mid8 prefix → ambiguous handle.
    _make_merged_mission(repo, slug="alpha", mission_id=_MID8 + "AAAAAAAAAAAAAAAAAA")
    second = repo / "kitty-specs" / f"beta-{_MID8}b"
    second.mkdir(parents=True)
    meta = {
        "slug": f"beta-{_MID8}b",
        "mission_slug": f"beta-{_MID8}b",
        "friendly_name": "Beta",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00+00:00",
        "mission_id": _MID8 + "BBBBBBBBBBBBBBBBBB",
        "mid8": _MID8,
    }
    (second / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    monkeypatch.chdir(repo)

    result = _invoke(repo, "reopen", _MID8, "--reason", "x", "--json")
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert set(payload) == {"ok", "error", "handle", "candidates"}
    assert payload["ok"] is False
    assert payload["error"]["code"] == "MISSION_AMBIGUOUS_SELECTOR"
    assert payload["handle"] == _MID8
    assert sorted(payload["candidates"]) == [f"alpha-{_MID8}", f"beta-{_MID8}b"]
    assert isinstance(payload["error"]["message"], str) and payload["error"]["message"]
