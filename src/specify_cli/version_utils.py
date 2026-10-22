"""Version detection utilities for spec-kitty CLI."""

import os
from functools import cache
from kernel._safe_re import re
from pathlib import Path


def read_version_from_pyproject() -> str | None:
    """Read version from pyproject.toml as fallback.

    Returns:
        Version string if found, None otherwise
    """
    try:
        # Find pyproject.toml relative to this file
        package_root = Path(__file__).parent.parent.parent
        pyproject_path = package_root / "pyproject.toml"

        if not pyproject_path.exists():
            return None

        content = pyproject_path.read_text()

        # Match: version = "X.Y.Z"
        pattern = re.compile(r'^\s*version\s*=\s*"(\d+\.\d+\.\d+[^"]*)"', re.MULTILINE)
        match = pattern.search(content)

        if match:
            result: str = match.group(1)
            return result

        return None
    except Exception:
        # Any error reading file -> return None
        return None


def get_version() -> str:
    """Get spec-kitty version with smart fallback strategy.

    Priority:
    1. importlib.metadata for the resolved CLI package name
    2. pyproject.toml (fallback for editable installs)
    3. "0.0.0-dev" (last resort if both fail)

    Returns:
        Version string
    """
    try:
        from importlib.metadata import version as get_metadata_version

        from specify_cli.distribution.package_name import resolve_cli_package_name

        return get_metadata_version(resolve_cli_package_name())
    except Exception:  # noqa: S110
        pass

    # Try reading from pyproject.toml (editable installs)
    pyproject_version = read_version_from_pyproject()
    if pyproject_version:
        return pyproject_version

    # Last resort fallback
    return "0.0.0-dev"


@cache
def cli_version() -> str:
    """Return the version this CLI reports as ``specify_cli.__version__``.

    Resolved on first use and then fixed for the process, so the
    ``SPEC_KITTY_TEST_MODE`` environment at the first read decides it (it used
    to be the environment at import). Under
    ``SPEC_KITTY_TEST_MODE=1`` it is ``SPEC_KITTY_CLI_VERSION`` (default
    ``0.5.0-dev``), so tests see the source version; otherwise it is
    :func:`get_version`.

    Deferred rather than computed at import (#6584): :func:`get_version`
    resolves the distribution name through ``packages_distributions()``, which
    reads the metadata of every installed distribution, and a command that
    never prints a version (``spec-kitty --help``) should not pay for that.
    """
    if os.environ.get("SPEC_KITTY_TEST_MODE") == "1":
        return os.environ.get("SPEC_KITTY_CLI_VERSION", "0.5.0-dev")
    return get_version()
