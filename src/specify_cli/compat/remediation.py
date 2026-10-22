"""Remediation-command types and planner for the upgrade-nag.

Public surface
--------------
RemediationIntent    -- StrEnum with 3 intent values.
RemediationCommand   -- Frozen dataclass: a fully specified remediation action.
plan_remediation     -- Pure function: build a RemediationCommand from runtime + intent.

Security properties enforced here
-----------------------------------
CHK028  ``render()`` validates the composed command string against
        ``^[A-Za-z0-9 .\\-+_/=:]{1,COMMAND_ALLOWLIST_MAX_LEN}$``
        (identical character class to ``compat/upgrade_hint.py``).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from kernel.site_urls import INSTALL_AND_UPGRADE_URL

if TYPE_CHECKING:
    from specify_cli.compat._detect.runtime import InstalledCliRuntime, UvRequirement

# ---------------------------------------------------------------------------
# CHK028 validation (shared with upgrade_hint.py)
# ---------------------------------------------------------------------------

COMMAND_ALLOWLIST_MAX_LEN = 512
_COMMAND_RE = re.compile(
    rf"^[A-Za-z0-9 .\-+_/=:]{{1,{COMMAND_ALLOWLIST_MAX_LEN}}}$"
)  # CHK028 — character class unchanged; length raised for index URLs

# Version specifier validation — same pattern as upgrade_hint.py _VERSION_RE
_VERSION_RE = re.compile(r"^[A-Za-z0-9.\-+]{1,64}$")

_PACKAGE_NAME = "spec-kitty-cli"
_PYTEST_NAME = "pytest"

# Shown when a uv-tool reinstall cannot be reconstructed from the receipt
# without risking a clobber of the user's real source (unsupported/unknown
# requirement shape, or missing spec-kitty entry). Mirrors the legacy
# ``_fallback_uv_tool_reinstall_command`` guidance; the substring
# "same uv tool source" is asserted by the provenance regression tests.
_UV_PROVENANCE_FALLBACK_NOTE = (
    "Spec Kitty could not preserve uv receipt provenance automatically; "
    "reinstall the same uv tool source with --with pytest"
)


# ---------------------------------------------------------------------------
# PowerShell quoting helper  (mirrors review/__init__.py _powershell_quote)
# ---------------------------------------------------------------------------


def _powershell_quote(value: str) -> str:
    """Wrap *value* in PowerShell single quotes, escaping embedded ``'``.

    Mirrors ``_powershell_quote()`` in ``review/__init__.py`` (C-005).
    """
    return "'" + value.replace("'", "''") + "'"


# ---------------------------------------------------------------------------
# RemediationIntent enum
# ---------------------------------------------------------------------------


class RemediationIntent(StrEnum):
    """What the remediation command is attempting to do."""

    UPGRADE = "upgrade"
    REINSTALL_WITH_TEST = "reinstall_with_test"
    MANUAL_GUIDANCE = "manual_guidance"


# ---------------------------------------------------------------------------
# RemediationCommand dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RemediationCommand:
    """A fully specified remediation action.

    NFR-004: Instances are constructed by ``plan_remediation()``, a pure
    function (no I/O). Construction itself does NOT raise on invalid
    content — validation happens in ``render()`` (NFR-002).

    Invariant: if ``intent == MANUAL_GUIDANCE``, ``argv`` is None and
    ``note`` is non-None. For UPGRADE and REINSTALL_WITH_TEST, ``argv``
    is non-None when the install method supports automated remediation.
    """

    intent: RemediationIntent
    argv: tuple[str, ...] | None              # subprocess-ready args, or None for manual
    env: Mapping[str, str]                    # env vars to prepend (e.g. UV_TOOL_DIR=...)
    note: str | None                          # human-readable note, or None

    def render(self, platform: Literal["posix", "windows"]) -> str:
        """Return a CHK028-validated, env-prefixed, platform-quoted command string.

        Raises:
            ValueError: if ``self.intent`` is ``MANUAL_GUIDANCE``.
            ValueError: if ``self.argv`` is ``None``.
            ValueError: if the composed string does not match CHK028
                        (``^[A-Za-z0-9 .\\-+_/=:]{1,512}$``).

        The returned string is safe for copy-paste display.  The same
        ``argv`` and ``env`` fields can be passed directly to
        ``subprocess.run()`` for programmatic execution.
        """
        import shlex  # stdlib — deferred to keep module-level imports minimal

        if self.intent == RemediationIntent.MANUAL_GUIDANCE:
            raise ValueError(
                "cannot render MANUAL_GUIDANCE RemediationCommand"
                " — check intent before calling render()"
            )
        if self.argv is None:
            raise ValueError("argv is None")

        # --- 1. Build env prefix -------------------------------------------
        if self.env:
            if platform == "posix":
                # KEY=shlex.quote(value) per entry, space-joined with trailing space.
                env_prefix = "".join(
                    f"{k}={shlex.quote(v)} " for k, v in self.env.items()
                )
            else:
                # $env:KEY='ps-quoted-value'; per entry, concatenated with trailing space.
                env_prefix = "".join(
                    f"$env:{k}={_powershell_quote(v)}; " for k, v in self.env.items()
                )
        else:
            env_prefix = ""

        # --- 2. Build argv string -------------------------------------------
        argv_str = (
            " ".join(shlex.quote(a) for a in self.argv)
            if platform == "posix"
            else " ".join(self.argv)
        )

        # --- 3. Compose and CHK028-validate ---------------------------------
        composed = env_prefix + argv_str
        if not _COMMAND_RE.match(composed):
            raise ValueError(f"CHK028 violation: {composed!r}")

        return composed


# ---------------------------------------------------------------------------
# plan_remediation() — pure planner function (NFR-004)
# ---------------------------------------------------------------------------


def plan_remediation(
    runtime: InstalledCliRuntime,
    intent: RemediationIntent,
    target_version: str | None,
    *,
    package_name: str = _PACKAGE_NAME,
    package_aliases: tuple[str, ...] = (),
    index_url: str | None = None,
    extra_index_url: str | None = None,
) -> RemediationCommand:
    """Return a :class:`RemediationCommand` for *runtime* and *intent*.

    NFR-004: Pure function — no I/O, no side effects.  Deterministic for
    the same inputs.  Callers that resolve a :class:`DistributionProfile`
    (e.g. ``build_upgrade_hint``) pass package/index knobs explicitly.

    Args:
        runtime: Immutable snapshot of the running installation.
        intent:  What the caller wants to achieve.
        target_version: Optional version specifier for the upgrade.  Only
            applied to UV_TOOL UPGRADE when the value matches
            ``^[A-Za-z0-9.\\-+]{1,64}$``.  Ignored for other methods.
        package_name: Distribution name for argv composition.
        package_aliases: Alternate names when matching uv receipt entries.
        index_url: Optional ``--index-url`` for pip/pipx/uv remediation.
        extra_index_url: Optional ``--extra-index-url`` for pip/pipx/uv.

    Returns:
        A :class:`RemediationCommand`.  For install methods that do not
        support automated remediation for the requested intent the returned
        command will have ``intent == MANUAL_GUIDANCE`` and ``argv == None``.
    """
    from specify_cli.compat._detect.install_method import InstallMethod  # deferred

    packaging = _RemediationPackaging(
        package_name=package_name,
        package_aliases=package_aliases,
        index_url=index_url,
        extra_index_url=extra_index_url,
    )
    install_method = runtime.install_method

    if install_method == InstallMethod.UV_TOOL:
        return _plan_uv_tool(runtime, intent, target_version, packaging)
    if install_method == InstallMethod.PIPX:
        return _plan_pipx(intent, packaging)
    if install_method == InstallMethod.BREW:
        return _plan_brew(intent, packaging)
    if install_method == InstallMethod.PIP_USER:
        return _plan_pip_user(intent, packaging)
    if install_method == InstallMethod.PIP_SYSTEM:
        return _plan_pip_system(intent, packaging)

    # SOURCE, UNKNOWN, SYSTEM_PACKAGE — no automated path
    note = _manual_note(str(install_method), intent)
    return RemediationCommand(
        intent=RemediationIntent.MANUAL_GUIDANCE,
        argv=None,
        env={},
        note=note,
    )


@dataclass(frozen=True)
class _RemediationPackaging:
    """Pure packaging knobs for remediation argv composition."""

    package_name: str = _PACKAGE_NAME
    package_aliases: tuple[str, ...] = ()
    index_url: str | None = None
    extra_index_url: str | None = None


def _index_argv_flags(packaging: _RemediationPackaging) -> tuple[str, ...]:
    """Return ``--index-url`` / ``--extra-index-url`` flags when set."""
    flags: list[str] = []
    if packaging.index_url:
        flags.extend(["--index-url", packaging.index_url])
    if packaging.extra_index_url:
        flags.extend(["--extra-index-url", packaging.extra_index_url])
    return tuple(flags)


def _with_index_before_package(
    argv: tuple[str, ...],
    packaging: _RemediationPackaging,
) -> tuple[str, ...]:
    """Insert index URL flags immediately before the final package token."""
    flags = _index_argv_flags(packaging)
    if not flags:
        return argv
    if not argv:
        return flags
    return argv[:-1] + flags + argv[-1:]


# ---------------------------------------------------------------------------
# Per-method planning helpers
# ---------------------------------------------------------------------------


def _plan_uv_tool(
    runtime: InstalledCliRuntime,
    intent: RemediationIntent,
    target_version: str | None,
    packaging: _RemediationPackaging,
) -> RemediationCommand:
    """Build a RemediationCommand for UV_TOOL installs."""
    if intent == RemediationIntent.REINSTALL_WITH_TEST:
        return _plan_uv_tool_reinstall(runtime, target_version, packaging)
    return _plan_uv_tool_upgrade(runtime, target_version, packaging)


def _pypi_package_arg(
    target_version: str | None,
    package_name: str,
) -> str:
    """``package_name``, version-pinned when *target_version* is valid (CHK)."""
    return (
        f"{package_name}=={target_version}"
        if target_version is not None and _VERSION_RE.match(target_version)
        else package_name
    )


def _plan_uv_tool_upgrade(
    runtime: InstalledCliRuntime,
    target_version: str | None,
    packaging: _RemediationPackaging,
) -> RemediationCommand:
    """UPGRADE intent: pin to the published release (provenance not preserved)."""
    pkg = _pypi_package_arg(target_version, packaging.package_name)

    base: tuple[str, ...] = ("uv", "tool", "install", "--force")
    if runtime.python is not None:
        base = base + ("--python", runtime.python)
    base = base + (pkg,)
    base = _with_index_before_package(base, packaging)

    return RemediationCommand(
        intent=RemediationIntent.UPGRADE, argv=base, env=_uv_tool_env(runtime), note=None
    )


def _plan_uv_tool_reinstall(
    runtime: InstalledCliRuntime,
    target_version: str | None,
    packaging: _RemediationPackaging,
) -> RemediationCommand:
    """REINSTALL_WITH_TEST: rebuild the install with pytest, preserving provenance."""
    env = _uv_tool_env(runtime)

    main_req = _find_main_requirement(runtime.requirements, packaging)
    if main_req is None:
        if runtime.receipt_path is None:
            return _uv_tool_reinstall_pypi_fallback(env, target_version, packaging)
        return RemediationCommand(
            intent=RemediationIntent.MANUAL_GUIDANCE,
            argv=None,
            env={},
            note=_UV_PROVENANCE_FALLBACK_NOTE,
        )

    package_args = _uv_main_package_args(main_req, packaging.package_name)
    with_args = _uv_with_args(runtime.requirements, packaging)
    if package_args is None or with_args is None:
        return RemediationCommand(
            intent=RemediationIntent.MANUAL_GUIDANCE,
            argv=None,
            env={},
            note=_UV_PROVENANCE_FALLBACK_NOTE,
        )

    argv: tuple[str, ...] = ("uv", "tool", "install", "--force")
    if runtime.python is not None:
        argv = argv + ("--python", runtime.python)
    argv = argv + tuple(with_args) + tuple(package_args)
    argv = _with_index_before_package(argv, packaging)

    return RemediationCommand(
        intent=RemediationIntent.REINSTALL_WITH_TEST,
        argv=argv,
        env=env,
        note=_UV_PROVENANCE_FALLBACK_NOTE,
    )


def _uv_tool_reinstall_pypi_fallback(
    env: dict[str, str],
    target_version: str | None,
    packaging: _RemediationPackaging,
) -> RemediationCommand:
    """Reinstall command when no source provenance is available (receipt absent)."""
    pkg = _pypi_package_arg(target_version, packaging.package_name)
    argv: tuple[str, ...] = ("uv", "tool", "install", "--force", "--with", _PYTEST_NAME, pkg)
    argv = _with_index_before_package(argv, packaging)
    return RemediationCommand(
        intent=RemediationIntent.REINSTALL_WITH_TEST,
        argv=argv,
        env=env,
        note=_UV_PROVENANCE_FALLBACK_NOTE,
    )


def _uv_tool_env(runtime: InstalledCliRuntime) -> dict[str, str]:
    """Env prefix for a uv-tool command: UV_TOOL_DIR / UV_TOOL_BIN_DIR when non-default.

    Order is load-bearing for byte-for-byte display fidelity: UV_TOOL_DIR
    first, UV_TOOL_BIN_DIR second (matches the legacy ``_uv_tool_env_values``).
    """
    env: dict[str, str] = {}
    if runtime.is_default_tool_dir is False and runtime.tool_dir is not None:
        env["UV_TOOL_DIR"] = str(runtime.tool_dir)
    if runtime.is_default_bin_dir is False and runtime.bin_dir is not None:
        env["UV_TOOL_BIN_DIR"] = str(runtime.bin_dir)
    return env


def _find_main_requirement(
    requirements: tuple[UvRequirement, ...],
    packaging: _RemediationPackaging,
) -> UvRequirement | None:
    """Return the main package requirement entry, or None if absent."""
    names = {packaging.package_name, *packaging.package_aliases}
    for req in requirements:
        if req.name in names:
            return req
    return None


def _uv_main_package_args(req: UvRequirement, package_name: str) -> list[str] | None:
    """Package args preserving the main package's source provenance.

    Returns None when the entry's shape is unsupported (the caller then
    refuses and shows manual guidance rather than re-pinning to PyPI).
    """
    if not req.is_supported:
        return None
    if req.directory is not None:
        return [req.directory]
    if req.editable is not None:
        return ["--editable", req.editable]
    if req.path is not None:
        return [req.path]
    if req.git is not None:
        return [package_name, "--from", _uv_git_source(req.git)]
    if req.url is not None:
        return [req.url]
    if req.specifier is not None:
        return [f"{package_name}{req.specifier}"]
    return [package_name]


def _uv_with_args(
    requirements: tuple[UvRequirement, ...],
    packaging: _RemediationPackaging,
) -> list[str] | None:
    """`--with`/`--with-editable` args for injected deps, ensuring pytest is present.

    Returns None when any injected dep has an unsupported shape (conservative).
    """
    names = {packaging.package_name, *packaging.package_aliases}
    args: list[str] = []
    has_pytest = False
    for req in requirements:
        if req.name in names:
            continue
        if req.name == _PYTEST_NAME:
            has_pytest = True
        dep_args = _uv_injected_dep_args(req)
        if dep_args is None:
            return None
        args.extend(dep_args)
    if not has_pytest:
        args.extend(["--with", _PYTEST_NAME])
    return args


def _uv_injected_dep_args(req: UvRequirement) -> list[str] | None:
    """`--with`/`--with-editable` args for a single injected dependency."""
    if not req.is_supported:
        return None
    if req.editable is not None:
        return ["--with-editable", req.editable]
    # _uv_injected_dep_source is total (always returns a non-empty str via the
    # name+specifier fallback), so no None guard is needed here (S2583).
    return ["--with", _uv_injected_dep_source(req)]


def _uv_injected_dep_source(req: UvRequirement) -> str:
    """Resolve the `--with` source token for an injected dependency."""
    if req.directory is not None:
        return req.directory
    if req.path is not None:
        return req.path
    if req.git is not None:
        return _uv_git_source(req.git)
    if req.url is not None:
        return req.url
    return f"{req.name}{req.specifier or ''}"


def _uv_git_source(git: str) -> str:
    """Normalize a git source to uv's ``git+`` URL form."""
    return git if git.startswith("git+") else f"git+{git}"


