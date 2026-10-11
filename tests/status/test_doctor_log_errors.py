"""Read-only corruption diagnosis through the real store, doctor and CLI (#5924)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import IO, Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.status import app
from specify_cli.status.doctor import Category, Finding, Severity, run_doctor
from specify_cli.status.lifecycle_events import MISSION_CREATED, REVIEWER_SELF_APPROVAL
from specify_cli.status.reducer import SNAPSHOT_FILENAME, materialize_snapshot
from specify_cli.status.store import EVENTS_FILENAME, StoreError, read_event_stream

pytestmark = pytest.mark.fast

SLUG = "034-test"
EVENT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
ANNOTATION_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAW"
VALID_DELTA = {"agent": "test-agent", "subtasks": {"T001": "done"}}
CASES = ("json", "nonobject", "schema", "unknown-kind", "delta", "subtasks", "utf8", "permission", "directory", "identity")


def _annotation(delta: object) -> dict[str, object]:
    return {
        "kind": "annotation",
        "event_id": ANNOTATION_ID,
        "wp_id": "WP01",
        "at": "2026-10-11T14:00:00Z",
        "actor": "test-agent",
        "delta": delta,
    }


def _valid_history() -> bytes:
    transition = {
        "event_id": EVENT_ID,
        "mission_slug": SLUG,
        "wp_id": "WP01",
        "from_lane": "genesis",
        "to_lane": "planned",
        "at": "2026-10-11T14:00:00Z",
        "actor": "test-agent",
        "force": False,
        "execution_mode": "direct_repo",
    }
    lifecycle = {"event_type": MISSION_CREATED, "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAT", "payload": {"mission_slug": SLUG}}
    # Line 6 is the appended bad record; blank rows count as physical rows.
    return ("\n".join([json.dumps(lifecycle), json.dumps(transition), "", json.dumps(_annotation(VALID_DELTA)), " "]) + "\n").encode()


@pytest.fixture(params=[False, True], ids=["no-snapshot", "snapshot"])
def mission_dir(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    mission = tmp_path / "kitty-specs" / SLUG
    (mission / "tasks").mkdir(parents=True)
    (mission / "tasks" / "WP01-work.md").write_text("---\nwork_package_id: WP01\n---\n", encoding="utf-8")
    (mission / EVENTS_FILENAME).write_bytes(_valid_history())
    if request.param:
        snapshot = materialize_snapshot(mission).to_dict()
        (mission / SNAPSHOT_FILENAME).write_text(json.dumps(snapshot), encoding="utf-8")
    return mission


def _evidence(mission: Path) -> tuple[bytes | str | None, bytes | None]:
    log, snapshot = mission / EVENTS_FILENAME, mission / SNAPSHOT_FILENAME
    log_state = "directory" if log.is_dir() else log.read_bytes() if log.exists() else None
    return log_state, snapshot.read_bytes() if snapshot.exists() else None


@pytest.fixture(params=CASES)
def damaged_log(
    mission_dir: Path,
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[str, int | None]]:
    log = mission_dir / EVENTS_FILENAME
    case = request.param
    records = {
        "json": (b"{not json\n", "Expecting property name enclosed in double quotes"),
        "nonobject": (b"[]\n", "expected JSON object"),
        "schema": (b"{}\n", "'event_id'"),
        "unknown-kind": (b'{"kind":"future-kind"}\n', "Unknown event kind 'future-kind'"),
        "delta": ((json.dumps(_annotation([])) + "\n").encode(), "'list' object has no attribute 'get'"),
        "subtasks": ((json.dumps(_annotation({"subtasks": []})) + "\n").encode(), "'list' object has no attribute 'items'"),
        "utf8": (b"\xff\n", "'utf-8' codec can't decode byte 0xff"),
    }
    # Otherwise valid transition: only its identity is malformed, with no mission_id.
    bad_identity = json.loads(_valid_history().splitlines()[1])
    bad_identity["mission_slug"] = 123
    records["identity"] = ((json.dumps(bad_identity) + "\n").encode(), "'int' object has no attribute 'strip'")
    with monkeypatch.context() as boundary:
        if case == "directory":
            log.unlink()
            log.mkdir()
            # Windows may report PermissionError for a directory; use the real
            # filesystem reason rather than pinning a POSIX-only error string.
            with pytest.raises(OSError, match=re.escape(str(log))) as exc_info:
                log.read_text(encoding="utf-8")
            reason = str(exc_info.value)
            line = None
        elif case == "permission":
            original_read = Path.read_text

            def scoped_read(path: Path, *args: Any, **kwargs: Any) -> str:
                if path == log:
                    raise PermissionError(13, "Permission denied", str(log))
                return original_read(path, *args, **kwargs)

            boundary.setattr(Path, "read_text", scoped_read)
            reason, line = "Permission denied", None
        else:
            bad_row, reason = records[case]
            log.write_bytes(_valid_history() + bad_row)
            line = None if case == "utf8" else 6
        yield reason, line
    # Recovery is explicit fixture work, never doctor work.
    if log.is_dir():
        log.rmdir()
    log.write_bytes(_valid_history())
    before = _evidence(mission_dir)
    stream = read_event_stream(mission_dir)
    assert len(stream.transitions) == len(stream.annotations) == 1
    assert stream.annotations[0].delta.subtasks == {"T001": "done"}
    repaired = run_doctor(mission_dir, SLUG, mission_dir.parents[1])
    if (mission_dir / SNAPSHOT_FILENAME).exists():
        assert repaired.is_healthy
    else:
        # Existing semantics: readable populated history needs a derived snapshot.
        assert [f.category for f in repaired.findings] == [Category.MATERIALIZATION_DRIFT]
        assert "status.json is missing" in repaired.findings[0].message
        assert not repaired.has_errors
    assert _evidence(mission_dir) == before


def _assert_diagnostic(finding: Finding, mission: Path, reason: str, line: int | None) -> None:
    assert finding.severity == Severity.ERROR
    assert finding.category == "event_log_error"
    assert finding.wp_id is None
    assert str((mission / EVENTS_FILENAME).resolve()) in finding.message
    assert reason in finding.message
    if line is None:
        assert not re.search(r"\bline \d+", finding.message)
    else:
        assert re.findall(r"\bon line (\d+)\b", finding.message) == [str(line)]
    action = finding.recommended_action.lower()
    assert "preserve" in action and "evidence" in action
    assert "trusted" in action and "access" in action and "rerun" in action
    assert not any(word in action for word in ("delete", "drop", "--fix", "backfill", "materialize"))


def test_run_doctor_reports_corrupt_authority_without_mutation(
    mission_dir: Path,
    damaged_log: tuple[str, int | None],
) -> None:
    before = _evidence(mission_dir)
    result = run_doctor(mission_dir, SLUG, mission_dir.parents[1])

    assert not result.is_healthy and result.has_errors
    assert len(result.findings) == 1  # No initialization/drift/backfill/self-review fallout.
    _assert_diagnostic(result.findings[0], mission_dir, *damaged_log)
    assert _evidence(mission_dir) == before


@pytest.mark.parametrize("json_output", [False, True], ids=["text", "json"])
def test_cli_reports_corrupt_authority_without_traceback_or_mutation(
    mission_dir: Path,
    damaged_log: tuple[str, int | None],
    json_output: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.cli.commands.agent import status

    # Keep Rich's text table wide enough to inspect the actual path/reason, not ellipses.
    monkeypatch.setattr(status.console, "width", 2000)
    before = _evidence(mission_dir)
    with (
        patch("specify_cli.runtime.doctor.run_global_checks", return_value=[]),
        patch("specify_cli.cli.commands.agent.status._resolve_status_surface", return_value=(mission_dir, SLUG, mission_dir.parents[1])),
    ):
        result = CliRunner().invoke(app, ["doctor"] + (["--json"] if json_output else []))

    assert result.exit_code == 1, (result.output, result.exception)
    assert isinstance(result.exception, SystemExit), result.exception
    assert "Traceback" not in result.output
    if json_output:
        report = json.loads(result.output)
        assert report["healthy"] is False
        assert report["mission_slug"] == SLUG
        assert len(report["findings"]) == 1
        _assert_diagnostic(Finding(**report["findings"][0]), mission_dir, *damaged_log)
    else:
        assert "Issues found" in result.output and "Healthy" not in result.output
        assert "error" in result.output and "event_log_error" in result.output
        assert str((mission_dir / EVENTS_FILENAME).resolve()) in result.output
        assert damaged_log[0] in result.output
        assert "preserve" in result.output.lower() and "rerun" in result.output.lower()
    assert _evidence(mission_dir) == before


def test_independent_checks_survive_corruption_and_dependent_checks_do_not(
    mission_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.git.sparse_checkout import scan_repo

    # Real issue/frontmatter checks; only the repo-level probe is deterministic setup.
    (mission_dir / "spec.md").write_text("Fixes #5924.\n", encoding="utf-8")
    (mission_dir / "plan.md").write_text("---\nagent: first\nagent: second\n---\n", encoding="utf-8")
    (mission_dir / "tasks" / "WP02-work.md").write_text("---\nwork_package_id: WP02\n---\n", encoding="utf-8")
    (mission_dir / EVENTS_FILENAME).write_bytes(b"{not json\n")
    repo = mission_dir.parents[1]
    clean_report = scan_repo(repo)
    from dataclasses import replace

    active = replace(clean_report.primary, config_enabled=True)
    report = replace(clean_report, primary=active)
    monkeypatch.setattr("specify_cli.git.sparse_checkout.scan_repo", lambda _root: report)
    before = _evidence(mission_dir)

    result = run_doctor(mission_dir, SLUG, repo)

    assert {str(f.category) for f in result.findings} == {
        "event_log_error",
        "issue_matrix",
        "sparse_checkout",
        "duplicate_frontmatter_key",
    }
    assert any("#5924" in f.message for f in result.findings_by_category(Category.ISSUE_MATRIX))
    assert any("agent" in f.message for f in result.findings_by_category(Category.DUPLICATE_FRONTMATTER_KEY))
    assert _evidence(mission_dir) == before


@pytest.mark.parametrize("content", [None, b"", b"\n \n\n"], ids=["missing", "empty", "blank"])
def test_legitimate_empty_history_preserves_initialization_semantics(
    tmp_path: Path,
    content: bytes | None,
) -> None:
    if content is not None:
        (tmp_path / EVENTS_FILENAME).write_bytes(content)
    before = _evidence(tmp_path)
    assert run_doctor(tmp_path, SLUG, tmp_path).is_healthy
    assert _evidence(tmp_path) == before
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "WP01-work.md").write_text("---\nwork_package_id: WP01\n---\n", encoding="utf-8")
    result = run_doctor(tmp_path, SLUG, tmp_path)
    assert [f.category for f in result.findings] == [Category.UNINITIALIZED_STATUS]
    assert result.findings[0].severity == Severity.WARNING
    assert _evidence(tmp_path) == before


def test_readable_history_keeps_real_drift_and_wp_reconciliation(mission_dir: Path) -> None:
    (mission_dir / SNAPSHOT_FILENAME).write_text(json.dumps({"work_packages": {}}), encoding="utf-8")
    (mission_dir / "tasks" / "WP01-work.md").unlink()
    (mission_dir / "tasks" / "WP02-work.md").write_text("---\nwork_package_id: WP02\n---\n", encoding="utf-8")
    before = _evidence(mission_dir)

    result = run_doctor(mission_dir, SLUG, mission_dir.parents[1])

    assert result.findings_by_category(Category.MATERIALIZATION_DRIFT)
    membership = result.findings_by_category(Category.WP_FILE_DRIFT)
    assert [(f.wp_id, f.severity) for f in membership] == [("WP01", Severity.ERROR), ("WP02", Severity.ERROR)]
    assert not any(f.category == "event_log_error" for f in result.findings)
    assert _evidence(mission_dir) == before


@pytest.mark.parametrize("state", ["claimed", "done", "empty"])
def test_unreadable_log_suppresses_real_snapshot_dependent_findings(tmp_path: Path, state: str) -> None:
    mission = tmp_path / "kitty-specs" / SLUG
    (mission / "tasks").mkdir(parents=True)
    (mission / "tasks" / "WP01-work.md").write_text("---\nwork_package_id: WP01\n---\n", encoding="utf-8")
    (tmp_path / ".worktrees" / f"{SLUG}-lane-a").mkdir(parents=True)
    wps = (
        {}
        if state == "empty"
        else {
            "WP01": {"lane": state, "agent": "", "last_transition_at": "2020-01-01T00:00:00Z"},
        }
    )
    (mission / SNAPSHOT_FILENAME).write_text(json.dumps({"work_packages": wps}), encoding="utf-8")
    (mission / EVENTS_FILENAME).write_bytes(b"{not json\n")
    before = _evidence(mission)

    broken = run_doctor(mission, SLUG, tmp_path)

    assert len(broken.findings) == 1
    _assert_diagnostic(broken.findings[0], mission, "Invalid JSON", 1)
    assert _evidence(mission) == before
    # The same snapshot must expose legitimate findings once authority is restored.
    (mission / EVENTS_FILENAME).write_bytes(_valid_history())
    repaired_before = _evidence(mission)
    repaired = run_doctor(mission, SLUG, tmp_path)
    expected = {
        "claimed": {Category.STALE_CLAIM, Category.BLANKED_RUNTIME_SLOT, Category.MATERIALIZATION_DRIFT},
        "done": {Category.ORPHAN_WORKSPACE, Category.MATERIALIZATION_DRIFT},
        "empty": {Category.UNINITIALIZED_STATUS, Category.MATERIALIZATION_DRIFT},
    }
    assert {f.category for f in repaired.findings} == expected[state]
    assert _evidence(mission) == repaired_before


def _add_independent_findings(mission: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.git.sparse_checkout import scan_repo

    (mission / "spec.md").write_text("Fixes #5924.\n", encoding="utf-8")
    (mission / "plan.md").write_text("---\nagent: first\nagent: second\n---\n", encoding="utf-8")
    (mission / "tasks" / "WP02-work.md").write_text("---\nwork_package_id: WP02\n---\n", encoding="utf-8")
    report = scan_repo(mission.parents[1])
    active_report = replace(report, primary=replace(report.primary, config_enabled=True))
    monkeypatch.setattr("specify_cli.git.sparse_checkout.scan_repo", lambda _root: active_report)


@pytest.fixture(params=["next-read", "review-read"])
def late_read_failure(
    mission_dir: Path,
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[Exception], int]:
    """Fail a specific later text-open, not any unrelated path or binary read."""
    original_open = Path.open
    has_snapshot = (mission_dir / SNAPSHOT_FILENAME).exists()
    # With a snapshot drift replays through both typed and raw store readers.
    fail_at = 4 if request.param == "review-read" and has_snapshot else 2
    reads = 0

    def install(error: Exception) -> int:
        def scoped_open(path: Path, mode: str = "r", *args: Any, **kwargs: Any) -> IO[Any]:
            nonlocal reads
            if path == mission_dir / EVENTS_FILENAME and mode == "r":
                reads += 1
                if reads == fail_at:
                    raise error
            return original_open(path, mode, *args, **kwargs)

        monkeypatch.setattr(Path, "open", scoped_open)
        return fail_at

    return install


def _late_read_error(kind: str, mission: Path) -> Exception:
    return {
        "unicode": UnicodeDecodeError("utf-8", b"\xff", 0, 1, "late decode failure"),
        "permission": PermissionError(13, "late permission failure", str(mission / EVENTS_FILENAME)),
        "store": StoreError("Invalid event structure on line 6: late store failure"),
    }[kind]


@pytest.mark.parametrize("kind", ["unicode", "permission", "store"])
def test_late_read_failure_discards_dependent_advice_and_keeps_independent_checks(
    mission_dir: Path,
    late_read_failure: Callable[[Exception], int],
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    _add_independent_findings(mission_dir, monkeypatch)
    # A present, stale snapshot produces provisional advice BEFORE the failed reread.
    snapshot_path = mission_dir / SNAPSHOT_FILENAME
    if snapshot_path.exists():
        snapshot_path.write_text(
            json.dumps({"work_packages": {"WP01": {"lane": "claimed", "agent": "", "last_transition_at": "2020-01-01T00:00:00Z"}}}),
            encoding="utf-8",
        )
    before = _evidence(mission_dir)
    error = _late_read_error(kind, mission_dir)
    assert late_read_failure(error) > 1

    result = run_doctor(mission_dir, SLUG, mission_dir.parents[1])

    assert [f.category for f in result.findings] == [
        Category.EVENT_LOG_ERROR,
        Category.ISSUE_MATRIX,
        Category.SPARSE_CHECKOUT,
        Category.DUPLICATE_FRONTMATTER_KEY,
    ]
    assert not result.is_healthy and result.has_errors
    _assert_diagnostic(result.findings[0], mission_dir, str(error), 6 if kind == "store" else None)
    assert _evidence(mission_dir) == before


@pytest.mark.parametrize("kind", ["unicode", "permission", "store"])
@pytest.mark.parametrize("json_output", [False, True], ids=["text", "json"])
def test_cli_reports_late_read_failure_without_partial_advice(
    mission_dir: Path,
    late_read_failure: Callable[[Exception], int],
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    json_output: bool,
) -> None:
    from specify_cli.cli.commands.agent import status

    monkeypatch.setattr(status.console, "width", 2000)
    before = _evidence(mission_dir)
    error = _late_read_error(kind, mission_dir)
    late_read_failure(error)
    with (
        patch("specify_cli.runtime.doctor.run_global_checks", return_value=[]),
        patch("specify_cli.cli.commands.agent.status._resolve_status_surface", return_value=(mission_dir, SLUG, mission_dir.parents[1])),
    ):
        result = CliRunner().invoke(app, ["doctor"] + (["--json"] if json_output else []))

    assert result.exit_code == 1, (result.output, result.exception)
    assert isinstance(result.exception, SystemExit), result.exception
    assert "Traceback" not in result.output
    if json_output:
        report = json.loads(result.output)
        assert report["healthy"] is False
        assert len(report["findings"]) == 1
        _assert_diagnostic(Finding(**report["findings"][0]), mission_dir, str(error), 6 if kind == "store" else None)
    else:
        assert "event_log_error" in result.output and "error" in result.output
        assert str(error) in result.output
        assert "materialization_drift" not in result.output and "wp_file_drift" not in result.output
    assert _evidence(mission_dir) == before


def test_reviewer_self_approval_returns_after_authority_is_restored(mission_dir: Path) -> None:
    lifecycle = {
        "event_type": REVIEWER_SELF_APPROVAL,
        "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAX",
        "aggregate_id": "WP01",
        "payload": {"wp_id": "WP01", "implementing_actor": "ivan", "intended_reviewer": "renata", "failure_reason": "reviewer_failed"},
    }
    valid = _valid_history() + (json.dumps(lifecycle) + "\n").encode()
    log = mission_dir / EVENTS_FILENAME
    log.write_bytes(valid)
    before = _evidence(mission_dir)
    readable = run_doctor(mission_dir, SLUG, mission_dir.parents[1])
    reviews = readable.findings_by_category(Category.REVIEW_INDEPENDENCE)
    assert len(reviews) == 1
    assert reviews[0].wp_id == "WP01" and "ivan" in reviews[0].message and "renata" in reviews[0].message
    assert _evidence(mission_dir) == before

    log.write_bytes(valid + b"{not json\n")
    damaged = _evidence(mission_dir)
    broken = run_doctor(mission_dir, SLUG, mission_dir.parents[1])
    assert [f.category for f in broken.findings] == [Category.EVENT_LOG_ERROR]
    assert not broken.findings_by_category(Category.REVIEW_INDEPENDENCE)
    assert _evidence(mission_dir) == damaged

    log.write_bytes(valid)
    assert run_doctor(mission_dir, SLUG, mission_dir.parents[1]).findings == readable.findings
    assert _evidence(mission_dir) == before


def test_unexpected_programming_error_is_not_reported_as_log_corruption(
    mission_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_read = Path.read_text

    def scoped_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path == mission_dir / EVENTS_FILENAME:
            raise RuntimeError("unexpected reader defect")
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", scoped_read)
    before = _evidence(mission_dir)
    with pytest.raises(RuntimeError, match="^unexpected reader defect$"):
        run_doctor(mission_dir, SLUG, mission_dir.parents[1])
    assert _evidence(mission_dir) == before
