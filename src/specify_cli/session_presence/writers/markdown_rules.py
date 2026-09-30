"""MarkdownRulesWriter — generic Markdown section idempotency writer.

Manages a ``<!-- spec-kitty:orientation --> … <!-- /spec-kitty:orientation -->``
section in a Markdown file.  Supports two modes:

- ``append_mode=True``: the section lives *within* a larger existing file
  (e.g., CLAUDE.md, GEMINI.md).  Appends on first write; replaces in-place
  on subsequent writes.
- ``append_mode=False``: the file *is* the section (e.g.,
  ``.cursor/rules/spec-kitty.mdc``).  Writes the full rendered block as the
  file's entire content.

All writes are atomic: a temp file in the same directory is written first,
then ``os.replace()`` is used to make the swap visible to readers.
"""

from __future__ import annotations

import os
import re
import stat
from contextlib import contextmanager, suppress
from collections.abc import Iterator
from dataclasses import dataclass, replace
from hashlib import sha256  # noqa: TID251 -- exact physical file integrity, not doctrine hashing.
from pathlib import Path
from uuid import uuid4

from specify_cli.core.no_follow import chmod_fd, fd_relative_dir_ops_supported
from specify_cli.tool_surface.operations import FileState, InputObservation

from ..content import SECTION_CLOSE, SECTION_OPEN, SessionPresenceContent

__all__ = ["MarkdownRulesWriter"]


@dataclass(frozen=True)
class PreparedPresenceFile:
    """Exact owner-rendered bytes and destination state; never a replay token."""

    path: str
    before: FileState
    content: bytes
    disposition: str = "unchanged"
    reason: str = "Session presence is current"

    @property
    def changed(self) -> bool:
        return self.disposition != "preserve" and self.before.sha256 != sha256(self.content).hexdigest()

    @property
    def execution_artifacts(self) -> tuple[tuple[str, str, str], ...]:
        """Bound temporary writes by directory, basename pattern and purpose."""
        path = Path(self.path)
        return ((path.parent.as_posix(), f".{path.name}." + "[0-9a-f]" * 32 + ".tmp", "atomic replacement; removed before return"),) if self.changed else ()


def observe_presence_path(root: Path, relative: str) -> tuple[InputObservation, ...]:
    """Observe each parent and destination without traversing a child link."""
    parts = Path(relative).parts
    if Path(relative).is_absolute() or ".." in parts:
        raise ValueError("Unconfined presence path")
    paths = [Path(".")] + [Path(*parts[:i]) for i in range(1, len(parts) + 1)]
    observations = []
    for index, rel in enumerate(paths):
        path = root / rel
        try:
            info = path.lstat()
        except FileNotFoundError:
            observations.append(InputObservation(str(rel), (FileState("absent"), None, None)))
            continue
        mode = stat.S_IMODE(info.st_mode)
        if stat.S_ISLNK(info.st_mode):
            raise ValueError(f"Refusing unowned symlink: {rel}")
        if stat.S_ISDIR(info.st_mode):
            # Sibling effects change directory mtimes, not confinement. Keep
            # directory identity/mode and exact file mtimes as preconditions.
            state = FileState("directory", mode=mode)
        elif stat.S_ISREG(info.st_mode) and index == len(paths) - 1:
            data = read_presence_bytes(path)
            state = FileState("file", sha256=sha256(data).hexdigest(), mode=mode, mtime_ns=info.st_mtime_ns)
        else:
            raise ValueError(f"Unsupported presence node: {rel}")
        after = path.lstat()
        if (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_mode) != (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_mode):
            raise ValueError(f"Presence input changed while reading: {rel}")
        observations.append(InputObservation(str(rel), (state, info.st_dev, info.st_ino)))
    return tuple(observations)


