"""Tests for src/specify_cli/audit/classifiers/ (T011–T018).

Covers all 7 per-artifact classifiers using tmp_path fixtures.
Total: ≥ 25 test cases.
"""

from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path


from specify_cli.audit.classifiers._details import format_exception_detail
from specify_cli.audit.classifiers.decisions_events import classify_decisions_events_jsonl
from specify_cli.audit.classifiers.handoff_events import classify_handoff_events_jsonl
from specify_cli.audit.classifiers.meta import classify_meta_json
from specify_cli.audit.classifiers.mission_events import classify_mission_events_jsonl
from specify_cli.audit.classifiers.status_events import classify_status_events_jsonl
from specify_cli.audit.classifiers.status_json import classify_status_json
from specify_cli.audit.classifiers.wp_files import classify_wp_files
from specify_cli.audit.models import Severity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


import pytest

pytestmark = [pytest.mark.integration]


def _assert_no_absolute_path_leak(detail: str | None, leaked_path: Path) -> None:
    assert detail is not None
    assert str(leaked_path) not in detail
    assert leaked_path.name not in detail

def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n",
        encoding="utf-8",
    )


def _write_corrupt_jsonl(path: Path, corrupt_line: str = "NOT JSON {{") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(corrupt_line + "\n", encoding="utf-8")


def _codes(findings: list) -> list[str]:
    return [f.code for f in findings]


def test_oserror_detail_preserves_non_path_message() -> None:
    """Message-only OSError details without paths should not be erased."""
    assert (
        format_exception_detail(OSError("network share unavailable"))
        == "OSError: network share unavailable"
    )


def test_oserror_detail_redacts_absolute_paths_with_spaces() -> None:
    """OSError messages may carry POSIX, Windows, or UNC paths with spaces."""
    cases = [
        OSError("failed reading /nonexistent/My Project/secret.txt"),
        OSError(5, "failed reading /nonexistent/My Project/secret.txt"),
        OSError(5, r"failed reading C:\Users\Rob Douglass\secret.txt"),
        OSError(5, r"failed reading \\server\My Share\secret.txt"),
    ]

    for exc in cases:
        detail = format_exception_detail(exc)
        assert detail.endswith("failed reading <path>")
        assert "secret.txt" not in detail
        assert "My Project" not in detail
        assert "Rob Douglass" not in detail
        assert "My Share" not in detail


def test_oserror_detail_redacts_posix_edge_paths() -> None:
    """POSIX absolute paths may be single-segment or contain colons."""
    cases = [
        OSError("failed reading /tmp"),  # bare /tmp (no trailing slash): tests single-component regex; must stay literal
        OSError("failed reading /secret.txt"),
        OSError("failed reading /nonexistent/project:secret.txt"),
    ]

    for exc in cases:
        detail = format_exception_detail(exc)
        assert detail == "OSError: failed reading <path>"
        assert "/tmp" not in detail
        assert "/secret.txt" not in detail
        assert "project:secret.txt" not in detail


def test_oserror_detail_does_not_redact_non_path_slashes_or_urls() -> None:
    """Slash commands and URLs are stable messages, not local path evidence."""
    assert (
        format_exception_detail(OSError("open /help or https://example.com/path/file"))
        == "OSError: open /help or https://example.com/path/file"
    )


# Minimal valid ULID
_VALID_ULID = "01KQHRB8GCFJAX7HM4ZY52AQGR"

# Minimal modern meta.json (no legacy keys, valid identity)
_MODERN_META: dict[str, object] = {
    "mission_id": _VALID_ULID,
    "mission_slug": "test-mission",
    "mission_number": 1,
    "friendly_name": "Test Mission",
}

# Minimal modern status event row
_MODERN_EVENT: dict[str, object] = {
    "actor": "finalize-tasks",
    "at": "2026-05-01T12:00:00+00:00",
    "event_id": _VALID_ULID,
    "evidence": None,
    "execution_mode": "worktree",
    "force": False,
    "from_lane": "planned",
    "mission_id": _VALID_ULID,
    "mission_slug": "test-mission",
    "policy_metadata": None,
    "reason": None,
    "review_ref": None,
    "to_lane": "planned",
    "wp_id": "WP01",
}


# ---------------------------------------------------------------------------
# T011/meta.json classifier
# ---------------------------------------------------------------------------


def test_meta_classifier_absent_file(tmp_path: Path) -> None:
    """Absent meta.json → empty findings."""
    assert classify_meta_json(tmp_path) == []


def test_meta_classifier_clean_modern(tmp_path: Path) -> None:
    """Clean modern meta.json → no findings."""
    _write_json(tmp_path / "meta.json", _MODERN_META)
    findings = classify_meta_json(tmp_path)
    assert findings == []


