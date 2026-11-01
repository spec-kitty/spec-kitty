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
def test_wheel_ships_the_frozen_migration_template_sources(build_artifacts: dict[str, Path]) -> None:
    """The shipped 0.9.2 / 0.12.0 migrations read their sources from the wheel's own tree (#5280).

    Their ``specify_cli/missions/{documentation,research}/templates/`` sources are
    frozen in place (``tests/runtime/test_frozen_migration_template_sources.py``),
    so the wheel must keep shipping every pinned file at that exact path.
    """
    from tests.runtime.test_frozen_migration_template_sources import FROZEN_TEMPLATE_SOURCES

    with zipfile.ZipFile(build_artifacts["wheel"]) as zf:
        shipped = set(zf.namelist())

    missing = sorted(rel for rel in FROZEN_TEMPLATE_SOURCES if f"specify_cli/missions/{rel}" not in shipped)
    assert missing == [], f"Wheel missing frozen migration sources: {missing}"


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


def test_wheel_config_only_includes_built_in_pack_skills() -> None:
    """Config-level twin (no build): the built-in tree ships via the build hook, never ``packs/internal``."""
    import tomllib

    root = Path(__file__).resolve().parents[3]
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    build = pyproject["tool"]["hatch"]["build"]
    wheel, sdist = build["targets"]["wheel"], build["targets"]["sdist"]
    assert "custom" in build["hooks"], "the pinned-tree build hook must be registered"
    assert "packs/built-in" not in wheel.get("force-include", {}), "force-include now lives in the hook (applied only after verification)"
    assert "packs/built-in/**" in sdist["artifacts"], "VCS-ignored built-in tree must still reach the sdist"
    declared = [*wheel.get("force-include", {}), *wheel.get("include", []), *sdist.get("include", []), *sdist.get("artifacts", [])]
    packs_entries = [entry for entry in declared if "packs/" in entry]
    assert packs_entries
    assert all(entry.startswith("packs/built-in") for entry in packs_entries), packs_entries
    assert not any("internal" in entry for entry in packs_entries)


@pytest.mark.slow
def test_wheel_and_sdist_contain_built_in_files_and_no_internal(build_artifacts: dict[str, Path]) -> None:
    """FR-007 / C-002: both archives ship ``packs/built-in`` (with the pin) and nothing of ``packs/internal``."""
    with zipfile.ZipFile(build_artifacts["wheel"]) as zf:
        wheel_files = zf.namelist()
    with tarfile.open(build_artifacts["sdist"], "r:gz") as tar:
        sdist_files = [name.split("/", 1)[1] for name in tar.getnames() if "/" in name]

    assert any(name.startswith("packs/built-in/") and name.endswith("pack.yaml") for name in wheel_files)
    assert any(name.startswith("packs/built-in/") and name.endswith("pack.yaml") for name in sdist_files)
    assert "packs/built-in.source.yaml" in sdist_files, "the sdist must carry the pin so the hook can verify offline"
    for label, names in (("wheel", wheel_files), ("sdist", sdist_files)):
        leaked = [name for name in names if name.startswith(("packs/internal", "packs/internal.source"))]
        assert not leaked, f"{label} leaked packs/internal: {leaked[:5]}"


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


@pytest.mark.slow
def test_sdist_excludes_acceptance_runner_and_scenarios(build_artifacts: dict[str, Path]) -> None:
    """The acceptance runner + scenario corpus must not ship in the sdist (FR-013 / C-004).

    ``acceptance-jvm/`` (the Cucumber-JVM nightly runner) and
    ``tests/scenarios/`` (the scenario corpus) are nightly/CI-only trees
    excluded from the published source distribution via
    ``[tool.hatch.build.targets.sdist].exclude``. A same-fixture positive
    control (a known ``src/`` package IS present) guarantees the absence
    assertions are non-vacuous and not merely passing against an
    empty/broken archive.
    """
    sdist_path = build_artifacts["sdist"]

    with tarfile.open(sdist_path, "r:gz") as tar:
        all_files = tar.getnames()

    leaked_runner = [f for f in all_files if "acceptance-jvm/" in f]
    leaked_scenarios = [f for f in all_files if "tests/scenarios/" in f]

    assert not leaked_runner, f"Source dist contains the acceptance-jvm runner: {leaked_runner}"
    assert not leaked_scenarios, f"Source dist contains the scenario corpus: {leaked_scenarios}"

    # Positive control (same built sdist): a known src/ package must be present,
    # so the absence assertions above cannot pass against an empty archive.
    present_src_pkg = [f for f in all_files if "src/specify_cli/" in f]
    assert present_src_pkg, "Source dist is missing the specify_cli package (positive control failed)"


