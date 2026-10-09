"""Tests for specify_cli.runtime.doctor -- global runtime health checks.

Covers:
- T029: Global runtime health check functions
- T031: Missing ~/.kittify/ detected (1A-11)
- T032: version.lock mismatch detected (1A-12)
- T033: Corrupted mission directory detected (1A-13)
- T034: Stale legacy assets counted (1A-10)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.runtime.doctor import (
    DoctorCheck,
    check_global_runtime_exists,
    check_mission_integrity,
    check_stale_legacy_assets,
    check_version_lock,
    run_global_checks,
    MANAGED_MISSION_DIRS,
)


# ---------------------------------------------------------------------------
# T029: DoctorCheck dataclass
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

class TestDoctorCheck:
    """DoctorCheck dataclass holds name, passed, message, severity."""

    def test_dataclass_fields(self) -> None:
        check = DoctorCheck(
            name="test_check",
            passed=True,
            message="All good",
            severity="info",
        )
        assert check.name == "test_check"
        assert check.passed is True
        assert check.message == "All good"
        assert check.severity == "info"

    def test_failed_check(self) -> None:
        check = DoctorCheck(
            name="failing", passed=False, message="Bad", severity="error"
        )
        assert check.passed is False
        assert check.severity == "error"


# ---------------------------------------------------------------------------
# T031: Missing ~/.kittify/ detected (1A-11)
# ---------------------------------------------------------------------------


class TestCheckGlobalRuntimeExists:
    """Detect missing ~/.kittify/ directory."""

    def test_detects_missing_global_runtime(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing ~/.kittify/ is detected and reported (1A-11)."""
        nonexistent = tmp_path / "nonexistent"
        monkeypatch.setenv("SPEC_KITTY_HOME", str(nonexistent))
        check = check_global_runtime_exists()
        assert not check.passed
        assert check.severity == "error"
        assert "Missing global runtime" in check.message

    def test_passes_when_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Existing ~/.kittify/ passes the check."""
        home = tmp_path / "kittify"
        home.mkdir()
        monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
        check = check_global_runtime_exists()
        assert check.passed
        assert check.severity == "info"
        assert "exists" in check.message

    def test_check_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Check has the expected name."""
        monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "nope"))
        check = check_global_runtime_exists()
        assert check.name == "global_runtime_exists"


# ---------------------------------------------------------------------------
# T032: version.lock mismatch detected (1A-12)
# ---------------------------------------------------------------------------


