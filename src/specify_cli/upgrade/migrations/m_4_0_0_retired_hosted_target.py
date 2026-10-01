"""Migration: delete the retired first-party hosted target from ``config.toml``.

#4259 / WP07 (mission ``hosted-opt-in-drain-ledger``, FR-013): machines
configured before #3980 still carry the retired first-party app endpoint
``https://app.spec-kitty.ai`` in the runtime root's ``config.toml``
``[sync].server_url`` (written by the ``spec-kitty sync server <url>``
command that died with the sync transport, issue #5). This migration used to
*rewrite* that stale value to the packaged default
(:data:`specify_cli.auth.config.DEFAULT_HOSTED_SAAS_URL`); endpoint opt-in
(WP06, reversing #3980 D-5) removed the packaged default from the resolver
entirely, so rewriting to a live address here would silently point a machine
that never configured a hosted endpoint at one. ``apply()`` now **deletes**
the stale key instead and emits guidance pointing the operator at
``SPEC_KITTY_SAAS_URL`` / ``config.toml [sync].server_url`` — the two ways to
configure an endpoint explicitly.

**Scope is exactly the retired first-party address (#4259 agreed scope).**
A deletion happens only when the saved ``server_url``'s parsed hostname is
exactly ``app.spec-kitty.ai`` (:func:`specify_cli.auth.config.
is_retired_first_party_url` — a component-wise host match, never a
substring test over the whole URL, which could fire on an unrelated domain
that merely contains the literal). Every other value is left untouched:
custom and self-hosted endpoints, URLs on other domains, look-alike
hostnames, and — per R-4 — the *canonical* value itself (a machine already
carrying ``https://team.spec-kitty.ai``, written by an earlier run of this
same migration before this behaviour change, is left completely untouched;
that value is now explicit, opt-in configuration, not a stale target). The
deletion ignores no environment variable: an explicit ``SPEC_KITTY_SAAS_URL``
is a live per-process opinion handled by the resolver, while the saved
address is dead first-party infrastructure regardless of any override.

**Everything else in ``config.toml`` is preserved.** The deletion is
load-mutate-dump (``toml`` in, ``tomli_w`` out, one key removed): every
other table, key, and value survives semantically. If ``server_url`` was the
``[sync]`` table's only key, the now-empty table is left in place rather
than dropped — minimal TOML-shape churn beyond the one key. Comments and
hand formatting do not survive — the file is machine-managed legacy state
(nothing in the current CLI writes it), and a surgical text edit over TOML's
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

**``target_version`` pinned to the installed package version, unchanged by
this WP.** Same documented precedent as ``m_3_2_8_provision_kitty_env`` /
``m_3_2_9_migrate_lifecycle_envelope``:
``test_discovered_migration_targets_do_not_exceed_package_version`` skips
any migration whose ``target_version`` exceeds the installed package
version (``pyproject.toml`` was ``"4.0.0rc1"`` at authoring time), and the
chain-integrity gate fails a chain head newer than the package. The
migration therefore keeps targeting ``"4.0.0rc1"`` — the already-shipped rc
— so every upgrade from anything older than 4.0.0rc1 (3.2.6 → 4.0.0
included) selects it through the normal from/to window, and an
already-on-4.0.0rc1 machine re-selects it through ``detect()`` while the
stale value persists. This WP changes only what ``apply()`` does once
selected, never the identity/version the runner selects it by — see
``m_4_0_0rc5_hosted_endpoint_session_backfill`` for why a *new* migration
module, not an edit to this one's ``target_version``, is the vehicle for the
sibling D-6 change. ``apply()`` is idempotent: once the value is deleted (or
was never present, or names something other than the retired address), it
records no changes and changes nothing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import toml
import tomli_w

from kernel.atomic import atomic_write
from specify_cli.auth.config import (
    RETIRED_HOSTED_SAAS_URL,
    format_endpoint_unconfigured_message,
    is_retired_first_party_url,
)
from specify_cli.paths import get_runtime_config_toml_path

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

MIGRATION_ID = "4_0_0_retired_hosted_target"
TARGET_VERSION = "4.0.0rc1"

_SYNC_TABLE = "sync"
_SERVER_URL_KEY = "server_url"


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
    return value if is_retired_first_party_url(value) else None


def retired_server_url_value(path: Path) -> str | None:
    """The retired first-party ``server_url`` saved in ``config.toml``, if any."""
    data = _load_home_config(path)
    return None if data is None else _retired_server_url(data)


@MigrationRegistry.register
class RetiredHostedTargetMigration(BaseMigration):
    """Delete a stale retired first-party ``[sync].server_url`` and guide the operator."""

    migration_id = MIGRATION_ID
    # 250 chars: compat-planner.json caps a migration description at 256
    # (tests/upgrade/test_auto_discovery.py contract gate) — keep any edit
    # to this string under that bound.
    description = (
        f"Delete a config.toml sync.server_url naming {RETIRED_HOSTED_SAAS_URL} "
        "(retired) — no packaged default exists to rewrite it to any more. "
        "Machine-scoped, idempotent; other endpoints/settings untouched."
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
        guidance = format_endpoint_unconfigured_message()
        if dry_run:
            return MigrationResult(
                success=True,
                changes_made=[
                    f"would remove retired config.toml sync.server_url {stale_value}; {guidance}",
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
                f"removed retired config.toml sync.server_url {stale_value}; {guidance}",
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
