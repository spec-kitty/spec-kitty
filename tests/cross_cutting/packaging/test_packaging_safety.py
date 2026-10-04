"""Validate packaging safety for template relocation and charter isolation."""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

import pytest


# build_artifacts fixture comes from conftest.py (session-scoped, shared)


pytestmark = [pytest.mark.integration]

@pytest.mark.slow
def test_wheel_contains_no_kittify_paths(build_artifacts: dict[str, Path]) -> None:
    """Verify wheel doesn't contain .kittify/ paths."""
    wheel_path = build_artifacts["wheel"]

    with zipfile.ZipFile(wheel_path) as zf:
        all_files = zf.namelist()

    kittify_files = [f for f in all_files if ".kittify/" in f]
    assert not kittify_files, f"Wheel contains .kittify/ paths (packaging contamination): {kittify_files}"


@pytest.mark.slow
def test_wheel_contains_no_filled_charter(build_artifacts: dict[str, Path]) -> None:
    """Verify wheel doesn't contain a filled charter under memory/."""
    wheel_path = build_artifacts["wheel"]

    with zipfile.ZipFile(wheel_path) as zf:
        all_files = zf.namelist()

    charter_files = [f for f in all_files if "charter.md" in f.lower()]

    for const_file in charter_files:
        assert "memory/charter" not in const_file, f"Wheel contains filled charter from memory/: {const_file}"
        assert "templates/" in const_file or "missions/" in const_file, (
            f"Found non-template charter in wheel: {const_file}"
        )


@pytest.mark.slow
def test_wheel_contains_templates(build_artifacts: dict[str, Path]) -> None:
    """Verify wheel does contain templates and missions."""
    wheel_path = build_artifacts["wheel"]

    with zipfile.ZipFile(wheel_path) as zf:
        all_files = zf.namelist()

    template_files = [f for f in all_files if "specify_cli/templates/" in f]
    mission_files = [f for f in all_files if "specify_cli/missions/" in f]

    assert template_files, "Wheel missing template files"
    assert mission_files, "Wheel missing mission files"


@pytest.mark.slow
def test_wheel_contains_only_known_packages(build_artifacts: dict[str, Path]) -> None:
    """Verify wheel only contains known package directories."""
    wheel_path = build_artifacts["wheel"]

    known_prefixes = (
        "specify_cli/",
        # "doctrine/" retained defensively: no wheel content lands under this
        # top-level directory prefix anymore (charter-code-topology-01M152G1,
        # S5) -- the former src/doctrine package relocated to
        # src/charter/offering/ (S2a), so doctrine content ships under
        # "charter/offering/" below. The bare src/doctrine.py CR-06
        # deprecation-shim module was deleted past its 3.3.0 removal release
        # (#805) and is no longer force-included.
        "doctrine/",
        "charter/",
        "kernel/",
        "glossary/",
        "mission_runtime/",
        "runtime/",
        # Built-in doctrine data relocated to a top-level packs/built-in pack root,
        # force-included in the wheel as a site-packages sibling of ``charter``
        # (mission relocate-builtin-doctrine-packs). Scoped to ``packs/built-in/``:
        # only the PUBLIC product doctrine ships. Maintainer-only org packs such as
        # ``packs/internal/`` must never appear in the wheel.
        "packs/built-in/",
    )

    with zipfile.ZipFile(wheel_path) as zf:
        all_files = [f for f in zf.namelist() if ".dist-info/" not in f]

    for file_path in all_files:
        assert any(file_path.startswith(p) for p in known_prefixes), (
            f"File outside known package directories: {file_path}"
        )

    # Explicit boundary: the internal (maintainer-only) org pack must not ship.
    leaked_internal = [f for f in all_files if f.startswith("packs/internal/")]
    assert not leaked_internal, (
        "Maintainer-only packs/internal/ leaked into the consumer wheel: "
        f"{leaked_internal}"
    )


@pytest.mark.slow
def test_wheel_ships_no_internal_pack_skills(build_artifacts: dict[str, Path]) -> None:
    """No ``packs/internal/skills/`` path ships: in-house pack skills never reach consumers (#5193)."""
    with zipfile.ZipFile(build_artifacts["wheel"]) as zf:
        leaked = [f for f in zf.namelist() if f.startswith("packs/internal/skills/") or "/internal/skills/" in f]
    assert not leaked, f"Maintainer-only packs/internal/skills/ leaked into the consumer wheel: {leaked}"


def test_wheel_config_only_includes_built_in_pack_skills() -> None:
    """Config-level twin (no build): the wheel include/force-include is scoped to ``packs/built-in``."""
    import tomllib

    pyproject = tomllib.loads((Path(__file__).resolve().parents[3] / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]
    packs_entries = [entry for entry in (*wheel.get("force-include", {}), *wheel.get("include", [])) if "packs/" in entry]
    assert packs_entries, "expected the packs/built-in include to be declared"
    assert all(entry.startswith("packs/built-in") for entry in packs_entries), packs_entries
    assert not any("internal" in entry for entry in packs_entries)


@pytest.mark.slow
def test_wheel_excludes_build_only_files(build_artifacts: dict[str, Path]) -> None:
    """Build-tooling files must never ship inside the runtime wheel (#3163).

    ``src/kernel/pyproject.toml`` is dormant packaging metadata for the
    planned standalone ``spec-kitty-kernel`` wheel (never imported at
    runtime) -- before the root pyproject.toml's wheel ``exclude`` list
    covered it, it landed in every ``spec-kitty-cli`` consumer's
    site-packages as pure packaging debris.

    Historical note (charter-code-topology-01M152G1, S5): the sibling
    dormant ``spec-kitty-doctrine`` wheel groundwork this test used to guard
    (``src/charter/offering/hatch_build.py`` + ``.../pyproject.toml``, née
    ``src/charter/offering/hatch_build.py`` + ``.../pyproject.toml``) was DELETED
    outright per MAP-BUILD rather than merely excluded -- it was never built
    or published by any CI job. The two doctrine keys below stay in the
    checked set as an inert regression guard (they can only ever be
    vacuously satisfied now that the source files are gone); the live
    invariant this gate still enforces is the ``kernel/pyproject.toml`` key.
    """
    wheel_path = build_artifacts["wheel"]

    with zipfile.ZipFile(wheel_path) as zf:
        all_files = set(zf.namelist())

    offending = sorted(
        name
        for name in all_files
        if name
        in {
            "doctrine/hatch_build.py",
            "doctrine/pyproject.toml",
            "charter/offering/hatch_build.py",
            "charter/offering/pyproject.toml",
            "kernel/pyproject.toml",
        }
    )
    assert not offending, f"Build-only files leaked into the runtime wheel: {offending}"


@pytest.mark.slow
def test_sdist_contains_no_kittify_paths(build_artifacts: dict[str, Path]) -> None:
    """Verify sdist doesn't contain .kittify/ runtime paths."""
    sdist_path = build_artifacts["sdist"]

    with tarfile.open(sdist_path, "r:gz") as tar:
        all_files = tar.getnames()

    bad_kittify_files = [f for f in all_files if ".kittify/" in f and "/src/" not in f]

    assert not bad_kittify_files, f"Source dist contains .kittify/ paths outside src/: {bad_kittify_files}"
