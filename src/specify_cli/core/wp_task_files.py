"""The one rule for which files in a Mission's ``tasks/`` belong to a work package.

A WP task file is a ``tasks/*.md`` entry whose name starts with the WP id,
matched case-insensitively, followed by a word boundary: ``WP04.md``,
``WP04-slug.md``, ``WP04_slug.md`` and ``WP04.x.md`` belong to ``WP04``;
``WP04b.md`` does not. ``readme.md`` never matches, in any case. This is the
spec-kitty-events R26 rule; before #7443 the dependency guard, the subtask
roster and the WP view each carried their own copy, and the guard's copy was
case-sensitive, so a lowercase ``wp02-x.md`` declared no dependencies.

The matcher does not filter by entry type. A directory (or a dangling link)
named like a task file is returned, so a gate can refuse it instead of
reporting "no file"; :func:`non_regular` names those entries for the callers.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from kernel._safe_re import re

__all__ = ["WP_FILE_SEP", "match_wp_task_files", "non_regular"]

#: Tail after the WP id: a separator (``-``, ``_``, ``.``) or the ``.md`` suffix
#: itself, so ``WP04b.md`` is not a ``WP04`` file.
WP_FILE_SEP = r"(?:[-_.]|\.md$)"

_README = "readme.md"


def match_wp_task_files(feature_dir: Path, wp_id: str) -> list[Path]:
    """Return every ``tasks/*.md`` entry of *feature_dir* that belongs to *wp_id*, sorted.

    Returns ``[]`` when ``tasks/`` does not exist. Entries that are not regular
    files are included; the caller decides what a non-regular match means.
    """
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.is_dir():
        return []
    pattern = re.compile(rf"^{re.escape(wp_id)}{WP_FILE_SEP}", re.IGNORECASE)
    return sorted(path for path in tasks_dir.glob("*.md") if path.name.lower() != _README and pattern.match(path.name))


def non_regular(matches: Iterable[Path]) -> list[Path]:
    """Return the entries of *matches* that are not regular files.

    ``Path.is_file`` follows a symbolic link, so a link to a file counts as
    regular while a directory or a dangling link does not.
    """
    return [path for path in matches if not path.is_file()]