def _plan_pipx(
    intent: RemediationIntent,
    packaging: _RemediationPackaging,
) -> RemediationCommand:
    """Build a RemediationCommand for PIPX installs."""
    argv: tuple[str, ...]
    if intent == RemediationIntent.UPGRADE:
        argv = ("pipx", "upgrade", packaging.package_name)
    else:
        argv = ("pipx", "install", "--include-deps", f"{packaging.package_name}[test]")
    argv = _with_index_before_package(argv, packaging)
    return RemediationCommand(intent=intent, argv=argv, env={}, note=None)


def _plan_brew(
    intent: RemediationIntent,
    packaging: _RemediationPackaging,
) -> RemediationCommand:
    """Build a RemediationCommand for BREW installs (no index URL flags)."""
    if intent == RemediationIntent.UPGRADE:
        return RemediationCommand(
            intent=intent,
            argv=("brew", "upgrade", packaging.package_name),
            env={},
            note=None,
        )
    return RemediationCommand(
        intent=RemediationIntent.MANUAL_GUIDANCE,
        argv=None,
        env={},
        note=_manual_note("brew", intent),
    )


def _plan_pip_user(
    intent: RemediationIntent,
    packaging: _RemediationPackaging,
) -> RemediationCommand:
    """Build a RemediationCommand for PIP_USER installs."""
    if intent == RemediationIntent.UPGRADE:
        argv: tuple[str, ...] = ("pip", "install", "--user", "--upgrade", packaging.package_name)
        argv = _with_index_before_package(argv, packaging)
        return RemediationCommand(
            intent=intent,
            argv=argv,
            env={},
            note=None,
        )
    return RemediationCommand(
        intent=RemediationIntent.MANUAL_GUIDANCE,
        argv=None,
        env={},
        note=_manual_note("pip-user", intent),
    )


