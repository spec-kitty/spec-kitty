"""T021 snapshot parity tests for the WP04 review/__init__.py migration.

These tests assert that the migrated _missing_test_extra_remediation()
function produces the correct output for each install method after the Set A
helpers were deleted and replaced with calls to detect_runtime() and
plan_remediation().

They serve as the regression guard for WP04: if any future change breaks the
output contract, these tests catch it.

Markers: fast + non_sandbox (matching the test_review.py suite so that CI
gates pick these up in the same bucket as the existing review tests).
"""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
from typing import Literal

import pytest

pytestmark = [pytest.mark.fast, pytest.mark.non_sandbox]


# ---------------------------------------------------------------------------
# Test helper
# ---------------------------------------------------------------------------


def _make_runtime(
    install_method_name: str,
    *,
    tool_dir: str | None = None,
    is_default_tool_dir: bool | None = True,
    python: str | None = None,
    platform: str = "posix",
    receipt_path: str | None = None,
    requirements: tuple[object, ...] = (),
) -> object:
    """Construct an InstalledCliRuntime for monkeypatching detect_runtime().

    Args:
        install_method_name: enum name, e.g. "UV_TOOL", "PIPX", "UNKNOWN".
        tool_dir: uv tool directory (raw path text); only meaningful for UV_TOOL.
        is_default_tool_dir: True/False/None depending on install context.
        python: Python version override from receipt (UV_TOOL only).
        platform: "posix" or "windows".
        receipt_path: receipt file path text, or None.
        requirements: uv receipt requirement entries (provenance).

    Issue #3726: path fields are built with the DECLARED platform's flavor
    (PurePosixPath / PureWindowsPath), never a host ``Path``. On a Windows
    host ``Path("/opt/uv")`` renders ``\\opt\\uv``; the backslash falls
    outside CHK028's character allowlist (compat/remediation.py), so a
    mocked POSIX runtime degrades to the provenance fallback note instead
    of the byte-for-byte reinstall snapshot below. Pure flavors pin the
    path semantics to the declared platform on any host.
    """
    from specify_cli.compat._detect.install_method import (
        InstallMethod,
        _SAFE_AUTO_UPGRADE_METHODS,
    )
    from specify_cli.compat._detect.runtime import InstalledCliRuntime, PackageSource

    method = InstallMethod[install_method_name]
    resolved_platform: Literal["posix", "windows"] = (
        "windows" if platform == "windows" else "posix"
    )
    path_cls: type[PurePosixPath] | type[PureWindowsPath] = (
        PurePosixPath if resolved_platform == "posix" else PureWindowsPath
    )

    return InstalledCliRuntime(
        install_method=method,
        executable="/usr/local/bin/python",
        # PurePath is the honest fixture type: InstalledCliRuntime's consumers
        # only None-check / str() these fields (issue #3726), so a pure path
        # of the declared platform's flavor is safe on any host.
        receipt_path=path_cls(receipt_path) if receipt_path is not None else None,  # type: ignore[arg-type]
        tool_dir=path_cls(tool_dir) if tool_dir is not None else None,  # type: ignore[arg-type]
        bin_dir=None,
        is_default_tool_dir=is_default_tool_dir,
        is_default_bin_dir=None,
        python=python,
        requirements=requirements,  # type: ignore[arg-type]
        package_source=(
            PackageSource.PYPI_SPECIFIER
            if method == InstallMethod.UV_TOOL
            else PackageSource.UNKNOWN
        ),
        platform=resolved_platform,
        safe_for_auto_upgrade=(method in _SAFE_AUTO_UPGRADE_METHODS),
    )