def test_meta_classifier_legacy_feature_slug(tmp_path: Path) -> None:
    """meta.json with feature_slug → LEGACY_KEY finding."""
    data = {**_MODERN_META, "feature_slug": "001-old-slug"}
    _write_json(tmp_path / "meta.json", data)
    findings = classify_meta_json(tmp_path)
    assert "LEGACY_KEY" in _codes(findings)


def test_meta_classifier_identity_missing(tmp_path: Path) -> None:
    """meta.json without mission_id → IDENTITY_MISSING finding."""
    data = {k: v for k, v in _MODERN_META.items() if k != "mission_id"}
    _write_json(tmp_path / "meta.json", data)
    findings = classify_meta_json(tmp_path)
    assert "IDENTITY_MISSING" in _codes(findings)
    assert all(f.severity == Severity.ERROR for f in findings if f.code == "IDENTITY_MISSING")


def test_meta_classifier_identity_invalid(tmp_path: Path) -> None:
    """meta.json with invalid ULID → IDENTITY_INVALID finding."""
    data = {**_MODERN_META, "mission_id": "not-a-ulid"}
    _write_json(tmp_path / "meta.json", data)
    findings = classify_meta_json(tmp_path)
    assert "IDENTITY_INVALID" in _codes(findings)
    assert all(f.severity == Severity.ERROR for f in findings if f.code == "IDENTITY_INVALID")


def test_meta_classifier_corrupt_json(tmp_path: Path) -> None:
    """Corrupt meta.json → CORRUPT_JSON finding."""
    (tmp_path / "meta.json").write_text("not valid json {{{", encoding="utf-8")
    findings = classify_meta_json(tmp_path)
    assert len(findings) == 1
    assert findings[0].code == "CORRUPT_JSON"
    assert findings[0].severity == Severity.ERROR


@pytest.mark.parametrize("payload", ["[]", '"x"', "42", "true", "null"])
def test_meta_classifier_non_object_json_returns_corrupt_json(
    tmp_path: Path, payload: str
) -> None:
    """Valid non-object meta.json → CORRUPT_JSON finding, not a crash."""
    (tmp_path / "meta.json").write_text(payload, encoding="utf-8")
    findings = classify_meta_json(tmp_path)
    assert len(findings) == 1
    assert findings[0].code == "CORRUPT_JSON"
    assert findings[0].severity == Severity.ERROR
    assert findings[0].detail == "top-level JSON value must be an object"