def read_presence_bytes(path: Path) -> bytes:
    """Read a regular file without following a final symlink."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError(f"Expected regular file: {path}")
        return stream.read()


def presence_state(observation: InputObservation) -> FileState:
    """Extract the WP02 state from an owner observation."""
    value = observation.value
    if not isinstance(value, tuple) or not isinstance(value[0], FileState):
        raise TypeError("Invalid presence observation")
    return value[0]


@dataclass
class MarkdownRulesWriter:
    """Generic Markdown-based harness writer with section idempotency.

    Parameters
    ----------
    harness_key:
        Identifies this harness in the writer registry (e.g. ``"gemini"``).
    rules_path:
        Path to the target file, relative to *project_root*.
    append_mode:
        ``True`` when the orientation section lives within a larger file;
        ``False`` when the file IS the section.
    check_dir:
        Optional directory path (relative to *project_root*) to check in
        ``can_write()`` instead of the parent of ``rules_path``.  Use this
        for harnesses whose rules file lives in a subdirectory that may not
        yet exist (e.g. ``.cursor/rules/spec-kitty.mdc`` → ``check_dir=".cursor"``).
        When ``None`` (default), ``can_write()`` checks the parent of ``rules_path``.
    """

    harness_key: str
    rules_path: str
    append_mode: bool
    check_dir: str | None = None

    def can_write(self, project_root: Path) -> bool:
        """Return ``True`` when the harness root (or rules parent) directory exists."""
        if self.check_dir is not None:
            return (project_root / self.check_dir).exists()
        return (project_root / self.rules_path).parent.exists()

    def has_presence(self, project_root: Path) -> bool:
        """Return ``True`` when the orientation section marker is present."""
        target = project_root / self.rules_path
        if not target.exists():
            return False
        try:
            return SECTION_OPEN in target.read_text(encoding="utf-8")
        except OSError:
            return False

    def write(self, project_root: Path, content: SessionPresenceContent) -> None:
        """Write or replace the orientation section.

        Idempotent — safe to call when the section is already present.
        A second call replaces the existing section in-place; no duplicates.
        """
        before = observe_presence_path(project_root, self.rules_path)
        prepared = self.prepare(project_root, content)
        if before != observe_presence_path(project_root, self.rules_path):
            raise ValueError("Orientation input changed before write")
        self.apply_prepared(project_root, prepared)

    def prepare(self, project_root: Path, content: SessionPresenceContent) -> PreparedPresenceFile:
        """Render only the proven managed region, preserving foreign bytes."""
        observations = observe_presence_path(project_root, self.rules_path)
        before = presence_state(observations[-1])
        if before.kind not in ("file", "absent"):
            raise ValueError("Orientation destination is not a regular file")
        target = project_root / self.rules_path
        original = read_presence_bytes(target) if before.kind == "file" else b""
        existing = original.decode("utf-8")
        newline = "\r\n" if "\r\n" in existing else "\n"
        rendered = content.render().replace("\n", newline)
        prepared = PreparedPresenceFile(self.rules_path, before, original)
        if SECTION_OPEN in existing or SECTION_CLOSE in existing:
            start, end = _section_bounds(existing)
            block = existing[start:end]
            if not _canonical_section(block, content):
                return replace(prepared, disposition="preserve", reason="Edited managed orientation")
            if f"**Spec Kitty v{content.version}**" in block:
                return prepared
            desired = existing[:start] + rendered.rstrip("\r\n") + existing[end:]
        elif existing and not self.append_mode:
            return replace(prepared, disposition="preserve", reason="Unowned whole-file rules")
        else:
            desired = existing + (newline + newline if existing else "") + rendered
        return replace(prepared, content=desired.encode("utf-8"), reason="Prepare managed orientation")

    def apply_prepared(self, project_root: Path, prepared: PreparedPresenceFile) -> None:
        """Consume retained bytes through the existing atomic writer."""
        if prepared.path != self.rules_path:
            raise ValueError("Prepared orientation belongs to another writer")
        if prepared.changed:
            _atomic_write(project_root / prepared.path, prepared.content.decode("utf-8"), root=project_root, expected=prepared.before)

    def remove(self, project_root: Path) -> None:
        """Remove the orientation section.

        In ``append_mode=True``: strips the section, leaving the rest of the
        file intact.  In ``append_mode=False``: deletes the file entirely.
        No-op if the file does not exist or the section is not present.
        """
        target = project_root / self.rules_path
        if not target.exists():
            return
        if self.append_mode:
            existing = target.read_text(encoding="utf-8")
            if SECTION_OPEN not in existing:
                return
            new_text = _remove_section(existing)
            _atomic_write(target, new_text)
        else:
            target.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _atomic_write(target: Path, text: str, *, root: Path | None = None, expected: FileState | None = None) -> None:
    """Write *text* to *target* atomically via a sibling temp file.

    Creates parent directories if they do not exist.
    On failure the temp file is cleaned up and the exception re-raised.
    """
    root = target.parent if root is None else root
    relative = target.relative_to(root)
    observed = observe_presence_path(root, relative.as_posix())
    initial = presence_state(observed[-1])
    if expected is not None and initial != expected:
        raise ValueError("Presence destination changed before atomic write")
    data = text.encode("utf-8")
    if target.is_file() and read_presence_bytes(target) == data:
        return
    mode = stat.S_IMODE(target.lstat().st_mode) if target.exists() else 0o644
    if not fd_relative_dir_ops_supported():
        _windows_atomic_write(root, relative, target, data, mode, initial)
        return
    with _presence_parent(root, relative.parent, create=True) as parent_fd:
        temporary = f".{target.name}.{uuid4().hex}.tmp"
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode, dir_fd=parent_fd)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                os.fchmod(stream.fileno(), mode)
            # The lexical parent must still identify our confined descriptor.
            current = target.parent.stat(follow_symlinks=False)
            held = os.fstat(parent_fd)
            if (current.st_dev, current.st_ino) != (held.st_dev, held.st_ino):
                raise ValueError("Presence parent changed before atomic replacement")
            if presence_state(observe_presence_path(root, relative.as_posix())[-1]) != initial:
                raise ValueError("Presence destination changed before atomic replacement")
            os.replace(temporary, target.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        finally:
            with suppress(FileNotFoundError):
                os.unlink(temporary, dir_fd=parent_fd)


@contextmanager
def _presence_parent(root: Path, relative: Path, *, create: bool) -> Iterator[int]:
    """Hold no-follow directory descriptors across the existing atomic write."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(root, flags)
    try:
        for part in relative.parts:
            try:
                child = os.open(part, flags, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, 0o755, dir_fd=fd)
                child = os.open(part, flags, dir_fd=fd)
                try:
                    os.fchmod(child, 0o755)
                except OSError:
                    os.close(child)
                    raise
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def _walk_confined_parent(root: Path, relative: Path, *, create: bool) -> Path:
    """Path-based confined parent resolution for platforms without dir_fd (Windows).

    Mirrors ``coordination.atomic_write._reject_symlinked_components``: walk
    each component from *root*, rejecting a symlinked directory anywhere in
    the chain -- the same containment guarantee :func:`_presence_parent`'s
    O_NOFOLLOW dir_fd chaining provides, minus the atomicity a held
    descriptor affords (unavailable on this platform). Missing directories
    are created (mode ``0o755``) when *create* is ``True``.
    """
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Refusing unowned symlink: {current}")
        if not current.exists():
            if not create:
                raise FileNotFoundError(current)
            current.mkdir(mode=0o755)
            if current.is_symlink():
                raise ValueError(f"Refusing unowned symlink: {current}")
        elif not current.is_dir():
            raise ValueError(f"Expected directory: {current}")
    return current