@pytest.mark.slow
def test_sdist_excludes_the_mission_status_service_and_the_contract_tree(build_artifacts: dict[str, Path]) -> None:
    """The standalone Mission Status API service and its contract tree must not ship in the sdist (C-009).

    ``contracts/`` (the handoff fixtures) sits at the repository root and is a CI-only tree; ``services/`` was removed
    from core (#6915), and the absence assertion keeps it out if it ever returns. ``pyproject.toml`` excludes ``contracts/**``
    from the sdist; this test reads the BUILT archive, so a future
    ``only-include``, ``shared-data`` or ``artifacts`` entry that pulls them in turns it red. The same-fixture positive control
    (a known ``src/`` package IS present, and the root has a project file) keeps the absence assertions non-vacuous.
    """
    sdist_path = build_artifacts["sdist"]

    with tarfile.open(sdist_path, "r:gz") as tar:
        all_files = tar.getnames()

    # Members are ``<name>-<version>/<path>``; anchor at the archive root so a nested ``src/**/contracts/`` package is not caught.
    rooted = [name.split("/", 1)[1] for name in all_files if "/" in name]
    leaked = [path for path in rooted if path.startswith(("services/", "contracts/")) or path in {"services", "contracts"}]

    assert not leaked, f"Source dist contains the service or contract tree: {leaked[:10]}"
    assert any(path.startswith("src/specify_cli/") for path in rooted), "Source dist is missing the specify_cli package (positive control failed)"
    assert "pyproject.toml" in rooted, "Source dist root has no pyproject.toml (the anchoring assumption failed)"


@pytest.mark.slow
def test_sdist_member_list_has_the_source_packages_and_the_built_in_tree(build_artifacts: dict[str, Path]) -> None:
    """T047: the sdist carries ``src/kernel``, ``src/charter`` and ``packs/built-in/**`` and zero ``packs/internal/*``."""
    with tarfile.open(build_artifacts["sdist"], "r:gz") as tar:
        rooted = [name.split("/", 1)[1] for name in tar.getnames() if "/" in name]

    for required in ("src/kernel/", "src/charter/", "packs/built-in/"):
        assert any(path.startswith(required) for path in rooted), f"sdist has no member under {required}"
    assert "hatch_build.py" in rooted, "the build hook must ship in the sdist or an sdist build silently skips verification"
    assert not [path for path in rooted if path.startswith("packs/internal/")]


# --------------------------------------------------------------------------- #
# Service pins ship; service binaries and cache content never do (#6590, FR-014, SC-005)
# --------------------------------------------------------------------------- #

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PINS_DIR = _REPO_ROOT / "pins"
#: Where the wheel carries ``pins/`` (``INSTALLED_PINS_PACKAGE_DIR`` in ``specify_cli.services.resolution``).
_INSTALLED_PINS = "specify_cli/_pins/"
#: File-name endings of a released service build (``<prefix>-<ver>-<target>[.exe]`` or ``<prefix>-<ver>.jar``).
_SERVICE_ASSET_SUFFIXES = ("-linux-x64", "-linux-arm64", "-macos-arm64", "-windows-x64.exe", ".jar")
#: Path segments of the service asset cache (``<cache>/spec-kitty/services/<service>/<tag>/<name>``).
_SERVICE_CACHE_MARKERS = ("spec-kitty/services/", ".cache/spec-kitty/")


def _wheel_members(build_artifacts: dict[str, Path]) -> list[str]:
    with zipfile.ZipFile(build_artifacts["wheel"]) as zf:
        return zf.namelist()


def _sdist_rooted_members(build_artifacts: dict[str, Path]) -> list[str]:
    with tarfile.open(build_artifacts["sdist"], "r:gz") as tar:
        return [name.split("/", 1)[1] for name in tar.getnames() if "/" in name]


