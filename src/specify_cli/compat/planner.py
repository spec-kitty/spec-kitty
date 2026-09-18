"""Compatibility planner for spec-kitty CLI upgrade-nag and project-migration gate.

This module implements:
- All core dataclasses (T021): Decision, Fr023Case, ProjectState, CliStatus,
  ProjectStatus, MigrationStep, Plan, Invocation.
- ``decide()`` — pure truth-table function (T023).
- ``plan()`` — the main entry point that assembles a Plan (T024).

Design notes
------------
- ``decide()`` is pure (no I/O).
- ``plan()`` body is wrapped in a fail-closed try/except that returns a
  BLOCK_PROJECT_CORRUPT Plan on any unexpected exception.
- ``Invocation.from_argv()`` is a best-effort parser; it never raises.
"""

from __future__ import annotations

import contextlib
import logging
import os
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from collections.abc import Callable, Mapping

from kernel.clock import datetime, now_utc

# StrEnum is stdlib 3.11+
from enum import StrEnum

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# CI environment helper (single source of truth for all call sites)
# ---------------------------------------------------------------------------


def is_ci_env() -> bool:
    """Return True if the current environment indicates CI / non-interactive mode.

    Used by the planner, the typer callback, and the gate. Single source of truth
    so all call sites agree on what 'CI' means.
    """
    raw = os.environ.get("CI", "")
    return bool(raw and raw.strip().lower() not in ("0", "false", "no", "off", ""))


# ---------------------------------------------------------------------------
# Migration registry auto-load guard
# ---------------------------------------------------------------------------

_REGISTRY_AUTOLOADED = False

_LOGGER = logging.getLogger(__name__)


def _ensure_registry_loaded() -> None:
    """Auto-discover migrations once per process, fail-open on any error.

    A stale ``.pyc`` from an interrupted install (Windows file locking /
    antivirus) can kill the whole ``specify_cli.upgrade`` import chain before
    discovery even runs; that failure class is self-healed once — cache purge
    plus retry — before degrading (#4124, ``specify_cli.bytecode_heal``). Any
    remaining failure degrades *loudly* to an empty registry: the upgrade
    nag/preview quietly goes away either way, but the operator now gets one
    warning saying why, and the manual fix.
    """
    global _REGISTRY_AUTOLOADED
    if _REGISTRY_AUTOLOADED:
        return
    try:
        _load_migration_registry_with_heal()
    except Exception as exc:  # noqa: BLE001 — fail-open: empty pending_migrations is preferable to crash
        _LOGGER.warning(
            "upgrade migrations unavailable: %s. If this persists, delete the "
            "__pycache__ directories under the installed specify_cli package "
            "and reinstall spec-kitty. Continuing without the upgrade check.",
            exc,
        )
    finally:
        _REGISTRY_AUTOLOADED = True


