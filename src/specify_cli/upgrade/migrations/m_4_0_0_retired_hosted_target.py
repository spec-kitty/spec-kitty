"""Migration: delete the retired first-party hosted target from ``config.toml``.

Machines configured before #3980 still carry the retired first-party app
endpoint ``https://app.spec-kitty.ai`` in the runtime root's ``config.toml``
``[sync].server_url`` (written by the ``spec-kitty sync server <url>``
command that died with the sync transport). The hosted, sync and drain
surfaces were removed from open-core in #6164 (code preserved in
``spec-kitty/event-router``), but this one-way cleanup stays: it deletes the
stale key so no dead address lingers on disk.

**Self-contained.** The retired-host check and the config path are private
helpers here; the migration depends on no hosted module.

**Scope is exactly the retired first-party address.** A deletion happens only
when the saved ``server_url``'s parsed hostname is exactly
``app.spec-kitty.ai`` (a component-wise host match, never a substring test).
Custom endpoints, other domains and look-alike hostnames are left untouched.

**Everything else in ``config.toml`` is preserved.** The deletion is
load-mutate-dump (``toml`` in, ``tomli_w`` out, one key removed). An empty
``[sync]`` table is left in place. The write is atomic
(:func:`kernel.atomic.atomic_write`), and an unparseable or unreadable
``config.toml`` is a no-op: an upgrade never makes a broken file more broken.
The migration never creates a directory or file.

**Machine-scoped, not project-scoped.** ``config.toml`` lives in the runtime
root (``SPEC_KITTY_HOME``, else the platform home), so ``detect()`` /
``apply()`` ignore ``project_path`` and ``runs_on_worktrees`` is ``False``.

``target_version`` stays ``"4.0.0rc1"``, the already-shipped rc, so every
upgrade from an older version selects it through the normal from/to window
(same precedent as ``m_3_2_8_provision_kitty_env``). ``apply()`` is
idempotent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import toml
import tomli_w

from kernel.atomic import atomic_write
from specify_cli.paths import get_runtime_config_toml_path

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

MIGRATION_ID = "4_0_0_retired_hosted_target"
TARGET_VERSION = "4.0.0rc1"

_SYNC_TABLE = "sync"
_SERVER_URL_KEY = "server_url"
_RETIRED_HOSTED_URL = "https://app.spec-kitty.ai"
_RETIRED_HOSTED_HOSTNAME = "app.spec-kitty.ai"


def _is_retired_first_party_url(url: str) -> bool:
    """True when ``url``'s parsed hostname is exactly the retired app host.

    Scheme, port and path are ignored; look-alike domains that merely contain
    the literal are ``False``. A value that is not a URL never matches.
    """
    try:
        return urlsplit(url.strip()).hostname == _RETIRED_HOSTED_HOSTNAME
    except ValueError:
        return False


def home_config_path() -> Path:
    """The machine-scoped ``config.toml`` the resolver reads.

    Resolved through the canonical runtime root at call time (pure — no
    I/O, no directory creation), so tests drive it with ``SPEC_KITTY_HOME``
    exactly like every other runtime-root consumer.

    DIRECTIVE_044: delegates to the one canonical
    ``get_runtime_config_toml_path()`` (``specify_cli.paths``) every
    "config.toml path" consumer now shares.
    """
    path: Path = get_runtime_config_toml_path()
    return path


def _load_home_config(path: Path) -> dict[str, Any] | None:
    """Parse ``config.toml``, or ``None`` for missing/unreadable/unparseable.

    ``None`` is "nothing this migration understands" — never an error: an
    upgrade must not fail (or rewrite anything) because of a file it
    cannot safely read.
    """
    if not path.is_file():
        return None
    try:
        data = toml.load(path)
    except (toml.TomlDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _retired_server_url(data: dict[str, Any]) -> str | None:
    """Return the saved ``server_url`` when it names the retired endpoint.

    ``None`` when there is no ``sync`` table / ``server_url`` key, when the
    value is not a string, or when it points anywhere other than the
    retired first-party host — every one of those shapes is somebody
    else's configuration and stays exactly as it is.
    """
    sync_table = data.get(_SYNC_TABLE)
    if not isinstance(sync_table, dict):
        return None
    value = sync_table.get(_SERVER_URL_KEY)
    if not isinstance(value, str):
        return None
    return value if _is_retired_first_party_url(value) else None


def retired_server_url_value(path: Path) -> str | None:
    """The retired first-party ``server_url`` saved in ``config.toml``, if any."""
    data = _load_home_config(path)
    return None if data is None else _retired_server_url(data)


@MigrationRegistry.register
class RetiredHostedTargetMigration(BaseMigration):
    """Delete a stale retired first-party ``[sync].server_url`` ."""

    migration_id = MIGRATION_ID
    # compat-planner.json caps a migration description at 256 chars.
    description = f"Delete a config.toml sync.server_url naming {_RETIRED_HOSTED_URL} (retired). Machine-scoped, idempotent; other endpoints/settings untouched."
    target_version = TARGET_VERSION
    runs_on_worktrees = False

    def detect(self, project_path: Path) -> bool:
        # project_path is unused: the stale value lives in the machine's
        # runtime root, not in the project being upgraded (module docstring).
        del project_path
        return retired_server_url_value(home_config_path()) is not None

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if self.detect(project_path):
            return True, ""
        return (
            False,
            "no retired first-party server_url in config.toml (already canonical, unset, or custom)",
        )

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        del project_path  # machine-scoped (module docstring)
        path = home_config_path()
        data = _load_home_config(path)
        stale_value = None if data is None else _retired_server_url(data)
        if data is None or stale_value is None:
            return MigrationResult(
                success=True,
                changes_made=[
                    "no retired first-party server_url in config.toml (already canonical, unset, or custom)",
                ],
            )
        if dry_run:
            return MigrationResult(
                success=True,
                changes_made=[
                    f"would remove retired config.toml sync.server_url {stale_value}",
                ],
            )
        # Load-mutate-dump on the one already-loaded document: only
        # sync.server_url is removed; every other table, key, and value is
        # carried through semantically unchanged, and the write is atomic.
        # An empty [sync] table is left in place rather than dropped —
        # minimal TOML-shape churn beyond the one key (module docstring).
        sync_table = data[_SYNC_TABLE]
        del sync_table[_SERVER_URL_KEY]
        atomic_write(path, tomli_w.dumps(data))
        return MigrationResult(
            success=True,
            changes_made=[
                f"removed retired config.toml sync.server_url {stale_value}",
            ],
        )


# Class-only ``__all__``, the majority migration convention (e.g.
# ``m_zz_runtime_state_backfill``): the class is consumed through
# ``@MigrationRegistry.register`` auto-discovery (T013 auto-exempt), and the
# module constants/helpers below are module-private — ``MIGRATION_ID`` /
# ``TARGET_VERSION`` are read off the class, never imported. Exporting them
# would collide with ``m_3_2_0rc35_unified_bundle``'s same-name exports (both
# ``MIGRATION_ID = "<str>"`` normalize identically under the token
# normalizer) in the dead-symbol gate's runtime collision index, which would
# disable the re-export auto-exempt (condition 1) for both.
__all__ = [
    "RetiredHostedTargetMigration",
]