def service_binary_leaks(members: list[str]) -> list[str]:
    """Members that look like a service build or service-cache content.

    ``services/`` under ``src/`` (none today) or at the archive root would be the Mission Status
    service tree removed at the cut-over (#6915), which the sdist test keeps out; this helper looks
    only at asset names and cache paths.
    """
    leaks: list[str] = []
    for member in members:
        name = member.rstrip("/").rsplit("/", 1)[-1]
        if name.endswith(_SERVICE_ASSET_SUFFIXES) or any(marker in member for marker in _SERVICE_CACHE_MARKERS):
            leaks.append(member)
    return leaks


def test_service_binary_helper_flags_planted_members() -> None:
    """Self-test: the same helper the archive tests use catches every asset shape and the cache path."""
    planted = [
        "specify_cli/_pins/command-cli-0.1.0-linux-x64",
        "specify_cli/_pins/command-cli-0.1.0-linux-arm64",
        "bin/mission-status-api-0.1.0-macos-arm64",
        "specify_cli/command-cli-0.1.0-windows-x64.exe",
        "kernel/vendor/mission-status-api-0.1.0.jar",
        "home/.cache/spec-kitty/services/write-service/service-v0.1.0/README.md",
    ]
    clean = [
        "specify_cli/_pins/README.md",
        "specify_cli/_pins/write-service.source.yaml",
        "specify_cli/services/launcher.py",
        "kernel/service_artifacts.py",
        "charter/offering/linux-x64-notes.md",
    ]
    assert service_binary_leaks(planted + clean) == planted


@pytest.mark.slow
def test_wheel_and_sdist_ship_no_service_binary_or_cache_content(build_artifacts: dict[str, Path]) -> None:
    wheel = _wheel_members(build_artifacts)
    sdist = _sdist_rooted_members(build_artifacts)

    assert not service_binary_leaks(wheel), f"service binary or cache content in the wheel: {service_binary_leaks(wheel)[:10]}"
    assert not service_binary_leaks(sdist), f"service binary or cache content in the sdist: {service_binary_leaks(sdist)[:10]}"
    # Positive control: the archives are real (the services package itself ships).
    assert "specify_cli/services/launcher.py" in wheel
    assert "src/specify_cli/services/launcher.py" in sdist


@pytest.mark.slow
def test_pins_readme_ships_in_the_sdist_and_the_wheel(build_artifacts: dict[str, Path]) -> None:
    """``pins/`` reaches both archives even before the first pin: the wheel force-include maps it to ``specify_cli/_pins``."""
    assert "pins/README.md" in _sdist_rooted_members(build_artifacts)
    assert f"{_INSTALLED_PINS}README.md" in _wheel_members(build_artifacts)


#: The only files ``pins/`` may hold, so the directory force-include ships nothing else
#: (no renamed binary, editor backup or stray file).
_PINS_ALLOWED = ("README.md",)
_PIN_SUFFIX = ".source.yaml"


def unexpected_pins_files(names: list[str]) -> list[str]:
    """Names in ``pins/`` that are neither the README nor a ``*.source.yaml`` lockfile."""
    return [name for name in names if name not in _PINS_ALLOWED and not name.endswith(_PIN_SUFFIX)]


def test_pins_directory_holds_only_the_readme_and_lockfiles() -> None:
    """``pins/`` is shipped whole, so anything else placed there would reach every install."""
    names = sorted(path.name for path in _PINS_DIR.iterdir())
    assert "README.md" in names, "pins/README.md is missing (positive control)"
    assert unexpected_pins_files(names) == [], f"unexpected files in pins/: {unexpected_pins_files(names)}"


def test_pins_allow_list_flags_planted_names() -> None:
    planted = ["command-cli-0.1.0-linux-x64", "write-service.source.yaml~", "notes.txt", ".DS_Store"]
    clean = ["README.md", "write-service.source.yaml", "read-service.source.yaml"]
    assert unexpected_pins_files(planted + clean) == planted


@pytest.mark.slow
def test_every_service_pin_ships_in_both_archives(build_artifacts: dict[str, Path]) -> None:
    pins = sorted(path.name for path in _PINS_DIR.glob("*.source.yaml"))
    if not pins:
        pytest.skip("no pins/*.source.yaml yet: spec-kitty-events has not cut its first service-v* release")
    wheel = set(_wheel_members(build_artifacts))
    sdist = set(_sdist_rooted_members(build_artifacts))
    for name in pins:
        assert f"{_INSTALLED_PINS}{name}" in wheel, f"{name} is not in the wheel at {_INSTALLED_PINS}"
        assert f"pins/{name}" in sdist, f"{name} is not in the sdist"