def _load_migration_registry_with_heal() -> None:
    """Import and auto-discover migrations, healing a stale bytecode cache once."""
    from specify_cli.bytecode_heal import invoke_with_bytecode_heal

    def _load() -> None:
        from specify_cli.upgrade.migrations import auto_discover_migrations

        auto_discover_migrations()

    invoke_with_bytecode_heal(
        _load,
        on_healed=lambda removed: _LOGGER.warning(
            "repaired %d stale bytecode cache file(s) left by an interrupted install; migrations reloaded from source",
            removed,
        ),
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Decision(StrEnum):
    """Planner decision; maps 1:1 to an exit-code policy and an FR-023 case."""

    ALLOW = "ALLOW"
    ALLOW_WITH_NAG = "ALLOW_WITH_NAG"
    BLOCK_PROJECT_MIGRATION = "BLOCK_PROJECT_MIGRATION"
    BLOCK_CLI_UPGRADE = "BLOCK_CLI_UPGRADE"
    BLOCK_PROJECT_CORRUPT = "BLOCK_PROJECT_CORRUPT"
    BLOCK_INCOMPATIBLE_FLAGS = "BLOCK_INCOMPATIBLE_FLAGS"


class Fr023Case(StrEnum):
    """Stable JSON token for the FR-023 case.

    See data-model §1.9.  These values appear in ``rendered_json["case"]``
    and golden test files.  Adding a new case requires a minor-version bump.
    """

    NONE = "none"
    CLI_UPDATE_AVAILABLE = "cli_update_available"
    PROJECT_MIGRATION_NEEDED = "project_migration_needed"
    PROJECT_TOO_NEW_FOR_CLI = "project_too_new_for_cli"
    PROJECT_NOT_INITIALIZED = "project_not_initialized"
    PROJECT_METADATA_CORRUPT = "project_metadata_corrupt"
    INSTALL_METHOD_UNKNOWN = "install_method_unknown"


class ProjectState(StrEnum):
    """State of the project detected by the planner.

    See data-model §1.4.
    """

    NO_PROJECT = "no_project"
    UNINITIALIZED = "uninitialized"
    LEGACY = "legacy"
    STALE = "stale"
    COMPATIBLE = "compatible"
    TOO_NEW = "too_new"
    CORRUPT = "corrupt"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CliStatus:
    """Snapshot of the CLI's version status.

    Attributes:
        installed_version: Version string from importlib.metadata.
        latest_version: Latest version from provider, or None.
        latest_source: Where the latest version came from.
        is_outdated: True iff parse(latest) > parse(installed).
        fetched_at: When the latest lookup completed, or None.
    """

    installed_version: str
    latest_version: str | None
    latest_source: Literal["pypi", "simple_index", "none"]
    is_outdated: bool
    fetched_at: datetime | None


@dataclass(frozen=True)
class ProjectStatus:
    """Snapshot of the project's schema compatibility state.

    Attributes:
        state: Computed ProjectState.
        project_root: Absolute path to project root, or None.
        schema_version: Integer from .kittify/metadata.yaml, or None.
        min_supported: MIN_SUPPORTED_SCHEMA at this build.
        max_supported: MAX_SUPPORTED_SCHEMA at this build.
        metadata_error: Short human description when state == CORRUPT.
    """

    state: ProjectState
    project_root: Path | None
    schema_version: int | None
    min_supported: int
    max_supported: int
    metadata_error: str | None


@dataclass(frozen=True)
class MigrationStep:
    """One step in the pending migration plan.

    Attributes:
        migration_id: Stable slug (e.g. ``"m_3_0_0_canonical_context"``).
        target_schema_version: Schema version this migration targets.
        description: One-line human description.
        files_modified: Files this migration would touch, or None.
    """

    migration_id: str
    target_schema_version: int
    description: str
    files_modified: tuple[Path, ...] | None


@dataclass(frozen=True)
class Plan:
    """Immutable result of ``plan()``.

    Every CLI surface consumes this object.  See data-model §1.1.

    Attributes:
        decision: Planner decision.
        cli_status: CLI version snapshot.
        project_status: Project schema snapshot.
        safety: Safety classification of the invocation.
        pending_migrations: Ordered migration steps (non-empty iff
            decision == BLOCK_PROJECT_MIGRATION).
        install_method: Detected install method.
        upgrade_hint: Upgrade hint for the detected install method.
        fr023_case: Stable FR-023 JSON token.
        exit_code: Exit code the CLI should use.
        rendered_human: Ready-for-stdout single message (≤4 lines).
        rendered_json: Ready-for-``--json``; matches compat-planner.json.
    """

    decision: Decision
    cli_status: CliStatus
    project_status: ProjectStatus
    safety: Any  # Safety enum from compat.safety (avoid circular import)
    pending_migrations: tuple[MigrationStep, ...]
    install_method: Any  # InstallMethod enum from compat._detect
    upgrade_hint: Any  # UpgradeHint dataclass from compat.upgrade_hint
    fr023_case: Fr023Case
    exit_code: int
    rendered_human: str
    rendered_json: dict[str, Any]


@dataclass(frozen=True)
class Invocation:
    """Parsed representation of a single CLI invocation.

    Attributes:
        command_path: Tuple of path segments, e.g. ``("upgrade",)``.
        raw_args: Post-parse argv excluding the program name.
        is_help: ``--help`` / ``-h`` was present.
        is_version: ``--version`` was present.
        flag_no_nag: ``--no-nag`` was present.
        env_ci: ``CI`` env var is set and truthy.
        stdout_is_tty: ``sys.stdout.isatty()`` at invocation time.
    """

    command_path: tuple[str, ...]
    raw_args: tuple[str, ...]
    is_help: bool
    is_version: bool
    flag_no_nag: bool
    env_ci: bool
    stdout_is_tty: bool

    # ------------------------------------------------------------------
    # Classmethods
    # ------------------------------------------------------------------

    @classmethod
    def from_argv(cls, argv: list[str] | None = None) -> Invocation:
        """Best-effort parse of an argv list into an Invocation.

        Parses the first non-flag positional tokens as ``command_path``.
        All remaining tokens become ``raw_args``.

        Args:
            argv: Argument list to parse.  Defaults to ``sys.argv[1:]``.

        Returns:
            A new :class:`Invocation`.  Never raises.
        """
        if argv is None:
            argv = sys.argv[1:]

        args = list(argv)
        is_help = "--help" in args or "-h" in args
        is_version = bool(args[:1]) and args[0] in {"--version", "-v"}
        flag_no_nag = "--no-nag" in args
        env_ci = is_ci_env()

        try:
            stdout_is_tty = sys.stdout.isatty()
        except Exception:  # noqa: BLE001
            stdout_is_tty = False

        # Extract command path: leading tokens that don't start with '-'
        command_parts: list[str] = []
        rest: list[str] = []
        passed_command = False
        for token in args:
            if not passed_command and not token.startswith("-"):
                command_parts.append(token)
            else:
                passed_command = True
                rest.append(token)

        return cls(
            command_path=tuple(command_parts),
            raw_args=tuple(rest),
            is_help=is_help,
            is_version=is_version,
            flag_no_nag=flag_no_nag,
            env_ci=env_ci,
            stdout_is_tty=stdout_is_tty,
        )

    # ------------------------------------------------------------------
    # Predicates
    # ------------------------------------------------------------------

    def suppresses_nag(self) -> bool:
        """Return True if nag output should be suppressed for this invocation.

        Suppression conditions (any one is sufficient):
        - ``--no-nag`` flag is present.
        - ``CI`` environment variable is set.
        - stdout is not a TTY for passive invocations.
        - ``--help`` or ``--version`` is present.

        Explicit ``upgrade --cli`` guidance remains visible in pipes and CI.
        """
        if "--cli" in self.raw_args:
            return self.flag_no_nag or self.is_help or self.is_version
        return self.flag_no_nag or self.env_ci or (not self.stdout_is_tty) or self.is_help or self.is_version

    def suppresses_network(self) -> bool:
        """Return True if network requests should be suppressed for this invocation.

        Used to select NoNetworkProvider in ``plan()`` defaults.

        Suppression conditions:
        - ``CI`` environment variable is set.
        - stdout is not a TTY.
        - ``--no-nag`` flag is present.
        """
        return self.env_ci or (not self.stdout_is_tty) or self.flag_no_nag


# ---------------------------------------------------------------------------
# Pure decision function (T023)
# ---------------------------------------------------------------------------

_EXIT_CODE_MAP: dict[Decision, int] = {
    Decision.ALLOW: 0,
    Decision.ALLOW_WITH_NAG: 0,
    Decision.BLOCK_PROJECT_MIGRATION: 4,
    Decision.BLOCK_CLI_UPGRADE: 5,
    Decision.BLOCK_PROJECT_CORRUPT: 6,
    Decision.BLOCK_INCOMPATIBLE_FLAGS: 2,
}


def decide(
    project: ProjectStatus,
    safety: Any,
    cli: CliStatus,
    invocation: Invocation,
) -> tuple[Decision, Fr023Case]:
    """Pure truth-table function implementing data-model §2.

    Rows are checked top-to-bottom; the first matching row wins.

    Args:
        project: Project status snapshot.
        safety: Safety classification from ``compat.safety.classify``.
        cli: CLI version snapshot.
        invocation: Current invocation context.

    Returns:
        A ``(Decision, Fr023Case)`` tuple.
    """
    from specify_cli.compat.safety import Safety

    state = project.state

    # Help and version output must remain available for every command path,
    # including otherwise-unsafe commands in stale or too-new projects.
    if invocation.is_help or invocation.is_version:
        return Decision.ALLOW, Fr023Case.NONE

    # Row 1: CORRUPT (any safety) → block
    if state == ProjectState.CORRUPT:
        return Decision.BLOCK_PROJECT_CORRUPT, Fr023Case.PROJECT_METADATA_CORRUPT

    # Row 2: TOO_NEW + UNSAFE → block CLI upgrade
    if state == ProjectState.TOO_NEW and safety == Safety.UNSAFE:
        return Decision.BLOCK_CLI_UPGRADE, Fr023Case.PROJECT_TOO_NEW_FOR_CLI

    # Row 3: STALE or LEGACY + UNSAFE → block project migration
    if state in (ProjectState.STALE, ProjectState.LEGACY) and safety == Safety.UNSAFE:
        return Decision.BLOCK_PROJECT_MIGRATION, Fr023Case.PROJECT_MIGRATION_NEEDED

    # Row 4: UNINITIALIZED or NO_PROJECT + UNSAFE → allow with PROJECT_NOT_INITIALIZED label.
    # Decision stays ALLOW (do not block — the user can still init or use --cli);
    # the case label lets JSON consumers distinguish this from a generic ALLOW.
    if state in (ProjectState.NO_PROJECT, ProjectState.UNINITIALIZED) and safety == Safety.UNSAFE:
        return Decision.ALLOW, Fr023Case.PROJECT_NOT_INITIALIZED

    # Row 5: nag / allow check
    if cli.is_outdated and not invocation.suppresses_nag():
        return Decision.ALLOW_WITH_NAG, Fr023Case.CLI_UPDATE_AVAILABLE

    return Decision.ALLOW, Fr023Case.NONE


# ---------------------------------------------------------------------------
# plan() entry point (T024)
# ---------------------------------------------------------------------------

_MAX_METADATA_BYTES = 262_144  # 256 KiB


def _get_schema_bounds() -> tuple[int, int]:
    """Return (min_supported, max_supported) schema version bounds.

    Defensively reads from ``specify_cli.migration.schema_version``.
    Falls back gracefully if WP07 has not added the new attrs yet.
    """
    try:
        from specify_cli.migration import schema_version as sv

        min_s = getattr(sv, "MIN_SUPPORTED_SCHEMA", None)
        max_s = getattr(sv, "MAX_SUPPORTED_SCHEMA", None)

        if min_s is None or max_s is None:
            # Fall back to REQUIRED_SCHEMA_VERSION
            req = getattr(sv, "REQUIRED_SCHEMA_VERSION", None)
            if req is not None:
                return (int(req), int(req))
            return (0, 999)

        return (int(min_s), int(max_s))

    except Exception:  # noqa: BLE001
        return (0, 999)


def _get_installed_version() -> str:
    """Return the installed CLI distribution version, or 'unknown'.

    Uses the active :class:`DistributionProfile` package name and aliases
    via :func:`resolve_installed_distribution_version`.
    """
    from specify_cli.distribution import (
        resolve_distribution_profile,
        resolve_installed_distribution_version,
    )

    profile = resolve_distribution_profile()
    return resolve_installed_distribution_version(
        profile.package_name,
        profile.package_aliases,
    )


_CACHEABLE_LATEST_SOURCES: frozenset[str] = frozenset({"pypi", "simple_index"})


def _default_latest_provider(*, network_suppressed: bool, profile: Any) -> Any:
    """Select the default latest-version provider for ``plan()``.

    When network is suppressed, always use :class:`NoNetworkProvider`.
    Otherwise prefer ``profile.upgrade_provider``, then
    :func:`resolve_upgrade_provider` (stock PyPI fallback).
    """
    from specify_cli.compat.provider import NoNetworkProvider, PyPIProvider
    from specify_cli.distribution import resolve_upgrade_provider

    if network_suppressed:
        return NoNetworkProvider()
    if profile.upgrade_provider is not None:
        return profile.upgrade_provider
    try:
        return resolve_upgrade_provider()
    except Exception:  # noqa: BLE001 — fail-open to stock PyPI
        return PyPIProvider()


def _write_nag_cache_for_fetch(
    *,
    nag_cache: Any,
    preference_record: Any,
    installed_version: str,
    latest_version: str,
    latest_source: Literal["pypi", "simple_index"],
    now: datetime,
) -> None:
    """Persist a successful provider fetch into the nag cache."""
    from specify_cli.compat.cache import NagCacheRecord

    if preference_record is not None:
        new_record = replace(
            preference_record,
            cli_version_key=installed_version,
            latest_version=latest_version,
            latest_source=latest_source,
            fetched_at=now,
            last_shown_at=preference_record.last_shown_at,
        )
    else:
        new_record = NagCacheRecord(
            cli_version_key=installed_version,
            latest_version=latest_version,
            latest_source=latest_source,
            fetched_at=now,
            last_shown_at=None,
        )
    with contextlib.suppress(Exception):
        nag_cache.write(new_record)


def _version_is_outdated(installed: str, latest: str | None) -> bool:
    """Return True iff parse(latest) > parse(installed).

    Never raises; returns False on any parse error.
    """
    if latest is None:
        return False
    try:
        from packaging.version import Version

        return Version(latest) > Version(installed)
    except Exception:  # noqa: BLE001
        return False


def _scan_project(
    project_root_resolver: Callable[[Path], Path | None],
    min_supported: int,
    max_supported: int,
) -> ProjectStatus:
    """Scan the project state by walking from cwd upward.

    Args:
        project_root_resolver: Callable(start: Path) → Path | None.
        min_supported: Minimum supported schema version.
        max_supported: Maximum supported schema version.

    Returns:
        A :class:`ProjectStatus`.
    """
    try:
        project_root = project_root_resolver(Path.cwd())
    except Exception:  # noqa: BLE001
        return ProjectStatus(
            state=ProjectState.NO_PROJECT,
            project_root=None,
            schema_version=None,
            min_supported=min_supported,
            max_supported=max_supported,
            metadata_error=None,
        )

    if project_root is None:
        return ProjectStatus(
            state=ProjectState.NO_PROJECT,
            project_root=None,
            schema_version=None,
            min_supported=min_supported,
            max_supported=max_supported,
            metadata_error=None,
        )

    metadata_path = project_root / ".kittify" / "metadata.yaml"

    # No .kittify/ or missing metadata → UNINITIALIZED
    if not metadata_path.exists():
        return ProjectStatus(
            state=ProjectState.UNINITIALIZED,
            project_root=project_root,
            schema_version=None,
            min_supported=min_supported,
            max_supported=max_supported,
            metadata_error=None,
        )

    # Size guard: refuse > 256 KiB (CHK020)
    try:
        file_size = metadata_path.stat().st_size
    except OSError as exc:
        return ProjectStatus(
            state=ProjectState.CORRUPT,
            project_root=project_root,
            schema_version=None,
            min_supported=min_supported,
            max_supported=max_supported,
            metadata_error=f"stat failed: {exc}",
        )

    if file_size > _MAX_METADATA_BYTES:
        return ProjectStatus(
            state=ProjectState.CORRUPT,
            project_root=project_root,
            schema_version=None,
            min_supported=min_supported,
            max_supported=max_supported,
            metadata_error="oversized",
        )

    # Read schema version
    try:
        from specify_cli.migration.schema_version import get_project_schema_version

        schema_version = get_project_schema_version(project_root)
    except Exception as exc:  # noqa: BLE001
        return ProjectStatus(
            state=ProjectState.CORRUPT,
            project_root=project_root,
            schema_version=None,
            min_supported=min_supported,
            max_supported=max_supported,
            metadata_error=f"read error: {exc}",
        )

    # No schema_version field → LEGACY
    if schema_version is None:
        return ProjectStatus(
            state=ProjectState.LEGACY,
            project_root=project_root,
            schema_version=None,
            min_supported=min_supported,
            max_supported=max_supported,
            metadata_error=None,
        )

    # Validate integer in [0, 1000] (CHK021)
    if not isinstance(schema_version, int) or not (0 <= schema_version <= 1000):
        return ProjectStatus(
            state=ProjectState.CORRUPT,
            project_root=project_root,
            schema_version=None,
            min_supported=min_supported,
            max_supported=max_supported,
            metadata_error=f"schema_version out of range: {schema_version!r}",
        )

    # Map to ProjectState
    if schema_version < min_supported:
        state = ProjectState.STALE
    elif schema_version > max_supported:
        state = ProjectState.TOO_NEW
    else:
        state = ProjectState.COMPATIBLE

    return ProjectStatus(
        state=state,
        project_root=project_root,
        schema_version=schema_version,
        min_supported=min_supported,
        max_supported=max_supported,
        metadata_error=None,
    )


def _migration_step_from(migration: Any) -> MigrationStep:
    """Convert a registry ``BaseMigration`` into a contract ``MigrationStep``.

    ``target_schema_version`` is read from the migration when present and
    otherwise inferred best-effort from the target version's major component so
    the JSON contract always carries an integer.

    Args:
        migration: A registry migration instance.

    Returns:
        The corresponding :class:`MigrationStep`.
    """
    schema_int: int | None = getattr(migration, "target_schema_version", None)
    if schema_int is None:
        try:
            from packaging.version import Version

            schema_int = int(Version(migration.target_version).major)
        except Exception:  # noqa: BLE001
            schema_int = 0

    files_raw = getattr(migration, "files_modified", None)
    files: tuple[Path, ...] | None = None
    if files_raw is not None:
        try:
            files = tuple(Path(f) for f in files_raw)
        except Exception:  # noqa: BLE001
            files = None

    return MigrationStep(
        migration_id=str(migration.migration_id),
        target_schema_version=int(schema_int),
        description=str(getattr(migration, "description", "")),
        files_modified=files,
    )


def _pending_migrations_for(
    project: ProjectStatus, target_version: str | None = None
) -> tuple[MigrationStep, ...]:
    """Return the pending migration steps a real upgrade run would apply.

    Drives the preview through the *same* selector the real run uses
    (:meth:`VersionDetector.applicable_migrations` →
    :meth:`MigrationRegistry.get_applicable`) so the compat preview can never
    diverge from the applied set (FR-009). When ``target_version`` is omitted it
    defaults to the installed CLI version, matching the real run's default
    target.

    Returns an empty tuple when the project root is unknown or the registry is
    unavailable (fail-open: an empty preview beats a crash).

    Args:
        project: Project status snapshot.
        target_version: Version the real run would target; defaults to the
            installed CLI version.

    Returns:
        Tuple of :class:`MigrationStep` instances, in application order.
    """
    _ensure_registry_loaded()
    if project.project_root is None:
        return ()
    if target_version is None:
        from specify_cli import __version__

        target_version = __version__
    try:
        from specify_cli.upgrade.detector import VersionDetector

        migrations = VersionDetector(project.project_root).applicable_migrations(target_version)
        return tuple(_migration_step_from(m) for m in migrations)
    except Exception:  # noqa: BLE001
        return ()


def plan(
    invocation: Invocation,
    *,
    latest_version_provider: Any = None,
    nag_cache: Any = None,
    config: Any = None,
    now: datetime | None = None,
    project_root_resolver: Callable[[Path], Path | None] | None = None,
    read_only: bool = False,
    query_latest: bool = False,
    include_migrations: bool = True,
) -> Plan:
    """Build the compatibility plan for this invocation.

    This is the main entry point for the planner.  The entire body is wrapped
    in a fail-closed try/except that returns a BLOCK_PROJECT_CORRUPT Plan on
    any unexpected exception.

    Args:
        invocation: The parsed invocation context.
        latest_version_provider: Override for the version provider.
            Defaults to :class:`NoNetworkProvider` when
            ``invocation.suppresses_network()`` else :class:`PyPIProvider`.
        nag_cache: Override for the nag cache.
            Defaults to ``NagCache.default()``.
        config: Override for the upgrade configuration.
            Defaults to ``UpgradeConfig.load()``.
        now: Override for the current UTC datetime (for testing).
            Defaults to ``datetime.now(timezone.utc)``.
        project_root_resolver: Override for the project root resolver.
            Defaults to ``locate_project_root`` from
            ``specify_cli.core.project_resolver``.
        read_only: Read existing cache only; never fetch or persist data unless
            ``query_latest`` is set for an explicit upgrade query.
        query_latest: Resolve the latest CLI version for a user-requested upgrade
            query, including piped/CI output. With ``read_only``, the cache is
            never written.
        include_migrations: False when the upgrade caller owns validated target
            selection, so invalid targets cannot trigger implicit discovery.

    Returns:
        A :class:`Plan`.  Never raises.
    """
    try:
        return _plan_impl(
            invocation,
            latest_version_provider=latest_version_provider,
            nag_cache=nag_cache,
            config=config,
            now=now,
            project_root_resolver=project_root_resolver,
            read_only=read_only,
            query_latest=query_latest,
            include_migrations=include_migrations,
        )
    except Exception:  # noqa: BLE001 — fail-closed
        # Build the minimal fail-closed plan
        from specify_cli.compat._detect.install_method import InstallMethod
        from specify_cli.compat.safety import Safety
        from specify_cli.compat.upgrade_hint import build_upgrade_hint

        try:
            install_method = InstallMethod.UNKNOWN
            upgrade_hint = build_upgrade_hint(install_method)
        except Exception:  # noqa: BLE001
            from specify_cli.compat.upgrade_hint import UpgradeHint

            install_method = InstallMethod.UNKNOWN
            upgrade_hint = UpgradeHint(
                install_method=InstallMethod.UNKNOWN,
                command=None,
                note="Install method unknown.",
            )

        minimal_cli = CliStatus(
            installed_version=_get_installed_version(),
            latest_version=None,
            latest_source="none",
            is_outdated=False,
            fetched_at=None,
        )
        minimal_project = ProjectStatus(
            state=ProjectState.CORRUPT,
            project_root=None,
            schema_version=None,
            min_supported=0,
            max_supported=999,
            metadata_error="planner_error",
        )
        human = "Spec Kitty internal error in compatibility planner; refusing to run unsafe commands."
        rendered_json: dict[str, Any] = {
            "schema_version": 1,
            "case": Fr023Case.PROJECT_METADATA_CORRUPT,
            "decision": Decision.BLOCK_PROJECT_CORRUPT,
            "exit_code": 6,
            "cli": {
                "installed_version": minimal_cli.installed_version,
                "latest_version": None,
                "latest_source": "none",
                "is_outdated": False,
                "fetched_at": None,
            },
            "project": {
                "state": ProjectState.CORRUPT,
                "project_root": None,
                "schema_version": None,
                "min_supported": 0,
                "max_supported": 999,
                "metadata_error": "planner_error",
            },
            "safety": Safety.UNSAFE,
            "install_method": install_method,
            "upgrade_hint": {
                "install_method": install_method,
                "command": upgrade_hint.command,
                "note": upgrade_hint.note,
            },
            "pending_migrations": [],
            "rendered_human": human,
        }
        return Plan(
            decision=Decision.BLOCK_PROJECT_CORRUPT,
            cli_status=minimal_cli,
            project_status=minimal_project,
            safety=Safety.UNSAFE,
            pending_migrations=(),
            install_method=install_method,
            upgrade_hint=upgrade_hint,
            fr023_case=Fr023Case.PROJECT_METADATA_CORRUPT,
            exit_code=6,
            rendered_human=human,
            rendered_json=rendered_json,
        )


def _call_provider_get_latest(provider: Any, package: str, *, prerelease: bool) -> Any:
    """Call ``provider.get_latest``, threading *prerelease* only when supported (T022).

    ``LatestVersionProvider`` is a structural ``Protocol`` (``compat/
    provider.py``) whose stock implementations (``PyPIProvider``,
    ``SimpleIndexProvider``, ``NoNetworkProvider``, ``FakeLatestVersion
    Provider``) all accept ``prerelease`` as of this WP. A handful of ad-hoc
    test doubles elsewhere in the suite predate that parameter and are
    outside this WP's file ownership, so the call introspects the target's
    signature rather than assuming the new keyword exists everywhere —
    an unconditional ``prerelease=`` call would raise ``TypeError`` against
    those legacy doubles.
    """
    import inspect

    params: Mapping[str, inspect.Parameter]
    try:
        params = inspect.signature(provider.get_latest).parameters
    except (TypeError, ValueError):  # pragma: no cover - defensive
        params = {}
    accepts_prerelease = "prerelease" in params or any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()
    )
    if accepts_prerelease:
        return provider.get_latest(package, prerelease=prerelease)
    return provider.get_latest(package)


