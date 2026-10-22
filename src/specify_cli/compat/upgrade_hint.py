"""Upgrade-hint catalog for the upgrade-nag planner.

Public surface
--------------
UpgradeHint      -- frozen dataclass per data-model §1.8.
build_upgrade_hint -- factory function; one call per InstallMethod value.

Security properties enforced here
-----------------------------------
CHK028  ``command`` is sanitised against ``^[A-Za-z0-9 .\\-+_/=:]{1,512}$``
        at dataclass construction time; ANSI escapes and shell metacharacters
        are rejected.
CHK031  SOURCE and UNKNOWN hints carry ``command=None`` (a note instead),
        so they are never accidentally executed as shell commands.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from kernel.site_urls import INSTALL_AND_UPGRADE_URL
from specify_cli.compat._detect.install_method import InstallMethod
from specify_cli.compat.remediation import COMMAND_ALLOWLIST_MAX_LEN

# ---------------------------------------------------------------------------
# Validation regex (CHK028) — shared max length with remediation.py
# ---------------------------------------------------------------------------

_COMMAND_RE = re.compile(
    rf"^[A-Za-z0-9 .\-+_/=:]{{1,{COMMAND_ALLOWLIST_MAX_LEN}}}$"
)
_VERSION_RE = re.compile(r"^[A-Za-z0-9.\-+]{1,64}$")


# ---------------------------------------------------------------------------
# UpgradeHint dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UpgradeHint:
    """A sanitised, copy-pasteable (or manual) upgrade hint for a given install method.

    Exactly one of ``command`` or ``note`` is non-None (invariant enforced in
    ``__post_init__``).

    Attributes:
        install_method: The detected install method that produced this hint.
        command: A short shell command string the user can copy-paste to upgrade.
            ``None`` for install methods where a single runnable command is
            inappropriate (SOURCE, SYSTEM_PACKAGE, UNKNOWN).
        note: A human-readable multi-line instruction string.  ``None`` when
            ``command`` is set.
    """

    install_method: InstallMethod
    command: str | None
    note: str | None

    def __post_init__(self) -> None:
        """Validate the invariant and sanitise *command* if present."""
        if (self.command is None) == (self.note is None):
            raise ValueError(f"UpgradeHint: exactly one of 'command' or 'note' must be non-None; got command={self.command!r}, note={self.note!r}")
        if self.command is not None and not _COMMAND_RE.match(self.command):
            raise ValueError(
                f"UpgradeHint.command contains disallowed characters or is out of range: "
                f"{self.command!r}. "
                "Only [A-Za-z0-9 .\\-+_/=:] (1-512 chars) is permitted (CHK028)."
            )


# ---------------------------------------------------------------------------
# Static hint table
# ---------------------------------------------------------------------------

# Each entry: (command_or_None, note_or_None).
# Validated at module load time (any bad value raises ValueError immediately).
_HINT_TABLE: dict[InstallMethod, tuple[str | None, str | None]] = {
    InstallMethod.PIPX: (
        "pipx upgrade spec-kitty-cli",
        None,
    ),
    InstallMethod.UV_TOOL: (
        "uv tool install --force spec-kitty-cli",
        None,
    ),
    InstallMethod.PIP_USER: (
        "pip install --user --upgrade spec-kitty-cli",
        None,
    ),
    InstallMethod.PIP_SYSTEM: (
        "pip install --upgrade spec-kitty-cli",
        None,
    ),
    InstallMethod.BREW: (
        "brew upgrade spec-kitty-cli",
        None,
    ),
    InstallMethod.SYSTEM_PACKAGE: (
        None,
        ("Use your system package manager (apt/dnf/pacman/yum/zypper) to upgrade spec-kitty-cli."),
    ),
    InstallMethod.SOURCE: (
        None,
        "Rebuild from source: pip install -e . or use your normal dev workflow.",
    ),
    InstallMethod.UNKNOWN: (
        None,
        (
            "Your install method could not be detected automatically. "
            "Upgrade Spec Kitty using the same method you used to install it. "
            f"See {INSTALL_AND_UPGRADE_URL} for guidance."
        ),
    ),
}

_DEGRADED_PROFILE_NOTE = (
    "The configured distribution profile could not be loaded. Fix its "
    "spec_kitty.distribution_profile entry point before upgrading; no upgrade "
    "command is shown because the package source is unknown."
)

# Eagerly validate all table entries at import time so misconfiguration is
# caught before any runtime call.
for _method, (_cmd, _note) in _HINT_TABLE.items():
    UpgradeHint(install_method=_method, command=_cmd, note=_note)


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


def build_upgrade_hint(
    install_method: InstallMethod,
    *,
    package: str | None = None,
    target_version: str | None = None,
) -> UpgradeHint:
    """Return the :class:`UpgradeHint` for *install_method*.

    The returned hint satisfies the invariant that exactly one of ``command``
    or ``note`` is non-None.

    Implementation routes through ``plan_remediation()`` so that the planner
    path and the hint path share a single source of truth.  ``_HINT_TABLE``
    is retained as the authoritative fallback for MANUAL_GUIDANCE methods
    (SOURCE, UNKNOWN, SYSTEM_PACKAGE) to preserve the exact note strings
    (SC-003 / SC-006).

    Args:
        install_method: The detected :class:`InstallMethod`.
        package: Optional package-name override.  When ``None`` (default),
            uses the active :class:`DistributionProfile` package name.
        target_version: Optional latest version.  For uv-tool installs this
            is used to build a pinned upgrade command.

    Returns:
        A :class:`UpgradeHint` whose ``command`` / ``note`` is identical to
        the pre-migration static-table value for every install method on the
        stock profile (SC-003).
    """
    from dataclasses import replace as _replace  # stdlib — no circular import risk

    from specify_cli.compat._detect.runtime import detect_runtime  # deferred
    from specify_cli.compat.remediation import (  # deferred
        RemediationIntent,
        plan_remediation,
    )
    from specify_cli.distribution import (
        is_degraded_distribution_profile,
        resolve_distribution_profile,
    )

    profile = resolve_distribution_profile()
    if is_degraded_distribution_profile(profile):
        return UpgradeHint(
            install_method=install_method,
            command=None,
            note=_DEGRADED_PROFILE_NOTE,
        )

    package_name = profile.package_name if package is None else package

    runtime = detect_runtime()

    # When the caller supplies an install_method that differs from what
    # detect_runtime() found (e.g. tests that parametrise over all methods),
    # override the method so plan_remediation builds the correct argv while
    # preserving any uv-receipt details that may already be available.
    if runtime.install_method != install_method:
        runtime = _replace(runtime, install_method=install_method)

    # When the caller pins an explicit package (parity / stock tests), do not
    # inject profile index URLs — those belong to the profile-driven path.
    index_url = None if package is not None else profile.index_url
    extra_index_url = None if package is not None else profile.extra_index_url
    aliases: tuple[str, ...] = () if package is not None else profile.package_aliases

    cmd = plan_remediation(
        runtime,
        RemediationIntent.UPGRADE,
        target_version,
        package_name=package_name,
        package_aliases=aliases,
        index_url=index_url,
        extra_index_url=extra_index_url,
    )
    try:
        rendered = cmd.render(runtime.platform)
    except ValueError:
        # MANUAL_GUIDANCE or CHK028 violation — fall back to static table so
        # note strings remain byte-for-byte identical to the pre-migration values.
        command, note = _HINT_TABLE[install_method]
        return UpgradeHint(install_method=install_method, command=command, note=note)

    return UpgradeHint(install_method=install_method, command=rendered, note=None)


def current_upgrade_command(fallback: str = "pipx upgrade spec-kitty-cli") -> str:
    """Return the rendered upgrade command for the running install, or *fallback*.

    Convenience wrapper (does I/O via ``detect_runtime``) for callers that only
    need a copy-pasteable upgrade string. Routes through the single planner so
    every remediation surface shares one source of truth (issue #1358 "use one
    planner"); collapses the previously duplicated detect→plan→render→fallback
    block in ``core/version_checker.py`` and ``migration/schema_version.py``.
    """
    from specify_cli.compat._detect.runtime import detect_runtime  # deferred
    from specify_cli.compat.remediation import (  # deferred
        RemediationIntent,
        plan_remediation,
    )

    runtime = detect_runtime()
    cmd = plan_remediation(runtime, RemediationIntent.UPGRADE, target_version=None)
    try:
        return cmd.render(runtime.platform)
    except ValueError:
        return fallback
