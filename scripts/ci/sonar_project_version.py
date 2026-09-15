#!/usr/bin/env python3
"""Derive ``sonar.projectVersion`` from ``pyproject.toml`` (WP01, FR-001/FR-002).

The ``sonar-pr`` job in ``.github/workflows/ci-aggregate.yml`` calls this module
to stamp each SonarCloud analysis with a real project version read from the
canonical source (``pyproject.toml``'s ``[project].version``), so the new-code
quality-gate baseline resets per dev cycle instead of freezing at the "not
provided" anchor (#2421). (Until mission ``sonar-per-pr-coverage-reuse``, #4334,
the caller was ``ci-quality.yml``'s ``sonarcloud`` job; that job was retired for
re-measuring coverage the ``ci-modules`` shards had already produced, and the
per-change report moved to ``ci-aggregate.yml``.) The version is single-sourced here — never hardcoded
or duplicated into ``sonar-project.properties`` — so a version bump needs zero
further edits (FR-002).

Contract:

- ``read_project_version(path)`` returns EXACTLY ``[project].version`` as a
  non-empty ``str``.
- It **raises loudly** (``ProjectVersionError``) — and never returns an empty
  string — when the file is missing / unreadable, the TOML is malformed, the
  ``[project]`` table or ``version`` key is absent, or the version is not a
  non-empty string. A silent empty emit would let the workflow stamp an empty
  ``sonar.projectVersion`` and re-freeze the baseline: the exact failure this
  module closes.
- ``main`` prints the version to stdout (and nothing else) on success, exit
  ``0``; on any failure it prints a diagnostic to stderr, emits NOTHING to
  stdout, and exits non-zero — so a shell ``version="$(...)"`` capture is empty
  and the step fails rather than silently stamping ``sonar.projectVersion=``.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path

DEFAULT_PYPROJECT = "pyproject.toml"

EXIT_OK = 0
EXIT_ERROR = 1


class ProjectVersionError(RuntimeError):
    """The project version could not be derived from ``pyproject.toml``."""


def read_project_version(pyproject_path: Path | str) -> str:
    """Return ``[project].version`` from ``pyproject_path`` as a non-empty string.

    Raises ``ProjectVersionError`` (never returns empty) when the file is
    missing / unreadable, the TOML is malformed, the ``[project]`` table or
    ``version`` key is absent, or the version is not a non-empty string.

    SSOT note: this intentionally duplicates the pyproject-version read in
    ``specify_cli.release.payload._read_current_version`` (and the regex variant
    in ``specify_cli.version_utils.read_version_from_pyproject``). It is NOT
    consolidated because this script runs in a CI job that never installs the
    ``spec-kitty-cli`` package — so it must stay stdlib-only
    and cannot ``import specify_cli.*``. See ``release/payload.py`` for the
    in-process equivalent.
    """
    path = Path(pyproject_path)
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except OSError as exc:
        raise ProjectVersionError(f"cannot read {path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ProjectVersionError(f"cannot parse {path}: {exc}") from exc

    project = data.get("project")
    if not isinstance(project, dict) or "version" not in project:
        raise ProjectVersionError(
            f"{path} has no [project].version (dynamic or missing); "
            "sonar.projectVersion cannot be derived"
        )

    version = project["version"]
    if not isinstance(version, str) or not version.strip():
        raise ProjectVersionError(
            f"{path} [project].version must be a non-empty string, got {version!r}"
        )
    return version


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: print the derived project version to stdout; loud non-zero on error."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument(
        "--pyproject",
        default=DEFAULT_PYPROJECT,
        help=f"path to pyproject.toml (default: {DEFAULT_PYPROJECT})",
    )
    args = parser.parse_args(argv)
    try:
        version = read_project_version(args.pyproject)
    except ProjectVersionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(version)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
