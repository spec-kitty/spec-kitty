"""Direct unit tests for the check-prerequisites seam (#2056 WP05, T019).

Exercises the relocated helpers in
``specify_cli.cli.commands.agent.mission_check_prerequisites`` directly: the
paths-only payload shaper, the JSON / human result emitters, the detection-error
emitter, and the two ``meta.json`` readers' silent-degrade contracts. The
end-to-end command stays pinned by ``test_agent_feature.py``,
``test_check_prerequisites_surface_agreement.py`` and the WP01 golden harness.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.cli.commands.agent import mission_check_prerequisites as seam

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# _paths_only_payload
# ---------------------------------------------------------------------------


def test_paths_only_payload_aliases_legacy_keys() -> None:
    validation = {
        "paths": {
            "mission_dir": "/repo/kitty-specs/001-demo",
            "feature_dir": "/repo/kitty-specs/001-demo",
            "spec_file": "/repo/kitty-specs/001-demo/spec.md",
            "plan_file": "/repo/kitty-specs/001-demo/plan.md",
            "tasks_file": "/repo/kitty-specs/001-demo/tasks.md",
        },
        "artifact_files": {"x": 1},
        "artifact_dirs": {"y": 2},
        "available_docs": ["a"],
    }
    out = seam._paths_only_payload(validation)
    assert out["FEATURE_DIR"] == "/repo/kitty-specs/001-demo"
    assert out["SPEC_FILE"] == "/repo/kitty-specs/001-demo/spec.md"
    assert out["IMPL_PLAN"] == "/repo/kitty-specs/001-demo/plan.md"
    assert out["TASKS"] == "/repo/kitty-specs/001-demo/tasks.md"
    assert out["SPECS_DIR"] == "/repo/kitty-specs"
    assert out["artifact_files"] == {"x": 1}
    assert out["mission_dir"] == out["feature_dir"] == "/repo/kitty-specs/001-demo"


def test_paths_only_payload_empty_feature_dir() -> None:
    out = seam._paths_only_payload({"paths": {}})
    assert out["SPECS_DIR"] == ""


# ---------------------------------------------------------------------------
# --resume-probe tri-state/partial-scaffold contract (#3619)
# ---------------------------------------------------------------------------


def _write_resume_scaffold(
    repo_root: Path,
    human_slug: str,
    mid8: str,
    *,
    mission_type: str = "software-dev",
    mission_number: int | None = None,
) -> Path:
    feature_dir = repo_root / "kitty-specs" / f"{human_slug}-{mid8}"
    feature_dir.mkdir(parents=True)
    mission_id = f"{mid8}{'0' * 18}"
    meta = {
        "mission_id": mission_id,
        "mission_number": mission_number,
        "slug": feature_dir.name,
        "mission_slug": feature_dir.name,
        "mission_type": mission_type,
        "friendly_name": human_slug.replace("-", " ").title(),
        "purpose_tldr": f"Deliver {human_slug} safely.",
        "purpose_context": f"Resume {human_slug} without creating duplicate identity.",
        "target_branch": "feat/resume-probe",
        "topology": "single_branch",
        "created_at": "2026-08-22T09:00:00+00:00",
    }
    (feature_dir / "meta.json").write_text(
        json.dumps(meta),
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text("# Mission Specification\n", encoding="utf-8")
    from specify_cli.status import emit_mission_created_local

    emitted = emit_mission_created_local(
        feature_dir,
        mission_slug=meta["mission_slug"],
        mission_id=mission_id,
        mission_number=None,
        mission_type=mission_type,
        target_branch=meta["target_branch"],
        wp_count=0,
        friendly_name=meta["friendly_name"],
        purpose_tldr=meta["purpose_tldr"],
        purpose_context=meta["purpose_context"],
        created_at=meta["created_at"],
    )
    assert emitted is not None
    return feature_dir


def test_resume_probe_reports_not_found_amid_unrelated_missions(tmp_path: Path) -> None:
    """An unrelated Mission must not deadlock creation of a new slug."""
    _write_resume_scaffold(tmp_path, "existing-one", "01ABCDEF")

    payload = seam._build_resume_probe_payload(tmp_path, "new-one")

    assert payload == {
        "result": "success",
        "resume_state": "not_found",
        "handle": "new-one",
    }


def test_resume_probe_reports_unique_found_identity_and_creation_snapshot(tmp_path: Path) -> None:
    feature_dir = _write_resume_scaffold(tmp_path, "existing-one", "01ABCDEF")

    payload = seam._build_resume_probe_payload(tmp_path, "existing-one")

    assert payload["resume_state"] == "found"
    assert payload["mission_id"] == "01ABCDEF000000000000000000"
    assert payload["mission_slug"] == feature_dir.name
    assert payload["mission_type"] == "software-dev"
    assert payload["target_branch"] == "feat/resume-probe"
    assert payload["topology"] == "single_branch"
    assert payload["pr_bound"] is False
    assert payload["spec_committed_and_substantive"] is False


def test_resume_probe_marks_committed_substantive_spec_complete(tmp_path: Path) -> None:
    feature_dir = _write_resume_scaffold(tmp_path, "completed-one", "01ABCDEF")
    (feature_dir / "spec.md").write_text(
        "# Mission Specification\n\n- **FR-001**: Users can resume completed work safely.\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "kitty-specs"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "complete spec"], cwd=tmp_path, check=True, capture_output=True)

    payload = seam._build_resume_probe_payload(tmp_path, "completed-one")

    assert payload["resume_state"] == "found"
    assert payload["spec_committed_and_substantive"] is True


def test_resume_probe_conservatively_marks_committed_research_spec_complete(tmp_path: Path) -> None:
    feature_dir = _write_resume_scaffold(
        tmp_path,
        "completed-research",
        "01ABCDEF",
        mission_type="research",
    )
    (feature_dir / "spec.md").write_text(
        "# Research Specification\n\n| DR-001 | Bound the research question. | Open |\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "kitty-specs"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "complete research scope"], cwd=tmp_path, check=True, capture_output=True)

    payload = seam._build_resume_probe_payload(tmp_path, "completed-research")

    assert payload["resume_state"] == "found"
    assert payload["spec_committed_and_substantive"] is True


def test_resume_probe_reports_merged_mission_as_valid_existing_history(tmp_path: Path) -> None:
    feature_dir = _write_resume_scaffold(
        tmp_path,
        "merged-history",
        "01ABCDEF",
        mission_number=254,
    )
    (feature_dir / "status.events.jsonl").unlink()
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    del meta["topology"]
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    payload = seam._build_resume_probe_payload(tmp_path, "merged-history")

    assert payload["resume_state"] == "existing"
    assert payload["error_code"] == "MISSION_RESUME_EXISTING"
    assert payload["mission_number"] == 254
    assert "do not repair or remove" in str(payload["remediation"])
    assert "topology" in " ".join(payload["integrity_warnings"])


def test_resume_probe_matches_bare_slug_to_legacy_numbered_history(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "001-foo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_number": 1,
                "slug": "001-foo",
                "mission_slug": "001-foo",
                "mission_type": "software-dev",
                "friendly_name": "Foo",
                "target_branch": "main",
                "created_at": "2024-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text("# Mission Specification\n", encoding="utf-8")

    payload = seam._build_resume_probe_payload(tmp_path, "foo")

    assert payload["resume_state"] == "existing"
    assert payload["mission_slug"] == "001-foo"
    assert payload["mission_number"] == 1
    assert "mission_id" in " ".join(payload["integrity_warnings"])


def test_resume_probe_reports_ambiguous_duplicate_human_slug(tmp_path: Path) -> None:
    _write_resume_scaffold(tmp_path, "duplicate", "01ABCDEF")
    _write_resume_scaffold(tmp_path, "duplicate", "01BCDEFG")

    payload = seam._build_resume_probe_payload(tmp_path, "duplicate")

    assert payload["resume_state"] == "ambiguous"
    assert payload["error_code"] == "MISSION_RESUME_AMBIGUOUS"
    assert {candidate["mission_id"] for candidate in payload["candidates"]} == {
        "01ABCDEF000000000000000000",
        "01BCDEFG000000000000000000",
    }


def test_resume_probe_reports_malformed_partial_scaffold(tmp_path: Path) -> None:
    partial = tmp_path / "kitty-specs" / "partial-01ABCDEF"
    partial.mkdir(parents=True)
    (partial / "spec.md").write_text("# Partial\n", encoding="utf-8")

    payload = seam._build_resume_probe_payload(tmp_path, "partial")

    assert payload["resume_state"] == "malformed"
    assert payload["error_code"] == "MISSION_RESUME_MALFORMED"
    assert "meta.json is missing" in " ".join(payload["problems"])


@pytest.mark.parametrize(
    ("field", "invalid_value", "expected_problem"),
    [
        ("event_id", "not-an-event-id", "event_id"),
        ("schema_version", "future", "schema_version"),
        ("timestamp", "yesterday-ish", "timestamp"),
    ],
)
def test_resume_probe_rejects_invalid_mission_created_envelope(
    tmp_path: Path,
    field: str,
    invalid_value: str,
    expected_problem: str,
) -> None:
    feature_dir = _write_resume_scaffold(tmp_path, "bad-envelope", "01ABCDEF")
    event = json.loads((feature_dir / "status.events.jsonl").read_text(encoding="utf-8"))
    event[field] = invalid_value
    (feature_dir / "status.events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")

    payload = seam._build_resume_probe_payload(tmp_path, "bad-envelope")

    assert payload["resume_state"] == "malformed"
    assert expected_problem in " ".join(payload["problems"])


@pytest.mark.parametrize(
    ("field", "invalid_value", "expected_problem"),
    [
        ("mission_id", "01ABCDEF-not-a-ulid", "canonical ULID"),
        ("created_at", "not-a-time", "ISO-8601"),
        ("topology", "sometimes-coordinated", "recognized Mission topology"),
    ],
)
def test_resume_probe_rejects_coherent_but_invalid_creation_metadata(
    tmp_path: Path,
    field: str,
    invalid_value: str,
    expected_problem: str,
) -> None:
    feature_dir = _write_resume_scaffold(tmp_path, "bad-meta", "01ABCDEF")
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    event = json.loads((feature_dir / "status.events.jsonl").read_text(encoding="utf-8"))
    meta[field] = invalid_value
    if field in event["payload"]:
        event["payload"][field] = invalid_value
    if field == "mission_id":
        event["aggregate_id"] = invalid_value
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (feature_dir / "status.events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")

    payload = seam._build_resume_probe_payload(tmp_path, "bad-meta")

    assert payload["resume_state"] == "malformed"
    assert expected_problem in " ".join(payload["problems"])


def test_resume_probe_rejects_premerge_directory_with_wrong_identity_mid8(tmp_path: Path) -> None:
    feature_dir = _write_resume_scaffold(tmp_path, "wrong-mid8", "01ABCDEF")
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    event = json.loads((feature_dir / "status.events.jsonl").read_text(encoding="utf-8"))
    replacement_id = "01BCDEFG000000000000000000"
    meta["mission_id"] = replacement_id
    event["aggregate_id"] = replacement_id
    event["payload"]["mission_id"] = replacement_id
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (feature_dir / "status.events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")

    payload = seam._build_resume_probe_payload(tmp_path, "wrong-mid8")

    assert payload["resume_state"] == "malformed"
    assert "directory mid8" in " ".join(payload["problems"])


@pytest.mark.parametrize("drift", ["empty", "corrupt", "mismatch", "schema"])
def test_resume_probe_rejects_missing_or_drifted_mission_created_snapshot(
    tmp_path: Path,
    drift: str,
) -> None:
    feature_dir = _write_resume_scaffold(tmp_path, "event-drift", "01ABCDEF")
    event_log = feature_dir / "status.events.jsonl"
    if drift == "empty":
        event_log.write_text("", encoding="utf-8")
    elif drift == "corrupt":
        event_log.write_text("{not-json}\n", encoding="utf-8")
    elif drift == "mismatch":
        event = json.loads(event_log.read_text(encoding="utf-8"))
        event["payload"]["mission_type"] = "research"
        event_log.write_text(json.dumps(event) + "\n", encoding="utf-8")
    else:
        event = json.loads(event_log.read_text(encoding="utf-8"))
        del event["payload"]["wp_count"]
        event_log.write_text(json.dumps(event) + "\n", encoding="utf-8")

    payload = seam._build_resume_probe_payload(tmp_path, "event-drift")

    assert payload["resume_state"] == "malformed"
    assert payload["error_code"] == "MISSION_RESUME_MALFORMED"
    assert "MissionCreated" in " ".join(payload["problems"]) or "status.events" in " ".join(payload["problems"])


# ---------------------------------------------------------------------------
# _emit_check_prerequisites_result
# ---------------------------------------------------------------------------


def test_emit_result_json_injects_branch_contract(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    seam._emit_check_prerequisites_result(
        validation_result={"valid": True, "errors": [], "warnings": [], "paths": {}},
        feature_dir=tmp_path / "001-demo",
        json_output=True,
        paths_only=False,
        target_branch="main",
        current_branch="main",
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["target_branch"] == "main"
    assert "branch_context" in payload


def test_emit_result_human_pass(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    seam._emit_check_prerequisites_result(
        validation_result={"valid": True, "errors": [], "warnings": [], "paths": {}},
        feature_dir=tmp_path / "001-demo",
        json_output=False,
        paths_only=False,
        target_branch="main",
        current_branch="main",
    )
    assert "Prerequisites check passed" in capsys.readouterr().out


def test_emit_result_human_failure_lists_errors(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    seam._emit_check_prerequisites_result(
        validation_result={"valid": False, "errors": ["missing spec"], "warnings": ["stale tasks"], "paths": {}},
        feature_dir=tmp_path / "001-demo",
        json_output=False,
        paths_only=False,
        target_branch="main",
        current_branch="main",
    )
    out = capsys.readouterr().out
    assert "Prerequisites check failed" in out
    assert "missing spec" in out
    assert "stale tasks" in out


# ---------------------------------------------------------------------------
# _emit_check_prerequisites_detection_error
# ---------------------------------------------------------------------------


def test_emit_detection_error_json(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    monkeypatch.setattr(
        seam,
        "_build_setup_plan_detection_error",
        lambda *a, **k: {"error": "boom", "available_missions": ["001-demo"]},
    )
    seam._emit_check_prerequisites_detection_error(
        repo_root=tmp_path,
        detection_error=ValueError("ctx"),
        feature=None,
        json_output=True,
        paths_only=False,
        include_tasks=True,
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "boom"


def test_emit_detection_error_human(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    monkeypatch.setattr(
        seam,
        "_build_setup_plan_detection_error",
        lambda *a, **k: {"error": "boom", "available_missions": ["001-demo"], "example_command": "spec-kitty ..."},
    )
    seam._emit_check_prerequisites_detection_error(
        repo_root=tmp_path,
        detection_error=ValueError("ctx"),
        feature=None,
        json_output=False,
        paths_only=True,
        include_tasks=False,
    )
    out = capsys.readouterr().out
    assert "boom" in out
    assert "001-demo" in out


# ---------------------------------------------------------------------------
# meta readers — silent-degrade contracts
# ---------------------------------------------------------------------------


def test_read_meta_for_pr_bound_empty_when_missing(tmp_path: Path) -> None:
    assert seam._read_meta_for_pr_bound(tmp_path / "001-demo") == {}


def test_read_meta_for_pr_bound_reads_existing(tmp_path: Path) -> None:
    fd = tmp_path / "001-demo"
    fd.mkdir()
    (fd / "meta.json").write_text(json.dumps({"mission_id": "01ABC", "pr_bound": False}))
    out: dict[str, Any] = seam._read_meta_for_pr_bound(fd)
    assert out["mission_id"] == "01ABC"


def test_read_meta_for_emission_none_when_missing(tmp_path: Path) -> None:
    assert seam._read_meta_for_emission(tmp_path / "001-demo") is None


def test_read_meta_for_emission_reads_existing(tmp_path: Path) -> None:
    fd = tmp_path / "001-demo"
    fd.mkdir()
    (fd / "meta.json").write_text(json.dumps({"mission_id": "01ABC"}))
    out = seam._read_meta_for_emission(fd)
    assert out is not None
    assert out["mission_id"] == "01ABC"
