"""Shared guard: is ``docs/reports/`` ever published as live docs by docfx?

The terminology guard's ``docs/reports/`` exemption (see
``docs/development/reference/terminology-exemptions.md``, Exempt Surface 5)
is only safe while ``docs/docfx.json`` never turns those dated point-in-time
snapshots into published, live documentation. Three guard tests assert this:

- ``tests/contract/test_terminology_guards.py::
  test_docs_reports_exemption_is_not_published_as_live_docs``
- ``tests/specify_cli/cli/test_decision_command_shape_consistency.py::
  test_docs_reports_exemption_is_not_published_as_live_docs``
- ``tests/audit/test_no_legacy_agent_profiles_path.py::
  test_docs_reports_exemption_is_not_published_as_live_docs``

All of them reach :func:`docfx_publishes_reports` through
:func:`assert_docfx_does_not_publish_reports` here instead of carrying
their own copy, so there is exactly one glob-matching implementation to keep
correct (previously each file re-implemented a much weaker, vacuous-prone
check: a bare ``"reports" in pattern`` substring test that neither
understood ``**`` globs nor ``src``/``exclude`` semantics -- see the finding
that prompted this module).

A naive substring/``fnmatch`` check is not good enough for docfx globs:

- docfx (`Microsoft.DotNet.Glob`) uses ``**`` to match zero or more path
  segments, crossing ``/`` -- e.g. ``context/**.md`` matches both
  ``context/foo.md`` and ``context/sub/foo.md``. Python's ``fnmatch``
  treats a bare ``*`` as already crossing ``/`` with different semantics,
  so reusing it would silently mismatch docfx's own glob dialect.
- a build.content entry can carry a ``src`` (files/excludes are resolved
  *relative to that entry's src*, not relative to ``docs/``), and an
  ``exclude`` list that can carve a path back out even when ``files``
  would otherwise match it (e.g. a safe ``"exclude": ["reports/**"]``
  alongside a catch-all ``"files": ["**.md"]``).
- a ``"src": "reports"`` entry publishes everything under ``reports/`` via
  its own ``files`` globs without the literal substring ``"reports"``
  needing to appear in any glob pattern at all.

This module implements a small, correct-enough docfx glob translator and a
resolver that walks ``build.content`` entries the way docfx itself does:
resolve the probe path relative to each entry's ``src``, skip entries the
probe isn't under, test ``files`` globs, then subtract anything an
``exclude`` glob matches.
"""

from __future__ import annotations

import json
import posixpath
import re
from pathlib import Path
from typing import Any

# A representative probe path for a dated report snapshot, relative to
# docs/ (docfx.json's own directory -- the default ``src`` for a
# build.content entry that doesn't declare one). Mirrors a real file this
# mission's spec.md R6 cites:
# docs/reports/tracer-friction-recon/2026-09-26/coverage-matrix.md.
PROBE_REPORT_PATH = "reports/tracer-friction-recon/2026-09-26/coverage-matrix.md"
# A second, sibling-tree probe, so an ``exclude`` that carves out only the
# first probe's sub-tree cannot make the guard pass while other reports stay
# published.
SIBLING_PROBE_REPORT_PATH = "reports/any-other-report/2026-01-01/index.md"
PROBE_REPORT_PATHS = (PROBE_REPORT_PATH, SIBLING_PROBE_REPORT_PATH)
# docfx publishes both sections: ``content`` is transformed, ``resource`` is
# copied raw -- either one makes a report live.
_PUBLISHING_SECTIONS = ("content", "resource")
_BRACE_RE = re.compile(r"\{([^{}]*)\}")


