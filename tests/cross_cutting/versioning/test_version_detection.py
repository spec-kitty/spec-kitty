"""Tests for version detection and reporting.

Validates that spec-kitty version is read dynamically from package metadata
instead of being hardcoded, ensuring --version always shows correct version.

Problem: In v0.5.0, __version__ was hardcoded to "0.4.13" in __init__.py,
causing spec-kitty --version to report incorrect version even though package
metadata showed 0.5.0.

Solution: Use importlib.metadata.version() to read from package metadata.

These tests detect this problem and validate the fix.
"""

import os
import pytest
import subprocess
from pathlib import Path
from packaging.version import InvalidVersion, Version

from tests.test_isolation_helpers import get_installed_version, get_venv_python


pytestmark = [pytest.mark.integration]

#: Unreadable package metadata is always a defect (a declared-dependency /
#: stale-venv condition, FR-004) — never a platform limitation — so every
#: site that used to skip on it now fails loudly with this shared message.
_PKG_METADATA_UNAVAILABLE_MSG = "Package metadata not available"


def run_venv_python(code: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [str(get_venv_python()), "-c", code],
        capture_output=True,
        text=True,
        env=env,
    )


def get_venv_module_version() -> str:
    result = run_venv_python("import specify_cli; print(specify_cli.__version__)")
    if result.returncode != 0:
        pytest.fail(f"Could not import module version: {result.stderr}")
    return result.stdout.strip()


def run_cli_version() -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")
    return subprocess.run(
        [str(get_venv_python()), "-m", "specify_cli.__init__", "--version"],
        capture_output=True,
        text=True,
        env=env,
    )


def get_venv_metadata_version() -> str:
    """Get the spec-kitty-cli version from the test venv's metadata."""
    metadata_version = get_installed_version()
    if metadata_version is None:
        raise RuntimeError("Could not read package metadata from test venv")
    return metadata_version


class TestVersionReading:
    """Test that version is read from package metadata, not hardcoded."""

    def test_version_matches_package_metadata(self):
        """Verify __version__ matches package metadata version."""
        module_version = get_venv_module_version()

        # Get version from package metadata
        try:
            metadata_version = get_venv_metadata_version()
        except Exception as exc:
            pytest.fail(f"Could not read package metadata: {exc}")

        # Versions should match
        assert module_version == metadata_version, (
            f"Module __version__ ({module_version}) should match package metadata ({metadata_version})"
        )

    def test_cli_version_matches_package_metadata(self):
        """Verify spec-kitty --version command shows package metadata version."""
        # Get version from venv's package metadata (not test runner's)
        try:
            metadata_version = get_venv_metadata_version()
        except Exception as exc:
            pytest.fail(f"Could not read package metadata: {exc}")

        # Run CLI command
        result = run_cli_version()
        assert result.returncode == 0, f"--version failed: {result.stderr}"
        output = result.stdout + result.stderr

        # Should show the package metadata version
        assert metadata_version in output, f"CLI should show version {metadata_version}, got: {output}"

    def test_no_hardcoded_version_in_init(self):
        """Verify __init__.py doesn't have hardcoded version string."""
        # Find the __init__.py file
        try:
            import specify_cli

            init_file = Path(specify_cli.__file__)
        except Exception as exc:
            pytest.fail(f"Could not locate __init__.py: {exc}")

        init_content = init_file.read_text()

        # Should NOT have hardcoded version like __version__ = "0.4.13"
        # Should use version_utils or importlib.metadata
        assert (
            "version_utils" in init_content
            or "importlib.metadata" in init_content
            or "importlib_metadata" in init_content
        ), "__init__.py should use version_utils.get_version() or importlib.metadata to read version dynamically"

        # Should not have pattern like __version__ = "0.x.x"
        import re

        hardcoded_pattern = re.compile(r'__version__\s*=\s*["\']0\.\d+\.\d+["\']')
        match = hardcoded_pattern.search(init_content)
        assert match is None, f"Found hardcoded version in __init__.py: {match.group(0) if match else 'N/A'}"

    def test_version_format(self):
        """Verify version is parseable as a valid PEP 440 version."""
        module_version = get_venv_module_version()

        try:
            parsed = Version(module_version)
        except InvalidVersion as exc:  # pragma: no cover - explicit failure path
            pytest.fail(f"Version '{module_version}' is not a valid PEP 440 version: {exc}")

        assert len(parsed.release) >= 3, f"Version '{module_version}' should include major.minor.patch release segments"