def _resolve_latest_version(
    *,
    cache_data_fresh: bool,
    cache_record: Any,
    preference_record: Any,
    latest_version_provider: Any,
    profile: Any,
    nag_cache: Any,
    installed_version: str,
    now: datetime,
    prerelease: bool = False,
    read_only: bool = False,
    query_latest: bool = False,
) -> tuple[str | None, Literal["pypi", "simple_index", "none"], datetime | None]:
    """Return ``(latest_version, cli_source, fetched_at)`` for the CLI status.

    Fresh-cache fast path (NFR-001) trusts cached version data without a network
    call; otherwise fetch from the provider, classify the source, update the
    cache on a cacheable hit, and fall back to the cached version when the
    provider returns nothing useful. Extracted from ``_plan_impl`` (keeps it
    under the complexity ceiling and gives the fetch/source-classification a
    directly testable seam).

    Args:
        installed_version: The cache key written to ``NagCacheRecord.
            cli_version_key`` on a fetch. Callers pass the channel-folded
            composite key (T023) here, not necessarily the raw installed CLI
            version string — see ``_cache_version_key``.
        prerelease: Single-read channel bool (T021/T022), threaded down to
            ``latest_version_provider.get_latest`` unchanged. Default False
            reproduces the pre-WP05 provider call byte-for-byte (C-CHN-1).
    """
    if read_only and not query_latest:
        if cache_record is not None and cache_record.latest_source == "pypi":
            return cache_record.latest_version, "pypi", cache_record.fetched_at
        return None, "none", None
    if cache_data_fresh:
        # Cache data is fresh — trust it; no network call.
        latest_version = cache_record.latest_version if cache_record is not None else None
        cli_source: Literal["pypi", "simple_index", "none"] = (
            cache_record.latest_source if cache_record is not None else "none"
        )
        return latest_version, cli_source, None

    # Cache stale or missing — fetch from provider.
    latest_result = _call_provider_get_latest(
        latest_version_provider, profile.package_name, prerelease=prerelease
    )
    source = latest_result.source
    latest_version = latest_result.version

    cacheable_source: Literal["pypi", "simple_index"] | None = None
    if source == "pypi":
        cacheable_source = "pypi"
    elif source == "simple_index":
        cacheable_source = "simple_index"

    fetched_at = now if cacheable_source is not None else None

    # If we got a version from a cacheable source, update the cache
    # (preserve last_shown_at / user preferences).
    if cacheable_source is not None and latest_version is not None and not read_only:
        _write_nag_cache_for_fetch(
            nag_cache=nag_cache,
            preference_record=preference_record,
            installed_version=installed_version,
            latest_version=latest_version,
            latest_source=cacheable_source,
            now=now,
        )
    elif cache_record is not None and cache_record.latest_version is not None:
        # Provider returned nothing useful — fall back to cached version.
        latest_version = cache_record.latest_version
        fetched_at = None  # not fetched this run

    if cacheable_source is not None:
        cli_source = cacheable_source
    elif cache_record is not None:
        cli_source = cache_record.latest_source
    else:
        cli_source = "none"

    return latest_version, cli_source, fetched_at