def test_meta_classifier_unreadable_file_reports_cannot_read_not_non_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unreadable meta.json (OSError) -> the OSError detail arm, not the non-object arm.

    Regression for WP08 review defect #4: MissionMetaReadError.cause is always
    the intermediate ValueError from ``mission_metadata._parse_meta_text``, never
    the underlying OSError directly -- the OSError lives one hop further down
    at ``exc.cause.__cause__``. Checking ``isinstance(exc.cause, OSError)``
    was always False, so an unreadable file fell through to the "top-level
    JSON value must be an object" branch instead of reporting the real
    read failure.
    """
    path = tmp_path / "meta.json"
    path.write_text("{}", encoding="utf-8")
    original_read_text = Path.read_text

    def raise_for_meta_json(self: Path, *args: object, **kwargs: object) -> str:
        if self == path:
            raise PermissionError(13, "Permission denied", str(path))
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", raise_for_meta_json)

    findings = classify_meta_json(tmp_path)

    assert len(findings) == 1
    assert findings[0].code == "CORRUPT_JSON"
    assert findings[0].detail != "top-level JSON value must be an object"
    assert findings[0].detail == (
        "cannot read meta.json: [Errno 13] Permission denied: "
        f"'{path}'"
    )


def test_meta_classifier_non_utf8_reports_cannot_read_not_non_object(
    tmp_path: Path,
) -> None:
    """Non-UTF-8 meta.json bytes -> the "cannot read" arm, not a crash or
    the non-object misdiagnosis (#3163).

    Regression: ``UnicodeDecodeError`` is a ``ValueError`` subclass, NOT an
    ``OSError`` subclass, so before this fix it (a) escaped
    ``_parse_meta_text``'s ``except (json.JSONDecodeError, OSError)`` tuple
    unwrapped, and (b) even once wrapped, ``classify_meta_json``'s
    ``isinstance(underlying, OSError)`` check did not recognise it, so it
    fell through to the wrong diagnosis: "top-level JSON value must be an
    object" -- a decode failure is not a non-object-JSON case.
    """
    path = tmp_path / "meta.json"
    path.write_bytes(b"\xff\xfe\x00\x01garbage")

    findings = classify_meta_json(tmp_path)

    assert len(findings) == 1
    assert findings[0].code == "CORRUPT_JSON"
    assert findings[0].detail != "top-level JSON value must be an object"
    assert findings[0].detail.startswith("cannot read meta.json:")


def test_meta_classifier_unknown_key(tmp_path: Path) -> None:
    """meta.json with unrecognised key → UNKNOWN_SHAPE finding (info)."""
    data = {**_MODERN_META, "unrecognised_field_xyz": "value"}
    _write_json(tmp_path / "meta.json", data)
    findings = classify_meta_json(tmp_path)
    assert "UNKNOWN_SHAPE" in _codes(findings)


def test_meta_classifier_coordination_keys_not_unknown_shape(tmp_path: Path) -> None:
    """Writer-canonical coordination keys must NOT be flagged UNKNOWN_SHAPE (#2696, FR-011).

    The coordination write-path stamps ``coordination_branch`` / ``topology`` /
    ``flattened`` / ``pr_bound`` onto ``meta.json``; before FR-011 the audit
    shape registry (a hand-rolled frozenset) had drifted from the writer schema
    and reported every one of these canonical keys as an ``UNKNOWN_SHAPE``
    false positive. Assert on the specific keys (findings are INFO severity, so
    exit codes are not the signal).
    """
    coord_keys: dict[str, object] = {
        "coordination_branch": "kitty/mission-demo-01ABCDEF",
        "topology": "COORD",
        "flattened": False,
        "pr_bound": True,
    }
    data = {**_MODERN_META, **coord_keys}
    _write_json(tmp_path / "meta.json", data)
    findings = classify_meta_json(tmp_path)
    unknown_details = [f.detail or "" for f in findings if f.code == "UNKNOWN_SHAPE"]
    offenders = [key for key in coord_keys if any(key in d for d in unknown_details)]
    assert offenders == [], (
        f"coordination keys wrongly flagged UNKNOWN_SHAPE: {offenders} "
        f"(all UNKNOWN_SHAPE details: {unknown_details})"
    )


# ---------------------------------------------------------------------------
# T012/status_events.jsonl classifier
# ---------------------------------------------------------------------------


def test_status_events_absent_file(tmp_path: Path) -> None:
    """Absent status.events.jsonl → ([], False)."""
    result, flag = classify_status_events_jsonl(tmp_path)
    assert result == []
    assert flag is False


def test_status_events_clean_modern(tmp_path: Path) -> None:
    """Clean modern event row → no findings."""
    _write_jsonl(tmp_path / "status.events.jsonl", [_MODERN_EVENT])
    findings, flag = classify_status_events_jsonl(tmp_path)
    assert findings == []
    assert flag is False


def test_status_events_corrupt_line(tmp_path: Path) -> None:
    """Corrupt JSONL line → CORRUPT_JSONL finding and flag=True."""
    _write_corrupt_jsonl(tmp_path / "status.events.jsonl")
    findings, flag = classify_status_events_jsonl(tmp_path)
    assert "CORRUPT_JSONL" in _codes(findings)
    assert flag is True


def test_status_events_read_oserror_detail_is_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unreadable status.events.jsonl must not leak absolute paths."""
    path = tmp_path / "status.events.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    original_read_text = Path.read_text

    def raise_for_status_events(self: Path, *args: object, **kwargs: object) -> str:
        if self == path:
            raise PermissionError(13, "Permission denied", str(path))
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", raise_for_status_events)

    findings, flag = classify_status_events_jsonl(tmp_path)

    assert flag is True
    assert len(findings) == 1
    assert findings[0].code == "CORRUPT_JSONL"
    assert findings[0].detail == (
        "could not read file: PermissionError: [Errno 13] Permission denied"
    )
    _assert_no_absolute_path_leak(findings[0].detail, path)


def test_status_events_read_oserror_without_errno_does_not_echo_message_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OSError args without errno may include paths and must not be copied."""
    path = tmp_path / "status.events.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    original_read_text = Path.read_text

    def raise_for_status_events(self: Path, *args: object, **kwargs: object) -> str:
        if self == path:
            raise OSError(f"failed reading {path}")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", raise_for_status_events)

    findings, flag = classify_status_events_jsonl(tmp_path)

    assert flag is True
    assert findings[0].detail == "could not read file: OSError: failed reading <path>"
    _assert_no_absolute_path_leak(findings[0].detail, path)


def test_status_events_read_oserror_strerror_path_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OSError.strerror may be caller supplied and must not leak paths."""
    path = tmp_path / "status.events.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    original_read_text = Path.read_text

    def raise_for_status_events(self: Path, *args: object, **kwargs: object) -> str:
        if self == path:
            raise OSError(5, f"failed reading {path}")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", raise_for_status_events)

    findings, flag = classify_status_events_jsonl(tmp_path)

    assert flag is True
    assert findings[0].detail == (
        "could not read file: OSError: [Errno 5] failed reading <path>"
    )
    _assert_no_absolute_path_leak(findings[0].detail, path)


def test_status_events_legacy_key(tmp_path: Path) -> None:
    """Event row with work_package_id → LEGACY_KEY finding."""
    row = {**_MODERN_EVENT, "work_package_id": "WP01"}
    _write_jsonl(tmp_path / "status.events.jsonl", [row])
    findings, _ = classify_status_events_jsonl(tmp_path)
    assert "LEGACY_KEY" in _codes(findings)


def test_status_events_forbidden_key(tmp_path: Path) -> None:
    """Event row with event_type → FORBIDDEN_KEY finding."""
    row = {**_MODERN_EVENT, "event_type": "SomeLegacyType"}
    _write_jsonl(tmp_path / "status.events.jsonl", [row])
    findings, _ = classify_status_events_jsonl(tmp_path)
    assert "FORBIDDEN_KEY" in _codes(findings)


def test_status_events_actor_drift(tmp_path: Path) -> None:
    """Event row with bad actor format → ACTOR_DRIFT warning."""
    row = {**_MODERN_EVENT, "actor": "UPPERCASE_ACTOR"}
    _write_jsonl(tmp_path / "status.events.jsonl", [row])
    findings, _ = classify_status_events_jsonl(tmp_path)
    assert "ACTOR_DRIFT" in _codes(findings)
    drift_findings = [f for f in findings if f.code == "ACTOR_DRIFT"]
    assert drift_findings[0].severity == Severity.WARNING


def test_status_events_valid_actor_formats(tmp_path: Path) -> None:
    """Various valid actor formats should not produce ACTOR_DRIFT."""
    for actor in ("claude", "finalize-tasks", "migration", "human", "user", "claude:opus"):
        row = {**_MODERN_EVENT, "actor": actor}
        (tmp_path / "status.events.jsonl").write_text(
            json.dumps(row, sort_keys=True) + "\n", encoding="utf-8"
        )
        findings, _ = classify_status_events_jsonl(tmp_path)
        drift = [f for f in findings if f.code == "ACTOR_DRIFT"]
        assert drift == [], f"Unexpected ACTOR_DRIFT for actor={actor!r}"


def test_status_events_collects_all_corrupt_lines(tmp_path: Path) -> None:
    """Multiple corrupt lines → multiple CORRUPT_JSONL findings."""
    content = "NOT JSON\nALSO NOT JSON\n"
    (tmp_path / "status.events.jsonl").write_text(content, encoding="utf-8")
    findings, flag = classify_status_events_jsonl(tmp_path)
    corrupt = [f for f in findings if f.code == "CORRUPT_JSONL"]
    assert len(corrupt) == 2
    assert flag is True


# ---------------------------------------------------------------------------
# T013/status_json classifier
# ---------------------------------------------------------------------------


def test_status_json_absent_file(tmp_path: Path) -> None:
    """Absent status.json → []."""
    assert classify_status_json(tmp_path) == []


def test_status_json_corrupt_json(tmp_path: Path) -> None:
    """Corrupt status.json → CORRUPT_JSON finding."""
    (tmp_path / "status.json").write_text("{broken", encoding="utf-8")
    findings = classify_status_json(tmp_path)
    assert "CORRUPT_JSON" in _codes(findings)


@pytest.mark.parametrize("payload", ["[]", '"x"', "42", "true", "null"])
def test_status_json_non_object_json_returns_corrupt_json(
    tmp_path: Path, payload: str
) -> None:
    """Valid non-object status.json → CORRUPT_JSON finding, not a crash."""
    (tmp_path / "status.json").write_text(payload, encoding="utf-8")
    findings = classify_status_json(tmp_path)
    assert len(findings) == 1
    assert findings[0].code == "CORRUPT_JSON"
    assert findings[0].severity == Severity.ERROR
    assert findings[0].detail == "top-level JSON value must be an object"


def test_status_json_read_oserror_detail_is_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unreadable status.json must not raise or leak absolute paths."""
    path = tmp_path / "status.json"
    path.write_text("{}", encoding="utf-8")
    original_read_text = Path.read_text

    def raise_for_status_json(self: Path, *args: object, **kwargs: object) -> str:
        if self == path:
            raise PermissionError(13, "Permission denied", str(path))
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", raise_for_status_json)

    findings = classify_status_json(tmp_path)

    assert len(findings) == 1
    assert findings[0].code == "CORRUPT_JSON"
    assert findings[0].detail == (
        "could not read file: PermissionError: [Errno 13] Permission denied"
    )
    _assert_no_absolute_path_leak(findings[0].detail, path)


def test_status_json_skip_drift_true(tmp_path: Path) -> None:
    """skip_drift=True → no SNAPSHOT_DRIFT even with mismatched content."""
    # Write a status.json with content that would normally cause drift
    (tmp_path / "status.json").write_text('{"work_packages": {}}', encoding="utf-8")
    findings = classify_status_json(tmp_path, skip_drift=True)
    drift = [f for f in findings if f.code == "SNAPSHOT_DRIFT"]
    assert drift == []


def test_snapshot_drift_detected(tmp_path: Path) -> None:
    """Mismatched status.json vs reducer → SNAPSHOT_DRIFT finding."""
    # Write a minimal but parsable status.json that doesn't match what
    # the reducer would produce for an empty event log.
    status_data = {
        "mission_slug": "test",
        "work_packages": {"WP01": {"lane": "planned"}},
        "summary": {"total": 1, "by_lane": {}},
    }
    (tmp_path / "status.json").write_text(
        json.dumps(status_data, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    # No status.events.jsonl → reducer produces empty snapshot
    findings = classify_status_json(tmp_path)
    drift = [f for f in findings if f.code == "SNAPSHOT_DRIFT"]
    assert len(drift) >= 1
    assert drift[0].severity == Severity.ERROR


def test_status_json_reducer_oserror_detail_is_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reducer OSError details must not leak absolute paths into findings."""
    path = tmp_path / "status.events.jsonl"
    (tmp_path / "status.json").write_text("{}", encoding="utf-8")

    import specify_cli.status as status

    def raise_reducer_oserror(mission_dir: Path) -> object:
        assert mission_dir == tmp_path
        raise FileNotFoundError(2, "No such file or directory", str(path))

    monkeypatch.setattr(status, "materialize_snapshot", raise_reducer_oserror)

    findings = classify_status_json(tmp_path)

    drift = [f for f in findings if f.code == "SNAPSHOT_DRIFT"]
    assert len(drift) == 1
    assert drift[0].detail == (
        "reducer raised during drift check: FileNotFoundError: "
        "[Errno 2] No such file or directory"
    )
    _assert_no_absolute_path_leak(drift[0].detail, path)


def test_status_json_reducer_oserror_strerror_path_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reducer OSError.strerror paths must be redacted from drift findings."""
    path = tmp_path / "status.events.jsonl"
    (tmp_path / "status.json").write_text("{}", encoding="utf-8")

    import specify_cli.status as status

    def raise_reducer_oserror(mission_dir: Path) -> object:
        assert mission_dir == tmp_path
        raise OSError(None, f"failed reading {path}")

    monkeypatch.setattr(status, "materialize_snapshot", raise_reducer_oserror)

    findings = classify_status_json(tmp_path)

    drift = [f for f in findings if f.code == "SNAPSHOT_DRIFT"]
    assert len(drift) == 1
    assert drift[0].detail == (
        "reducer raised during drift check: OSError: failed reading <path>"
    )
    _assert_no_absolute_path_leak(drift[0].detail, path)


def test_status_json_retrospective_materialized_snapshot_is_not_drift(
    tmp_path: Path,
) -> None:
    """Freshly materialized retrospective state must not produce SNAPSHOT_DRIFT."""
    from specify_cli.status.reducer import materialize

    _write_json(
        tmp_path / "meta.json",
        {
            "mission_id": _VALID_ULID,
            "mission_slug": "test-mission",
            "mission_number": 1,
            "mission_type": "software-dev",
        },
    )
    _write_jsonl(
        tmp_path / "status.events.jsonl",
        [
            _MODERN_EVENT,
            {
                "at": "2026-05-01T12:01:00+00:00",
                "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGS",
                "event_name": "retrospective.requested",
                "payload": {"mode": "append"},
            },
        ],
    )
    materialize(tmp_path)

    findings = classify_status_json(tmp_path)

    assert "SNAPSHOT_DRIFT" not in _codes(findings)


def test_status_json_non_ascii_materialized_snapshot_is_not_drift(
    tmp_path: Path,
) -> None:
    """Fresh UTF-8 status.json content must not be normalised into drift."""
    from specify_cli.status.reducer import materialize

    _write_json(
        tmp_path / "meta.json",
        {
            "mission_id": _VALID_ULID,
            "mission_slug": "test-mission",
            "mission_number": 1,
            "mission_type": "software-dev",
        },
    )
    _write_jsonl(
        tmp_path / "status.events.jsonl",
        [
            {
                **_MODERN_EVENT,
                "actor": "José",
                "reason": "résolu",
            },
        ],
    )
    materialize(tmp_path)

    status_text = (tmp_path / "status.json").read_text(encoding="utf-8")
    assert "José" in status_text

    findings = classify_status_json(tmp_path)

    assert "SNAPSHOT_DRIFT" not in _codes(findings)


# ---------------------------------------------------------------------------
# T014/mission_events.jsonl classifier
# ---------------------------------------------------------------------------


def test_mission_events_absent_file(tmp_path: Path) -> None:
    """Absent mission-events.jsonl → []."""
    assert classify_mission_events_jsonl(tmp_path) == []


def test_mission_events_clean(tmp_path: Path) -> None:
    """Clean mission-events.jsonl row → no findings."""
    row = {
        "mission": "software-dev",
        "payload": {"action": "discovery"},
        "timestamp": "2026-05-01T12:00:00+00:00",
        "type": "MissionNextInvoked",
    }
    _write_jsonl(tmp_path / "mission-events.jsonl", [row])
    findings = classify_mission_events_jsonl(tmp_path)
    assert findings == []


def test_mission_events_corrupt(tmp_path: Path) -> None:
    """Corrupt mission-events.jsonl → CORRUPT_JSONL finding."""
    _write_corrupt_jsonl(tmp_path / "mission-events.jsonl")
    findings = classify_mission_events_jsonl(tmp_path)
    assert "CORRUPT_JSONL" in _codes(findings)


def test_mission_events_read_oserror_detail_is_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unreadable mission-events.jsonl must not leak absolute paths."""
    path = tmp_path / "mission-events.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    original_read_text = Path.read_text

    def raise_for_mission_events(self: Path, *args: object, **kwargs: object) -> str:
        if self == path:
            raise PermissionError(13, "Permission denied", str(path))
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", raise_for_mission_events)

    findings = classify_mission_events_jsonl(tmp_path)

    assert len(findings) == 1
    assert findings[0].code == "CORRUPT_JSONL"
    assert findings[0].detail == (
        "could not read file: PermissionError: [Errno 13] Permission denied"
    )
    _assert_no_absolute_path_leak(findings[0].detail, path)


@pytest.mark.parametrize(
    ("relative_path", "classifier"),
    [
        (Path("decisions/events.jsonl"), classify_decisions_events_jsonl),
        (Path("handoff/events.jsonl"), classify_handoff_events_jsonl),
    ],
)
def test_shared_jsonl_classifiers_read_oserror_detail_is_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative_path: Path,
    classifier: Callable[[Path], list],
) -> None:
    """Shared JSONL classifiers must sanitize OSError details."""
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}\n", encoding="utf-8")
    original_read_text = Path.read_text

    def raise_for_shared_jsonl(self: Path, *args: object, **kwargs: object) -> str:
        if self == path:
            raise PermissionError(13, "Permission denied", str(path))
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", raise_for_shared_jsonl)

    findings = classifier(tmp_path)

    assert len(findings) == 1
    assert findings[0].code == "CORRUPT_JSONL"
    assert findings[0].detail == (
        "could not read file: PermissionError: [Errno 13] Permission denied"
    )
    _assert_no_absolute_path_leak(findings[0].detail, path)