class TestVersionConsistency:
    """Test version consistency across different access methods."""

    def test_version_via_module_import(self):
        """Test version accessible via module import."""
        module_version = get_venv_module_version()
        assert module_version, "Should have __version__ attribute"
        assert isinstance(module_version, str), "__version__ should be string"

    def test_version_via_metadata(self):
        """Test version accessible via package metadata."""
        try:
            pkg_version = get_venv_metadata_version()
        except Exception as exc:
            pytest.fail(f"{_PKG_METADATA_UNAVAILABLE_MSG}: {exc}")
        assert pkg_version, "Should get version from metadata"
        assert isinstance(pkg_version, str), "Metadata version should be string"

    def test_version_via_cli_command(self):
        """Test version accessible via CLI --version flag."""
        result = run_cli_version()
        assert result.returncode == 0, f"--version failed: {result.stderr}"
        output = result.stdout + result.stderr
        assert "version" in output.lower(), "Output should mention version"

        # Should have a version number
        import re

        version_pattern = re.compile(r"\d+\.\d+\.\d+")
        assert version_pattern.search(output), f"Output should contain version number, got: {output}"

    def test_all_version_methods_agree(self):
        """Verify all version access methods return the same value."""
        # Method 1: Module import
        module_version = get_venv_module_version()

        # Method 2: Package metadata
        try:
            metadata_version = get_venv_metadata_version()
        except Exception:
            pytest.fail(_PKG_METADATA_UNAVAILABLE_MSG)

        # Method 3: CLI command
        result = run_cli_version()
        assert result.returncode == 0, f"--version failed: {result.stderr}"
        cli_output = result.stdout + result.stderr

        # All should agree
        assert module_version == metadata_version, (
            f"Module version ({module_version}) should match metadata ({metadata_version})"
        )

        assert metadata_version in cli_output, (
            f"CLI should show metadata version ({metadata_version}), got: {cli_output}"
        )


class TestEdgeCases:
    """Test edge cases for version detection."""

    def test_version_in_development_install(self):
        """Verify version works in development/editable installs."""
        # This test validates that even in -e installs, we get a version
        module_version = get_venv_module_version()

        # In dev install, might show "X.Y.Z-dev" as fallback
        assert module_version, "Should have version even in dev install"
        assert len(module_version) > 0, "Version should not be empty"

        # Should not be "unknown" or similar
        assert module_version.lower() != "unknown", "Version should not be 'unknown'"

    def test_version_does_not_crash_on_import(self):
        """Verify importing specify_cli doesn't crash when getting version."""
        result = run_venv_python("import specify_cli; print(specify_cli.__version__)")
        assert result.returncode == 0, f"Importing version should not crash: {result.stderr}"
        assert result.stdout.strip(), "Version should be available"

    def test_cli_version_flag_exists(self):
        """Verify --version flag exists and works."""
        result = run_cli_version()

        # Should not crash
        assert result.returncode == 0, f"--version should not crash, got exit code {result.returncode}"

        # Should produce output
        output = result.stdout + result.stderr
        assert len(output) > 0, "--version should produce output"


class TestVersionUpdateWorkflow:
    """Test that version updates work correctly."""

    def test_pyproject_toml_version_readable(self):
        """Verify pyproject.toml version can be read (for reference)."""
        # Find pyproject.toml
        try:
            import specify_cli

            package_root = Path(specify_cli.__file__).parent.parent.parent
            pyproject = package_root / "pyproject.toml"
        except Exception:
            pytest.fail("Could not locate pyproject.toml")

        if not pyproject.exists():
            pytest.fail("pyproject.toml not found")

        content = pyproject.read_text()

        # Should have a parseable version field
        import re

        version_pattern = re.compile(r'version\s*=\s*"([^"]+)"')
        match = version_pattern.search(content)

        if match:
            pyproject_version = match.group(1)
            try:
                parsed = Version(pyproject_version)
            except InvalidVersion as exc:  # pragma: no cover - explicit failure path
                pytest.fail(f"pyproject.toml version '{pyproject_version}' is invalid: {exc}")
            assert len(parsed.release) >= 3, (
                f"pyproject.toml version '{pyproject_version}' should include major.minor.patch"
            )

    def test_version_not_imported_from_pyproject(self):
        """Verify version prioritizes importlib.metadata over pyproject.toml."""
        # Reading from pyproject.toml should be FALLBACK only, not primary
        # Should try importlib.metadata first
        import specify_cli

        init_file = Path(specify_cli.__file__)
        init_content = init_file.read_text()

        # Should delegate to version_utils
        assert "version_utils" in init_content or "importlib.metadata" in init_content, (
            "Should use version_utils.get_version() or importlib.metadata"
        )

        # __init__.py should NOT parse pyproject.toml directly
        assert "pyproject.toml" not in init_content, "Should not parse pyproject.toml directly in __init__.py"

        # Verify version_utils uses importlib.metadata as primary method
        from specify_cli import version_utils

        utils_file = Path(version_utils.__file__)
        utils_content = utils_file.read_text()

        assert "importlib.metadata" in utils_content, "version_utils should try importlib.metadata first"

        # pyproject.toml is acceptable as FALLBACK in version_utils
        assert "pyproject.toml" in utils_content, "version_utils should have pyproject.toml fallback"


