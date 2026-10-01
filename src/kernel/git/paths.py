"""``GitPath``: a repository-relative path compared by its components.

Git reports paths relative to the repository root with ``/`` separators. Two
spellings of the same path must compare equal, and relations must respect
component boundaries: ``src/store`` is an ancestor of ``src/store/local.txt``
but has nothing to do with ``src/storehouse`` (#5400). String prefix checks
get this wrong in one direction or the other; comparing ``parts`` cannot.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["GitPath"]

_SEP: str = "/"
_FORBIDDEN_PARTS: frozenset[str] = frozenset({"", ".", ".."})


@dataclass(frozen=True, order=True)
class GitPath:
    """A path relative to the repository root.

    ``parts`` is empty for the repository root itself. The root relates to
    nothing: it is neither an ancestor of nor overlapping with any path, so an
    empty path can never be read as "obstructs everything".
    """

    parts: tuple[str, ...]

    @classmethod
    def parse(cls, text: str) -> GitPath:
        """Parse a git-style relative path; one trailing ``/`` (a directory marker) is dropped.

        Raises:
            ValueError: *text* is absolute or contains an empty, ``.`` or ``..`` component.
        """
        if text.startswith(_SEP):
            raise ValueError(f"not a repository-relative path: {text!r}")
        body = text[:-1] if text.endswith(_SEP) else text
        if not body:
            return cls(())
        parts = tuple(body.split(_SEP))
        if any(part in _FORBIDDEN_PARTS for part in parts):
            raise ValueError(f"not a normalized repository-relative path: {text!r}")
        return cls(parts)

    def __str__(self) -> str:
        return _SEP.join(self.parts)

    def as_posix(self) -> str:
        """The ``/``-joined path (``""`` for the root)."""
        return str(self)

    @property
    def name(self) -> str:
        """Last component (``""`` for the root)."""
        return self.parts[-1] if self.parts else ""

    def is_ancestor_of(self, other: GitPath) -> bool:
        """True when *other* lies strictly inside this path (the root is nobody's ancestor)."""
        return bool(self.parts) and len(other.parts) > len(self.parts) and other.parts[: len(self.parts)] == self.parts

    def contains(self, other: GitPath) -> bool:
        """True when *other* is this path or lies inside it (the root contains nothing)."""
        return bool(self.parts) and (other == self or self.is_ancestor_of(other))

    def overlaps(self, other: GitPath) -> bool:
        """True when either path contains the other.

        This is the "would one clobber the other" relation: a local file at
        ``src/store/local.txt`` overlaps an incoming file ``src/store`` (its
        directory is replaced) and an incoming ``src/store/local.txt`` (it is
        overwritten), but not ``src/storehouse``.
        """
        return self.contains(other) or other.contains(self)