def test_mission_events_legacy_key(tmp_path: Path) -> None:
    """mission-events.jsonl row with legacy key → LEGACY_KEY finding."""
    row = {
        "mission": "software-dev",
        "payload": {},
        "timestamp": "2026-05-01T12:00:00+00:00",
        "type": "SomeEvent",
        "feature_slug": "001-legacy",
    }
    _write_jsonl(tmp_path / "mission-events.jsonl", [row])
    findings = classify_mission_events_jsonl(tmp_path)
    assert "LEGACY_KEY" in _codes(findings)


# ---------------------------------------------------------------------------
# T015/decisions/events.jsonl classifier
# ---------------------------------------------------------------------------


def test_decisions_events_absent_file(tmp_path: Path) -> None:
    """Absent decisions/events.jsonl → []."""
    assert classify_decisions_events_jsonl(tmp_path) == []


def test_decisions_events_clean(tmp_path: Path) -> None:
    """Clean decision event row with canonical event_type → no findings."""
    row = {
        "at": "2026-05-01T12:00:00+00:00",
        "event_id": _VALID_ULID,
        "event_type": "DecisionPointOpened",
        "payload": {"question": "Which approach?"},
    }
    _write_jsonl(tmp_path / "decisions" / "events.jsonl", [row])
    findings = classify_decisions_events_jsonl(tmp_path)
    assert findings == []


