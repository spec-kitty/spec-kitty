"""Wheel packaging smoke tests for doctrine distribution assets."""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

import pytest

pytestmark = [pytest.mark.slow, pytest.mark.non_sandbox, pytest.mark.corpus]  # non_sandbox: builds and installs a wheel (>30s)
# These tests reuse the session-scoped build_artifacts and installed_wheel_venv
# fixtures from tests/cross_cutting/packaging/conftest.py.
# They are discovered via conftest.py fixture resolution because pytest
# collects fixtures from all conftest.py files in the test tree.

REPO_ROOT = Path(__file__).resolve().parents[2]
# Pre-move built-in home: before mission relocate-builtin-doctrine-packs-01KYT87F the
# shipped pack content rode inside the ``doctrine`` package at
# ``doctrine/<kind>/built-in/``. The move relocated it to the top-level ``packs/``
# tree (wheel path ``packs/built-in/<kind>/``), so that old in-package home must now
# be ABSENT from the wheel — the inverse of the pre-move assertion, which required
# the built-in assets to ship under ``doctrine/``. Mission
# charter-code-topology-01M152G1 subsequently relocated the ``doctrine`` package
# itself to ``charter/offering/`` in the wheel, so the (still-absent) legacy path
# is checked at its current package prefix.
LEGACY_BUILTIN_DIR = "charter/offering/" + "agent_profiles" + "/built-in/"


@pytest.fixture
def wheel_path(build_artifacts: dict[str, Path]) -> Path:
    """Get wheel path from shared session fixture."""
    return build_artifacts["wheel"]


def test_wheel_contains_doctrine_package_data(wheel_path: Path) -> None:
    """Built wheel should include doctrine code and shipped YAML assets."""
    with zipfile.ZipFile(wheel_path, "r") as zf:
        names = set(zf.namelist())

    required_prefixes = [
        # Code + schemas live under the relocated ``charter.offering`` package
        # (mission charter-code-topology-01M152G1; formerly the top-level
        # ``doctrine`` package).
        "charter/offering/agent_profiles/profile.py",
        "charter/offering/schemas/agent-profile.schema.yaml",
        "charter/offering/schemas/directive.schema.yaml",
        # Relocated built-in pack content ships under the flattened top-level
        # ``packs/built-in/<kind>/`` tree (mission relocate-builtin-doctrine-packs-01KYT87F).
        # NOTE: the inner ``built-in`` segment of the pre-move layout is dropped.
        "packs/built-in/agent_profiles/implementer-ivan.agent.yaml",
        "packs/built-in/directives/003-decision-documentation-requirement.directive.yaml",
    ]
    missing = [path for path in required_prefixes if path not in names]
    assert not missing, f"Missing doctrine wheel assets: {missing}"
    legacy_paths = sorted(name for name in names if name.startswith(LEGACY_BUILTIN_DIR))
    assert legacy_paths == [], f"Pre-move {LEGACY_BUILTIN_DIR} wheel assets should be absent: {legacy_paths}"


def test_wheel_install_imports_doctrine_and_lists_profiles(
    installed_wheel_venv: dict[str, Path],
) -> None:
    """Installed wheel should expose doctrine imports and shipped profiles."""
    python = installed_wheel_venv["python"]

    check = subprocess.run(
        [
            str(python),
            "-c",
            (
                "from charter.offering.agent_profiles import AgentProfileRepository; "
                "repo = AgentProfileRepository(project_dir=None); "
                "profiles = repo.list_all(); "
                "assert any(p.profile_id == 'implementer-ivan' for p in profiles); "
                "print(len(profiles))"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert check.returncode == 0, check.stderr