def test_packaging_config_ships_the_whole_pins_directory() -> None:
    """Config-level half of "pins ship once they exist": the force-include maps the directory, not a file list.

    The archive test above skips while no pin exists, so this keeps the "with a pin" case proven now: any
    ``pins/*.source.yaml`` added later lands at ``specify_cli/_pins/`` in the wheel and under ``pins/`` in the sdist.
    """
    import tomllib

    from specify_cli.services.resolution import INSTALLED_PINS_PACKAGE_DIR

    hatch = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["hatch"]["build"]["targets"]
    assert hatch["wheel"]["force-include"]["pins"] == f"specify_cli/{INSTALLED_PINS_PACKAGE_DIR}"
    assert "pins/**" in hatch["sdist"]["include"]
    assert not any(pattern.startswith("pins") for pattern in hatch["sdist"].get("exclude", []))
    assert _PINS_DIR.is_dir() and (_PINS_DIR / "README.md").is_file(), "the force-include source must always exist"


#: The optional companion distribution (#6904; ADR 2026-10-29-1, Amendment 2026-10-31): its import package and its
#: source tree. Neither ships in the CLI's wheel or sdist, which stay pure (pins only, D-4).
_COMPANION_MEMBER_PREFIXES = ("spec_kitty_services/", "spec_kitty_services-", "packages/")


def companion_leaks(members: list[str]) -> list[str]:
    """Members that belong to the ``spec-kitty-services`` companion (its package, dist-info or source tree)."""
    return [member for member in members if member.startswith(_COMPANION_MEMBER_PREFIXES)]


def test_companion_helper_flags_planted_members() -> None:
    """Self-test: the helper the archive test uses catches the companion's package, dist-info and source tree."""
    planted = [
        "spec_kitty_services/__init__.py",
        "spec_kitty_services/bin/command-cli-0.1.0-linux-x64",
        "spec_kitty_services-4.0.0rc8.dist-info/RECORD",
        "packages/spec-kitty-services/pyproject.toml",
        "packages/spec-kitty-services/README.md",
    ]
    clean = ["specify_cli/services/resolution.py", "src/specify_cli/services/launcher.py", "pins/README.md", "kernel/service_artifacts.py"]
    assert companion_leaks(planted + clean) == planted


@pytest.mark.slow
def test_wheel_and_sdist_ship_no_companion_file(build_artifacts: dict[str, Path]) -> None:
    wheel = _wheel_members(build_artifacts)
    sdist = _sdist_rooted_members(build_artifacts)

    assert not companion_leaks(wheel), f"companion content in the CLI wheel: {companion_leaks(wheel)[:10]}"
    assert not companion_leaks(sdist), f"companion content in the CLI sdist: {companion_leaks(sdist)[:10]}"
    # Positive control: the archives are real (the slot the companion fills ships).
    assert "specify_cli/services/resolution.py" in wheel
    assert "src/specify_cli/services/resolution.py" in sdist


# --------------------------------------------------------------------------- #
# Documentation, Mission and site trees never ship in the sdist (#6926; ADR 2026-10-31-1 D-12)
# --------------------------------------------------------------------------- #

#: Repository-root trees no sdist member may sit under. The bare ``README.md`` / ``CHANGELOG.md`` include entries
#: were gitignore-style and matched at any depth, so every nested README of ``docs/``, ``kitty-specs/``, ``tests/``
#: and ``scripts/`` shipped; ``site/`` is the doc-kitty docsite (#6930), excluded before it exists.
_SDIST_FORBIDDEN_TREES = ("docs/", "kitty-specs/", "site/", "tests/", "scripts/")


def sdist_stray_tree_members(rooted: list[str]) -> list[str]:
    """Rooted sdist members (``<name>-<version>/`` already stripped) under a tree that must never ship."""
    return [member for member in rooted if member.startswith(_SDIST_FORBIDDEN_TREES)]