def test_decisions_events_corrupt(tmp_path: Path) -> None:
    """Corrupt decisions/events.jsonl → CORRUPT_JSONL finding."""
    (tmp_path / "decisions").mkdir(parents=True, exist_ok=True)
    _write_corrupt_jsonl(tmp_path / "decisions" / "events.jsonl")
    findings = classify_decisions_events_jsonl(tmp_path)
    assert "CORRUPT_JSONL" in _codes(findings)


def test_decisions_events_legacy_key(tmp_path: Path) -> None:
    """decisions/events.jsonl row with legacy key → LEGACY_KEY finding."""
    row = {
        "at": "2026-05-01T12:00:00+00:00",
        "event_id": _VALID_ULID,
        "event_type": "DecisionPointOpened",
        "payload": {},
        "feature_slug": "001-old",
    }
    _write_jsonl(tmp_path / "decisions" / "events.jsonl", [row])
    findings = classify_decisions_events_jsonl(tmp_path)
    assert "LEGACY_KEY" in _codes(findings)


# ---------------------------------------------------------------------------
# T016/handoff/events.jsonl classifier
# ---------------------------------------------------------------------------


def test_handoff_events_absent_file(tmp_path: Path) -> None:
    """Absent handoff/events.jsonl → []."""
    assert classify_handoff_events_jsonl(tmp_path) == []


