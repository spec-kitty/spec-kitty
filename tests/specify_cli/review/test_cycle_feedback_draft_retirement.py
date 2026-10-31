"""#6632: the retirement seam's predicates, one test each.

``review.cycle._retire_consumed_feedback_source`` removes a reviewer's feedback draft only after the
``review-cycle-N.md`` record holding its text is durably committed. Removing a file is destructive, so
every predicate that can keep it is pinned here -- these are the "same-fixture positive control" half
of each refusal: the first test on each fixture shape proves the probe *can* remove a draft, so the
keep-cases below prove something real about the file rather than about a probe that never looks.

The production wiring (that ``create_rejected_review_cycle`` actually calls this, and that the CLI's
next ``move-task --to for_review`` passes) is covered end to end in
``tests/specify_cli/cli/commands/agent/test_review_feedback_draft_retirement.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.review.cycle import _retire_consumed_feedback_source

pytestmark = [pytest.mark.unit]

_MISSION_SLUG = "001-predicates"
_RECORD_NAME = "review-cycle-1.md"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _mission_tree(tmp_path: Path, *, git: bool = True) -> tuple[Path, Path]:
    """Return ``(mission_dir, draft)`` with an empty, ready-to-write draft file."""
    repo = tmp_path / "repo"
    repo.mkdir()
    if git:
        _git(repo, "init", "-b", "main")
        _git(repo, "config", "user.email", "6632@example.invalid")
        _git(repo, "config", "user.name", "Review Feedback")
        _git(repo, "config", "commit.gpgsign", "false")
    mission_dir = repo / "kitty-specs" / _MISSION_SLUG
    draft = mission_dir / "tasks" / "WP01-core" / "review-feedback-1.md"
    draft.parent.mkdir(parents=True)
    return mission_dir.resolve(), draft


def _record(body: str) -> bytes:
    """A committed ``review-cycle-N.md`` as the writer lays it out: frontmatter, then the body."""
    return f"---\ncycle_number: 1\n---\n\n{body}".encode()


def _retire(
    draft: Path, recorded: str | None, mission_dir: Path, *, record: bytes | None = None, unreadable_record: bool = False
) -> tuple[Path | None, str | None]:
    """Run the seam; by default the committed record holds *recorded* verbatim."""
    if record is None and recorded is not None and not unreadable_record:
        record = _record(recorded)
    return _retire_consumed_feedback_source(
        feedback_source=draft,
        recorded_source_text=recorded,
        record_name=_RECORD_NAME,
        wp_task_dirs=((mission_dir / "tasks" / "WP01-core").resolve(),),
        committed_record=record,
    )


def test_removes_an_untracked_unchanged_draft_inside_the_mission(tmp_path: Path) -> None:
    """The positive control: a durable record's draft is retired."""
    mission_dir, draft = _mission_tree(tmp_path)
    body = "**Issue 1**: fix the tally.\n"
    draft.write_text(body, encoding="utf-8")

    retired, warning = _retire(draft, body, mission_dir)

    assert warning is None
    assert retired == draft.resolve()
    assert not draft.exists()


def test_keeps_the_draft_when_the_record_was_not_durable(tmp_path: Path) -> None:
    """FR-002: no recorded text means no durable record to fall back on."""
    mission_dir, draft = _mission_tree(tmp_path)
    draft.write_text("**Issue 1**: not committed anywhere else.\n", encoding="utf-8")

    retired, warning = _retire(draft, None, mission_dir)

    assert (retired, warning) == (None, None)
    assert draft.exists()


def test_keeps_a_draft_the_reviewer_already_committed(tmp_path: Path) -> None:
    """FR-003: deleting a tracked draft would create a deletion -- still dirty."""
    mission_dir, draft = _mission_tree(tmp_path)
    body = "**Issue 1**: the reviewer committed this.\n"
    draft.write_text(body, encoding="utf-8")
    _git(mission_dir.parents[1], "add", str(draft))
    _git(mission_dir.parents[1], "commit", "-m", "reviewer: commit the draft")

    retired, warning = _retire(draft, body, mission_dir)

    assert (retired, warning) == (None, None)
    assert draft.exists()


