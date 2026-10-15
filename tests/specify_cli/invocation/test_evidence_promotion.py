"""Tests for evidence artifact promotion (Tier 2) via complete_invocation()."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.invocation.errors import (
    AlreadyClosedError,
    InvalidModeForEvidenceError,
    InvocationError,
    UnsupportedEvidenceError,
)
from specify_cli.invocation.executor import ProfileInvocationExecutor
from specify_cli.invocation.modes import ModeOfWork
from specify_cli.invocation.writer import EVENTS_DIR, InvocationWriter


pytestmark = [pytest.mark.unit, pytest.mark.fast]

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "profiles"

_COMPACT_CTX = MagicMock()
_COMPACT_CTX.mode = "compact"
_COMPACT_CTX.text = "test governance context"


def _setup_project(tmp_path: Path) -> Path:
    """Create a minimal project with fixture profiles."""
    profiles_dir = tmp_path / ".kittify" / "profiles"
    profiles_dir.mkdir(parents=True)
    for yaml_file in FIXTURES_DIR.glob("*.agent.yaml"):
        shutil.copy(yaml_file, profiles_dir / yaml_file.name)
    (tmp_path / "kitty-ops").mkdir(parents=True)
    return tmp_path


def _make_executor_with_started_record(
    tmp_path: Path,
    mode_of_work: ModeOfWork | None = None,
) -> tuple[ProfileInvocationExecutor, str]:
    """Create an executor and start an invocation; return (executor, invocation_id)."""
    project = _setup_project(tmp_path)
    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor = ProfileInvocationExecutor(project)
        profiles = list(executor._registry.list_all())
        if not profiles:
            pytest.skip("No fixture profiles available")
        profile = profiles[0]
        payload = executor.invoke(
            request_text="test evidence request",
            profile_hint=profile.profile_id,
            actor="claude",
            mode_of_work=mode_of_work,
        )
    return executor, payload.invocation_id


def test_complete_with_evidence_creates_tier2_directory(tmp_path: Path) -> None:
    """complete_invocation with evidence_ref must create the Tier 2 evidence directory."""
    evidence_file = tmp_path / "test_evidence.md"
    evidence_file.write_text("## Test Evidence\n\nAll assertions passed.", encoding="utf-8")

    executor, invocation_id = _make_executor_with_started_record(tmp_path)

    executor.complete_invocation(
        invocation_id=invocation_id,
        outcome="done",
        closed_by="agent",
        evidence_ref=str(evidence_file),
    )

    evidence_dir = tmp_path / ".kittify" / "evidence" / invocation_id
    assert evidence_dir.exists(), f"Tier 2 directory not created at {evidence_dir}"
    assert (evidence_dir / "evidence.md").exists()
    assert (evidence_dir / "record.json").exists()
    assert "All assertions passed." in (evidence_dir / "evidence.md").read_text()


def test_complete_without_evidence_skips_tier2(tmp_path: Path) -> None:
    """complete_invocation without evidence_ref must NOT create any evidence directory."""
    executor, invocation_id = _make_executor_with_started_record(tmp_path)

    executor.complete_invocation(invocation_id=invocation_id, outcome="done", closed_by="agent")

    evidence_dir = tmp_path / ".kittify" / "evidence"
    # Either dir doesn't exist, or exists but is empty
    if evidence_dir.exists():
        assert not list(evidence_dir.iterdir()), "Unexpected evidence directory created"


def test_complete_with_nonexistent_evidence_path_uses_inline_content(tmp_path: Path) -> None:
    """When evidence_ref is not a valid file path, use it as inline content."""
    executor, invocation_id = _make_executor_with_started_record(tmp_path)

    executor.complete_invocation(
        invocation_id=invocation_id,
        outcome="done",
        closed_by="agent",
        evidence_ref="all tests passed: 42/42",  # a label, not a path
    )

    evidence_dir = tmp_path / ".kittify" / "evidence" / invocation_id
    assert evidence_dir.exists()
    assert "all tests passed" in (evidence_dir / "evidence.md").read_text()


def test_complete_with_relative_escape_path_uses_inline_content(tmp_path: Path) -> None:
    """Relative evidence paths must stay inside repo_root after resolution."""
    outside_file = tmp_path.parent / f"{tmp_path.name}-outside.md"
    outside_file.write_text("top secret outside repo", encoding="utf-8")
    executor, invocation_id = _make_executor_with_started_record(tmp_path)

    executor.complete_invocation(
        invocation_id=invocation_id,
        outcome="done",
        closed_by="agent",
        evidence_ref=f"../{outside_file.name}",
    )

    evidence_dir = tmp_path / ".kittify" / "evidence" / invocation_id
    promoted_content = (evidence_dir / "evidence.md").read_text(encoding="utf-8")
    assert promoted_content == f"../{outside_file.name}"


# ---------------------------------------------------------------------------
# Unstorable evidence is refused before the terminal write (#5397)
# ---------------------------------------------------------------------------

_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
_UNENCODABLE = "missing-\udcff.txt"


def _record_path(project: Path, invocation_id: str) -> Path:
    return project / EVENTS_DIR / f"{invocation_id}.jsonl"


def _write_png(tmp_path: Path) -> Path:
    png = tmp_path / "shot.png"
    png.write_bytes(_PNG_BYTES)
    return png


def test_binary_evidence_file_raises_unsupported_evidence_before_any_write(tmp_path: Path) -> None:
    executor, invocation_id = _make_executor_with_started_record(tmp_path)
    record = _record_path(tmp_path, invocation_id)
    before = record.read_bytes()
    png = _write_png(tmp_path)

    with pytest.raises(UnsupportedEvidenceError) as excinfo:
        executor.complete_invocation(invocation_id=invocation_id, outcome="done", closed_by="agent", evidence_ref=str(png))

    err = excinfo.value
    assert isinstance(err, InvocationError)
    assert not isinstance(err, InvalidModeForEvidenceError)  # C-002: CLI must keep exit 1
    assert err.invocation_id == invocation_id
    assert err.evidence_label == str(png)
    assert invocation_id in str(err)
    assert "UTF-8" in str(err)
    assert "No completion was recorded" in str(err)
    assert record.read_bytes() == before
    assert not (tmp_path / ".kittify" / "evidence" / invocation_id).exists()


def test_unencodable_inline_evidence_raises_unsupported_evidence_before_any_write(tmp_path: Path) -> None:
    executor, invocation_id = _make_executor_with_started_record(tmp_path)
    record = _record_path(tmp_path, invocation_id)
    before = record.read_bytes()

    with pytest.raises(UnsupportedEvidenceError) as excinfo:
        executor.complete_invocation(invocation_id=invocation_id, outcome="done", closed_by="agent", evidence_ref=_UNENCODABLE)

    assert not isinstance(excinfo.value, InvalidModeForEvidenceError)
    assert excinfo.value.evidence_label == "inline evidence text"
    assert record.read_bytes() == before
    assert not (tmp_path / ".kittify" / "evidence" / invocation_id).exists()


def test_evidence_is_not_reread_after_the_completed_event(tmp_path: Path) -> None:
    """FR-004 oracle: promotion uses the pre-read content, never a post-close re-read."""
    executor, invocation_id = _make_executor_with_started_record(tmp_path)
    evidence_file = tmp_path / "proof.txt"
    evidence_file.write_text("original evidence text", encoding="utf-8")
    original_write_completed = InvocationWriter.write_completed

    def write_then_delete(self: InvocationWriter, *args: object, **kwargs: object) -> object:
        result = original_write_completed(self, *args, **kwargs)  # type: ignore[arg-type]
        evidence_file.unlink()
        return result

    with patch.object(InvocationWriter, "write_completed", autospec=True, side_effect=write_then_delete):
        executor.complete_invocation(invocation_id=invocation_id, outcome="done", closed_by="agent", evidence_ref=str(evidence_file))

    stored = tmp_path / ".kittify" / "evidence" / invocation_id / "evidence.md"
    assert stored.read_text(encoding="utf-8") == "original evidence text"


def test_evidence_file_read_exactly_once(tmp_path: Path) -> None:
    """NFR-001 ratchet: the evidence file is read a single time per close."""
    executor, invocation_id = _make_executor_with_started_record(tmp_path)
    evidence_file = tmp_path / "proof.txt"
    evidence_file.write_text("read me once", encoding="utf-8")
    original_read_text = Path.read_text
    reads: list[Path] = []

    def counting_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self == evidence_file:
            reads.append(self)
        return original_read_text(self, *args, **kwargs)  # type: ignore[arg-type]

    with patch.object(Path, "read_text", counting_read_text):
        executor.complete_invocation(invocation_id=invocation_id, outcome="done", closed_by="agent", evidence_ref=str(evidence_file))

    assert len(reads) == 1


def test_mode_refusal_still_wins_over_binary_evidence(tmp_path: Path) -> None:
    """FR-005: the mode gate runs before the evidence content check."""
    executor, invocation_id = _make_executor_with_started_record(tmp_path, mode_of_work=ModeOfWork.ADVISORY)
    png = _write_png(tmp_path)

    with pytest.raises(InvalidModeForEvidenceError):
        executor.complete_invocation(invocation_id=invocation_id, outcome="done", closed_by="agent", evidence_ref=str(png))

    events = _record_path(tmp_path, invocation_id).read_text(encoding="utf-8").splitlines()
    assert len(events) == 1


def test_empty_evidence_string_still_hits_the_mode_gate(tmp_path: Path) -> None:
    """--evidence "" is supplied evidence: the mode gate keys on `is not None`, not truthiness."""
    executor, invocation_id = _make_executor_with_started_record(tmp_path, mode_of_work=ModeOfWork.ADVISORY)

    with pytest.raises(InvalidModeForEvidenceError):
        executor.complete_invocation(invocation_id=invocation_id, outcome="done", closed_by="agent", evidence_ref="")

    events = _record_path(tmp_path, invocation_id).read_text(encoding="utf-8").splitlines()
    assert len(events) == 1


def test_spine_closed_op_still_reports_already_closed_with_binary_evidence(tmp_path: Path) -> None:
    """FR-005: a closure-spine-closed Op keeps reporting already_closed, not the evidence error."""
    executor, invocation_id = _make_executor_with_started_record(tmp_path)
    executor.complete_invocation(invocation_id=invocation_id, outcome="abandoned", closed_by="doctor_sweep")
    png = _write_png(tmp_path)

    with pytest.raises(AlreadyClosedError):
        executor.complete_invocation(invocation_id=invocation_id, outcome="done", closed_by="agent", evidence_ref=str(png))


def test_record_closed_op_with_binary_evidence_refuses_and_leaves_record_untouched(tmp_path: Path) -> None:
    """Analysis C1: an Op already closed in its own record is refused on evidence, byte-identical."""
    executor, invocation_id = _make_executor_with_started_record(tmp_path)
    executor.complete_invocation(invocation_id=invocation_id, outcome="done", closed_by="agent")
    record = _record_path(tmp_path, invocation_id)
    before = record.read_bytes()
    png = _write_png(tmp_path)

    with pytest.raises(UnsupportedEvidenceError):
        executor.complete_invocation(invocation_id=invocation_id, outcome="done", closed_by="agent", evidence_ref=str(png))

    assert record.read_bytes() == before


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("diagram.svg", '<svg xmlns="http://www.w3.org/2000/svg"></svg>'),
        ("result.json", '{"ok": true}'),
        ("empty.txt", ""),
    ],
)
def test_utf8_valid_and_empty_evidence_files_are_accepted(tmp_path: Path, name: str, content: str) -> None:
    executor, invocation_id = _make_executor_with_started_record(tmp_path)
    evidence_file = tmp_path / name
    evidence_file.write_text(content, encoding="utf-8")

    executor.complete_invocation(invocation_id=invocation_id, outcome="done", closed_by="agent", evidence_ref=str(evidence_file))

    stored = tmp_path / ".kittify" / "evidence" / invocation_id / "evidence.md"
    assert stored.read_text(encoding="utf-8") == content


def test_unreadable_evidence_path_falls_back_to_inline_text(tmp_path: Path) -> None:
    """FR-005: a directory (OSError on read) is stored as the inline reference text."""
    executor, invocation_id = _make_executor_with_started_record(tmp_path)
    directory = tmp_path / "a-directory"
    directory.mkdir()

    executor.complete_invocation(invocation_id=invocation_id, outcome="done", closed_by="agent", evidence_ref=str(directory))

    stored = tmp_path / ".kittify" / "evidence" / invocation_id / "evidence.md"
    assert stored.read_text(encoding="utf-8") == str(directory)
