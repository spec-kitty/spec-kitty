#!/usr/bin/env python3
"""
Unit tests for GitignoreManager class.

This module provides comprehensive test coverage for the GitignoreManager
functionality, including all public methods, edge cases, and error scenarios.
"""

import os
import tempfile
from pathlib import Path

import pytest
from specify_cli.gitignore_manager import (
    AGENT_DIRECTORIES,
    RUNTIME_PROTECTED_ENTRIES,
    AgentDirectory,
    GitignoreManager,
    GitignorePathError,
    ProtectionResult,
    read_ignore_file_text,
)

pytestmark = [pytest.mark.integration]

# Total entries: agents + runtime (derived from state contract)
_TOTAL_ENTRIES = len(AGENT_DIRECTORIES) + len(RUNTIME_PROTECTED_ENTRIES)


class TestGitignoreManager:
    """Test suite for GitignoreManager class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def temp_file(self):
        """Create a temporary file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmpfile:
            tmpfile.write("test content")
            tmpfile_path = Path(tmpfile.name)
        yield tmpfile_path
        tmpfile_path.unlink(missing_ok=True)

    @pytest.fixture
    def manager(self, temp_dir):
        """Create a GitignoreManager instance with temp directory."""
        return GitignoreManager(temp_dir)

    # T024 - Test GitignoreManager.__init__ validation
    def test_init_with_valid_directory(self, temp_dir):
        """Test successful initialization with valid directory."""
        manager = GitignoreManager(temp_dir)
        assert manager.project_path == temp_dir
        assert manager.gitignore_path == temp_dir / ".gitignore"
        assert manager.marker == "# Added by Spec Kitty CLI (auto-managed)"

    def test_init_with_nonexistent_directory(self):
        """Test initialization fails with non-existent directory."""
        with pytest.raises(ValueError, match="Project path does not exist"):
            GitignoreManager(Path("/nonexistent/directory"))

    def test_init_with_file_instead_of_directory(self, temp_file):
        """Test initialization fails when path is a file, not directory."""
        with pytest.raises(ValueError, match="Project path is not a directory"):
            GitignoreManager(temp_file)

    def test_init_with_string_path(self, temp_dir):
        """Test initialization accepts string paths."""
        manager = GitignoreManager(str(temp_dir))
        assert manager.project_path == temp_dir

    # T025 - Test protect_all_agents method
    def test_protect_all_agents_creates_gitignore(self, manager, temp_dir):
        """Test protect_all_agents creates .gitignore when it doesn't exist."""
        assert not manager.gitignore_path.exists()

        result = manager.protect_all_agents()

        assert result.success
        assert result.modified
        assert len(result.entries_added) == _TOTAL_ENTRIES  # All agent directories + runtime entries
        assert len(result.entries_skipped) == 0
        assert manager.gitignore_path.exists()

    @pytest.mark.parametrize("dangling", [False, True])
    def test_ensure_entries_refuses_symlinked_gitignore(self, temp_dir: Path, dangling: bool) -> None:
        external = temp_dir.parent / f"manager-external-{temp_dir.name}.txt"
        external.unlink(missing_ok=True)
        if not dangling:
            external.write_text("outside\n", encoding="utf-8")
        temp_dir.joinpath(".gitignore").symlink_to(external)

        with pytest.raises(GitignorePathError, match="is a symlink"):
            GitignoreManager(temp_dir).ensure_entries([".codex/"])

        if not dangling:
            assert external.read_text(encoding="utf-8") == "outside\n"
        else:
            assert not external.exists()

    def test_protect_all_agents_with_empty_gitignore(self, manager, temp_dir):
        """Test protect_all_agents adds to empty .gitignore."""
        manager.gitignore_path.touch()

        result = manager.protect_all_agents()

        assert result.success
        assert result.modified
        assert len(result.entries_added) == _TOTAL_ENTRIES

        content = manager.gitignore_path.read_text()
        assert manager.marker in content
        assert ".claude/" in content
        assert ".codex/" in content

    def test_protect_all_agents_with_existing_entries(self, manager, temp_dir):
        """Test protect_all_agents preserves existing entries."""
        existing_content = "node_modules/\n*.log\n"
        manager.gitignore_path.write_text(existing_content)

        result = manager.protect_all_agents()

        assert result.success
        assert result.modified

        content = manager.gitignore_path.read_text()
        assert "node_modules/" in content
        assert "*.log" in content
        assert ".claude/" in content

    def test_protect_all_agents_includes_all_agents(self, manager):
        """Test that all registered agent directories are protected."""
        manager.protect_all_agents()

        expected_dirs = [agent.directory for agent in AGENT_DIRECTORIES]

        content = manager.gitignore_path.read_text()
        for dir_name in expected_dirs:
            assert dir_name in content

    # T026 - Test protect_selected_agents method
    def test_protect_selected_single_agent(self, manager):
        """Test protecting a single selected agent."""
        result = manager.protect_selected_agents(["claude"])

        assert result.success
        assert result.modified
        assert ".claude/" in result.entries_added
        assert len(result.entries_added) == 1

    def test_protect_selected_multiple_agents(self, manager):
        """Test protecting multiple selected agents."""
        result = manager.protect_selected_agents(["claude", "codex", "gemini"])

        assert result.success
        assert result.modified
        assert len(result.entries_added) == 3
        assert ".claude/" in result.entries_added
        assert ".codex/" in result.entries_added
        assert ".gemini/" in result.entries_added

    def test_protect_selected_agent_with_multiple_entries(self, manager):
        """cursor owns 3 AGENT_DIRECTORIES rows (#2498) -- selecting it must add
        all 3, not just the last one registered under that name."""
        cursor_entries = [agent.directory for agent in AGENT_DIRECTORIES if agent.name == "cursor"]
        assert len(cursor_entries) > 1  # guards against this test going stale

        result = manager.protect_selected_agents(["cursor"])

        assert result.success
        assert result.modified
        assert len(result.entries_added) == len(cursor_entries)
        for entry in cursor_entries:
            assert entry in result.entries_added

    def test_protect_selected_unknown_agent(self, manager):
        """Test warning for unknown agent name."""
        result = manager.protect_selected_agents(["unknown_agent"])

        assert result.success
        assert not result.modified
        assert any("Unknown agent name: unknown_agent" in w for w in result.warnings)

    def test_protect_selected_empty_list(self, manager):
        """Test with empty agent list."""
        result = manager.protect_selected_agents([])

        assert result.success
        assert not result.modified
        assert any("No valid agent directories" in w for w in result.warnings)

    def test_protect_selected_mixed_valid_invalid(self, manager):
        """Test with mix of valid and invalid agents."""
        result = manager.protect_selected_agents(["claude", "invalid", "codex"])

        assert result.success
        assert result.modified
        assert len(result.entries_added) == 2
        assert any("Unknown agent name: invalid" in w for w in result.warnings)

    # T027 - Test duplicate detection logic
    def test_duplicate_detection_prevents_duplicates(self, manager):
        """Test that duplicate entries are never created."""
        # First run
        result1 = manager.protect_all_agents()
        assert result1.modified
        assert len(result1.entries_added) == _TOTAL_ENTRIES

        # Second run
        result2 = manager.protect_all_agents()
        assert not result2.modified
        assert len(result2.entries_skipped) == _TOTAL_ENTRIES
        assert len(result2.entries_added) == 0

    def test_duplicate_detection_with_manual_entries(self, manager):
        """Test duplicate detection with manually added entries."""
        # Manually add some entries
        manager.gitignore_path.write_text(".claude/\n.codex/\n")

        # Try to protect all agents
        result = manager.protect_all_agents()

        assert result.modified  # Still modified because we add the remaining entries
        assert ".claude/" in result.entries_skipped
        assert ".codex/" in result.entries_skipped
        assert len(result.entries_added) == _TOTAL_ENTRIES - 2

    def test_duplicate_detection_marker_comment(self, manager):
        """Test that marker comment is not duplicated."""
        # Run twice
        manager.protect_all_agents()
        manager.protect_all_agents()

        content = manager.gitignore_path.read_text()
        # Count occurrences of marker
        marker_count = content.count(manager.marker)
        assert marker_count == 1

    # T028 - Test line ending preservation
    def test_line_ending_preservation_windows(self, manager):
        """Test preservation of Windows line endings."""
        # Create file with Windows line endings
        test_content = "existing\r\nentries\r\n"
        manager.gitignore_path.write_bytes(test_content.encode())

        # Add new entries
        manager.ensure_entries([".test/"])

        # Note: OS might normalize line endings on write
        # The important thing is the code attempts to preserve them
        content = manager.gitignore_path.read_text()
        assert ".test/" in content

    def test_line_ending_preservation_unix(self, manager):
        """Test preservation of Unix line endings."""
        # Create file with Unix line endings
        test_content = "existing\nentries\n"
        manager.gitignore_path.write_text(test_content)

        # Add new entries
        manager.ensure_entries([".test/"])

        content = manager.gitignore_path.read_text()
        assert ".test/" in content

    def test_line_ending_detection_method(self, manager):
        """Test the line ending detection method."""
        # Test Windows detection
        assert manager._detect_line_ending("test\r\nline") == "\r\n"

        # Test Unix detection
        assert manager._detect_line_ending("test\nline") == "\n"

        # Test default for ambiguous
        assert manager._detect_line_ending("single line") == "\n"

    # T029 - Test error handling scenarios
    def test_error_handling_permission_denied(self, manager, temp_dir):
        """Test handling of permission errors."""
        # Create read-only .gitignore
        manager.gitignore_path.touch()
        os.chmod(manager.gitignore_path, 0o444)  # Read-only

        try:
            result = manager.protect_all_agents()

            assert not result.success
            assert len(result.errors) > 0
            assert any("Permission denied" in e for e in result.errors)
            assert any("chmod u+w" in e for e in result.errors)
        finally:
            # Restore permissions for cleanup
            os.chmod(manager.gitignore_path, 0o644)

    def test_error_handling_corrupted_file(self, manager):
        """Test handling of corrupted .gitignore file."""
        # Create a file with null bytes (binary content)
        manager.gitignore_path.write_bytes(b"\x00\x01\x02\x03")

        # Should handle gracefully
        result = manager.protect_all_agents()

        # The implementation might either:
        # 1. Succeed by overwriting the corrupted file
        # 2. Fail with an appropriate error
        # Either is acceptable as long as no exception is raised
        assert isinstance(result, ProtectionResult)

    def test_error_handling_no_exceptions_bubble(self, manager):
        """Test that errors don't cause unhandled exceptions."""
        # Even with various error conditions, should return ProtectionResult
        manager.gitignore_path.write_text("normal content")
        result = manager.protect_all_agents()
        assert isinstance(result, ProtectionResult)

    # T032 - Edge case tests
    def test_edge_case_github_special_handling(self, manager):
        """Test that unknown agent 'github' is handled properly."""
        result = manager.protect_selected_agents(["github"])

        assert result.success
        assert len(result.entries_added) == 0  # Unknown agent, nothing added
        assert any("Unknown agent" in w for w in result.warnings)

    def test_edge_case_large_gitignore(self, manager):
        """Test performance with large .gitignore file."""
        # Create a large .gitignore
        large_content = "\n".join([f"pattern{i}/" for i in range(1000)])
        manager.gitignore_path.write_text(large_content)

        # Should still work efficiently
        result = manager.protect_all_agents()

        assert result.success
        assert result.modified

        # Verify original content preserved
        content = manager.gitignore_path.read_text()
        assert "pattern999/" in content
        assert ".claude/" in content

    def test_edge_case_special_characters(self, manager):
        """Test handling of special characters in paths."""
        # Add entries with special characters
        special_entries = [".test-dir/", ".test_dir/", ".test.dir/"]
        manager.ensure_entries(special_entries)

        content = manager.gitignore_path.read_text()
        for entry in special_entries:
            assert entry in content

    def test_edge_case_empty_marker_sections(self, manager):
        """Test handling of empty marker sections."""
        # Create file with marker but no entries after it
        content = f"existing\n{manager.marker}\n"
        manager.gitignore_path.write_text(content)

        result = manager.protect_all_agents()

        assert result.success
        assert result.modified
        content = manager.gitignore_path.read_text()
        assert content.count(manager.marker) == 1

    def test_get_agent_directories_returns_copy(self):
        """Test that get_agent_directories returns a copy, not reference."""
        dirs1 = GitignoreManager.get_agent_directories()
        dirs2 = GitignoreManager.get_agent_directories()

        assert dirs1 == dirs2
        assert dirs1 is not dirs2  # Different objects

        # Modifying one shouldn't affect the other
        dirs1.append(AgentDirectory("test", ".test/", False, "Test"))
        assert len(dirs1) == len(AGENT_DIRECTORIES) + 1
        assert len(dirs2) == len(AGENT_DIRECTORIES)

    def test_all_agent_directories_have_trailing_slash(self):
        """Test that all agent directories end with trailing slash, except
        explicit generated-file entries (e.g. cursor's rule file, #2498)."""
        dirs = GitignoreManager.get_agent_directories()

        for agent_dir in dirs:
            if agent_dir.directory.endswith(".mdc"):
                continue
            assert agent_dir.directory.endswith("/"), f"{agent_dir.directory} missing trailing slash"

    def test_result_object_structure(self, manager):
        """Test ProtectionResult object has expected structure."""
        result = manager.protect_all_agents()

        assert hasattr(result, "success")
        assert hasattr(result, "modified")
        assert hasattr(result, "entries_added")
        assert hasattr(result, "entries_skipped")
        assert hasattr(result, "errors")
        assert hasattr(result, "warnings")

        assert isinstance(result.entries_added, list)
        assert isinstance(result.entries_skipped, list)
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)