def test_handoff_events_clean(tmp_path: Path) -> None:
    """Clean handoff event row (modern keys only) → no findings.

    Note: real handoff/events.jsonl rows may carry ``feature_slug`` which
    is a LEGACY_KEY.  This test uses only modern canonical keys.
    """
    row = {
        "actor": "user",
        "at": "2026-05-01T12:00:00+00:00",
        "event_id": _VALID_ULID,
        "evidence": None,
        "execution_mode": "worktree",
        "mission_slug": "045-handoff",
        "force": False,
        "from_lane": "planned",
        "policy_metadata": None,
        "reason": None,
        "review_ref": None,
        "to_lane": "in_progress",
        "wp_id": "WP01",
    }
    _write_jsonl(tmp_path / "handoff" / "events.jsonl", [row])
    findings = classify_handoff_events_jsonl(tmp_path)
    assert findings == []


def test_handoff_events_corrupt(tmp_path: Path) -> None:
    """Corrupt handoff/events.jsonl → CORRUPT_JSONL finding."""
    (tmp_path / "handoff").mkdir(parents=True, exist_ok=True)
    _write_corrupt_jsonl(tmp_path / "handoff" / "events.jsonl")
    findings = classify_handoff_events_jsonl(tmp_path)
    assert "CORRUPT_JSONL" in _codes(findings)


