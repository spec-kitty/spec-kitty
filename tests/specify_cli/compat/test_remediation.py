"""Tests for RemediationCommand, plan_remediation(), and build_upgrade_hint() parity.

T017 / SC-003: snapshot-parity tests asserting that the WP03 reimplementation
of ``build_upgrade_hint()`` (now routing through ``plan_remediation()``)
produces IDENTICAL output to the pre-migration static table for every
:class:`InstallMethod`.

These tests are the regression guard for WP04 and WP05.

Covers:
- RemediationCommand.render() for posix and windows.
- CHK028 validation: metacharacters and over-length commands are rejected.
- plan_remediation() for every install method and both intents.
- Snapshot parity: build_upgrade_hint() output unchanged after reimplementation.
- Edge cases: UV_TOOL with custom tool_dir + python, target_version, purity.
- PowerShell quoting helper.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from unittest import mock

import pytest

from kernel.site_urls import INSTALL_AND_UPGRADE_URL
from specify_cli.compat._detect.install_method import InstallMethod
from specify_cli.compat._detect.runtime import (
    InstalledCliRuntime,
    PackageSource,
    UvRequirement,
)
from specify_cli.compat.remediation import (
    RemediationCommand,
    RemediationIntent,
    _manual_note,
    _powershell_quote,
    plan_remediation,
)
from specify_cli.compat.upgrade_hint import build_upgrade_hint

pytestmark = [pytest.mark.fast]

# ---------------------------------------------------------------------------
# Runtime factories
# ---------------------------------------------------------------------------

_SAFE_METHODS = frozenset({
    InstallMethod.UV_TOOL,
    InstallMethod.PIPX,
    InstallMethod.BREW,
    InstallMethod.PIP_USER,
    InstallMethod.PIP_SYSTEM,
})


def _make_runtime(
    install_method: InstallMethod,
    *,
    tool_dir: Path | None = None,
    is_default_tool_dir: bool | None = None,
    is_default_bin_dir: bool | None = None,
    python: str | None = None,
    platform: Literal["posix", "windows"] = "posix",
) -> InstalledCliRuntime:
    return InstalledCliRuntime(
        install_method=install_method,
        executable="/usr/local/bin/python3",
        receipt_path=None,
        tool_dir=tool_dir,
        bin_dir=None,
        is_default_tool_dir=is_default_tool_dir,
        is_default_bin_dir=is_default_bin_dir,
        python=python,
        requirements=(),
        package_source=PackageSource.UNKNOWN,
        platform=platform,
        safe_for_auto_upgrade=install_method in _SAFE_METHODS,
    )


def _uv_default_runtime(
    platform: Literal["posix", "windows"] = "posix",
) -> InstalledCliRuntime:
    """UV_TOOL runtime with default tool directory (no env var needed)."""
    return _make_runtime(
        InstallMethod.UV_TOOL,
        tool_dir=Path.home() / ".local/share/uv/tools",
        is_default_tool_dir=True,
        platform=platform,
    )


def _uv_custom_runtime(
    tool_dir: str = "/opt/tools",
    python: str | None = None,
    platform: Literal["posix", "windows"] = "posix",
) -> InstalledCliRuntime:
    """UV_TOOL runtime with a non-default tool directory."""
    return _make_runtime(
        InstallMethod.UV_TOOL,
        tool_dir=Path(tool_dir),
        is_default_tool_dir=False,
        python=python,
        platform=platform,
    )


# ---------------------------------------------------------------------------
# Provenance fixtures (FR-019 / SC-003 / issue #1358)
# ---------------------------------------------------------------------------


def _req(
    name: str = "spec-kitty-cli",
    *,
    specifier: str | None = None,
    directory: str | None = None,
    editable: str | None = None,
    path: str | None = None,
    git: str | None = None,
    url: str | None = None,
    is_supported: bool = True,
) -> UvRequirement:
    return UvRequirement(
        name=name,
        specifier=specifier,
        directory=directory,
        editable=editable,
        path=path,
        git=git,
        url=url,
        is_supported=is_supported,
    )


def _uv_runtime_with_reqs(
    requirements: tuple[UvRequirement, ...],
    *,
    tool_dir: Path | None = None,
    is_default_tool_dir: bool | None = True,
    bin_dir: Path | None = None,
    is_default_bin_dir: bool | None = None,
    python: str | None = None,
    receipt_path: Path | None = None,
    platform: Literal["posix", "windows"] = "posix",
) -> InstalledCliRuntime:
    """A UV_TOOL runtime carrying a provenance-rich requirements tuple."""
    return InstalledCliRuntime(
        install_method=InstallMethod.UV_TOOL,
        executable="/usr/local/bin/python3",
        receipt_path=receipt_path,
        tool_dir=tool_dir,
        bin_dir=bin_dir,
        is_default_tool_dir=is_default_tool_dir,
        is_default_bin_dir=is_default_bin_dir,
        python=python,
        requirements=requirements,
        package_source=PackageSource.PYPI_SPECIFIER,
        platform=platform,
        safe_for_auto_upgrade=True,
    )


_RECEIPT = Path("/t/uv-receipt.toml")


def _reinstall(runtime: InstalledCliRuntime) -> RemediationCommand:
    return plan_remediation(runtime, RemediationIntent.REINSTALL_WITH_TEST, None)


class TestUvToolReinstallProvenance:
    """REINSTALL_WITH_TEST must preserve install provenance, never re-pin to PyPI.

    Byte-for-byte ports of the pre-migration ``review`` provenance guards
    (issue #1358 acceptance criterion: provenance modeled for PyPI pins,
    directory, editable, path, git, url, and injected deps — nothing discarded).
    A regression here silently clobbers a source/editable/git install with the
    PyPI release.
    """

    def test_directory_source_preserved(self) -> None:
        cmd = _reinstall(_uv_runtime_with_reqs((_req(directory="/src"),), receipt_path=_RECEIPT))
        assert cmd.render("posix") == "uv tool install --force --with pytest /src"

    def test_editable_source_preserved(self) -> None:
        cmd = _reinstall(_uv_runtime_with_reqs((_req(editable="/src"),), receipt_path=_RECEIPT))
        assert cmd.render("posix") == (
            "uv tool install --force --with pytest --editable /src"
        )

    def test_path_source_preserved(self) -> None:
        cmd = _reinstall(_uv_runtime_with_reqs((_req(path="/src"),), receipt_path=_RECEIPT))
        assert cmd.render("posix") == "uv tool install --force --with pytest /src"

    def test_git_source_preserved(self) -> None:
        cmd = _reinstall(
            _uv_runtime_with_reqs((_req(git="file:///srv/spec-kitty"),), receipt_path=_RECEIPT)
        )
        assert cmd.render("posix") == (
            "uv tool install --force --with pytest spec-kitty-cli --from git+file:///srv/spec-kitty"
        )

    def test_url_source_preserved(self) -> None:
        cmd = _reinstall(
            _uv_runtime_with_reqs(
                (_req(url="https://example.test/pkg.whl"),), receipt_path=_RECEIPT
            )
        )
        assert cmd.render("posix") == (
            "uv tool install --force --with pytest https://example.test/pkg.whl"
        )

    def test_specifier_preserved(self) -> None:
        cmd = _reinstall(
            _uv_runtime_with_reqs((_req(specifier="==3.2.0rc25"),), receipt_path=_RECEIPT)
        )
        assert cmd.render("posix") == (
            "uv tool install --force --with pytest spec-kitty-cli==3.2.0rc25"
        )

    def test_bare_name_maps_to_pypi(self) -> None:
        cmd = _reinstall(_uv_runtime_with_reqs((_req(),), receipt_path=_RECEIPT))
        assert cmd.render("posix") == (
            "uv tool install --force --with pytest spec-kitty-cli"
        )

    def test_injected_dep_carried_through(self) -> None:
        cmd = _reinstall(
            _uv_runtime_with_reqs(
                (_req(git="file:///srv/spec-kitty"), _req(name="click")),
                receipt_path=_RECEIPT,
            )
        )
        assert cmd.render("posix") == (
            "uv tool install --force --with click --with pytest "
            "spec-kitty-cli --from git+file:///srv/spec-kitty"
        )

    def test_injected_editable_dep_stays_editable(self) -> None:
        cmd = _reinstall(
            _uv_runtime_with_reqs(
                (_req(specifier="==3.2.0rc25"), _req(name="extra-dep", editable="/extra")),
                receipt_path=_RECEIPT,
            )
        )
        assert cmd.render("posix") == (
            "uv tool install --force --with-editable /extra --with pytest "
            "spec-kitty-cli==3.2.0rc25"
        )

    def test_existing_pytest_not_duplicated(self) -> None:
        cmd = _reinstall(
            _uv_runtime_with_reqs(
                (_req(specifier="==3.2.0rc25"), _req(name="pytest")),
                receipt_path=_RECEIPT,
            )
        )
        assert cmd.render("posix") == (
            "uv tool install --force --with pytest spec-kitty-cli==3.2.0rc25"
        )

    def test_env_prefix_tool_and_bin_dir(self) -> None:
        cmd = _reinstall(
            _uv_runtime_with_reqs(
                (_req(specifier="==3.2.0rc25"),),
                tool_dir=Path("/opt/uv"),
                is_default_tool_dir=False,
                bin_dir=Path("/opt/bin"),
                is_default_bin_dir=False,
                receipt_path=_RECEIPT,
            )
        )
        assert cmd.render("posix") == (
            "UV_TOOL_DIR=/opt/uv UV_TOOL_BIN_DIR=/opt/bin uv tool install --force "
            "--with pytest spec-kitty-cli==3.2.0rc25"
        )

    def test_unsupported_main_requirement_is_conservative(self) -> None:
        cmd = _reinstall(
            _uv_runtime_with_reqs((_req(is_supported=False),), receipt_path=_RECEIPT)
        )
        assert cmd.intent == RemediationIntent.MANUAL_GUIDANCE
        assert cmd.argv is None
        assert "same uv tool source" in (cmd.note or "")

    def test_unsupported_injected_dep_is_conservative(self) -> None:
        cmd = _reinstall(
            _uv_runtime_with_reqs(
                (_req(specifier="==3.2.0rc25"), _req(name="extra-dep", is_supported=False)),
                receipt_path=_RECEIPT,
            )
        )
        assert cmd.intent == RemediationIntent.MANUAL_GUIDANCE
        assert "same uv tool source" in (cmd.note or "")

    def test_receipt_present_without_spec_kitty_entry_is_conservative(self) -> None:
        cmd = _reinstall(
            _uv_runtime_with_reqs((_req(name="other-tool"),), receipt_path=_RECEIPT)
        )
        assert cmd.intent == RemediationIntent.MANUAL_GUIDANCE
        assert "same uv tool source" in (cmd.note or "")


# ---------------------------------------------------------------------------
# SC-003 snapshot parity — plan_remediation() render() matches static table
# ---------------------------------------------------------------------------


class TestPlanRemediationRenderParity:
    """Verify plan_remediation() + render("posix") matches _HINT_TABLE values.

    These are the golden snapshots that WP04/WP05 must not break.
    """

    @pytest.mark.parametrize(
        "install_method,expected",
        [
            (InstallMethod.PIPX, "pipx upgrade spec-kitty-cli"),
            (InstallMethod.UV_TOOL, "uv tool install --force spec-kitty-cli"),
            (InstallMethod.PIP_USER, "pip install --user --upgrade spec-kitty-cli"),
            (InstallMethod.PIP_SYSTEM, "pip install --upgrade spec-kitty-cli"),
            (InstallMethod.BREW, "brew upgrade spec-kitty-cli"),
        ],
    )
    def test_upgrade_posix_matches_static_table(
        self,
        install_method: InstallMethod,
        expected: str,
    ) -> None:
        """plan_remediation + render('posix') == _HINT_TABLE[method].command."""
        runtime = (
            _uv_default_runtime()
            if install_method == InstallMethod.UV_TOOL
            else _make_runtime(install_method)
        )
        cmd = plan_remediation(runtime, RemediationIntent.UPGRADE, None)
        assert cmd.intent == RemediationIntent.UPGRADE
        assert cmd.argv is not None
        assert cmd.render("posix") == expected

    @pytest.mark.parametrize(
        "install_method",
        [InstallMethod.SOURCE, InstallMethod.UNKNOWN, InstallMethod.SYSTEM_PACKAGE],
    )
    def test_manual_guidance_methods_produce_no_argv(
        self, install_method: InstallMethod
    ) -> None:
        """SOURCE/UNKNOWN/SYSTEM_PACKAGE → MANUAL_GUIDANCE, argv=None."""
        runtime = _make_runtime(install_method)
        cmd = plan_remediation(runtime, RemediationIntent.UPGRADE, None)
        assert cmd.intent == RemediationIntent.MANUAL_GUIDANCE
        assert cmd.argv is None
        assert cmd.note is not None


# ---------------------------------------------------------------------------
# SC-003 snapshot parity — build_upgrade_hint() via mocked detect_runtime
# ---------------------------------------------------------------------------


class TestBuildUpgradeHintParity:
    """Snapshot parity: build_upgrade_hint() produces IDENTICAL output after WP03.

    detect_runtime() is mocked so that CI environments (SOURCE / UNKNOWN /
    PIP_SYSTEM) do not pollute the hint for methods other than the detected one.
    """

    @pytest.mark.parametrize(
        "install_method,expected_command",
        [
            (InstallMethod.PIPX, "pipx upgrade spec-kitty-cli"),
            (InstallMethod.UV_TOOL, "uv tool install --force spec-kitty-cli"),
            (InstallMethod.PIP_USER, "pip install --user --upgrade spec-kitty-cli"),
            (InstallMethod.PIP_SYSTEM, "pip install --upgrade spec-kitty-cli"),
            (InstallMethod.BREW, "brew upgrade spec-kitty-cli"),
        ],
    )
    def test_command_hint_unchanged(
        self,
        install_method: InstallMethod,
        expected_command: str,
    ) -> None:
        """After WP03, build_upgrade_hint() must return the pre-migration command."""
        controlled = (
            _uv_default_runtime()
            if install_method == InstallMethod.UV_TOOL
            else _make_runtime(install_method)
        )
        with mock.patch(
            "specify_cli.compat._detect.runtime.detect_runtime",
            return_value=controlled,
        ):
            hint = build_upgrade_hint(
                install_method, package="spec-kitty-cli", target_version=None
            )

        assert hint.install_method == install_method
        assert hint.command == expected_command
        assert hint.note is None

    @pytest.mark.parametrize(
        "install_method",
        [InstallMethod.SOURCE, InstallMethod.UNKNOWN, InstallMethod.SYSTEM_PACKAGE],
    )
    def test_note_hint_command_is_none(self, install_method: InstallMethod) -> None:
        """SOURCE/UNKNOWN/SYSTEM_PACKAGE produce command=None, note non-None."""
        controlled = _make_runtime(install_method)
        with mock.patch(
            "specify_cli.compat._detect.runtime.detect_runtime",
            return_value=controlled,
        ):
            hint = build_upgrade_hint(install_method)

        assert hint.install_method == install_method
        assert hint.command is None
        assert hint.note is not None

    def test_uv_tool_target_version_pinned(self) -> None:
        """UV_TOOL + valid target_version → pinned command (pre-migration behaviour)."""
        controlled = _uv_default_runtime()
        with mock.patch(
            "specify_cli.compat._detect.runtime.detect_runtime",
            return_value=controlled,
        ):
            hint = build_upgrade_hint(
                InstallMethod.UV_TOOL,
                package="spec-kitty-cli",
                target_version="3.2.2",
            )

        assert hint.command == "uv tool install --force spec-kitty-cli==3.2.2"

    def test_uv_tool_invalid_target_version_falls_back_to_unpinned(self) -> None:
        """UV_TOOL + unsafe target_version → unpinned command (pre-migration behaviour)."""
        controlled = _uv_default_runtime()
        with mock.patch(
            "specify_cli.compat._detect.runtime.detect_runtime",
            return_value=controlled,
        ):
            hint = build_upgrade_hint(
                InstallMethod.UV_TOOL,
                package="spec-kitty-cli",
                target_version="3.2.2;rm",
            )

        assert hint.command == "uv tool install --force spec-kitty-cli"

    @pytest.mark.parametrize("method", list(InstallMethod))
    def test_invariant_holds_for_all_methods(self, method: InstallMethod) -> None:
        """Exactly one of command / note must be non-None for every method."""
        controlled = (
            _uv_default_runtime()
            if method == InstallMethod.UV_TOOL
            else _make_runtime(method)
        )
        with mock.patch(
            "specify_cli.compat._detect.runtime.detect_runtime",
            return_value=controlled,
        ):
            hint = build_upgrade_hint(method)

        assert (hint.command is None) != (hint.note is None), (
            f"{method}: invariant violated; "
            f"command={hint.command!r}, note={hint.note!r}"
        )


# ---------------------------------------------------------------------------
# RemediationCommand.render() — posix
# ---------------------------------------------------------------------------


class TestRenderPosix:
    def test_pipx_upgrade(self) -> None:
        cmd = RemediationCommand(
            intent=RemediationIntent.UPGRADE,
            argv=("pipx", "upgrade", "spec-kitty-cli"),
            env={},
            note=None,
        )
        assert cmd.render("posix") == "pipx upgrade spec-kitty-cli"

    def test_uv_tool_default_no_env(self) -> None:
        cmd = RemediationCommand(
            intent=RemediationIntent.UPGRADE,
            argv=("uv", "tool", "install", "--force", "spec-kitty-cli"),
            env={},
            note=None,
        )
        assert cmd.render("posix") == "uv tool install --force spec-kitty-cli"

    def test_uv_tool_custom_dir(self) -> None:
        cmd = RemediationCommand(
            intent=RemediationIntent.UPGRADE,
            argv=("uv", "tool", "install", "--force", "spec-kitty-cli"),
            env={"UV_TOOL_DIR": "/opt/tools"},
            note=None,
        )
        assert cmd.render("posix") == (
            "UV_TOOL_DIR=/opt/tools uv tool install --force spec-kitty-cli"
        )

    def test_uv_tool_custom_dir_and_python(self) -> None:
        """Acceptance scenario: UV_TOOL_DIR=/opt, python=3.11."""
        cmd = RemediationCommand(
            intent=RemediationIntent.UPGRADE,
            argv=("uv", "tool", "install", "--force", "--python", "3.11", "spec-kitty-cli"),
            env={"UV_TOOL_DIR": "/opt"},
            note=None,
        )
        assert cmd.render("posix") == (
            "UV_TOOL_DIR=/opt uv tool install --force --python 3.11 spec-kitty-cli"
        )

    def test_pip_user_upgrade(self) -> None:
        cmd = RemediationCommand(
            intent=RemediationIntent.UPGRADE,
            argv=("pip", "install", "--user", "--upgrade", "spec-kitty-cli"),
            env={},
            note=None,
        )
        assert cmd.render("posix") == "pip install --user --upgrade spec-kitty-cli"

    def test_pip_system_upgrade(self) -> None:
        cmd = RemediationCommand(
            intent=RemediationIntent.UPGRADE,
            argv=("pip", "install", "--upgrade", "spec-kitty-cli"),
            env={},
            note=None,
        )
        assert cmd.render("posix") == "pip install --upgrade spec-kitty-cli"

    def test_brew_upgrade(self) -> None:
        cmd = RemediationCommand(
            intent=RemediationIntent.UPGRADE,
            argv=("brew", "upgrade", "spec-kitty-cli"),
            env={},
            note=None,
        )
        assert cmd.render("posix") == "brew upgrade spec-kitty-cli"


# ---------------------------------------------------------------------------
# RemediationCommand.render() — windows
# ---------------------------------------------------------------------------


class TestRenderWindows:
    def test_pipx_upgrade_no_env(self) -> None:
        """Windows render without env vars: simple command passes CHK028."""
        cmd = RemediationCommand(
            intent=RemediationIntent.UPGRADE,
            argv=("pipx", "upgrade", "spec-kitty-cli"),
            env={},
            note=None,
        )
        assert cmd.render("windows") == "pipx upgrade spec-kitty-cli"

    def test_uv_tool_default_no_env(self) -> None:
        cmd = RemediationCommand(
            intent=RemediationIntent.UPGRADE,
            argv=("uv", "tool", "install", "--force", "spec-kitty-cli"),
            env={},
            note=None,
        )
        assert cmd.render("windows") == "uv tool install --force spec-kitty-cli"

    def test_windows_render_with_env_raises_chk028(self) -> None:
        """Windows env prefix ($env:KEY='value'; ) contains chars outside CHK028."""
        cmd = RemediationCommand(
            intent=RemediationIntent.UPGRADE,
            argv=("uv", "tool", "install", "--force", "spec-kitty-cli"),
            env={"UV_TOOL_DIR": "C:\\tools"},
            note=None,
        )
        with pytest.raises(ValueError, match="CHK028 violation"):
            cmd.render("windows")


# ---------------------------------------------------------------------------
# RemediationCommand.render() — error cases
# ---------------------------------------------------------------------------


class TestRenderErrors:
    def test_manual_guidance_raises(self) -> None:
        cmd = RemediationCommand(
            intent=RemediationIntent.MANUAL_GUIDANCE,
            argv=None,
            env={},
            note="Some note",
        )
        with pytest.raises(ValueError, match="cannot render MANUAL_GUIDANCE"):
            cmd.render("posix")

    def test_argv_none_with_upgrade_intent_raises(self) -> None:
        cmd = RemediationCommand(
            intent=RemediationIntent.UPGRADE,
            argv=None,
            env={},
            note=None,
        )
        with pytest.raises(ValueError, match="argv is None"):
            cmd.render("posix")


# ---------------------------------------------------------------------------
# CHK028 regression tests (NFR-002)
# ---------------------------------------------------------------------------


class TestChk028:
    @pytest.mark.parametrize(
        "bad_argv",
        [
            ("pipx", "upgrade", "$(rm -rf /)"),
            ("pipx", "upgrade", "pkg; rm -rf /"),
            ("pipx", "upgrade", "pkg && evil"),
            ("pipx", "upgrade", "pkg`cmd`"),
            ("pipx", "upgrade", "pkg|cat"),
            ("pipx", "upgrade", "pkg\nnewline"),
        ],
    )
    def test_metacharacter_argv_raises_chk028(
        self, bad_argv: tuple[str, ...]
    ) -> None:
        """Shell metacharacters in argv → CHK028 violation."""
        cmd = RemediationCommand(
            intent=RemediationIntent.UPGRADE,
            argv=bad_argv,
            env={},
            note=None,
        )
        with pytest.raises(ValueError, match="CHK028 violation"):
            cmd.render("posix")

    def test_too_long_command_raises_chk028(self) -> None:
        """Composed string > COMMAND_ALLOWLIST_MAX_LEN chars → CHK028 violation."""
        from specify_cli.compat.remediation import COMMAND_ALLOWLIST_MAX_LEN

        long_pkg = "a" * COMMAND_ALLOWLIST_MAX_LEN
        cmd = RemediationCommand(
            intent=RemediationIntent.UPGRADE,
            argv=("pip", "install", long_pkg),
            env={},
            note=None,
        )
        with pytest.raises(ValueError, match="CHK028"):
            cmd.render("posix")

    def test_valid_command_passes(self) -> None:
        cmd = RemediationCommand(
            intent=RemediationIntent.UPGRADE,
            argv=("pip", "install", "--user", "--upgrade", "spec-kitty-cli"),
            env={},
            note=None,
        )
        result = cmd.render("posix")
        assert result == "pip install --user --upgrade spec-kitty-cli"


# ---------------------------------------------------------------------------
# plan_remediation() edge cases
# ---------------------------------------------------------------------------


class TestPlanRemediationEdgeCases:
    def test_uv_tool_custom_dir_and_python_posix(self) -> None:
        """UV_TOOL: is_default_tool_dir=False AND python → env var + --python flag."""
        runtime = _uv_custom_runtime(tool_dir="/opt/tools", python="3.11")
        cmd = plan_remediation(runtime, RemediationIntent.UPGRADE, None)
        assert cmd.env == {"UV_TOOL_DIR": "/opt/tools"}
        assert cmd.argv is not None
        assert "--python" in cmd.argv
        assert "3.11" in cmd.argv
        rendered = cmd.render("posix")
        assert rendered == (
            "UV_TOOL_DIR=/opt/tools uv tool install --force --python 3.11 spec-kitty-cli"
        )

    def test_uv_tool_default_dir_no_env_var(self) -> None:
        """UV_TOOL with is_default_tool_dir=True → env is empty."""
        runtime = _uv_default_runtime()
        cmd = plan_remediation(runtime, RemediationIntent.UPGRADE, None)
        assert cmd.env == {}

    def test_uv_tool_none_default_dir_no_env_var(self) -> None:
        """UV_TOOL with is_default_tool_dir=None → env is empty (None != False)."""
        runtime = _make_runtime(InstallMethod.UV_TOOL, is_default_tool_dir=None)
        cmd = plan_remediation(runtime, RemediationIntent.UPGRADE, None)
        assert cmd.env == {}

    def test_uv_tool_target_version_pinned(self) -> None:
        """Valid target_version for UV_TOOL UPGRADE → spec-kitty-cli==VER in argv."""
        runtime = _uv_default_runtime()
        cmd = plan_remediation(runtime, RemediationIntent.UPGRADE, "3.2.2")
        assert cmd.argv is not None
        assert "spec-kitty-cli==3.2.2" in cmd.argv
        assert cmd.render("posix") == "uv tool install --force spec-kitty-cli==3.2.2"

    def test_uv_tool_invalid_target_version_ignored(self) -> None:
        """Invalid target_version for UV_TOOL → unpinned package."""
        runtime = _uv_default_runtime()
        cmd = plan_remediation(runtime, RemediationIntent.UPGRADE, "3.2.2;rm")
        assert cmd.argv is not None
        assert "spec-kitty-cli" in cmd.argv
        assert "spec-kitty-cli==3.2.2;rm" not in str(cmd.argv)
        assert cmd.render("posix") == "uv tool install --force spec-kitty-cli"

    def test_uv_tool_reinstall_receipt_specifier_wins_over_target_version(self) -> None:
        """REINSTALL: a receipt specifier is authoritative; target_version is ignored.

        Provenance from the receipt must win — target_version only pins the
        receipt-absent PyPI fallback (FR-019 / SC-003).
        """
        runtime = _uv_runtime_with_reqs(
            (_req(specifier="==3.2.0rc25"),), receipt_path=Path("/t/uv-receipt.toml")
        )
        cmd = plan_remediation(runtime, RemediationIntent.REINSTALL_WITH_TEST, "9.9.9")
        assert cmd.render("posix") == (
            "uv tool install --force --with pytest spec-kitty-cli==3.2.0rc25"
        )

    def test_uv_tool_reinstall_receipt_absent_pins_target_version(self) -> None:
        """REINSTALL with no receipt → PyPI fallback pinned to the known version."""
        runtime = _uv_default_runtime()  # requirements=(), receipt_path=None
        cmd = plan_remediation(runtime, RemediationIntent.REINSTALL_WITH_TEST, "3.2.2")
        assert cmd.render("posix") == (
            "uv tool install --force --with pytest spec-kitty-cli==3.2.2"
        )

    def test_plan_remediation_is_pure(self) -> None:
        """plan_remediation() is pure: identical inputs → equal RemediationCommand."""
        runtime = _make_runtime(InstallMethod.PIPX)
        cmd1 = plan_remediation(runtime, RemediationIntent.UPGRADE, None)
        cmd2 = plan_remediation(runtime, RemediationIntent.UPGRADE, None)
        assert cmd1 == cmd2

    def test_brew_reinstall_with_test_is_manual(self) -> None:
        """BREW REINSTALL_WITH_TEST → MANUAL_GUIDANCE (no standard brew test extra)."""
        runtime = _make_runtime(InstallMethod.BREW)
        cmd = plan_remediation(runtime, RemediationIntent.REINSTALL_WITH_TEST, None)
        assert cmd.intent == RemediationIntent.MANUAL_GUIDANCE
        assert cmd.argv is None
        assert cmd.note is not None

    def test_pip_user_reinstall_with_test_is_manual(self) -> None:
        """PIP_USER REINSTALL_WITH_TEST → MANUAL_GUIDANCE."""
        runtime = _make_runtime(InstallMethod.PIP_USER)
        cmd = plan_remediation(runtime, RemediationIntent.REINSTALL_WITH_TEST, None)
        assert cmd.intent == RemediationIntent.MANUAL_GUIDANCE

    def test_pip_system_reinstall_with_test_is_manual(self) -> None:
        """PIP_SYSTEM REINSTALL_WITH_TEST → MANUAL_GUIDANCE."""
        runtime = _make_runtime(InstallMethod.PIP_SYSTEM)
        cmd = plan_remediation(runtime, RemediationIntent.REINSTALL_WITH_TEST, None)
        assert cmd.intent == RemediationIntent.MANUAL_GUIDANCE

    def test_source_upgrade_is_manual(self) -> None:
        """SOURCE UPGRADE → MANUAL_GUIDANCE."""
        runtime = _make_runtime(InstallMethod.SOURCE)
        cmd = plan_remediation(runtime, RemediationIntent.UPGRADE, None)
        assert cmd.intent == RemediationIntent.MANUAL_GUIDANCE

    def test_unknown_upgrade_is_manual(self) -> None:
        """UNKNOWN UPGRADE → MANUAL_GUIDANCE."""
        runtime = _make_runtime(InstallMethod.UNKNOWN)
        cmd = plan_remediation(runtime, RemediationIntent.UPGRADE, None)
        assert cmd.intent == RemediationIntent.MANUAL_GUIDANCE

    def test_system_package_upgrade_is_manual(self) -> None:
        """SYSTEM_PACKAGE UPGRADE → MANUAL_GUIDANCE."""
        runtime = _make_runtime(InstallMethod.SYSTEM_PACKAGE)
        cmd = plan_remediation(runtime, RemediationIntent.UPGRADE, None)
        assert cmd.intent == RemediationIntent.MANUAL_GUIDANCE


# ---------------------------------------------------------------------------
# PowerShell quoting helper
# ---------------------------------------------------------------------------


class TestPowershellQuote:
    def test_no_single_quotes(self) -> None:
        assert _powershell_quote("C:\\tools") == "'C:\\tools'"

    def test_embedded_single_quote_doubled(self) -> None:
        assert _powershell_quote("it's") == "'it''s'"

    def test_empty_string(self) -> None:
        assert _powershell_quote("") == "''"

    def test_multiple_single_quotes(self) -> None:
        assert _powershell_quote("a'b'c") == "'a''b''c'"

    def test_windows_render_env_prefix_format(self) -> None:
        """The $env:KEY='value'; format is built correctly (format verification)."""
        from specify_cli.compat.remediation import _powershell_quote as psq

        key = "UV_TOOL_DIR"
        value = "C:\\tools"
        entry = f"$env:{key}={psq(value)}; "
        assert entry == "$env:UV_TOOL_DIR='C:\\tools'; "


class TestCurrentUpgradeCommand:
    """current_upgrade_command(): the single detect→plan→render→fallback seam."""

    def test_renders_planner_upgrade_command(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specify_cli.compat import upgrade_hint

        monkeypatch.setattr(
            "specify_cli.compat._detect.runtime.detect_runtime",
            _uv_default_runtime,
        )
        assert upgrade_hint.current_upgrade_command() == (
            "uv tool install --force spec-kitty-cli"
        )

    def test_falls_back_when_render_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specify_cli.compat import upgrade_hint

        # SOURCE → UPGRADE is MANUAL_GUIDANCE → render() raises → fallback.
        monkeypatch.setattr(
            "specify_cli.compat._detect.runtime.detect_runtime",
            lambda: _make_runtime(InstallMethod.SOURCE),
        )
        assert upgrade_hint.current_upgrade_command() == "pipx upgrade spec-kitty-cli"
        assert upgrade_hint.current_upgrade_command("custom fallback") == "custom fallback"


def test_unknown_upgrade_remediation_links_the_install_guide() -> None:
    """Both call sites print the same link, so they cannot drift apart again."""
    note = _manual_note("unknown", RemediationIntent.UPGRADE)
    assert note is not None
    assert INSTALL_AND_UPGRADE_URL in note