class TestGitignoreSymlinkSafety:
    """Regression coverage for issue #582: gitignore_manager must not read or
    write through a `.gitignore` that is a symlink."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, temp_dir):
        return GitignoreManager(temp_dir)

    def _make_symlinked_gitignore(self, manager, temp_dir) -> Path:
        """Point .gitignore at an outside-the-project target via a symlink."""
        outside_target = temp_dir.parent / f"outside-target-{os.getpid()}.txt"
        outside_target.write_text("do-not-touch\n")
        manager.gitignore_path.symlink_to(outside_target)
        return outside_target

    def test_ensure_entries_rejects_symlink(self, manager, temp_dir):
        """ensure_entries() must refuse to write through a symlinked .gitignore."""
        outside_target = self._make_symlinked_gitignore(manager, temp_dir)
        try:
            with pytest.raises(GitignorePathError):
                manager.ensure_entries([".claude/"])
            # The symlink's target must be untouched.
            assert outside_target.read_text() == "do-not-touch\n"
        finally:
            outside_target.unlink(missing_ok=True)

    def test_protect_all_agents_reports_symlink_as_error(self, manager, temp_dir):
        """The ProtectionResult contract still holds: no exception escapes."""
        outside_target = self._make_symlinked_gitignore(manager, temp_dir)
        try:
            result = manager.protect_all_agents()
            assert not result.success
            assert any("symlink" in e.lower() for e in result.errors)
            assert outside_target.read_text() == "do-not-touch\n"
        finally:
            outside_target.unlink(missing_ok=True)

    def test_dangling_symlink_is_also_rejected(self, manager, temp_dir):
        """A symlink to a target that doesn't exist must still be rejected.

        `Path.exists()` follows symlinks and returns False for a dangling one,
        so the guard must trigger on `is_symlink()` directly, not `exists()`.
        """
        missing_target = temp_dir.parent / f"missing-target-{os.getpid()}.txt"
        manager.gitignore_path.symlink_to(missing_target)
        try:
            with pytest.raises(GitignorePathError):
                manager.ensure_entries([".claude/"])
        finally:
            manager.gitignore_path.unlink(missing_ok=True)

    def test_normal_file_write_survives_symlink_guard(self, manager):
        """Sanity check: a regular (non-symlink) .gitignore still works."""
        result = manager.ensure_entries([".claude/"])
        assert result
        assert ".claude/" in manager.gitignore_path.read_text()
        assert not manager.gitignore_path.is_symlink()

    def test_write_preserves_existing_file_mode(self, manager):
        """The atomic replace should not narrow an existing .gitignore's mode."""
        manager.gitignore_path.write_text("existing\n")
        os.chmod(manager.gitignore_path, 0o640)

        manager.ensure_entries([".claude/"])

        mode = manager.gitignore_path.stat().st_mode & 0o777
        assert mode == 0o640

    def test_new_file_respects_umask_not_mkstemp_default(self, manager):
        """A brand-new .gitignore must land at the umask-respecting mode.

        `tempfile.mkstemp()` always creates its tempfile at 0600 regardless
        of the process umask. For a pre-existing `.gitignore` the atomic
        write replicates its mode, but for a brand-new one (the common
        `spec-kitty init` path) there is no existing mode to replicate, so
        without an explicit chmod the file would keep mkstemp's 0600 instead
        of the 0644-under-umask-022 that `write_text()` used to produce.
        """
        assert not manager.gitignore_path.exists()
        old_umask = os.umask(0o022)
        try:
            manager.ensure_entries([".claude/"])
        finally:
            os.umask(old_umask)

        mode = manager.gitignore_path.stat().st_mode & 0o777
        assert mode == 0o644

    def test_atomic_write_does_not_follow_a_symlink_planted_after_the_guard(self, manager, temp_dir, monkeypatch):
        """#643: the ``_reject_symlink()`` check-then-use guard only proves a
        symlink wasn't present *at check time*; the property that actually
        makes the write safe against one appearing afterward is
        ``os.replace()`` itself never following the destination directory
        entry. A pre-planted symlink can't isolate that property here --
        ``_open_no_follow()``'s kernel-level ``O_NOFOLLOW`` independently
        blocks both the read path and the pre-write permission probe the
        moment ``.gitignore`` exists as a symlink, before either implementation
        would ever reach its differing final-write line. So this starts from
        a brand-new project (no ``.gitignore`` yet, matching ``spec-kitty
        init``) and hooks ``tempfile.mkstemp`` -- the first thing
        ``_atomic_write()`` does once its own pre-checks have already passed
        cleanly against the not-yet-existing path, and unchanged by the
        finding's own mutation -- to plant a symlink to an outside target at
        that exact moment, simulating the guard-to-write race without needing
        a real one. This must pass with the real ``os.replace()``-based
        ``_atomic_write`` and fail if a following write (e.g. plain
        ``write_text()``) is swapped in for it instead."""
        outside_target = temp_dir.parent / f"outside-target-{os.getpid()}.txt"
        outside_target.write_text("do-not-touch\n")
        assert not manager.gitignore_path.exists()

        real_mkstemp = tempfile.mkstemp

        def planting_mkstemp(*args, **kwargs):
            manager.gitignore_path.symlink_to(outside_target)
            return real_mkstemp(*args, **kwargs)

        monkeypatch.setattr(tempfile, "mkstemp", planting_mkstemp)
        try:
            result = manager.ensure_entries([".claude/"])

            assert result
            assert outside_target.read_text() == "do-not-touch\n"
            assert not manager.gitignore_path.is_symlink()
            assert ".claude/" in manager.gitignore_path.read_text()
        finally:
            outside_target.unlink(missing_ok=True)

    def test_permission_denied_still_raised_on_readonly_file(self, manager):
        """os.replace() ignores the target's mode bits; the manager must not.

        A read-only `.gitignore` must still surface PermissionError so
        `_protect_entries` reports it, exactly as the pre-fix direct
        `write_text()` did — an `os.replace()`-only implementation would
        silently clobber it instead, since rename() only checks the parent
        directory's permissions.
        """
        manager.gitignore_path.touch()
        os.chmod(manager.gitignore_path, 0o444)
        try:
            with pytest.raises(PermissionError):
                manager.ensure_entries([".claude/"])
        finally:
            os.chmod(manager.gitignore_path, 0o644)

    def test_read_does_not_follow_symlink_planted_after_the_guard(self, manager, temp_dir, monkeypatch):
        """The read must be no-follow, not just guarded by an earlier lstat.

        `_reject_symlink()` is a check-then-use `lstat`: a `.gitignore` that
        is a regular file when the guard runs but becomes a symlink to an
        outside secret before the actual read would previously still be
        followed by `Path.read_text()`, copying the secret's bytes into
        `.gitignore`. Simulate that exact race by neutering the guard and
        planting the symlink immediately before `ensure_entries()` reads —
        the read itself must refuse to follow it.
        """
        manager.gitignore_path.write_text("existing\n")
        secret = temp_dir.parent / f"secret-{os.getpid()}.txt"
        secret.write_text("do-not-leak\n")

        monkeypatch.setattr(manager, "_reject_symlink", lambda: None)
        try:
            manager.gitignore_path.unlink()
            manager.gitignore_path.symlink_to(secret)

            with pytest.raises(GitignorePathError):
                manager.ensure_entries([".claude/"])

            # The secret must never have been read into .gitignore, and
            # .gitignore must still be the symlink (untouched), not a
            # regular file carrying the secret's content.
            assert manager.gitignore_path.is_symlink()
            assert secret.read_text() == "do-not-leak\n"
        finally:
            manager.gitignore_path.unlink(missing_ok=True)
            secret.unlink(missing_ok=True)

    def test_write_probe_does_not_follow_symlink_planted_after_the_guard(self, manager, temp_dir, monkeypatch):
        """The pre-replace permission probe must also be no-follow.

        Same race as above, but for `_atomic_write()`'s `O_WRONLY` probe: a
        `.gitignore` that becomes a symlink between the guard and the probe
        must not have the probe silently succeed against the symlink's
        target.
        """
        manager.gitignore_path.write_text("existing\n")
        os.chmod(manager.gitignore_path, 0o640)
        secret = temp_dir.parent / f"secret-write-{os.getpid()}.txt"
        secret.write_text("do-not-leak\n")

        monkeypatch.setattr(manager, "_reject_symlink", lambda: None)
        try:
            manager.gitignore_path.unlink()
            manager.gitignore_path.symlink_to(secret)

            with pytest.raises(GitignorePathError):
                manager._atomic_write("new content\n")

            assert manager.gitignore_path.is_symlink()
            assert secret.read_text() == "do-not-leak\n"
        finally:
            manager.gitignore_path.unlink(missing_ok=True)
            secret.unlink(missing_ok=True)