def _spec_kitty_req(**kwargs: object) -> object:
    """A spec-kitty-cli uv requirement entry (provenance)."""
    from specify_cli.compat._detect.runtime import UvRequirement

    return UvRequirement(name="spec-kitty-cli", **kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# T021-A  Byte-for-byte parity: UV_TOOL custom tool_dir + python override
# ---------------------------------------------------------------------------


def test_uv_tool_custom_tool_dir_and_python_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UV_TOOL with non-default tool_dir + python override preserves provenance.

    Snapshot: UV_TOOL_DIR=/opt/uv uv tool install --force --python 3.13 --with pytest spec-kitty-cli==3.2.0rc25

    Byte-for-byte regression guard for the REINSTALL_WITH_TEST path: the
    receipt specifier is preserved (never re-pinned), pytest is injected via
    ``--with pytest`` (FR-019 / SC-003 / issue #1358).
    """
    import specify_cli.cli.commands.review as review_mod

    tool_dir = "/opt/uv"
    runtime = _make_runtime(
        "UV_TOOL",
        tool_dir=tool_dir,
        is_default_tool_dir=False,
        python="3.13",
        receipt_path=f"{tool_dir}/uv-receipt.toml",
        requirements=(_spec_kitty_req(specifier="==3.2.0rc25"),),
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.detect_runtime",
        lambda: runtime,
    )

    result = review_mod._missing_test_extra_remediation()  # noqa: SLF001
    expected = (
        "UV_TOOL_DIR=/opt/uv uv tool install --force --python 3.13 "
        "--with pytest spec-kitty-cli==3.2.0rc25"
    )
    assert result == expected, f"Snapshot mismatch: {result!r}"


# ---------------------------------------------------------------------------
# T021-B  UV_TOOL directory install: provenance preserved, NOT re-pinned to PyPI
# ---------------------------------------------------------------------------


def test_uv_tool_directory_source_not_clobbered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A local directory uv-tool install must reinstall from that directory.

    Regression guard for the clobber bug: re-pinning a source install to the
    PyPI release destroys the user's working checkout linkage.
    Snapshot: uv tool install --force --with pytest /src
    """
    import specify_cli.cli.commands.review as review_mod

    runtime = _make_runtime(
        "UV_TOOL",
        is_default_tool_dir=True,
        receipt_path="/t/uv-receipt.toml",
        requirements=(_spec_kitty_req(directory="/src"),),
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.detect_runtime",
        lambda: runtime,
    )

    result = review_mod._missing_test_extra_remediation()  # noqa: SLF001
    assert result == "uv tool install --force --with pytest /src"
    assert "spec-kitty-cli" not in result  # never re-pinned to PyPI


# ---------------------------------------------------------------------------
# T021-C  PIPX install: non-UV_TOOL path -> "uv sync --extra test"
# ---------------------------------------------------------------------------


def test_pipx_install_falls_back_to_uv_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PIPX is not UV_TOOL; _missing_test_extra_remediation returns 'uv sync --extra test'.

    This is the parity snapshot for the PIPX path: the migrated code returns
    the same non-UV_TOOL fallback that the legacy helper returned when PIPX was
    the install method (the legacy _HINT_TABLE PIPX entry covered UPGRADE only;
    reinstall-with-test was always a manual step for non-UV_TOOL methods).
    """
    import specify_cli.cli.commands.review as review_mod

    runtime = _make_runtime("PIPX")
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.detect_runtime",
        lambda: runtime,
    )

    result = review_mod._missing_test_extra_remediation()  # noqa: SLF001
    assert result == "uv sync --extra test"


# ---------------------------------------------------------------------------
# T021-D  Malformed receipt / UNKNOWN install method: graceful degradation
# ---------------------------------------------------------------------------


def test_malformed_receipt_graceful_degradation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UNKNOWN install method (e.g. malformed receipt) degrades gracefully.

    CHK032 guarantees detect_runtime() never raises; for an unrecognised
    install method the function must return a safe fallback without raising.
    """
    import specify_cli.cli.commands.review as review_mod

    runtime = _make_runtime("UNKNOWN", is_default_tool_dir=None)
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.detect_runtime",
        lambda: runtime,
    )

    result = review_mod._missing_test_extra_remediation()  # noqa: SLF001
    assert result == "uv sync --extra test"
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# T021-E  Windows platform, non-default tool_dir: CHK028 violation -> fallback
# ---------------------------------------------------------------------------


def test_windows_non_default_tool_dir_chk028_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows + non-default tool_dir: render() raises CHK028 -> note fallback.

    The Windows env prefix format ($env:KEY='value'; ) contains characters
    outside the CHK028 allowed set (dollar signs, apostrophes, semicolons).
    A short fixed path is used; the CHK028 violation comes from the $env:
    prefix format itself, not path length.
    """
    import specify_cli.cli.commands.review as review_mod

    tool_dir = "/opt/uv"
    runtime = _make_runtime(
        "UV_TOOL",
        tool_dir=tool_dir,
        is_default_tool_dir=False,
        platform="windows",
        receipt_path=f"{tool_dir}/uv-receipt.toml",
        requirements=(_spec_kitty_req(specifier="==3.2.0rc25"),),
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.detect_runtime",
        lambda: runtime,
    )

    result = review_mod._missing_test_extra_remediation()  # noqa: SLF001
    # render("windows") raises ValueError (CHK028): $env:UV_TOOL_DIR='\opt\uv';
    # contains $, ', ; (and \) which are outside the CHK028 character class.
    # -> fallback to cmd.note, which carries the safe provenance guidance.
    assert "could not preserve uv receipt provenance" in result


# ---------------------------------------------------------------------------
# T021-F  Windows platform, default tool_dir: no env prefix -> CHK028 passes
# ---------------------------------------------------------------------------


def test_windows_default_tool_dir_renders_successfully(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows + default tool_dir: no env vars -> CHK028 passes.

    When UV_TOOL_DIR is not injected (default tool_dir) the argv-only
    render on Windows produces a valid CHK028 command with no $env: prefix.
    """
    import specify_cli.cli.commands.review as review_mod

    runtime = _make_runtime(
        "UV_TOOL",
        is_default_tool_dir=True,
        platform="windows",
        receipt_path="/t/uv-receipt.toml",
        requirements=(_spec_kitty_req(specifier="==3.2.0rc25"),),
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.detect_runtime",
        lambda: runtime,
    )

    result = review_mod._missing_test_extra_remediation()  # noqa: SLF001
    assert result == "uv tool install --force --with pytest spec-kitty-cli==3.2.0rc25"