_PRERELEASE_CACHE_KEY_SUFFIX = "#prerelease"


def _cache_version_key(installed_version: str, *, prerelease: bool) -> str:
    """Fold the release channel into the nag-cache version key (T023).

    Default (stable, ``prerelease=False``) returns *installed_version*
    unchanged — the nag-cache freshness check is byte-identical to the
    pre-WP05 behaviour (C-CHN-1). When the rc channel is opted into, a
    suffix is appended so a cache record written under the other channel no
    longer matches ``cli_version_key``: the FR-025-style invalidation check
    in ``_plan_impl`` then treats the cache as stale and forces a fresh
    provider call instead of silently reusing stable-channel (or stale
    rc-channel) data across a channel toggle.
    """
    return f"{installed_version}{_PRERELEASE_CACHE_KEY_SUFFIX}" if prerelease else installed_version


def _plan_impl(
    invocation: Invocation,
    *,
    latest_version_provider: Any,
    nag_cache: Any,
    config: Any,
    now: datetime | None,
    project_root_resolver: Callable[[Path], Path | None] | None,
    read_only: bool = False,
    query_latest: bool = False,
    include_migrations: bool = True,
) -> Plan:
    """Inner implementation of plan() — may raise; caller wraps in try/except."""
    from specify_cli.compat._detect.runtime import detect_runtime
    from specify_cli.compat.cache import NagCache, NagCacheRecord
    from specify_cli.compat.config import UpgradeConfig
    from specify_cli.compat.provider import (
        FakeLatestVersionProvider,  # noqa: F401
    )
    from specify_cli.compat.safety import classify
    from specify_cli.compat.upgrade_hint import build_upgrade_hint
    from specify_cli.core.channel import prerelease_enabled
    from specify_cli.distribution import resolve_distribution_profile

    # Defaults
    if now is None:
        now = now_utc()

    if config is None:
        config = UpgradeConfig.load()

    if nag_cache is None:
        nag_cache = NagCache.default()

    if project_root_resolver is None:
        from specify_cli.core.project_resolver import locate_project_root

        project_root_resolver = locate_project_root

    profile = resolve_distribution_profile()

    if latest_version_provider is None and (not read_only or query_latest):
        latest_version_provider = _default_latest_provider(
            network_suppressed=invocation.suppresses_network() and not query_latest,
            profile=profile,
        )

    # --- Step 1: Build CliStatus ---
    installed_version = _get_installed_version()

    # T021: single channel read, threaded down through the cache key (T023)
    # and the provider call (T022) rather than re-read at each site.
    channel_prerelease = prerelease_enabled()
    cache_version_key = _cache_version_key(installed_version, prerelease=channel_prerelease)

    # Fresh-cache fast path (NFR-001): read cache first; only call the provider
    # if the version data in the cache is stale or absent.  This avoids a
    # network round-trip on every interactive invocation.
    #
    # Two separate predicates are used:
    # - has_fresh_data: "should we skip the provider call?" (uses fetched_at)
    # - is_fresh: "should we suppress the nag display?" (uses last_shown_at)
    #
    # The distinction matters for the "fully up-to-date" case: when
    # installed == latest there is no nag to show, so last_shown_at stays None
    # forever.  The old is_fresh predicate would return False (never shown →
    # not fresh), causing every invocation to hit the provider even though the
    # cached version data was recent.  has_fresh_data checks fetched_at instead
    # and correctly returns True in that case (FIX C, P2).
    #
    # FR-012: when the profile sets data_freshness_seconds, that TTL drives
    # has_fresh_data only.  Display throttle (is_fresh) always uses
    # config.throttle_seconds.
    cache_record: NagCacheRecord | None = nag_cache.read()
    preference_record: NagCacheRecord | None = cache_record

    # Invalidate cached version data if CLI version changed (FR-025), but
    # preserve user preferences such as snooze/auto/never-ask for the next
    # write. Those preferences are anchored to the remote version, not to the
    # currently installed CLI version.
    if cache_record is not None and cache_record.cli_version_key != cache_version_key:
        cache_record = None

    data_throttle_seconds = (
        profile.data_freshness_seconds
        if profile.data_freshness_seconds is not None
        else config.throttle_seconds
    )

    # Check whether the cached VERSION DATA is fresh enough to trust (skip provider).
    cache_data_fresh = NagCache.has_fresh_data(
        cache_record,
        throttle_seconds=data_throttle_seconds,
        now=now,
        current_cli_version=cache_version_key,
    )

    # Separately, check whether the NAG should be suppressed (throttle display).
    cache_is_fresh = NagCache.is_fresh(
        cache_record,
        throttle_seconds=config.throttle_seconds,
        now=now,
        current_cli_version=cache_version_key,
    )

    latest_version, cli_source, fetched_at = _resolve_latest_version(
        cache_data_fresh=cache_data_fresh,
        cache_record=cache_record,
        preference_record=preference_record,
        latest_version_provider=latest_version_provider,
        profile=profile,
        nag_cache=nag_cache,
        installed_version=cache_version_key,
        now=now,
        prerelease=channel_prerelease,
        read_only=read_only,
        query_latest=query_latest,
    )

    is_outdated = _version_is_outdated(installed_version, latest_version)

    # Nag preferences cannot change the factual status of an explicit query.
    if not config.nag_enabled and not query_latest:
        is_outdated = False

    # A recent nag suppresses passive output, not an explicit query.
    if cache_is_fresh and not query_latest:
        is_outdated = False

    cli_status = CliStatus(
        installed_version=installed_version,
        latest_version=latest_version,
        latest_source=cli_source,
        is_outdated=is_outdated,
        fetched_at=fetched_at,
    )

    # --- Step 2: Scan project ---
    min_supported, max_supported = _get_schema_bounds()
    project_status = _scan_project(project_root_resolver, min_supported, max_supported)

    # --- Step 3: Classify safety ---
    safety = classify(invocation)

    # --- Step 4: Detect install method ---
    install_method = detect_runtime().install_method

    # --- Step 5: Build upgrade hint ---
    upgrade_hint = build_upgrade_hint(install_method, target_version=latest_version)

    # --- Step 6: Decide ---
    decision, fr023_case = decide(project_status, safety, cli_status, invocation)

    # --- Step 7/8: Override fr023_case for UNKNOWN install method ---
    from specify_cli.compat._detect.install_method import InstallMethod

    if install_method == InstallMethod.UNKNOWN and decision == Decision.ALLOW_WITH_NAG:
        fr023_case = Fr023Case.INSTALL_METHOD_UNKNOWN

    # --- Step 9: Pending migrations ---
    # Computed via the real detector (FR-009) but still gated on the block
    # decision here to keep the general per-command compat check off the
    # migration-discovery hot path. The `upgrade` preview overrides this with
    # the unconditional real set (see cli/commands/upgrade.py).
    pending_migrations = (
        _pending_migrations_for(project_status, cli_status.installed_version) if include_migrations and decision == Decision.BLOCK_PROJECT_MIGRATION else ()
    )

    # --- Step 10: Exit code ---
    exit_code = _EXIT_CODE_MAP.get(decision, 0)

    # --- Step 11/12: Render messages (deferred import to avoid circular) ---
    from specify_cli.compat import messages as _messages

    # Assemble partial plan for rendering (rendered_human / rendered_json populated after)
    partial_plan = Plan(
        decision=decision,
        cli_status=cli_status,
        project_status=project_status,
        safety=safety,
        pending_migrations=pending_migrations,
        install_method=install_method,
        upgrade_hint=upgrade_hint,
        fr023_case=fr023_case,
        exit_code=exit_code,
        rendered_human="",
        rendered_json={},
    )

    rendered_human = _messages.render_human(partial_plan)
    rendered_json = _messages.render_json(partial_plan)

    # --- Step 13: Return final Plan ---
    return Plan(
        decision=decision,
        cli_status=cli_status,
        project_status=project_status,
        safety=safety,
        pending_migrations=pending_migrations,
        install_method=install_method,
        upgrade_hint=upgrade_hint,
        fr023_case=fr023_case,
        exit_code=exit_code,
        rendered_human=rendered_human,
        rendered_json=rendered_json,
    )


__all__ = [
    "Decision",
    "Fr023Case",
    "ProjectState",
    "CliStatus",
    "ProjectStatus",
    "MigrationStep",
    "Plan",
    "Invocation",
    "decide",
    "plan",
    "is_ci_env",
]
