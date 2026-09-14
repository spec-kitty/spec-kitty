"""Migration: rewrite the retired first-party hosted target in ``config.toml``.

#4259: machines configured before #3980 (D-5 revised) promoted
``https://team.spec-kitty.ai`` to the packaged default still carry the
retired first-party app endpoint ``https://app.spec-kitty.ai`` in the
runtime root's ``config.toml`` ``[sync].server_url`` (written by the
``spec-kitty sync server <url>`` command that died with the sync transport,
issue #5). The 4.0.0rc1 resolver regression that let that stale value win
over an explicit canonical ``SPEC_KITTY_SAAS_URL`` is fixed separately in
``specify_cli.auth.server_target`` (#4259); this migration removes the stale
value itself, so the machine's *saved* target is the canonical one.

**Scope is exactly the retired first-party address (#4259 agreed scope).**
A rewrite happens only when the saved ``server_url``'s parsed hostname is
exactly ``app.spec-kitty.ai`` (:func:`specify_cli.auth.config.
is_retired_first_party_url` — a component-wise host match, never a
substring test over the whole URL, which could fire on an unrelated domain
that merely contains the literal). Every other value is left untouched:
custom and self-hosted endpoints, URLs on other domains, and look-alike
hostnames keep working unchanged — self-hosting is supported and is not
"migrated" to the canonical host. The rewrite ignores no environment
variable: an explicit ``SPEC_KITTY_SAAS_URL`` is a live per-process opinion
handled by the resolver, while the saved address is dead first-party
infrastructure regardless of any override.

**Everything else in ``config.toml`` is preserved.** The rewrite is
load-mutate-dump (``toml`` in, ``tomli_w`` out, one key changed): every
other table, key, and value survives semantically. Comments and hand
formatting do not — the file is machine-managed legacy state (nothing in
the current CLI writes it), and a surgical text edit over TOML's
multiline/dotted-key surface would be strictly riskier for zero functional
gain. The write itself is atomic (:func:`kernel.atomic.atomic_write`), and
an unparseable or unreadable ``config.toml`` is a no-op recorded as a
warning — a broken file this migration cannot understand is never made
more broken by an upgrade.

**Machine-scoped, not project-scoped.** ``config.toml`` lives in the
runtime root (``SPEC_KITTY_HOME``, else the platform home), not under the
project being upgraded, so ``detect()``/``apply()`` read the runtime root
and ignore ``project_path`` (kept in the signature for the
:class:`BaseMigration` contract). ``runs_on_worktrees`` is ``False`` for
the same reason: the home config is shared by every checkout of the
machine, and one run from the main checkout covers them all. The runner
records the migration in each project's metadata, so the first upgraded
project fixes the machine and every later upgrade skips via ``detect()``.

**``target_version`` pinned to the installed package version.** Same
documented precedent as ``m_3_2_8_provision_kitty_env`` /
``m_3_2_9_migrate_lifecycle_envelope``:
``test_discovered_migration_targets_do_not_exceed_package_version`` skips
any migration whose ``target_version`` exceeds the installed package
version (``pyproject.toml`` is ``"4.0.0rc1"`` at authoring time), and the
chain-integrity gate fails a chain head newer than the package. The
migration therefore targets ``"4.0.0rc1"`` — the already-shipped rc — so
every upgrade from anything older than 4.0.0rc1 (3.2.6 → 4.0.0 included)
selects it through the normal from/to window, and an
already-on-4.0.0rc1 machine re-selects it through ``detect()`` while the
stale value persists. ``apply()`` is idempotent: once the value is
canonical (or absent), it records no changes and changes nothing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import toml
import tomli_w

from kernel.atomic import atomic_write
from specify_cli.auth.config import (
    DEFAULT_HOSTED_SAAS_URL,
    RETIRED_HOSTED_SAAS_URL,
    is_retired_first_party_url,
)
from specify_cli.paths import get_runtime_root

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

MIGRATION_ID = "4_0_0_retired_hosted_target"
TARGET_VERSION = "4.0.0rc1"

_CONFIG_FILENAME = "config.toml"
_SYNC_TABLE = "sync"
_SERVER_URL_KEY = "server_url"


def home_config_path() -> Path:
    """The machine-scoped ``config.toml`` the resolver reads.

    Resolved through the canonical runtime root at call time (pure — no
    I/O, no directory creation), so tests drive it with ``SPEC_KITTY_HOME``
    exactly like every other runtime-root consumer.
    """
    # Typed local: get_runtime_root() resolves as Any under mypy's
    # follow_imports=skip for specify_cli.* — binding to Path keeps the
    # declared return type honest without an ignore.
    base: Path = get_runtime_root().base
    return base / _CONFIG_FILENAME


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
    return value if is_retired_first_party_url(value) else None


def retired_server_url_value(path: Path) -> str | None:
    """The retired first-party ``server_url`` saved in ``config.toml``, if any."""
    data = _load_home_config(path)
    return None if data is None else _retired_server_url(data)


@MigrationRegistry.register
class RetiredHostedTargetMigration(BaseMigration):
    """Rewrite a stale retired first-party ``[sync].server_url`` to canonical."""

    migration_id = MIGRATION_ID
    # 250 chars: compat-planner.json caps a migration description at 256
    # (tests/upgrade/test_auto_discovery.py contract gate) — keep any edit
    # to this string under that bound.
    description = (
        "Rewrite a config.toml sync.server_url naming the retired first-party "
        f"endpoint ({RETIRED_HOSTED_SAAS_URL}) as the canonical target "
        f"({DEFAULT_HOSTED_SAAS_URL}). Machine-scoped, idempotent; "
        "custom/self-hosted endpoints and unrelated settings untouched."
    )
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
                    f"would rewrite config.toml sync.server_url {stale_value} -> {DEFAULT_HOSTED_SAAS_URL}",
                ],
            )
        # Load-mutate-dump on the one already-loaded document: only
        # sync.server_url changes; every other table, key, and value is
        # carried through semantically unchanged, and the write is atomic.
        sync_table = data[_SYNC_TABLE]
        sync_table[_SERVER_URL_KEY] = DEFAULT_HOSTED_SAAS_URL
        atomic_write(path, tomli_w.dumps(data))
        return MigrationResult(
            success=True,
            changes_made=[
                f"rewrote config.toml sync.server_url {stale_value} -> {DEFAULT_HOSTED_SAAS_URL}",
            ],
        )


# Class-only ``__all__``, the majority migration convention (e.g.
# ``m_zz_runtime_state_backfill``): the class is consumed through
# ``@MigrationRegistry.register`` auto-discovery (T013 auto-exempt), and the
# module constants/helpers below are module-private — ``MIGRATION_ID`` /
# ``TARGET_VERSION`` are read off the class, never imported. Exporting them
# would collide with ``m_3_2_0rc35_unified_bundle``'s same-name exports in
# the dead-symbol gate's body-hash identity (string-literal content is
# dropped by the token normalizer, so every ``MIGRATION_ID = "<str>"``
# normalizes identically) and fail-close both modules' allowlist entries.
__all__ = [
    "RetiredHostedTargetMigration",
]