class TestRegressionPrevention:
    """Tests to prevent version regression bugs."""

    def test_version_mismatch_regression(self):
        """Detect if version becomes hardcoded again (regression)."""
        module_version = get_venv_module_version()

        try:
            metadata_version = get_venv_metadata_version()
        except Exception:
            pytest.fail(_PKG_METADATA_UNAVAILABLE_MSG)

        # This is the regression test - if someone hardcodes the version again,
        # this test will fail because module version won't match metadata
        mismatch = module_version != metadata_version

        if mismatch:
            pytest.fail(
                f"VERSION MISMATCH DETECTED - Possible hardcoded version regression!\n"
                f"Module __version__: {module_version}\n"
                f"Package metadata: {metadata_version}\n"
                f"The version should be read from package metadata, not hardcoded.\n"
                f"Check src/specify_cli/__init__.py for hardcoded version string."
            )

    def test_cli_reports_current_version_not_old(self):
        """Detect if CLI reports old version (like 0.4.13 when package is 0.5.0)."""
        try:
            metadata_version = get_venv_metadata_version()
        except Exception:
            pytest.fail(_PKG_METADATA_UNAVAILABLE_MSG)

        result = run_cli_version()
        assert result.returncode == 0, f"--version failed: {result.stderr}"
        output = result.stdout + result.stderr

        # CLI should show current version, not old version
        assert metadata_version in output, f"CLI should show current version {metadata_version}, got: {output}"

        # Specifically check it doesn't show old versions
        old_versions = ["0.4.13", "0.4.12", "0.4.11"]
        for old_ver in old_versions:
            if metadata_version != old_ver:  # Only check if we're not actually that version
                assert old_ver not in output, f"CLI should not show old version {old_ver}, got: {output}"


class TestPackageMetadataIntegrity:
    """Test package metadata is correct."""

    def test_package_metadata_accessible(self):
        """Verify package metadata can be accessed."""
        try:
            pkg_version = get_venv_metadata_version()
            result = run_venv_python(
                "from importlib.metadata import metadata; m = metadata('spec-kitty-cli'); print(m.get('Name'))"
            )
        except Exception as exc:
            pytest.fail(f"Package metadata should be accessible: {exc}")
        pkg_name = result.stdout.strip()

        assert pkg_version, "Should have version in metadata"
        assert pkg_name == "spec-kitty-cli", "Should have metadata"

    def test_package_name_is_spec_kitty_cli(self):
        """Verify package is installed as spec-kitty-cli."""
        try:
            # This should not raise - package should be named spec-kitty-cli
            get_venv_metadata_version()
        except Exception as exc:
            pytest.fail(f"Package should be named 'spec-kitty-cli': {exc}")

    def test_version_is_valid_pep440(self):
        """Verify package metadata version is valid PEP 440."""
        try:
            pkg_version = get_venv_metadata_version()
        except Exception:
            pytest.fail(_PKG_METADATA_UNAVAILABLE_MSG)

        try:
            parsed = Version(pkg_version)
        except InvalidVersion as exc:  # pragma: no cover - explicit failure path
            pytest.fail(f"Version '{pkg_version}' is not valid PEP 440: {exc}")

        assert len(parsed.release) >= 3, f"Version '{pkg_version}' should include major.minor.patch release segments"
