"""Shared atomic single-key TOML-table rewrite primitive.

Extracted from ``zeitgeist_client.moments.write_agents_mode`` (WP01/T002) so
:mod:`specify_cli.core.hosted_posture`'s personal-drain writer does not
duplicate the load-mutate-dump-atomic-rename cycle. ``moments.py`` now calls
this function instead of inlining the same sequence; its own behaviour is
unchanged (a behaviour-preserving extraction, not a rewrite).

Non-test caller map (S1): ``write_toml_table_key`` is called from
``zeitgeist_client/moments.py::write_agents_mode`` (the pre-existing,
``strict=False`` caller) and from
``specify_cli.core.hosted_posture.set_personal_drain`` (WP01, ``strict=True``).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import tomllib
import tomli_w

# ``UnreadableTomlTableError`` is intentionally NOT in ``__all__``: no in-tree
# caller catches it yet (the non-strict caller ``moments.py`` is slated for
# removal, #6164), so exporting it trips the #470 symbol-level dead-code gate.
# It stays a public module-level name kept alive by its own ``raise`` below, and
# tests / future catchers import it directly.
__all__ = ["write_toml_table_key"]


class UnreadableTomlTableError(RuntimeError):
    """An existing TOML file could not be read or parsed.

    Raised by :func:`write_toml_table_key` in non-strict mode instead of
    silently starting from an empty document and overwriting the file
    wholesale -- that would drop every other table and key the file carries
    (e.g. ``[sync].server_url`` / ``[hosted] drain``). Refusing preserves the
    data; the caller can surface the actionable message and leave the file be.
    """


def write_toml_table_key(
    path: Path,
    *,
    table: str,
    key: str,
    value: Any,
    strict: bool = False,
) -> Path:
    """Persist ``[table] key = value`` to ``path``, preserving every other
    key and table in the document, via an atomic load-mutate-dump-rename
    cycle. Returns ``path``.

    A missing file (``FileNotFoundError``) always starts from an empty
    document -- there is nothing to preserve. An existing file that
    ``tomllib`` cannot parse, or cannot be read for another OS-level reason,
    must NOT start from ``{}``: the whole-file rewrite below would then drop
    every other table and key. Both modes refuse rather than destroy data:

    * ``strict=True``: re-raises the original ``tomllib.TOMLDecodeError`` /
      ``OSError`` and writes nothing. Used by a caller whose file carries
      state it must never silently drop (e.g. the personal ``config.toml``'s
      ``[sync].server_url`` -- see ``hosted_posture.set_personal_drain``).
    * ``strict=False`` (the default, used by ``moments.write_agents_mode``):
      raises :class:`UnreadableTomlTableError` with an actionable message and
      writes nothing. This replaces the historical behaviour of starting from
      an empty document and overwriting the file wholesale, which silently
      destroyed the file's other keys with no backup (#5451).
    """
    try:
        with path.open("rb") as fh:
            document: dict[str, Any] = tomllib.load(fh)
    except FileNotFoundError:
        document = {}
    except (tomllib.TOMLDecodeError, OSError) as error:
        if strict:
            raise
        raise UnreadableTomlTableError(
            f"{path}: existing TOML config is unreadable and cannot be safely "
            f"rewritten without losing its other keys ({error}). "
            "Fix or remove the file, then retry."
        ) from error

    section = document.get(table)
    section = dict(section) if isinstance(section, Mapping) else {}
    section[key] = value
    document[table] = section

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("wb") as fh:
        tomli_w.dump(document, fh)
    tmp_path.replace(path)  # atomic on POSIX and Windows (same volume)
    return path