def _plan_pip_system(
    intent: RemediationIntent,
    packaging: _RemediationPackaging,
) -> RemediationCommand:
    """Build a RemediationCommand for PIP_SYSTEM installs."""
    if intent == RemediationIntent.UPGRADE:
        argv: tuple[str, ...] = ("pip", "install", "--upgrade", packaging.package_name)
        argv = _with_index_before_package(argv, packaging)
        return RemediationCommand(
            intent=intent,
            argv=argv,
            env={},
            note=None,
        )
    return RemediationCommand(
        intent=RemediationIntent.MANUAL_GUIDANCE,
        argv=None,
        env={},
        note=_manual_note("pip-system", intent),
    )


# ---------------------------------------------------------------------------
# Manual-guidance note catalogue
# ---------------------------------------------------------------------------

_MANUAL_NOTES: dict[str, dict[str, str]] = {
    RemediationIntent.UPGRADE: {
        "source": "Rebuild from source using your normal dev workflow.",
        "unknown": (
            "Reinstall spec-kitty-cli using your original install method. "
            f"See {INSTALL_AND_UPGRADE_URL} for guidance."
        ),
        "system-package": (
            "Use your system package manager to upgrade spec-kitty-cli."
        ),
    },
    RemediationIntent.REINSTALL_WITH_TEST: {
        "brew": (
            "Homebrew does not support test extras automatically. "
            "Run: pip install spec-kitty-cli[test] in a virtual environment."
        ),
        "pip-user": "Run: pip install --user spec-kitty-cli[test]",
        "pip-system": "Run: pip install spec-kitty-cli[test]",
        "source": "Run: pip install -e .[test] to reinstall with test extras.",
        "unknown": (
            "Install spec-kitty-cli with test extras using your original install method."
        ),
        "system-package": (
            "Use your system package manager to install spec-kitty-cli, "
            "then add test extras via pip."
        ),
    },
}


def _manual_note(install_method_str: str, intent: RemediationIntent) -> str:
    """Return a human-readable note for MANUAL_GUIDANCE cases."""
    return _MANUAL_NOTES.get(intent, {}).get(
        install_method_str,
        f"Manually manage spec-kitty-cli ({install_method_str}).",
    )