def _docfx_glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a docfx build.content glob into an anchored regex.

    Supports the two docfx glob metacharacters that matter for this guard:

    - ``**`` -- matches any sequence of characters, including ``/``
      (zero or more path segments). A ``/`` immediately following ``**``
      is consumed as part of the wildcard so ``**/`` and ``**`` behave
      the same way.
    - ``*`` -- matches any sequence of characters *except* ``/`` (matches
      within a single path segment).
    - ``?`` -- matches exactly one character except ``/``.

    Everything else is matched literally (escaped for regex safety).
    """
    regex_parts: list[str] = []
    i = 0
    length = len(pattern)
    while i < length:
        char = pattern[i]
        if char == "*":
            if i + 1 < length and pattern[i + 1] == "*":
                regex_parts.append(".*")
                i += 2
                if i < length and pattern[i] == "/":
                    i += 1
                continue
            regex_parts.append("[^/]*")
            i += 1
            continue
        if char == "?":
            regex_parts.append("[^/]")
            i += 1
            continue
        regex_parts.append(re.escape(char))
        i += 1
    return re.compile("^" + "".join(regex_parts) + "$")


def _expand_braces(pattern: str) -> list[str]:
    """Expand docfx ``{a,b}`` alternations into plain glob patterns."""
    match = _BRACE_RE.search(pattern)
    if match is None:
        return [pattern]
    head, tail = pattern[: match.start()], pattern[match.end() :]
    expanded: list[str] = []
    for option in match.group(1).split(","):
        expanded.extend(_expand_braces(head + option + tail))
    return expanded


def _normalize_pattern(pattern: str) -> str:
    """Drop a leading ``./`` (docfx treats it as the entry's own ``src``)."""
    while pattern.startswith("./"):
        pattern = pattern[2:]
    return pattern


def _glob_matches(pattern: str, candidate: str) -> bool:
    return any(_docfx_glob_to_regex(_normalize_pattern(expanded)).match(candidate) is not None for expanded in _expand_braces(pattern))


def _as_pattern_list(value: object) -> list[str]:
    """docfx accepts a single string where a list of globs is expected."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _relative_to_src(probe_path: str, src: str) -> str | None:
    """Return ``probe_path`` relative to a build.content entry's ``src``.

    ``src`` is resolved against ``docs/`` (docfx.json's own directory) and
    normalised, so ``./reports`` and ``../docs/reports`` both mean
    ``reports``. Returns ``None`` when ``probe_path`` is not under ``src`` at
    all, so the caller can skip that entry entirely (mirroring docfx, which
    never lets one entry's globs reach outside its own ``src``).
    """
    resolved = posixpath.normpath(posixpath.join("docs", src or "."))
    if resolved == "docs":
        return probe_path
    if not resolved.startswith("docs/"):
        return None
    normalized_src = resolved[len("docs/") :]
    prefix = normalized_src + "/"
    if probe_path == normalized_src:
        return ""
    if not probe_path.startswith(prefix):
        return None
    return probe_path[len(prefix) :]


def docfx_publishes_path(config: dict[str, Any], probe_path: str) -> bool:
    """Return ``True`` if any ``build.content`` entry publishes ``probe_path``.

    ``probe_path`` is relative to ``docs/`` (docfx.json's own directory),
    the same root every build.content entry's default ``src`` resolves
    against.

    For each entry: resolve ``probe_path`` relative to that entry's
    ``src`` (skipping the entry if the probe isn't under it), then the
    path is published by that entry if any of its ``files`` globs match
    and no ``exclude`` glob matches it back out.
    """
    build = config.get("build", {})
    for section in _PUBLISHING_SECTIONS:
        for entry in build.get(section, []):
            if _entry_publishes(entry, probe_path):
                return True
    return False


def _entry_publishes(entry: dict[str, Any], probe_path: str) -> bool:
    relative = _relative_to_src(probe_path, entry.get("src", "."))
    if relative is None:
        return False
    if not any(_glob_matches(pattern, relative) for pattern in _as_pattern_list(entry.get("files"))):
        return False
    return not any(_glob_matches(pattern, relative) for pattern in _as_pattern_list(entry.get("exclude")))


def docfx_publishes_reports(config: dict[str, Any]) -> bool:
    """Return ``True`` if ``config`` publishes any ``docs/reports/`` probe path."""
    return any(docfx_publishes_path(config, probe) for probe in PROBE_REPORT_PATHS)


def assert_docfx_does_not_publish_reports(docfx_config_path: Path) -> None:
    """Load ``docfx_config_path`` and fail loudly if it publishes docs/reports/.

    Shared assertion body for the guard tests listed in the module
    docstring, so they stay identical by construction instead of by
    discipline.
    """
    config = json.loads(docfx_config_path.read_text(encoding="utf-8"))
    assert not docfx_publishes_reports(config), (
        "docs/docfx.json now publishes docs/reports/ as live docs (probe path "
        f"{PROBE_REPORT_PATH!r} matched a build.content entry's files globs "
        "and was not excluded). The docs/reports/ exemption in "
        "tests/contract/test_terminology_guards.py, "
        "tests/specify_cli/cli/test_decision_command_shape_consistency.py and "
        "tests/audit/test_no_legacy_agent_profiles_path.py "
        "assumes reports/ snapshots are never published as live docs -- if "
        "that changed on purpose, the exemption must be removed/narrowed, "
        "not left in place."
    )
