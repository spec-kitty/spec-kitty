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

__all__ = ["write_toml_table_key"]


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

    A missing file always starts from an empty document -- there is nothing
    to preserve. An existing file that ``tomllib`` cannot parse, or cannot be
    read for another OS-level reason, is handled according to ``strict``:

    * ``strict=False`` (the default, used by
      ``moments.write_agents_mode``): the rewrite starts from an empty
      document, exactly matching that function's historical behaviour --
      today's callers accept losing an unreadable file's other keys in
      exchange for never raising on a corrupt preference file.
    * ``strict=True``: the same condition raises instead, and nothing is
      written. This is for a caller whose file also carries state it must
      never silently drop by starting over from ``{}`` (e.g. the personal
      ``config.toml``'s ``[sync].server_url`` -- see
      ``hosted_posture.set_personal_drain``).
    """
    try:
        with path.open("rb") as fh:
            document: dict[str, Any] = tomllib.load(fh)
    except FileNotFoundError:
        document = {}
    except (tomllib.TOMLDecodeError, OSError):
        if strict:
            raise
        document = {}

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