def test_handoff_events_legacy_key(tmp_path: Path) -> None:
    """handoff/events.jsonl row with legacy key → LEGACY_KEY finding."""
    row = {
        "actor": "user",
        "at": "2026-05-01T12:00:00+00:00",
        "event_id": _VALID_ULID,
        "feature_slug": "045-handoff",
        "force": False,
        "from_lane": "planned",
        "to_lane": "in_progress",
        "wp_id": "WP01",
        # legacy key:
        "mission_key": "old-key",
    }
    _write_jsonl(tmp_path / "handoff" / "events.jsonl", [row])
    findings = classify_handoff_events_jsonl(tmp_path)
    assert "LEGACY_KEY" in _codes(findings)


# ---------------------------------------------------------------------------
# T017/wp_files classifier
# ---------------------------------------------------------------------------


def test_wp_files_no_tasks_dir(tmp_path: Path) -> None:
    """No tasks directory → []."""
    assert classify_wp_files(tmp_path) == []


def test_wp_files_no_wp_files(tmp_path: Path) -> None:
    """tasks/ dir exists but no WP*.md files → []."""
    (tmp_path / "tasks").mkdir()
    assert classify_wp_files(tmp_path) == []


def test_wp_files_no_frontmatter(tmp_path: Path) -> None:
    """WP file without frontmatter → [] (no finding)."""
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "WP01.md").write_text("# WP01\n\nSome content\n", encoding="utf-8")
    assert classify_wp_files(tmp_path) == []


def test_wp_files_known_frontmatter(tmp_path: Path) -> None:
    """WP file with clean modern frontmatter → []."""
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    content = "---\nwork_package_id: WP01\ntitle: Test WP\ndependencies: []\n---\n\n# Body\n"
    (tasks_dir / "WP01.md").write_text(content, encoding="utf-8")
    findings = classify_wp_files(tmp_path)
    assert findings == []


