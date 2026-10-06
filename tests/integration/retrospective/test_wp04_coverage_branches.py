"""WP04 branch coverage — exercise the classify + remediation helpers.

Covers the uncovered branches in:
  - ``_classify_exc``: RecordExistsError, FileNotFoundError/IsADirectoryError, other
  - ``_remediation_hint``: RecordExistsError, FileNotFoundError/IsADirectoryError, other
  - ``_build_retrospective_facilitator_callback``: RecordExistsError on write (non-fatal)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]

import ulid as _ulid_mod


def _scaffold_minimal_mission(tmp_path: Path, mission_slug: str) -> tuple[Path, str]:
    """Create a minimal mission directory."""
    mission_id = str(_ulid_mod.ULID())
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({
            "mission_id": mission_id,
            "mission_slug": mission_slug,
            "mission_type": "software-dev",
        }),
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text(
        "# Spec\n\n## Functional Requirements\n\n"
        "| ID | Requirement | Acceptance Criteria | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| FR-001 | Test | Covered by WP01. | proposed |\n",
        encoding="utf-8",
    )
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "WP01.md").write_text(
        "---\nwork_package_id: WP01\nlane: done\ndependencies: []\n"
        "requirement_refs: [FR-001]\ntitle: WP01\n---\n# WP01\n",
        encoding="utf-8",
    )
    events_path = feature_dir / "status.events.jsonl"
    events_path.write_text(
        json.dumps({
            "actor": "test", "at": "2026-01-01T00:00:00+00:00",
            "event_id": str(_ulid_mod.ULID()), "evidence": None,
            "execution_mode": "worktree", "feature_slug": mission_slug,
            "force": False, "from_lane": "planned", "reason": None,
            "review_ref": None, "to_lane": "done", "wp_id": "WP01",
        }) + "\n",
        encoding="utf-8",
    )
    return feature_dir, mission_id


# ---------------------------------------------------------------------------
# _classify_exc branch coverage
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_classify_exc_record_exists_error() -> None:
    """_classify_exc returns 'other' for RecordExistsError."""
    from runtime.next.runtime_bridge_retrospective import _classify_exc
    from specify_cli.retrospective.writer import RecordExistsError

    exc = RecordExistsError(Path("/some/path"))
    assert _classify_exc(exc) == "other"


@pytest.mark.integration
def test_classify_exc_file_not_found() -> None:
    """_classify_exc returns 'missing_artifacts' for FileNotFoundError."""
    from runtime.next.runtime_bridge_retrospective import _classify_exc

    assert _classify_exc(FileNotFoundError("missing")) == "missing_artifacts"


@pytest.mark.integration
def test_classify_exc_is_a_directory() -> None:
    """_classify_exc returns 'missing_artifacts' for IsADirectoryError."""
    from runtime.next.runtime_bridge_retrospective import _classify_exc

    assert _classify_exc(IsADirectoryError("is a dir")) == "missing_artifacts"


@pytest.mark.integration
def test_classify_exc_generic_exception() -> None:
    """_classify_exc returns 'generator_exception' for generic exceptions."""
    from runtime.next.runtime_bridge_retrospective import _classify_exc

    assert _classify_exc(RuntimeError("oops")) == "generator_exception"
    assert _classify_exc(ValueError("bad value")) == "generator_exception"


# ---------------------------------------------------------------------------
# _remediation_hint branch coverage
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_remediation_hint_record_exists() -> None:
    """_remediation_hint returns overwrite hint for RecordExistsError."""
    from runtime.next.runtime_bridge_retrospective import _remediation_hint
    from specify_cli.retrospective.writer import RecordExistsError

    exc = RecordExistsError(Path("/some/path"))
    hint = _remediation_hint(exc, {})
    assert hint is not None
    assert "overwrite" in hint.lower()


@pytest.mark.integration
def test_remediation_hint_file_not_found() -> None:
    """_remediation_hint returns migrate hint for FileNotFoundError."""
    from runtime.next.runtime_bridge_retrospective import _remediation_hint

    hint = _remediation_hint(FileNotFoundError("missing"), {})
    assert hint is not None
    assert "normalize-lifecycle" in hint or "migrate" in hint


@pytest.mark.integration
def test_remediation_hint_generic_uses_source_map() -> None:
    """_remediation_hint returns source-map info for generic exceptions."""
    from runtime.next.runtime_bridge_retrospective import _remediation_hint

    source_map = {"enabled": "<default>", "timing": ".kittify/config.yaml#retrospective.timing"}
    hint = _remediation_hint(RuntimeError("oops"), source_map)
    assert hint is not None
    assert "Check policy configuration" in hint


@pytest.mark.integration
def test_remediation_hint_empty_source_map() -> None:
    """_remediation_hint handles empty source_map gracefully."""
    from runtime.next.runtime_bridge_retrospective import _remediation_hint

    hint = _remediation_hint(RuntimeError("oops"), {})
    assert hint is not None
    assert "unknown" in hint


# ---------------------------------------------------------------------------
# RecordExistsError path in _build_retrospective_facilitator_callback
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_record_exists_error_is_non_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RecordExistsError on write is non-fatal: callback continues and emits Captured."""
    from runtime.next.runtime_bridge_retrospective import _build_retrospective_facilitator_callback
    from specify_cli.retrospective.writer import RecordExistsError
    from specify_cli.retrospective import writer as writer_mod

    mission_slug = "record-exists-test-01KQ"
    feature_dir, mission_id = _scaffold_minimal_mission(tmp_path, mission_slug)

    # Make write_gen_record raise RecordExistsError.
    def _raise_exists(*args, **kwargs):
        raise RecordExistsError(Path("/already/exists"))

    monkeypatch.setattr(writer_mod, "write_gen_record", _raise_exists)

    callback = _build_retrospective_facilitator_callback(
        mission_slug=mission_slug,
        repo_root=tmp_path,
        provenance_kind="runtime_post_completion",
    )

    # Should NOT raise — RecordExistsError is swallowed.
    callback(
        mission_id=mission_id,
        feature_dir=feature_dir,
        repo_root=tmp_path,
    )

    # Captured event is still emitted even though write was skipped.
    events_path = feature_dir / "status.events.jsonl"
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    captured_events = [e for e in events if e.get("type") == "RetrospectiveCaptured"]
    assert captured_events, (
        "RetrospectiveCaptured must be emitted even when write is skipped (RecordExistsError)"
    )


