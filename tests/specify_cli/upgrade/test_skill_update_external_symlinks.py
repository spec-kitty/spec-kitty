"""Skill write-path resilience: external symlinks (#1184) and read-only targets (#3771).

The gstack convention installs SKILL.md files as symlinks pointing to a
canonical copy in the operator's HOME directory. ``spec-kitty upgrade``
must NOT treat write failures on those symlinks as errors that change
the exit code — instead it should skip them and emit a warning (#1184).

Separately, managed skill trees are set read-only by
``skills/installer._make_tree_read_only``. On Windows, ``os.replace`` onto a
read-only target fails with ``[WinError 5]`` (``PermissionError``); the
``2.1.2_fix_*`` migrations catch that as ``OSError``, record the migration as
failed, and leave stale content on disk. The write path must clear the
read-only bit before the atomic replace so the rewrite lands (#3771).
"""

from __future__ import annotations

import errno
import logging
import os
import stat
import sys
from pathlib import Path

import pytest

from specify_cli.upgrade.skill_update import (
    is_external_symlink,
    write_skill_text,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# is_external_symlink
# ---------------------------------------------------------------------------


class TestIsExternalSymlink:
    def test_regular_file_is_not_external_symlink(self, tmp_path: Path) -> None:
        f = tmp_path / "SKILL.md"
        f.write_text("hello", encoding="utf-8")
        assert is_external_symlink(f, tmp_path) is False

    def test_in_repo_symlink_is_not_external(self, tmp_path: Path) -> None:
        target = tmp_path / "canonical.md"
        target.write_text("canonical", encoding="utf-8")
        link = tmp_path / "SKILL.md"
        os.symlink(target, link)
        assert is_external_symlink(link, tmp_path) is False

    def test_symlink_targeting_outside_repo_is_external(self, tmp_path: Path) -> None:
        external = tmp_path / "home" / "canonical.md"
        external.parent.mkdir(parents=True)
        external.write_text("canonical", encoding="utf-8")

        repo = tmp_path / "repo"
        repo.mkdir()
        link = repo / "SKILL.md"
        os.symlink(external, link)
        assert is_external_symlink(link, repo) is True

    def test_parent_directory_symlink_targeting_outside_repo_is_external(self, tmp_path: Path) -> None:
        external_skill_dir = tmp_path / "home" / ".claude" / "skills" / "x"
        external_skill_dir.mkdir(parents=True)
        (external_skill_dir / "SKILL.md").write_text("canonical", encoding="utf-8")

        repo = tmp_path / "repo"
        skill_parent = repo / ".claude" / "skills"
        skill_parent.mkdir(parents=True)
        os.symlink(external_skill_dir, skill_parent / "x")

        assert is_external_symlink(skill_parent / "x" / "SKILL.md", repo) is True

    def test_parent_directory_symlink_targeting_inside_repo_is_not_external(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        target_skill_dir = repo / "shared" / "x"
        target_skill_dir.mkdir(parents=True)
        (target_skill_dir / "SKILL.md").write_text("canonical", encoding="utf-8")

        skill_parent = repo / ".claude" / "skills"
        skill_parent.mkdir(parents=True)
        os.symlink(target_skill_dir, skill_parent / "x")

        assert is_external_symlink(skill_parent / "x" / "SKILL.md", repo) is False

    def test_missing_path_is_not_external_symlink(self, tmp_path: Path) -> None:
        missing = tmp_path / "no_such_file"
        assert is_external_symlink(missing, tmp_path) is False


# ---------------------------------------------------------------------------
# write_skill_text — the regression coverage for #1184
# ---------------------------------------------------------------------------


class TestWriteSkillTextExternalSymlink:
    """A SKILL.md symlink pointing outside the repo must be tolerated."""

    def test_external_symlink_is_skipped_and_warns(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        # External canonical copy (e.g. HOME-managed)
        external_home = tmp_path / "home" / ".claude" / "skills"
        external_home.mkdir(parents=True)
        canonical = external_home / "SKILL.md"
        canonical.write_text("CANONICAL CONTENT", encoding="utf-8")
        canonical_mtime = canonical.stat().st_mtime

        # Repo with a symlink pointing at the external canonical copy
        repo = tmp_path / "repo"
        skill_dir = repo / ".claude" / "skills" / "spec-kitty-glossary-context"
        skill_dir.mkdir(parents=True)
        link = skill_dir / "SKILL.md"
        os.symlink(canonical, link)

        with caplog.at_level(logging.WARNING, logger="specify_cli.upgrade.skill_update"):
            wrote, warning = write_skill_text(link, "NEW CONTENT", repo)

        # (a) writer did not raise, did not flag this as an error
        assert wrote is False
        assert warning is not None
        assert "symlink" in warning.lower()
        assert ".claude/skills/spec-kitty-glossary-context/SKILL.md" in warning

        # (b) the canonical file outside the repo is NOT modified
        assert canonical.read_text(encoding="utf-8") == "CANONICAL CONTENT"
        assert canonical.stat().st_mtime == canonical_mtime

        # (c) a warning was emitted
        assert any("symlink" in r.message.lower() for r in caplog.records)

    def test_regular_in_repo_file_is_written_normally(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / ".claude" / "skills" / "spec-kitty-glossary-context"
        skill_dir.mkdir(parents=True)
        dest = skill_dir / "SKILL.md"
        dest.write_text("OLD", encoding="utf-8")

        wrote, warning = write_skill_text(dest, "NEW", tmp_path)

        assert wrote is True
        assert warning is None
        assert dest.read_text(encoding="utf-8") == "NEW"

    def test_in_repo_symlink_is_written_normally(self, tmp_path: Path) -> None:
        """Symlinks whose target is INSIDE the repo are still written."""
        target = tmp_path / "shared" / "SKILL.md"
        target.parent.mkdir(parents=True)
        target.write_text("OLD", encoding="utf-8")

        skill_dir = tmp_path / ".claude" / "skills" / "x"
        skill_dir.mkdir(parents=True)
        link = skill_dir / "SKILL.md"
        os.symlink(target, link)

        wrote, warning = write_skill_text(link, "NEW", tmp_path)

        assert wrote is True
        assert warning is None
        # The write went through the symlink to the in-repo target.
        assert target.read_text(encoding="utf-8") == "NEW"

    def test_external_parent_directory_symlink_is_skipped(self, tmp_path: Path) -> None:
        """A symlinked skill directory pointing outside the repo is also skipped."""
        external_skill_dir = tmp_path / "home" / ".claude" / "skills" / "spec-kitty-runtime-next"
        external_skill_dir.mkdir(parents=True)
        canonical = external_skill_dir / "SKILL.md"
        canonical.write_text("CANONICAL CONTENT", encoding="utf-8")
        canonical_mtime = canonical.stat().st_mtime

        repo = tmp_path / "repo"
        skill_parent = repo / ".claude" / "skills"
        skill_parent.mkdir(parents=True)
        os.symlink(external_skill_dir, skill_parent / "spec-kitty-runtime-next")

        wrote, warning = write_skill_text(
            skill_parent / "spec-kitty-runtime-next" / "SKILL.md",
            "NEW CONTENT",
            repo,
        )

        assert wrote is False
        assert warning is not None
        assert "symlinked path" in warning
        assert canonical.read_text(encoding="utf-8") == "CANONICAL CONTENT"
        assert canonical.stat().st_mtime == canonical_mtime


# ---------------------------------------------------------------------------
# write_skill_text — read-only managed target (#3771)
# ---------------------------------------------------------------------------


def _install_windows_like_replace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``Path.replace`` fail on a read-only destination, as Windows does.

    On POSIX, ``os.replace`` onto a ``0o444`` file SUCCEEDS (the rename keys on
    the *directory's* write bit, not the target file's mode), so a bare
    ``chmod(0o444)`` does not reproduce the #3771 failure off Windows. This
    simulates the real Windows ``[WinError 5]`` — mirroring the
    ``windows_like_*`` monkeypatch technique in
    ``tests/specify_cli/skills/test_installer.py`` — so the regression runs on
    Linux CI.
    """
    real_replace = Path.replace

    def windows_like_replace(self: Path, target: str | os.PathLike[str]) -> Path:
        dest = Path(target)
        if dest.is_file() and not (dest.stat().st_mode & stat.S_IWRITE):
            raise PermissionError(errno.EACCES, "Access is denied", str(dest))
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", windows_like_replace)


# ``os.getuid`` is POSIX-only; on Windows the read-only path is exercised
# natively (root does not exist there), so guard the skip with ``hasattr``.
_skip_if_root = pytest.mark.skipif(
    hasattr(os, "getuid") and os.getuid() == 0,
    reason="root ignores file permissions",
)


class TestWriteSkillTextReadOnlyTarget:
    """A read-only managed SKILL.md must be rewritten, not silently skipped."""

    @_skip_if_root
    def test_readonly_target_is_rewritten_not_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        skill_dir = tmp_path / ".claude" / "skills" / "spec-kitty-glossary-context"
        skill_dir.mkdir(parents=True)
        dest = skill_dir / "SKILL.md"
        dest.write_text("OLD", encoding="utf-8")
        dest.chmod(0o444)  # managed read-only, as _make_tree_read_only leaves it

        _install_windows_like_replace(monkeypatch)

        # Pre-fix: the simulated Windows replace raises PermissionError here and
        # the migration write path drops the edit; post-fix the read-only bit is
        # cleared before the replace so the rewrite lands.
        wrote, warning = write_skill_text(dest, "NEW", tmp_path)

        assert wrote is True
        assert warning is None
        assert dest.read_text(encoding="utf-8") == "NEW"

    @_skip_if_root
    def test_writable_target_unaffected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The read-only clear must not disturb an already-writable target."""
        skill_dir = tmp_path / ".claude" / "skills" / "spec-kitty-glossary-context"
        skill_dir.mkdir(parents=True)
        dest = skill_dir / "SKILL.md"
        dest.write_text("OLD", encoding="utf-8")

        _install_windows_like_replace(monkeypatch)

        wrote, warning = write_skill_text(dest, "NEW", tmp_path)

        assert wrote is True
        assert warning is None
        assert dest.read_text(encoding="utf-8") == "NEW"

    @_skip_if_root
    def test_chmod_failure_does_not_abort_write(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A read-only target we cannot chmod (e.g. owned by another user) must
        not abort the write (squad F1).

        The write-bit restore is best-effort: when the chmod itself is refused,
        the code must still attempt the atomic replace, which on POSIX succeeds
        as long as the parent directory is writable. Without the guard, the
        chmod's PermissionError would propagate and record the migration as a
        failure — the very silent-drop #3771 set out to eliminate.
        """
        skill_dir = tmp_path / ".claude" / "skills" / "spec-kitty-glossary-context"
        skill_dir.mkdir(parents=True)
        dest = skill_dir / "SKILL.md"
        dest.write_text("OLD", encoding="utf-8")
        dest.chmod(0o444)

        real_chmod = Path.chmod

        def refusing_chmod(self: Path, mode: int, **kwargs: object) -> None:
            if self == dest:
                raise PermissionError(errno.EPERM, "Operation not permitted", str(self))
            real_chmod(self, mode, **kwargs)

        monkeypatch.setattr(Path, "chmod", refusing_chmod)

        wrote, warning = write_skill_text(dest, "NEW", tmp_path)

        assert wrote is True
        assert warning is None
        assert dest.read_text(encoding="utf-8") == "NEW"

    @pytest.mark.skipif(
        sys.platform != "win32",
        reason="exercises the real Windows os.replace read-only failure",
    )
    def test_readonly_target_is_rewritten_on_windows_native(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / ".claude" / "skills" / "spec-kitty-glossary-context"
        skill_dir.mkdir(parents=True)
        dest = skill_dir / "SKILL.md"
        dest.write_text("OLD", encoding="utf-8")
        dest.chmod(stat.S_IREAD)  # sets the Windows read-only attribute

        wrote, warning = write_skill_text(dest, "NEW", tmp_path)

        assert wrote is True
        assert warning is None
        assert dest.read_text(encoding="utf-8") == "NEW"