def test_wp_files_terminal_lane_no_evidence(tmp_path: Path) -> None:
    """WP file with terminal lane but no evidence → MISSING_EVIDENCE warning.

    The canonical lane is read from the event log (Phase-2 invariant). The
    frontmatter ``lane`` field is ignored; only the event log is authoritative.
    """
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    # WP frontmatter without evidence field
    content = "---\nwork_package_id: WP01\ntitle: Test WP\ndependencies: []\n---\n\n# Body\n"
    (tasks_dir / "WP01.md").write_text(content, encoding="utf-8")
    # Event log marks WP01 as 'done' — canonical Phase-2 lane source
    _write_jsonl(
        tmp_path / "status.events.jsonl",
        [{**_MODERN_EVENT, "to_lane": "done", "from_lane": "approved"}],
    )
    findings = classify_wp_files(tmp_path)
    assert "MISSING_EVIDENCE" in _codes(findings)
    missing = [f for f in findings if f.code == "MISSING_EVIDENCE"]
    assert missing[0].severity == Severity.WARNING
    assert missing[0].artifact_path == "tasks/WP01.md"


def test_wp_files_terminal_lane_with_evidence(tmp_path: Path) -> None:
    """WP file with terminal lane AND evidence → no MISSING_EVIDENCE."""
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    content = (
        "---\n"
        "work_package_id: WP01\n"
        "title: Test WP\n"
        "dependencies: []\n"
        "lane: done\n"
        "evidence: some evidence value\n"
        "---\n\n# Body\n"
    )
    (tasks_dir / "WP01.md").write_text(content, encoding="utf-8")
    findings = classify_wp_files(tmp_path)
    missing = [f for f in findings if f.code == "MISSING_EVIDENCE"]
    assert missing == []


def test_wp_files_legacy_key_in_frontmatter(tmp_path: Path) -> None:
    """WP file with feature_slug in frontmatter → LEGACY_KEY finding."""
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    content = (
        "---\n"
        "work_package_id: WP01\n"
        "title: Test WP\n"
        "dependencies: []\n"
        "feature_slug: old-feature\n"
        "---\n\n# Body\n"
    )
    (tasks_dir / "WP01.md").write_text(content, encoding="utf-8")
    findings = classify_wp_files(tmp_path)
    assert "LEGACY_KEY" in _codes(findings)


def test_wp_files_approved_lane_no_evidence(tmp_path: Path) -> None:
    """WP file with 'approved' terminal lane but no evidence → MISSING_EVIDENCE.

    The canonical lane is read from the event log (Phase-2 invariant).
    """
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    # WP frontmatter without evidence field
    content = "---\nwork_package_id: WP01\ntitle: Test WP\ndependencies: []\n---\n\n# Body\n"
    (tasks_dir / "WP01.md").write_text(content, encoding="utf-8")
    # Event log marks WP01 as 'approved' — canonical Phase-2 lane source
    _write_jsonl(
        tmp_path / "status.events.jsonl",
        [{**_MODERN_EVENT, "to_lane": "approved", "from_lane": "in_review"}],
    )
    findings = classify_wp_files(tmp_path)
    assert "MISSING_EVIDENCE" in _codes(findings)


def test_wp_files_artifact_path_forward_slashes(tmp_path: Path) -> None:
    """artifact_path in findings must use forward slashes."""
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    content = "---\nwork_package_id: WP01\ntitle: Test WP\ndependencies: []\nlane: done\n---\n\n# Body\n"
    (tasks_dir / "WP01.md").write_text(content, encoding="utf-8")
    findings = classify_wp_files(tmp_path)
    for finding in findings:
        assert "\\" not in finding.artifact_path, f"Non-forward-slash in {finding.artifact_path!r}"
        assert finding.artifact_path.startswith("tasks/")


# ---------------------------------------------------------------------------
# General: all classifiers return [] for empty mission directory
# ---------------------------------------------------------------------------


def test_absent_optional_files_no_findings(tmp_path: Path) -> None:
    """Mission dir with no optional files → all classifiers return empty/false."""
    assert classify_meta_json(tmp_path) == []
    findings_se, flag = classify_status_events_jsonl(tmp_path)
    assert findings_se == []
    assert flag is False
    assert classify_status_json(tmp_path) == []
    assert classify_mission_events_jsonl(tmp_path) == []
    assert classify_decisions_events_jsonl(tmp_path) == []
    assert classify_handoff_events_jsonl(tmp_path) == []
    assert classify_wp_files(tmp_path) == []
