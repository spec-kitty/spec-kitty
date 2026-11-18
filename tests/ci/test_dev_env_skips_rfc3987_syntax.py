"""No installed environment except the release SBOM step pulls in ``rfc3987-syntax`` (#7704).

``jsonschema`` imports ``rfc3987_syntax`` on load whenever it is installed, and
that import builds a Lark grammar (about 0.9 s). ``spec_kitty_events`` imports
``jsonschema`` lazily on the first event it validates, so with the package
present every process paid about 1 s on its first glossary event. That made each
glossary performance test fail when run alone and turned the nightly red.

The package arrived only through ``cyclonedx-bom`` (it requires
``cyclonedx-python-lib[validation]`` -> ``jsonschema[format-nongpl]``), which now
lives in the non-default ``sbom`` dependency group that only ``release.yml``
installs. Measured with a fresh process per sample, 5 samples each:

- consumer wheel install: cold first step 0.11-0.14 s, warm 0.075-0.08 s;
- dev ``--all-extras`` env before the move: cold 1.10-1.26 s, warm 0.07-0.11 s;
- dev ``--all-extras`` env after the move: cold 0.11-0.16 s, warm 0.07-0.09 s.

These tests walk ``uv.lock`` so the cost cannot come back unnoticed through
another extra or default group.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ROOT_PACKAGE = "spec-kitty-cli"
_SLOW_IMPORT_PACKAGE = "rfc3987-syntax"
_RELEASE_ONLY_GROUP = "sbom"


def _lock() -> dict[str, dict[str, Any]]:
    """Packages by name; a name locked at several versions gets the union of their edges."""
    data = tomllib.loads((_REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
    packages: dict[str, dict[str, Any]] = {}
    for package in data["package"]:
        merged = packages.setdefault(package["name"], {"dependencies": [], "optional-dependencies": {}, "dev-dependencies": {}})
        merged["dependencies"] = [*merged["dependencies"], *package.get("dependencies", ())]
        for key in ("optional-dependencies", "dev-dependencies"):
            for extra, deps in package.get(key, {}).items():
                merged[key][extra] = [*merged[key].get(extra, ()), *deps]
    return packages


def _edges(entries: Iterable[dict[str, Any]]) -> list[tuple[str, tuple[str, ...]]]:
    return [(entry["name"], tuple(entry.get("extra", ()))) for entry in entries]


def _reachable(packages: dict[str, dict[str, Any]], *, groups: Iterable[str]) -> set[str]:
    """Every package installable from the root's runtime deps, ALL its extras and *groups*."""
    root = packages[_ROOT_PACKAGE]
    pending = _edges(root.get("dependencies", ()))
    for extra_deps in root.get("optional-dependencies", {}).values():
        pending += _edges(extra_deps)
    for group in groups:
        pending += _edges(root.get("dev-dependencies", {}).get(group, ()))
    seen: set[tuple[str, tuple[str, ...]]] = set()
    names: set[str] = set()
    while pending:
        name, extras = pending.pop()
        if (name, extras) in seen or name not in packages:
            continue
        seen.add((name, extras))
        names.add(name)
        package = packages[name]
        pending += _edges(package.get("dependencies", ()))
        for extra in extras:
            pending += _edges(package.get("optional-dependencies", {}).get(extra, ()))
    return names


def _default_groups(packages: dict[str, dict[str, Any]]) -> list[str]:
    groups = packages[_ROOT_PACKAGE].get("dev-dependencies", {})
    return [group for group in groups if group != _RELEASE_ONLY_GROUP]


def test_no_extra_or_default_group_installs_the_slow_import_package() -> None:
    packages = _lock()
    reachable = _reachable(packages, groups=_default_groups(packages))
    assert _SLOW_IMPORT_PACKAGE not in reachable, (
        f"{_SLOW_IMPORT_PACKAGE} is reachable from spec-kitty-cli's runtime deps, an extra or a default "
        "dependency group; jsonschema then imports it on the first validated event (~0.9 s, #7704). "
        f"Keep whatever pulls it in inside the non-default '{_RELEASE_ONLY_GROUP}' group."
    )


def test_the_walk_finds_the_package_through_the_release_only_group() -> None:
    """Positive control: the same walk reaches it once the release-only group is included."""
    packages = _lock()
    assert _SLOW_IMPORT_PACKAGE in _reachable(packages, groups=[*_default_groups(packages), _RELEASE_ONLY_GROUP])


def test_the_release_job_installs_the_release_only_group() -> None:
    release = (_REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert f"--group {_RELEASE_ONLY_GROUP}" in release
    assert "cyclonedx-py environment" in release