def _windows_atomic_write(root: Path, relative: Path, target: Path, data: bytes, mode: int, initial: FileState) -> None:
    """Path-based atomic write for platforms without dir_fd (Windows).

    ``os.supports_dir_fd`` is empty on Windows and ``os.O_DIRECTORY`` /
    ``os.O_NOFOLLOW`` are undefined, so :func:`_presence_parent`'s
    fd-relative dance cannot run there. This fallback preserves the same
    guarantees as far as the platform allows: every path component from
    *root* is walked and rejected if it is a symlink
    (:func:`_walk_confined_parent`), the bytes go to a uniquely named
    sibling temp file, and ``os.replace`` (atomic on the same volume)
    moves it into place.
    """
    parent = _walk_confined_parent(root, relative.parent, create=True)
    if target.is_symlink():
        raise ValueError(f"Refusing unowned symlink: {target}")
    temporary = parent / f".{target.name}.{uuid4().hex}.tmp"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            chmod_fd(stream.fileno(), temporary, mode)
        if presence_state(observe_presence_path(root, relative.as_posix())[-1]) != initial:
            raise ValueError("Presence destination changed before atomic replacement")
        os.replace(temporary, target)
    except BaseException:
        with suppress(FileNotFoundError):
            temporary.unlink()
        raise


def _section_bounds(text: str) -> tuple[int, int]:
    if text.count(SECTION_OPEN) != 1 or text.count(SECTION_CLOSE) != 1:
        raise ValueError("Duplicate or unbalanced orientation markers")
    start = text.index(SECTION_OPEN)
    end = text.index(SECTION_CLOSE)
    if end < start:
        raise ValueError("Reversed orientation markers")
    return start, end + len(SECTION_CLOSE)


def _canonical_section(block: str, content: SessionPresenceContent) -> bool:
    """Prove the entire old block using the canonical renderer, not a suffix."""
    normalized = block.replace("\r\n", "\n")
    header = re.search(r"^\*\*Spec Kitty v([^\n]+?)\*\* — project: ([^\n]+?) \((healthy|upgrade-available|migration-required)\)$", normalized, re.MULTILINE)
    if header is None:
        return False
    version, slug, health = header.groups()
    old = replace(content, version=version, project_slug=slug)
    if health == "healthy":
        old = replace(old, health="healthy", available_version=None)
    elif health == "migration-required":
        old = replace(old, health="migration-required", available_version=None)
    else:
        warning = re.search(r"^⚠ Upgrade available: ([^\n]+?) — run `spec-kitty upgrade --cli` to update\.$", normalized, re.MULTILINE)
        if warning is None:
            return False
        old = replace(old, health="upgrade-available", available_version=warning.group(1))
    return normalized == old.render().rstrip("\n")


def _remove_section(text: str) -> str:
    """Remove the block from ``SECTION_OPEN`` to ``SECTION_CLOSE`` (inclusive).

    Returns *text* unchanged if either marker is not found.
    """
    start = text.find(SECTION_OPEN)
    end = text.find(SECTION_CLOSE, start)
    if start == -1 or end == -1:
        return text
    end += len(SECTION_CLOSE)
    if text[end : end + 1] == "\n":
        end += 1
    # Remove preceding blank line if present, keeping the rest clean.
    prefix = text[:start].rstrip("\n")
    suffix = text[end:]
    if prefix:
        return (prefix + "\n" + suffix).strip("\n") + "\n"
    return suffix