def test_sdist_stray_tree_helper_flags_planted_members() -> None:
    """Self-test: the helper the archive test uses flags the forbidden trees and nothing anchored elsewhere."""
    planted = [
        "docs/README.md",
        "docs/changelog/CHANGELOG.md",
        "kitty-specs/some-mission-01ABCDEF/README.md",
        "site/README.md",
        "site/dist/index.html",
        "tests/README.md",
        "scripts/release/README.md",
    ]
    clean = [
        "README.md",
        "CHANGELOG.md",
        "src/charter/README.md",
        "src/specify_cli/docs/notes.py",
        "packs/built-in/missions/README.md",
        "pins/README.md",
    ]
    assert sdist_stray_tree_members(planted + clean) == planted


@pytest.mark.slow
def test_sdist_ships_no_docs_kitty_specs_or_site_member(build_artifacts: dict[str, Path]) -> None:
    """The sdist carries the root README and CHANGELOG, and nothing under ``docs/``, ``kitty-specs/``, ``site/``, ``tests/`` or ``scripts/``."""
    rooted = _sdist_rooted_members(build_artifacts)

    stray = sdist_stray_tree_members(rooted)
    assert not stray, f"{len(stray)} sdist members under {_SDIST_FORBIDDEN_TREES}: {stray[:10]}"
    # Positive control (same archive): the root documents still ship as real content, and the archive is real.
    assert _sdist_root_documents_without_content(build_artifacts) == [], "the sdist's root README.md / CHANGELOG.md is missing, empty or a link"
    assert "pyproject.toml" in rooted
    assert any(member.startswith("src/specify_cli/") for member in rooted), "Source dist is missing the specify_cli package (positive control failed)"


#: Root documents the sdist must carry as regular, non-empty files. The repository's ``CHANGELOG.md`` is a symlink into
#: ``docs/changelog/``, so once ``docs/`` stops shipping an archived symlink would dangle.
_SDIST_ROOT_DOCUMENTS = ("README.md", "CHANGELOG.md")


def root_documents_without_content(members: dict[str, tarfile.TarInfo]) -> list[str]:
    """Root documents absent from rooted ``members``, or present only as a link or an empty file."""
    return [name for name in _SDIST_ROOT_DOCUMENTS if name not in members or not members[name].isfile() or members[name].size == 0]


def _sdist_root_documents_without_content(build_artifacts: dict[str, Path]) -> list[str]:
    with tarfile.open(build_artifacts["sdist"], "r:gz") as tar:
        members = {info.name.split("/", 1)[1]: info for info in tar.getmembers() if "/" in info.name}
    return root_documents_without_content(members)


def test_root_document_helper_flags_links_empty_and_missing_files() -> None:
    """Self-test: a symlink, an empty file and a missing document are all flagged; a regular file with content is not."""
    readme = tarfile.TarInfo("README.md")
    readme.size = 10
    link = tarfile.TarInfo("CHANGELOG.md")
    link.type, link.linkname = tarfile.SYMTYPE, "docs/changelog/CHANGELOG.md"
    assert root_documents_without_content({"README.md": readme, "CHANGELOG.md": link}) == ["CHANGELOG.md"]
    assert root_documents_without_content({"README.md": tarfile.TarInfo("README.md")}) == ["README.md", "CHANGELOG.md"]
    changelog = tarfile.TarInfo("CHANGELOG.md")
    changelog.size = 10
    assert root_documents_without_content({"README.md": readme, "CHANGELOG.md": changelog}) == []


def test_sdist_config_anchors_the_root_documents_and_excludes_site() -> None:
    """Config-level twin (no build): ``site/**`` is excluded and the README / CHANGELOG includes are root-anchored."""
    import tomllib

    sdist = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["hatch"]["build"]["targets"]["sdist"]
    assert "site/**" in sdist["exclude"]
    unanchored = [entry for entry in sdist["include"] if entry in {"README.md", "CHANGELOG.md"}]
    assert not unanchored, f"gitignore-style entries match at any depth; anchor them with a leading '/': {unanchored}"
    assert "/README.md" in sdist["include"]
    # The root CHANGELOG.md is a symlink into docs/changelog/; the sdist carries the real file at the root instead.
    assert sdist.get("force-include", {}).get("docs/changelog/CHANGELOG.md") == "CHANGELOG.md"
    assert (_REPO_ROOT / "docs" / "changelog" / "CHANGELOG.md").is_file()