class TestCheckVersionLock:
    """Detect version.lock mismatch with CLI version."""

    def test_detects_version_mismatch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """version.lock mismatch is detected (1A-12)."""
        home = tmp_path / "kittify"
        (home / "cache").mkdir(parents=True)
        (home / "cache" / "version.lock").write_text("0.0.0")
        monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
        check = check_version_lock()
        assert not check.passed
        assert check.severity == "warning"
        assert "Version mismatch" in check.message
        assert "lock=0.0.0" in check.message

    def test_detects_missing_version_lock(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing version.lock is detected as warning."""
        home = tmp_path / "kittify"
        home.mkdir()
        monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
        check = check_version_lock()
        assert not check.passed
        assert check.severity == "warning"
        assert "version.lock missing" in check.message

    def test_passes_when_version_matches(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Matching version.lock passes the check."""
        from specify_cli import __version__

        home = tmp_path / "kittify"
        (home / "cache").mkdir(parents=True)
        (home / "cache" / "version.lock").write_text(__version__)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
        check = check_version_lock()
        assert check.passed
        assert check.severity == "info"
        assert "matches CLI" in check.message

    def test_check_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Check has the expected name."""
        home = tmp_path / "kittify"
        home.mkdir()
        monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
        check = check_version_lock()
        assert check.name == "version_lock"


# ---------------------------------------------------------------------------
# T033: Corrupted mission directory detected (1A-13)
# ---------------------------------------------------------------------------


class TestCheckMissionIntegrity:
    """Detect corrupted/missing managed mission directories."""

    def test_detects_missing_mission_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Corrupted: managed mission directory missing (1A-13)."""
        home = tmp_path / "kittify"
        # Create some but not all managed dirs
        (home / "missions" / "software-dev").mkdir(parents=True)
        # missions/research and missions/documentation are missing
        monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
        check = check_mission_integrity()
        assert not check.passed
        assert check.severity == "error"
        assert "Missing" in check.message

    def test_passes_when_all_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All managed mission directories present passes the check."""
        home = tmp_path / "kittify"
        for managed_dir in MANAGED_MISSION_DIRS:
            (home / managed_dir).mkdir(parents=True)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
        check = check_mission_integrity()
        assert check.passed
        assert check.severity == "info"
        assert "mission dirs present" in check.message

    def test_detects_all_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All mission dirs missing reports all of them."""
        home = tmp_path / "kittify"
        home.mkdir()
        monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
        check = check_mission_integrity()
        assert not check.passed
        for managed_dir in MANAGED_MISSION_DIRS:
            assert managed_dir in check.message

    def test_check_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Check has the expected name."""
        home = tmp_path / "kittify"
        home.mkdir()
        monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
        check = check_mission_integrity()
        assert check.name == "mission_integrity"


# ---------------------------------------------------------------------------
# T034: Stale legacy assets counted (1A-10)
# ---------------------------------------------------------------------------


class TestCheckStaleLegacyAssets:
    """Count stale legacy shared assets in project .kittify/."""

    def test_counts_stale_legacy_assets(self, tmp_path: Path) -> None:
        """Stale legacy assets counted with migration recommendation (1A-10)."""
        project = tmp_path / "project"
        kittify = project / ".kittify"
        (kittify / "templates").mkdir(parents=True)
        (kittify / "templates" / "spec.md").write_text("stale")
        (kittify / "templates" / "plan.md").write_text("stale")

        check = check_stale_legacy_assets(project)
        assert not check.passed
        assert check.severity == "warning"
        assert "2 shared assets" in check.message
        assert "spec-kitty migrate" in check.message

    def test_no_kittify_directory(self, tmp_path: Path) -> None:
        """No .kittify/ directory passes the check."""
        project = tmp_path / "project"
        project.mkdir()
        check = check_stale_legacy_assets(project)
        assert check.passed
        assert check.severity == "info"
        assert "No .kittify/ directory" in check.message

    def test_no_stale_assets(self, tmp_path: Path) -> None:
        """Empty .kittify/ with no shared dirs/files passes."""
        project = tmp_path / "project"
        kittify = project / ".kittify"
        kittify.mkdir(parents=True)
        # config.yaml is not a shared asset
        (kittify / "config.yaml").write_text("agents:\n  available: []\n")

        check = check_stale_legacy_assets(project)
        assert check.passed
        assert check.severity == "info"
        assert "No stale shared assets" in check.message

    def test_counts_shared_files(self, tmp_path: Path) -> None:
        """AGENTS.md is counted as a shared file."""
        project = tmp_path / "project"
        kittify = project / ".kittify"
        kittify.mkdir(parents=True)
        (kittify / "AGENTS.md").write_text("# Agents")

        check = check_stale_legacy_assets(project)
        assert not check.passed
        assert "1 shared assets" in check.message

    def test_counts_multiple_shared_dirs(self, tmp_path: Path) -> None:
        """Multiple shared directories counted correctly."""
        project = tmp_path / "project"
        kittify = project / ".kittify"
        (kittify / "templates").mkdir(parents=True)
        (kittify / "templates" / "spec.md").write_text("stale")
        (kittify / "missions" / "software-dev").mkdir(parents=True)
        (kittify / "missions" / "software-dev" / "mission.yaml").write_text(
            "stale"
        )
        (kittify / "scripts").mkdir(parents=True)
        (kittify / "scripts" / "build.sh").write_text("stale")

        check = check_stale_legacy_assets(project)
        assert not check.passed
        assert "3 shared assets" in check.message

    def test_check_name(self, tmp_path: Path) -> None:
        """Check has the expected name."""
        project = tmp_path / "project"
        project.mkdir()
        check = check_stale_legacy_assets(project)
        assert check.name == "stale_legacy"


# ---------------------------------------------------------------------------
# T029: run_global_checks() aggregation
# ---------------------------------------------------------------------------


class TestRunGlobalChecks:
    """run_global_checks() aggregates all checks."""

    def test_returns_list_of_checks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Returns a list of DoctorCheck objects."""
        monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "kittify"))
        checks = run_global_checks()
        assert isinstance(checks, list)
        assert all(isinstance(c, DoctorCheck) for c in checks)

    def test_includes_three_global_checks_without_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without project_dir, returns 3 global checks."""
        monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "kittify"))
        checks = run_global_checks()
        assert len(checks) == 3
        names = {c.name for c in checks}
        assert names == {
            "global_runtime_exists",
            "version_lock",
            "mission_integrity",
        }

    def test_includes_legacy_check_with_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With project_dir, returns checks including stale_legacy and governance."""
        monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "kittify"))
        project = tmp_path / "project"
        project.mkdir()
        checks = run_global_checks(project_dir=project)
        assert len(checks) == 5
        names = {c.name for c in checks}
        assert "stale_legacy" in names
        assert "governance_resolution" in names

    def test_all_pass_with_healthy_setup(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All checks pass with a properly configured runtime."""
        import subprocess

        from specify_cli import __version__

        home = tmp_path / "kittify"
        for managed_dir in MANAGED_MISSION_DIRS:
            (home / managed_dir).mkdir(parents=True)
        (home / "cache").mkdir(parents=True)
        (home / "cache" / "version.lock").write_text(__version__)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(home))

        project = tmp_path / "project"
        project.mkdir()
        # check_governance_resolution → resolve_governance → ensure_charter_bundle_fresh
        # (PR #634) calls `git rev-parse --git-common-dir`, which requires a real git
        # repo at project_dir. Initialise one so the doctor happy-path check has all
        # its preconditions satisfied.
        subprocess.run(["git", "init", "-q"], cwd=project, check=True)

        checks = run_global_checks(project_dir=project)
        assert all(c.passed for c in checks)


# ---------------------------------------------------------------------------
# #4836: the template-fallback hint names the real charter.yaml key
# ---------------------------------------------------------------------------


def test_template_fallback_hint_names_the_real_charter_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The hint used to say ``charter.offering.template_set`` (a module path, not a key)."""
    from types import SimpleNamespace

    from specify_cli.runtime import doctor

    resolution = SimpleNamespace(template_set="software-dev-default", metadata={"template_set_source": "fallback"})
    monkeypatch.setattr(doctor, "resolve_project_governance", lambda _project_dir: resolution)

    check = doctor.check_governance_resolution(tmp_path)

    assert check.passed
    assert "Set governance.charter.template_set in .kittify/charter/charter.yaml" in check.message
    assert "charter.offering" not in check.message
