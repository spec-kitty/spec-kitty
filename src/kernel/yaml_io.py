"""Shared YAML serialization and durable-write primitives for the kernel layer.

Canonical home for the house YAML-dump conventions used by every writer that
persists a mapping (dict / ``CommentedMap``) as YAML: round-trip dumper (so
``ruamel`` comment/quote/anchor fidelity and ``CommentedMap`` inputs survive),
a wide fixed line width (so wrapped prose never fragments a scalar across
lines), and a post-dump normalizer that strips the non-semantic trailing
whitespace ``ruamel`` leaves on wrapped-scalar continuation lines.

Adopted by ``specify_cli.retrospective.writer`` (moved here verbatim) and
``specify_cli.review.arbiter`` (#3058) so both surfaces share one seam instead
of hand-rolling the same dump-then-normalize dance with drifting width
settings.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from kernel.no_follow import open_no_follow

__all__ = [
    "serialize_mapping",
    "write_mapping_atomic",
]

# Matches the house "prevent line wrapping" width used across writers
# (e.g. ``specify_cli.review.artifacts._make_yaml``): wide enough that no
# reviewer-prose or retrospective-detail scalar wraps under normal use.
CANONICAL_YAML_WIDTH = 4096


def serialize_mapping(data: Mapping[str, Any], *, width: int = CANONICAL_YAML_WIDTH) -> bytes:
    """Serialize a mapping to canonical YAML bytes.

    Uses a round-trip (``typ="rt"``) dumper, not a safe dumper: a safe dumper
    raises ``RepresenterError`` on a ``ruamel.yaml.comments.CommentedMap``
    (arbiter and other frontmatter-merge callers pass one in, since they load
    existing frontmatter with ``preserve_quotes=True`` before mutating it),
    and it would also strip the comment/quote fidelity round-trip is for.

    The dump is post-processed by :func:`_normalize_nonsemantic_trailing_whitespace`
    to remove the trailing-space/tab artifacts ``ruamel`` leaves on wrapped
    scalar continuation lines, without touching semantically-significant
    trailing whitespace inside literal block scalars.
    """
    yaml = YAML(typ="rt")
    yaml.default_flow_style = False
    yaml.preserve_quotes = True
    yaml.width = width

    buf = BytesIO()
    yaml.dump(data, buf)
    return _normalize_nonsemantic_trailing_whitespace(buf.getvalue())


def _normalize_nonsemantic_trailing_whitespace(serialized: bytes) -> bytes:
    """Remove writer wrapping artifacts only when YAML meaning remains unchanged.

    Falls back to the original bytes if the safety re-parse cannot confirm the
    normalized form is semantically identical, so normalization is never worse
    than emitting the un-normalized dump.
    """
    normalized = b"\n".join(line.rstrip(b" \t\r") for line in serialized.split(b"\n"))
    if normalized == serialized:
        return serialized

    yaml = YAML(typ="safe")
    try:
        original_data = yaml.load(serialized)
        normalized_data = yaml.load(normalized)
    except YAMLError:
        return serialized
    return normalized if normalized_data == original_data else serialized


def write_mapping_atomic(
    data: Mapping[str, Any],
    path: Path,
    *,
    width: int = CANONICAL_YAML_WIDTH,
    mkdir: bool = False,
) -> None:
    """Atomically write ``data`` as YAML to ``path``, fsyncing for durability.

    This is a durability-enhanced sibling of :func:`kernel.atomic.atomic_write`
    (which does write-temp-then-rename but does NOT ``fsync``). It is not
    reused here because canonical mission records (retrospective, review
    artifacts) need the extra fsync/dir-fsync durability delta: without it, a
    crash immediately after ``os.replace`` can still lose the rename on some
    filesystems/power-loss scenarios, because the directory entry update was
    never flushed. ``atomic_write`` is the right choice for lower-stakes
    generated/regenerable files; this function is for records whose loss is a
    correctness problem.

    Sequence:
    1. Serialize ``data`` via :func:`serialize_mapping`.
    2. Write to a uniquely-named ``.tmp`` file in ``path.parent`` (created
       ``O_WRONLY | O_CREAT | O_EXCL`` — through
       :func:`kernel.no_follow.open_no_follow`, so a symlink pre-planted at
       the temp path is refused rather than written through — so two
       concurrent writers never collide), ``fsync`` the file descriptor,
       close.
    3. ``os.replace(tmp, path)`` — atomic rename.
    4. Best-effort ``fsync`` on the parent directory fd to flush the rename
       into the directory inode (non-fatal on failure).

    On any failure the tempfile is unlinked and the original exception
    propagates — this function raises no kernel-specific exception type so
    callers remain free to translate failures into their own domain errors.
    """
    if mkdir:
        path.parent.mkdir(parents=True, exist_ok=True)

    serialized = serialize_mapping(data, width=width)

    tmp_name = f"{path.name}.tmp.{os.getpid()}.{os.urandom(4).hex()}"
    tmp_path = path.parent / tmp_name

    try:
        fd = open_no_follow(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            os.write(fd, serialized)
            os.fsync(fd)
        finally:
            os.close(fd)

        os.replace(str(tmp_path), str(path))

        # Best-effort dir fsync.
        try:
            dir_fd = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
    except Exception:
        with contextlib.suppress(OSError):
            tmp_path.unlink(missing_ok=True)
        raise