def test_keeps_a_draft_outside_the_mission_without_probing_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-004: not the mission's tree, so not this seam's file -- and no git call is spent on it."""
    import kernel.git

    def _fail_if_probed(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError("a draft outside the mission directory must not trigger a git probe")

    monkeypatch.setattr(kernel.git, "is_tracked", _fail_if_probed)
    mission_dir, _draft = _mission_tree(tmp_path)
    outside = tmp_path / "scratch-feedback.md"
    outside.write_text("**Issue 1**: a scratch note.\n", encoding="utf-8")

    retired, warning = _retire(outside, "**Issue 1**: a scratch note.\n", mission_dir)

    assert (retired, warning) == (None, None)
    assert outside.exists()


def test_keeps_a_draft_edited_after_the_record_was_written(tmp_path: Path) -> None:
    """FR-005: the draft now holds text the record does not -- removal would lose it."""
    mission_dir, draft = _mission_tree(tmp_path)
    recorded = "**Issue 1**: the first draft of the finding.\n"
    draft.write_text("**Issue 1**: the second draft, which the record does not carry.\n", encoding="utf-8")

    retired, warning = _retire(draft, recorded, mission_dir)

    assert retired is None
    assert warning is not None
    assert "does not hold" in warning
    assert draft.exists()


def test_keeps_the_draft_when_it_cannot_be_removed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-002: an unlink failure is reported, never raised over a committed verdict."""
    mission_dir, draft = _mission_tree(tmp_path)
    body = "**Issue 1**: an undeletable draft.\n"
    draft.write_text(body, encoding="utf-8")

    def _refuse(self: Path, *args: object, **kwargs: object) -> None:
        raise PermissionError("read-only directory")

    monkeypatch.setattr(Path, "unlink", _refuse)

    retired, warning = _retire(draft, body, mission_dir)

    assert retired is None
    assert warning is not None
    assert "could not be removed" in warning


def test_keeps_the_draft_outside_a_git_work_tree(tmp_path: Path) -> None:
    """No git repository means no dirty-tree contract to serve -- and no crash."""
    mission_dir, draft = _mission_tree(tmp_path, git=False)
    body = "**Issue 1**: no repository here.\n"
    draft.write_text(body, encoding="utf-8")

    retired, warning = _retire(draft, body, mission_dir)

    assert (retired, warning) == (None, None)
    assert draft.exists()


def test_refuses_to_delete_a_symlinked_draft(tmp_path: Path) -> None:
    """A symlink is never removed (the simplest safe rule), whether it points in or out.

    Containment on the resolved target alone let a link OUTSIDE the work package's directory that
    pointed INSIDE it be unlinked. Refusing every link needs no second scope test on the link itself.
    """
    mission_dir, draft = _mission_tree(tmp_path)
    body = "**Issue 1**: reached through a link.\n"
    target = draft.parent / "review-feedback-2.md"
    target.write_text(body, encoding="utf-8")
    outside_link = mission_dir / "linked-feedback.md"
    outside_link.symlink_to(target)

    retired, warning = _retire(outside_link, body, mission_dir)
    assert retired is None
    assert warning is not None
    assert "symbolic link" in warning
    assert outside_link.is_symlink()
    assert target.read_text(encoding="utf-8") == body


def test_keeps_a_draft_the_committed_record_does_not_hold(tmp_path: Path) -> None:
    """Durability claim: compared with the body read back from the destination ref, not the earlier read."""
    mission_dir, draft = _mission_tree(tmp_path)
    body = "**Issue 1**: the draft text.\n"
    draft.write_text(body, encoding="utf-8")

    retired, warning = _retire(draft, body, mission_dir, record=_record("**Issue 1**: a different committed body.\n"))
    assert retired is None
    assert warning is not None
    assert "as committed" in warning
    assert draft.exists()

    retired, warning = _retire(draft, body, mission_dir, unreadable_record=True)  # record unreadable at the ref
    assert retired is None
    assert warning is not None


def test_retires_a_draft_whose_record_carries_a_header_and_crlf(tmp_path: Path) -> None:
    """The comparison is after newline normalisation, and a ``body_header`` may precede the draft."""
    mission_dir, draft = _mission_tree(tmp_path)
    draft.write_bytes(b"**Issue 1**: windows line endings.\r\n")
    record = _record("Approved by someone: ref\n\n**Issue 1**: windows line endings.\n")

    retired, warning = _retire(draft, "**Issue 1**: windows line endings.\n", mission_dir, record=record)

    assert warning is None
    assert retired is not None
    assert not draft.exists()


def test_warns_when_a_tracked_draft_has_uncommitted_edits(tmp_path: Path) -> None:
    """A tracked draft is kept; with uncommitted edits the operator is told."""
    mission_dir, draft = _mission_tree(tmp_path)
    body = "**Issue 1**: committed text.\n"
    draft.write_text(body, encoding="utf-8")
    _git(mission_dir.parents[1], "add", str(draft))
    _git(mission_dir.parents[1], "commit", "-m", "reviewer: commit the draft")
    draft.write_text(body + "an uncommitted afterthought\n", encoding="utf-8")

    retired, warning = _retire(draft, body, mission_dir)

    assert retired is None
    assert warning is not None
    assert "uncommitted edits" in warning
    assert draft.exists()