# ---------------------------------------------------------------------------
# PolicyResolutionError path in _build_retrospective_facilitator_callback
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_policy_resolution_error_is_re_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PolicyResolutionError from resolve_policy is re-raised by the callback."""
    from runtime.next.runtime_bridge_retrospective import _build_retrospective_facilitator_callback
    from specify_cli.retrospective import policy as policy_mod
    from specify_cli.retrospective.policy import PolicyResolutionError

    mission_slug = "policy-error-test-01KQ"
    feature_dir, mission_id = _scaffold_minimal_mission(tmp_path, mission_slug)

    def _raise_policy_error(*args, **kwargs):
        raise PolicyResolutionError(
            source=".kittify/config.yaml",
            reason="invalid_yaml",
            detail="Simulated malformed config",
        )

    monkeypatch.setattr(policy_mod, "resolve_policy", _raise_policy_error)

    callback = _build_retrospective_facilitator_callback(
        mission_slug=mission_slug,
        repo_root=tmp_path,
        provenance_kind="runtime_post_completion",
    )

    with pytest.raises(PolicyResolutionError):
        callback(
            mission_id=mission_id,
            feature_dir=feature_dir,
            repo_root=tmp_path,
        )


@pytest.mark.integration
def test_write_io_error_emits_failure_and_re_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Generic exception on write_gen_record: CaptureFailed emitted, exception re-raised."""
    from runtime.next.runtime_bridge_retrospective import _build_retrospective_facilitator_callback
    from specify_cli.retrospective import writer as writer_mod

    mission_slug = "write-io-error-test-01KQ"
    feature_dir, mission_id = _scaffold_minimal_mission(tmp_path, mission_slug)

    def _raise_io(*args, **kwargs):
        raise OSError("Simulated write I/O error")

    monkeypatch.setattr(writer_mod, "write_gen_record", _raise_io)

    callback = _build_retrospective_facilitator_callback(
        mission_slug=mission_slug,
        repo_root=tmp_path,
        provenance_kind="runtime_post_completion",
    )

    with pytest.raises(OSError):
        callback(
            mission_id=mission_id,
            feature_dir=feature_dir,
            repo_root=tmp_path,
        )

    # RetrospectiveCaptureFailed must be emitted before re-raise.
    events_path = feature_dir / "status.events.jsonl"
    assert events_path.exists()
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    failed_events = [e for e in events if e.get("type") == "RetrospectiveCaptureFailed"]
    assert failed_events, (
        "RetrospectiveCaptureFailed must be emitted when write_gen_record raises OSError"
    )
