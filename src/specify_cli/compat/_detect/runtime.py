"""Runtime snapshot type for the installed spec-kitty-cli.

Public surface
--------------
PackageSource        -- StrEnum with 7 provenance values.
UvRequirement        -- Frozen dataclass: one uv receipt requirement entry.
InstalledCliRuntime  -- Frozen dataclass: immutable snapshot of a running installation.
detect_runtime       -- Build a runtime snapshot; NEVER raises (CHK032/NFR-001).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from kernel.paths import is_windows

if TYPE_CHECKING:
    from specify_cli.compat._detect.install_method import InstallMethod


# ---------------------------------------------------------------------------
# PackageSource enum
# ---------------------------------------------------------------------------


class PackageSource(StrEnum):
    """Derived package provenance from the uv receipt requirements entry."""

    PYPI_SPECIFIER = "pypi-specifier"  # { name = "...", specifier = "..." }
    GIT = "git"  # { git = "..." }
    URL = "url"  # { url = "..." }
    DIRECTORY = "directory"  # { directory = "..." }
    EDITABLE = "editable"  # { editable = "..." }
    PATH = "path"  # { path = "..." }
    UNKNOWN = "unknown"  # receipt unavailable or no spec-kitty entry


# ---------------------------------------------------------------------------
# UvRequirement dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UvRequirement:
    """A single requirement entry from a uv receipt.

    Fields mirror the uv receipt TOML schema. Only ``name`` is required;
    all others are optional depending on the requirement source type.

    ``is_supported`` is ``False`` when the source entry carried a key the
    domain does not model (e.g. a future/unknown uv receipt source kind).
    It is load-bearing for provenance preservation (FR-019 / SC-003,
    issue #1358 "nothing discarded"): a remediation planner MUST refuse to
    reconstruct a command from an unsupported entry rather than silently
    collapse it to a PyPI name — which would clobber the user's real source.
    """

    name: str
    specifier: str | None = None
    directory: str | None = None
    editable: str | None = None
    path: str | None = None
    git: str | None = None
    url: str | None = None
    is_supported: bool = True


# ---------------------------------------------------------------------------
# InstalledCliRuntime dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InstalledCliRuntime:
    """Immutable snapshot of a running spec-kitty-cli installation.

    CHK032 / NFR-001: ``detect_runtime()`` MUST NEVER raise; every probe
    is wrapped in try/except with silent fall-through to defaults.

    Invariant: ``receipt_path`` is None whenever ``install_method`` is not
    UV_TOOL, SOURCE, or UNKNOWN; ``requirements`` is ``()`` whenever
    ``receipt_path`` is None.
    """

    install_method: InstallMethod  # from _detect/install_method.py
    executable: str  # sys.executable value
    receipt_path: Path | None  # absolute path to uv-receipt.toml, or None
    tool_dir: Path | None  # UV tool env parent dir, or None
    bin_dir: Path | None  # bin dir carrying the spec-kitty entrypoint, or None
    is_default_tool_dir: bool | None  # None when not a uv-tool install
    is_default_bin_dir: bool | None  # None when not a uv-tool install
    python: str | None  # python version override from receipt, or None
    requirements: tuple[UvRequirement, ...]  # empty tuple when receipt unavailable
    package_source: PackageSource  # derived provenance enum
    platform: Literal["posix", "windows"]  # platform at runtime
    safe_for_auto_upgrade: bool  # True iff install_method in _SAFE_AUTO_UPGRADE_METHODS


# ---------------------------------------------------------------------------
# detect_runtime()
# ---------------------------------------------------------------------------


def detect_runtime() -> InstalledCliRuntime:
    """Return an immutable snapshot of the running spec-kitty-cli installation.

    CHK032 / NFR-001: NEVER raises.  Every probe is wrapped in try/except
    with silent fall-through to safe defaults.

    For UV_TOOL installs the uv receipt is parsed once to populate all
    receipt-derived fields (SC-001 — single receipt read per invocation).
    For all other install methods receipt/dir/python fields are None/empty.
    """
    try:  # noqa: BLE001
        from specify_cli.compat._detect.install_method import (
            InstallMethod as _InstallMethod,
            _SAFE_AUTO_UPGRADE_METHODS,
            detect_install_method as _detect_install_method,
        )
        from specify_cli.compat._adapters.uv_receipt import UvReceiptReader

        install_method = _detect_install_method()
        executable = sys.executable
        platform: Literal["posix", "windows"] = "windows" if is_windows() else "posix"
        safe_for_auto_upgrade = install_method in _SAFE_AUTO_UPGRADE_METHODS

        if install_method == _InstallMethod.UV_TOOL:
            result = UvReceiptReader.read_for_executable(executable)
            return InstalledCliRuntime(
                install_method=install_method,
                executable=executable,
                receipt_path=result.receipt_path,
                tool_dir=result.tool_dir,
                bin_dir=result.bin_dir,
                is_default_tool_dir=result.is_default_tool_dir,
                is_default_bin_dir=result.is_default_bin_dir,
                python=result.python,
                requirements=result.requirements,
                package_source=result.package_source,
                platform=platform,
                safe_for_auto_upgrade=safe_for_auto_upgrade,
            )

        # Non-UV_TOOL install: no receipt data available.
        return InstalledCliRuntime(
            install_method=install_method,
            executable=executable,
            receipt_path=None,
            tool_dir=None,
            bin_dir=None,
            is_default_tool_dir=None,
            is_default_bin_dir=None,
            python=None,
            requirements=(),
            package_source=PackageSource.UNKNOWN,
            platform=platform,
            safe_for_auto_upgrade=safe_for_auto_upgrade,
        )
    except Exception:  # noqa: BLE001
        # Catastrophic failure: return a safe default with UNKNOWN install method.
        from specify_cli.compat._detect.install_method import InstallMethod as _IM

        return InstalledCliRuntime(
            install_method=_IM.UNKNOWN,
            executable=sys.executable,
            receipt_path=None,
            tool_dir=None,
            bin_dir=None,
            is_default_tool_dir=None,
            is_default_bin_dir=None,
            python=None,
            requirements=(),
            package_source=PackageSource.UNKNOWN,
            platform="windows" if is_windows() else "posix",
            safe_for_auto_upgrade=False,
        )
