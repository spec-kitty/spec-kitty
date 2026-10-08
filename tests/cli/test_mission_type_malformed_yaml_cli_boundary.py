"""Post-verification-sweep regression: CL-006/NFR-002 CLI boundary for the
layered mission-type roster (mission ``up-mission-type-seam-01KZY1JB``).

The verification sweep found that ``charter activate mission-type <id>`` and
``charter mission-type list`` crashed with a **raw, uncaught Python
traceback** (not ``typer.Exit``) whenever a malformed/unreadable mission-type
YAML file existed anywhere in an activated org pack's ``mission_types/``.
Root cause: both commands call ``resolve_layered_roster`` ->
``resolve_layered_mission_types`` -> ``scan_mission_types_dir`` (which
loud-fails by design, WP03/PR-CONTRACT-002) with no exception handling at
the CLI boundary at all.

The finding's own regression tests never drove the real CLI (they exercised
the manager in isolation), which is exactly how the gap was missed — so
every test here crosses the real Typer app boundary via ``CliRunner``,
against a REAL (unmocked) ``PackContext.from_config`` reading a REAL
``.kittify/config.yaml``-registered org pack on disk. No mocking of the
charter/doctrine layers.

Covers the two named crash sites plus three siblings this mission's own
grep found reaching the same three functions without a handler:

- ``charter activate mission-type <id>``      (activate.py)
- ``charter mission-type list``               (charter/mission_type.py)
- ``charter mission-type list --include-inactive`` (charter/mission_type.py)
- ``mission-type show <id>``                   (mission_type.py)
- ``charter list --all --show-available``      (charter/list_cmd.py)

Each must exit cleanly with ``typer.Exit(1)`` (surfaced by ``CliRunner`` as
``result.exception`` being a bare ``SystemExit``, never the raw
``ValueError``/``pydantic.ValidationError``) and name the offending file in
the operator-facing output.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from charter.offering.missions.mission_type_repository import MissionTypeRepository
from specify_cli.cli.commands.charter import charter_app
from specify_cli.cli.commands.mission_type import app as mission_type_app

runner = CliRunner()
pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MALFORMED_YAML = "id: [unterminated\n"


@pytest.fixture()
def project_with_malformed_org_mission_type(tmp_path: Path) -> Path:
    """A project with a real, config.yaml-registered org pack whose
    ``mission_types/broken.yaml`` is syntactically malformed YAML.

    Deliberately real filesystem + real ``doctrine.org.packs`` config (no
    ``PackContext.from_config`` mock) -- this mirrors the finding's own
    reproduction and the ``tests/integration/test_org_pack_artifact_lifecycle.py``
    org-pack registration convention.
    """
    org_root = tmp_path / "org-pack"
    (org_root / "mission_types").mkdir(parents=True)
    (org_root / "mission_types" / "broken.yaml").write_text(_MALFORMED_YAML, encoding="utf-8")

    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        textwrap.dedent(
            f"""\
            mission_type_activations:
              - software-dev
            charter_packs:
              org:
                packs:
                  - name: broken-org-pack
                    local_path: {org_root}
            """
        ),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture(autouse=True)
def _clear_layered_cache():
    """The layered-roster resolver is ``functools.cache``d (keyed on
    ``(mission_types_dirs, pack_context)``) -- clear before AND after each
    test so no scratch ``tmp_path`` fixture leaks into another test's cache.
    """
    MissionTypeRepository.cache_clear()
    yield
    MissionTypeRepository.cache_clear()


def _asserts_clean_exit_naming_file(result: object, offending_filename: str = "broken.yaml") -> None:
    """Shared assertion: clean ``typer.Exit(1)``, never a raw exception.

    ``CliRunner`` (default ``catch_exceptions=True``) sets ``exit_code == 1``
    for BOTH a clean ``typer.Exit(1)`` AND an uncaught ``ValueError`` --
    ``result.exception`` is the only field that tells them apart:
    ``SystemExit(1)`` for the clean path, the raw exception instance for a
    crash. A raw crash also prints nothing to ``result.output`` (the
    traceback goes to the uncaptured stack, not the console), so the
    file-naming assertion doubles as a second, independent crash detector.
    """
    assert result.exit_code == 1, result.output
    assert isinstance(result.exception, SystemExit), (
        f"expected a clean typer.Exit(1) (SystemExit), got a raw "
        f"{type(result.exception).__name__}: {result.exception!r}"
    )
    assert offending_filename in result.output, result.output


class TestActivateMissionTypeMalformedYamlBoundary:
    """``charter activate mission-type <id>`` (activate.py, the finding's site 1)."""

    def test_fails_closed_not_raw_traceback(
        self, project_with_malformed_org_mission_type: Path
    ) -> None:
        result = runner.invoke(
            charter_app,
            [
                "activate",
                "--repo-root",
                str(project_with_malformed_org_mission_type),
                "mission-type",
                "software-dev",
            ],
        )
        _asserts_clean_exit_naming_file(result)


class TestCharterMissionTypeListMalformedYamlBoundary:
    """``charter mission-type list`` (charter/mission_type.py, the finding's site 2)."""

    def test_fails_closed_not_raw_traceback(
        self, project_with_malformed_org_mission_type: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(project_with_malformed_org_mission_type)
        result = runner.invoke(charter_app, ["mission-type", "list", "--json"])
        _asserts_clean_exit_naming_file(result)


class TestCharterMissionTypeListIncludeInactiveMalformedYamlBoundary:
    """``charter mission-type list --include-inactive`` -- sibling call site.

    Same ``resolve_layered_roster`` call, unguarded, found by this mission's
    own grep for every reachable call site.
    """

    def test_fails_closed_not_raw_traceback(
        self, project_with_malformed_org_mission_type: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(project_with_malformed_org_mission_type)
        result = runner.invoke(charter_app, ["mission-type", "list", "--include-inactive", "--json"])
        _asserts_clean_exit_naming_file(result)


class TestMissionTypeShowMalformedYamlBoundary:
    """``mission-type show <id>`` (mission_type.py) -- sibling call site."""

    def test_fails_closed_not_raw_traceback(
        self, project_with_malformed_org_mission_type: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(project_with_malformed_org_mission_type)
        result = runner.invoke(mission_type_app, ["show", "software-dev"])
        _asserts_clean_exit_naming_file(result)


class TestCharterListAllMalformedYamlBoundary:
    """``charter list --all --show-available`` (charter/list_cmd.py) -- sibling.

    Reaches ``scan_mission_types_dir`` via
    ``ActiveCharterManager.list_available_detailed``'s dedicated mission-type
    branch (PR-CONTRACT-002), not ``resolve_layered_roster`` -- the same
    underlying loud-fail primitive, a different direct caller.
    """

    def test_fails_closed_not_raw_traceback(
        self, project_with_malformed_org_mission_type: Path
    ) -> None:
        result = runner.invoke(
            charter_app,
            [
                "list",
                "--repo-root",
                str(project_with_malformed_org_mission_type),
                "--all",
                "--show-available",
            ],
        )
        _asserts_clean_exit_naming_file(result)
