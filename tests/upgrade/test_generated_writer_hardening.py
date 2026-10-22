"""Hardening tests for the canonical generated-file writer (#3651 follow-up).

An adversarial review of ``write_generated_file`` found three latent-safety
gaps that ``tests/upgrade/test_generated_writer.py`` did not cover:

- NOTE 1: the original write was not atomic — ``write_text`` truncates
  the target in place, and the read-only strip afterwards was a bare
  statement with no ``finally``. An interrupted or failing write could
  leave a previously-good file both truncated and writable.
- NOTE 2: ``Path.chmod`` follows symlinks, so a symlinked target would
  silently mutate the link's destination outside the managed tree.
- MINOR 2: the module docstring overclaimed which callers route through
  this writer.

This file covers the *behavioral* consequences of the fix for the first
two (the docstring fix has no runtime behavior to assert). Covers:

- (a) a failing/interrupted write leaves a pre-existing target's content
  and read-only bit untouched.
- (b) a symlink target is refused rather than silently written through.
- (c) the pre-existing round-trip contract (absent target, already
  read-only target, ``read_only=False``) still holds after the rewrite.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from specify_cli.runtime import generated_writer
from specify_cli.runtime.generated_writer import write_generated_file

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# (a) interrupted/failing write leaves the original file untouched
# ---------------------------------------------------------------------------


def test_failing_write_leaves_original_content_and_read_only_bit_intact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A write failure mid-way must not corrupt or unlock the prior file.

    Simulates a disk-full-style failure by making ``Path.write_text`` raise
    on the *temporary* sibling file the writer creates. The pre-existing
    target's content and read-only permission must be exactly what they
    were before the call.
    """
    target = tmp_path / "command.md"
    target.write_text("stale-but-good\n", encoding="utf-8")
    target.chmod(0o444)

    original_write_text = Path.write_text

    def failing_write_text(self: Path, *args: object, **kwargs: object) -> int:
        if self.name.startswith(".") and ".tmp" in self.name:
            raise OSError("simulated disk-full failure")
        return original_write_text(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "write_text", failing_write_text)

    with pytest.raises(OSError, match="simulated disk-full failure"):
        write_generated_file(target, "new-content-that-never-lands\n")

    monkeypatch.undo()
    assert target.read_text(encoding="utf-8") == "stale-but-good\n"
    assert stat.S_IMODE(target.stat().st_mode) == 0o444


def test_failing_write_does_not_leave_a_stray_temp_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed write cleans up its temporary sibling file."""
    target = tmp_path / "command.md"
    target.write_text("stale\n", encoding="utf-8")

    original_write_text = Path.write_text

    def failing_write_text(self: Path, *args: object, **kwargs: object) -> int:
        if self.name.startswith(".") and ".tmp" in self.name:
            # Fail mid-write: the temporary sibling exists, so cleanup has work to do.
            original_write_text(self, "partial", encoding="utf-8")
            raise OSError("simulated failure")
        return original_write_text(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "write_text", failing_write_text)

    with pytest.raises(OSError):
        write_generated_file(target, "content\n")

    monkeypatch.undo()
    leftovers = [p for p in tmp_path.iterdir() if p.name != target.name]
    assert leftovers == []


def test_failing_write_on_new_target_leaves_no_file_behind(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing write for a target that never existed leaves nothing on disk."""
    target = tmp_path / "brand-new.md"
    assert not target.exists()

    original_write_text = Path.write_text

    def failing_write_text(self: Path, *args: object, **kwargs: object) -> int:
        if self.name.startswith(".") and ".tmp" in self.name:
            raise OSError("simulated failure")
        return original_write_text(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "write_text", failing_write_text)

    with pytest.raises(OSError):
        write_generated_file(target, "content\n")

    monkeypatch.undo()
    assert not target.exists()


# ---------------------------------------------------------------------------
# (b) symlink target is refused
# ---------------------------------------------------------------------------


def test_symlink_target_is_refused(tmp_path: Path) -> None:
    """Writing to a path that is itself a symlink raises rather than
    silently mutating whatever the link points at."""
    real_target = tmp_path / "real-command.md"
    real_target.write_text("real content\n", encoding="utf-8")
    link = tmp_path / "linked-command.md"
    link.symlink_to(real_target)

    with pytest.raises(ValueError, match="symlink"):
        write_generated_file(link, "attempted overwrite\n")

    # The link's target is untouched — no write-through occurred.
    assert real_target.read_text(encoding="utf-8") == "real content\n"
    assert link.is_symlink()


def test_symlink_to_missing_target_is_also_refused(tmp_path: Path) -> None:
    """A dangling symlink is refused the same way a live one is."""
    link = tmp_path / "dangling-link.md"
    link.symlink_to(tmp_path / "does-not-exist.md")

    with pytest.raises(ValueError, match="symlink"):
        write_generated_file(link, "content\n")

    assert link.is_symlink()


# ---------------------------------------------------------------------------
# (c) round-trip contract still holds after the atomic rewrite
# ---------------------------------------------------------------------------


def test_round_trip_absent_target_creates_read_only_file(tmp_path: Path) -> None:
    target = tmp_path / "new-command.md"
    assert not target.exists()

    write_generated_file(target, "content\n")

    assert target.read_text(encoding="utf-8") == "content\n"
    assert stat.S_IMODE(target.stat().st_mode) & 0o222 == 0
    assert not target.is_symlink()


def test_round_trip_already_read_only_target_is_rewritten_and_stays_read_only(
    tmp_path: Path,
) -> None:
    target = tmp_path / "command.md"
    target.write_text("stale\n", encoding="utf-8")
    target.chmod(0o444)

    write_generated_file(target, "fresh\n")

    assert target.read_text(encoding="utf-8") == "fresh\n"
    assert stat.S_IMODE(target.stat().st_mode) == 0o444


def test_round_trip_read_only_false_leaves_target_writable(tmp_path: Path) -> None:
    target = tmp_path / "writable.md"

    write_generated_file(target, "content\n", read_only=False)

    assert target.read_text(encoding="utf-8") == "content\n"
    assert stat.S_IMODE(target.stat().st_mode) & 0o200 != 0


def test_replace_target_is_a_different_inode_than_the_temp_file_path(tmp_path: Path) -> None:
    """Sanity check that the writer really goes through a temp-then-replace
    path rather than writing ``path`` in place (regression guard for the
    atomicity fix itself)."""
    target = tmp_path / "atomic.md"
    target.write_text("old\n", encoding="utf-8")

    write_generated_file(target, "new\n")

    # No stray ".*.tmp*" siblings left behind after a successful write.
    tmp_siblings = [p for p in tmp_path.iterdir() if p.name != target.name]
    assert tmp_siblings == []
    assert target.read_text(encoding="utf-8") == "new\n"


def test_module_is_stdlib_only() -> None:
    """Guard the documented constraint that this module never imports from
    ``specify_cli.upgrade`` (runtime must not depend on upgrade)."""
    source = Path(generated_writer.__file__).read_text(encoding="utf-8")
    import_lines = [line for line in source.splitlines() if line.startswith("import ") or line.startswith("from ")]
    assert import_lines == ["from __future__ import annotations", "import os", "from pathlib import Path"]