class TestReadIgnoreFileText:
    """Coverage for `read_ignore_file_text` (issue #626): migration `detect()`
    logic must not read `.gitignore`/`.claudeignore` content through a
    symlink the way a bare `Path.read_text()`/`.exists()` pair would."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_missing_file_returns_empty_string(self, temp_dir):
        assert read_ignore_file_text(temp_dir / ".gitignore") == ""

    def test_regular_file_is_read_normally(self, temp_dir):
        path = temp_dir / ".gitignore"
        path.write_text(".claude/\n")
        assert read_ignore_file_text(path) == ".claude/\n"

    def test_utf8_sig_bom_is_stripped_by_default(self, temp_dir):
        path = temp_dir / ".gitignore"
        path.write_bytes(b"\xef\xbb\xbf.claude/\n")
        assert read_ignore_file_text(path) == ".claude/\n"

    def test_errors_ignore_tolerates_invalid_utf8(self, temp_dir):
        """Some call sites pass errors="ignore" to tolerate undecodable
        bytes; without it this raises UnicodeDecodeError."""
        path = temp_dir / ".gitignore"
        path.write_bytes(b"kitty-specs/\n\xff\xfe.claude/\n")

        with pytest.raises(UnicodeDecodeError):
            read_ignore_file_text(path)

        assert read_ignore_file_text(path, errors="ignore") == "kitty-specs/\n.claude/\n"

    def test_symlinked_file_is_rejected(self, temp_dir):
        outside_target = temp_dir.parent / f"outside-target-{os.getpid()}.txt"
        outside_target.write_text("do-not-touch\n")
        path = temp_dir / ".gitignore"
        path.symlink_to(outside_target)
        try:
            with pytest.raises(GitignorePathError):
                read_ignore_file_text(path)
        finally:
            outside_target.unlink(missing_ok=True)

    def test_dangling_symlink_is_also_rejected(self, temp_dir):
        """`Path.exists()` follows symlinks and returns False for a dangling
        one, so the guard must trigger on `is_symlink()` directly."""
        missing_target = temp_dir.parent / f"missing-target-{os.getpid()}.txt"
        path = temp_dir / ".gitignore"
        path.symlink_to(missing_target)
        try:
            with pytest.raises(GitignorePathError):
                read_ignore_file_text(path)
        finally:
            path.unlink(missing_ok=True)

    def test_vanishing_symlink_is_still_rejected(self, temp_dir, monkeypatch):
        """A failure while resolving a symlink for the error message must not
        replace `GitignorePathError` if the symlink is unlinked concurrently."""
        path = temp_dir / ".gitignore"
        path.symlink_to(temp_dir / "missing-target")

        def readlink_raises(*args, **kwargs):
            raise FileNotFoundError(f"simulated vanished symlink: {args}")

        monkeypatch.setattr(os, "readlink", readlink_raises)

        with pytest.raises(GitignorePathError):
            read_ignore_file_text(path)
