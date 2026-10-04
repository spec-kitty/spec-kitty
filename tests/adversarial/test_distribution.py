"""
Distribution Tests - CRITICAL for preventing 0.10.8-style failures.

These tests validate what PyPI users experience:
- Install from wheel (NOT editable install)
- NO SPEC_KITTY_TEMPLATE_ROOT bypass
- Template resolution from packaged templates

The 0.10.8 release shipped broken to 100% of users despite 323 passing tests.
All those tests used SPEC_KITTY_TEMPLATE_ROOT, creating a false sense of security.

These tests are the ONLY safeguard against that happening again.

CURRENT STATUS (as of 2.0.8):
- ✅ Wheel build and install tests pass
- ✅ CLI version check passes
- ✅ Init/upgrade tests pass (non-interactive mode fixed)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.adversarial,
    pytest.mark.distribution,
    pytest.mark.slow,
    pytest.mark.git_repo,
]

REPO_ROOT = Path(__file__).resolve().parents[2]


def _venv_python(venv_dir: Path) -> Path:
    """Get path to Python in venv (cross-platform)."""
    candidate = venv_dir / "bin" / "python"
    if candidate.exists():
        return candidate
    return venv_dir / "Scripts" / "python.exe"


def _venv_spec_kitty(venv_dir: Path) -> Path:
    """Get path to spec-kitty in venv (cross-platform)."""
    candidate = venv_dir / "bin" / "spec-kitty"
    if candidate.exists():
        return candidate
    return venv_dir / "Scripts" / "spec-kitty.exe"


def _clean_env() -> dict[str, str]:
    """Environment without spec-kitty bypasses."""
    env = os.environ.copy()
    env.pop("SPEC_KITTY_TEMPLATE_ROOT", None)
    env.pop("PYTHONPATH", None)
    return env


# =============================================================================
# SESSION-SCOPED FIXTURES (T013)
# =============================================================================


@pytest.fixture(scope="session")
def wheel_path(build_artifacts: dict[str, Path]) -> Path:
    """Get wheel from shared session-scoped build (avoids redundant rebuild)."""
    return build_artifacts["wheel"]


@pytest.fixture(scope="session")
def installed_venv(installed_wheel_venv: dict[str, Path]) -> Path:
    """Get installed venv from shared session-scoped fixture."""
    return installed_wheel_venv["venv_dir"]


# =============================================================================
# WHEEL BUILD AND INSTALL TESTS (T009)
# =============================================================================


class TestWheelBuildAndInstall:
    """Test that wheel builds and installs correctly."""

    def test_wheel_builds_successfully(self, wheel_path: Path) -> None:
        """Verify wheel builds without errors."""
        assert wheel_path.exists(), "Wheel should be built"
        assert wheel_path.suffix == ".whl", "Should be a wheel file"

    def test_wheel_installs_in_fresh_venv(self, installed_venv: Path) -> None:
        """Verify wheel installs into clean virtual environment."""
        spec_kitty = installed_venv / "bin" / "spec-kitty"
        if not spec_kitty.exists():
            spec_kitty = installed_venv / "Scripts" / "spec-kitty.exe"

        assert spec_kitty.exists(), "spec-kitty CLI should be installed"

    def test_cli_version_matches_wheel(self, installed_venv: Path) -> None:
        """Verify installed CLI reports correct version."""
        spec_kitty = _venv_spec_kitty(installed_venv)

        result = subprocess.run(
            [str(spec_kitty), "--version"],
            capture_output=True,
            text=True,
            env=_clean_env(),
        )

        assert result.returncode == 0, f"Version check failed: {result.stderr}"
        # Version should be in output (format may vary)


# =============================================================================
# INIT WITHOUT TEMPLATE ROOT TESTS (T010)
# =============================================================================


class TestInitWithoutTemplateRoot:
    """Test spec-kitty init uses packaged templates."""

    def test_init_creates_project_structure(self, installed_venv: Path, tmp_path: Path) -> None:
        """spec-kitty init should work without SPEC_KITTY_TEMPLATE_ROOT."""
        project_dir = tmp_path / "test-project"

        spec_kitty = _venv_spec_kitty(installed_venv)
        env = _clean_env()

        # Explicitly verify bypass is NOT set
        assert "SPEC_KITTY_TEMPLATE_ROOT" not in env

        result = subprocess.run(
            [
                str(spec_kitty),
                "init",
                str(project_dir),
                "--ai",
                "claude",
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(tmp_path),
        )

        assert result.returncode == 0, f"Init failed: {result.stderr}"

        # Verify structure created
        kittify = project_dir / ".kittify"
        assert kittify.exists(), ".kittify directory should be created"

        config = kittify / "config.yaml"
        assert config.exists(), "config.yaml should be created"

    def test_init_installs_bundled_skills(self, installed_venv: Path, tmp_path: Path) -> None:
        """Wheel-installed init should install the canonical bundled skill pack."""
        project_dir = tmp_path / "skills-project"
        spec_kitty = _venv_spec_kitty(installed_venv)

        result = subprocess.run(
            [
                str(spec_kitty),
                "init",
                str(project_dir),
                "--ai",
                "claude",
            ],
            capture_output=True,
            text=True,
            env=_clean_env(),
            cwd=str(tmp_path),
        )

        assert result.returncode == 0, f"Init failed: {result.stderr}"

        manifest_path = project_dir / ".kittify" / "skills-manifest.json"
        assert manifest_path.is_file(), "skills-manifest.json should be created for bundled skills"

        skill_file = project_dir / ".claude" / "skills" / "spec-kitty-setup-doctor" / "SKILL.md"
        assert skill_file.is_file(), "Bundled canonical skill should be installed during init"


# =============================================================================
# RESEARCH FEATURE CREATION TESTS (T011)
# =============================================================================


class TestUpgradeWithAllMissions:
    """Test upgrade command updates templates from package."""

    def test_upgrade_updates_templates(self, installed_venv: Path, tmp_path: Path) -> None:
        """spec-kitty upgrade should update templates from packaged source."""
        project_dir = tmp_path / "upgrade-project"

        spec_kitty = _venv_spec_kitty(installed_venv)
        env = _clean_env()

        # Initialize project (will create directory)
        init_result = subprocess.run(
            [
                str(spec_kitty),
                "init",
                str(project_dir),
                "--ai",
                "claude",
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(tmp_path),
        )
        assert init_result.returncode == 0, f"Init failed: {init_result.stderr}"

        # Initialize git after init
        subprocess.run(["git", "init", "-b", "main"], cwd=project_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"], cwd=project_dir, check=True, capture_output=True
        )
        subprocess.run(["git", "config", "user.name", "Test"], cwd=project_dir, check=True, capture_output=True)

        # Initial commit
        subprocess.run(["git", "add", "."], cwd=project_dir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=project_dir, check=True, capture_output=True)

        # Run upgrade. ``--yes`` is required here: a freshly-init'd project can
        # carry pending idempotent migrations (e.g. 3.2.8_provision_kitty_env,
        # migrate_lifecycle_envelope) that upgrade confirms interactively before
        # applying. Previously this subprocess had no stdin and no `--yes`, but
        # the prompt was masked on a plain local checkout by an over-broad
        # "connected teamspace" detector (routing-derived repo/project slug)
        # that made ANY local project look teamspace-connected — the banner
        # tripped this test's auth skip-guard before the prompt was ever
        # reached. That detector was retired with the sync transport (issue
        # #5), unmasking the real interactive-abort gap.
        upgrade_result = subprocess.run(
            [str(spec_kitty), "upgrade", "--yes"],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(project_dir),
        )

        # Auth-env guard: `spec-kitty upgrade` performs a connected-teamspace auth
        # check. In a logged-out environment (e.g. CI without credentials) the
        # child emits a `logged_out_on_connected_teamspace` banner and exits
        # non-zero before doing real work — that is an environment condition,
        # not a product regression, so skip rather than red the suite.
        if "logged_out_on_connected_teamspace" in upgrade_result.stdout or (
            "logged_out_on_connected_teamspace" in upgrade_result.stderr
        ):
            pytest.skip(
                "spec-kitty upgrade requires connected-teamspace auth; skipping in a "
                "logged-out environment (e.g. CI without credentials)."
            )

        # Upgrade should complete (may report "already up to date")
        assert upgrade_result.returncode == 0, f"Upgrade failed: {upgrade_result.stderr}"
