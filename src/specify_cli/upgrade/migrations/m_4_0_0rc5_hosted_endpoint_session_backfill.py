"""Migration: backfill ``config.toml [sync].server_url`` from a stored session.

D-6 (mission ``hosted-opt-in-drain-ledger``, spec.md Operator decisions,
FR-016; plan.md F-6). Endpoint opt-in (WP06) removed the packaged default:
an unconfigured machine now fails closed instead of silently binding a
hosted target. That is correct for a machine that never touched hosted
features — but it would also strand a machine that already completed
``spec-kitty auth login`` before this upgrade landed: it holds a valid
session for a real endpoint yet has no ``[sync].server_url`` or
``SPEC_KITTY_SAAS_URL`` naming that endpoint explicitly. This migration
treats a prior successful login as explicit opt-in to the endpoint it logged
into: when no endpoint is configured (neither env nor config) and the
stored session's ``issuer_url`` is set and is not the retired first-party
address, it writes that ``issuer_url`` into ``config.toml [sync].server_url``.

**Never touches drain posture.** The personal drain-consent flag lives in
the *same* runtime-root ``config.toml`` this migration writes
(``[hosted] drain``, spec D-5), but a backfilled endpoint is not a
backfilled drain consent — those are two independently-gated pieces of
opt-in (WP01), and this migration writes only ``[sync].server_url``. Any
``[hosted]`` table already present is carried through byte-for-byte
unchanged by the same load-mutate-dump write this module shares with its
sibling migration.

**Why a NEW migration module, not an edit to ``m_4_0_0_retired_hosted_target``.**
That migration's ``target_version`` (``"4.0.0rc1"``) has already shipped, and
the upgrade runner records a migration as applied per project, keyed by
``migration_id`` — it unconditionally skips a migration once recorded
(``specify_cli.upgrade.runner._apply_migration``:
``if metadata.has_migration(migration.migration_id): return ... "skipped"``).
Any project that already ran ``4_0_0_retired_hosted_target`` in an earlier rc
would therefore never re-evaluate new logic folded into that same migration's
``apply()`` — this backfill would be silently inert for every machine that
already upgraded once. Minting a new ``migration_id`` here means every
project's next upgrade evaluates it regardless of what that project already
recorded for the sibling migration. No manual registration list needs
updating: ``auto_discover_migrations()`` globs ``m_*.py`` and imports every
match, firing this module's ``@MigrationRegistry.register`` decorator on
import.

**Read-only session access — never ``EncryptedFileStorage.read()``.** That
method mutates on the read path: it creates the store directory, writes
``session.lock``, deletes ``session.json`` on any
:class:`~specify_cli.auth.errors.StorageDecryptionError`, and rewrites a
legacy v2 blob to v3 (unlinking ``session.salt``). An upgrade migration must
never touch credential material as a side effect of merely checking whether
it can help. This module instead reads the on-disk v3 format directly and
read-only (:func:`_read_only_session_issuer_url`): if ``session.json`` is
absent, no-op; check its permissions (NFR-013 — mirrors
``FileFallbackStorage.read()``'s own ``_check_file_permissions(cred_file)``
call; a group/world-readable session file is refused, not read); parse it;
if its ``version`` is not ``3``, no-op (a legacy v2 session is not migrated
to v3 from an upgrade step — the documented limitation from Context §2 of
this WP); read ``session.key`` (absent, unsafe permissions, or the wrong
length, no-op — the permission check mirrors ``_decrypt``'s own v3-branch
``_check_file_permissions(key_file)`` call); AES-GCM-decrypt exactly as
``FileFallbackStorage._decrypt``'s v3 branch does; and
:meth:`~specify_cli.auth.session.StoredSession.from_json` to extract only
``issuer_url``. Any exception anywhere in that path is a silent no-op logged
at debug level with the exception *type* only, never its payload
(DIRECTIVE_050 — no token material is ever read, logged, or printed; only
``issuer_url``, a bare URL, is extracted). The session directory is
byte-unchanged by every call: no new files, no lock file, no legacy rewrite.

**D5 — retired issuer is never backfilled.** When
:func:`~specify_cli.auth.config.is_retired_first_party_url` says the
session's ``issuer_url`` names the retired first-party app endpoint, this
migration is a no-op — backfilling it would resurrect exactly the stale
target the sibling migration exists to delete.

**Machine-scoped, not project-scoped**, for the same reason as the sibling
migration: ``config.toml`` and the session store both live under the
runtime root, not the project being upgraded, so ``detect()``/``apply()``
ignore ``project_path`` and ``runs_on_worktrees`` is ``False``.

**``target_version`` pinned to the installed package version at authoring
time** (``pyproject.toml`` was ``"4.0.0rc5"``), following the same
precedent as ``m_3_2_8_provision_kitty_env`` /
``m_4_0_0_retired_hosted_target``: this selects the migration via
``MigrationRegistry.get_applicable``'s ``target == from_v and detect()``
branch for every machine already on that version, and via the normal
``from_v < target <= to_v`` window for anything upgrading from older
versions. ``apply()`` is idempotent: once an endpoint is configured (by this
migration or otherwise), it records no changes and changes nothing.
"""

from __future__ import annotations

import json
import logging
import os
import stat
from pathlib import Path
from typing import Any

import toml
import tomli_w
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from kernel.atomic import atomic_write
from specify_cli.auth.config import is_retired_first_party_url
from specify_cli.auth.secure_storage.file_fallback import default_store_dir
from specify_cli.auth.server_target import resolve_server_target_or_none
from specify_cli.auth.session import StoredSession

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult
from .m_4_0_0_retired_hosted_target import home_config_path

_LOG = logging.getLogger(__name__)

MIGRATION_ID = "4_0_0rc5_hosted_endpoint_session_backfill"
TARGET_VERSION = "4.0.0rc5"

_SYNC_TABLE = "sync"
_SERVER_URL_KEY = "server_url"

_SESSION_FILENAME = "session.json"
_SESSION_KEY_FILENAME = "session.key"
_SESSION_FORMAT_VERSION = 3  # matches FileFallbackStorage._FILE_FORMAT_VERSION
_SESSION_KEY_BYTES = 32

_NOTHING_TO_BACKFILL = "no unconfigured endpoint with a backfillable, non-retired stored session issuer_url"
_CONFIG_UNSAFE_TO_WRITE = "config.toml is unparseable or its [sync] value is not a table; nothing backfilled"


def _is_endpoint_configured() -> bool:
    """True when either ``SPEC_KITTY_SAAS_URL`` or config names a target.

    DIRECTIVE_044 (review cycle 1, Issue 4): delegates to the canonical
    resolver, :func:`~specify_cli.auth.server_target.resolve_server_target_or_none`,
    rather than a local private-reader copy — "is a hosted endpoint
    configured?" already has one authoritative answer, and a local copy had
    already drifted (it treated a non-string ``server_url`` as unset, where
    the canonical reader accepts it via ``str(value)``). With the default
    ``process_wide_override=True`` this can never raise
    ``ServerTargetSplitBrainError`` — an env/config disagreement resolves via
    the whole-process override instead of failing closed — so this is a
    plain boolean, safe to call from both ``detect()`` and ``apply()``.
    """
    # Typed local: cross-module return resolves as Any under mypy's
    # follow_imports=skip for specify_cli.*.
    target: object | None = resolve_server_target_or_none()
    return target is not None


def _has_unsafe_permissions(path: Path) -> bool:
    """Mirror ``FileFallbackStorage._check_file_permissions``'s POSIX check (NFR-013).

    True when *path* is not owner-only (``mode & 0o077``). Windows has no
    POSIX permission bits (no ``os.getuid``), so this is always ``False``
    there — the same platform carve-out the production check makes. Caller
    must confirm *path* exists first.
    """
    if not hasattr(os, "getuid"):
        return False
    mode = stat.S_IMODE(path.stat().st_mode)
    return bool(mode & 0o077)


def _read_only_session_issuer_url() -> str | None:
    """Return the stored session's ``issuer_url``, or ``None`` — never mutates.

    See the module docstring's "Read-only session access" section for the
    full contract. Every failure mode (missing file, legacy v2, corrupt
    JSON, wrong-length key, unsafe permissions, decrypt failure, malformed
    payload) degrades to ``None`` silently; nothing under the session
    directory is ever written, deleted, or renamed by this function.

    Mirrors two permission checks the real read path makes (NFR-013, review
    cycle 1 Issue 3): ``FileFallbackStorage.read()`` checks the session file
    itself before parsing, and ``_decrypt``'s v3 branch checks the key file
    before reading it. A group/world-readable ``session.json`` or
    ``session.key`` is refused here exactly as production refuses to decrypt
    it — backfilling from a session the CLI itself would not trust is worse
    than not backfilling at all.
    """
    auth_dir = default_store_dir()
    session_path = auth_dir / _SESSION_FILENAME
    key_path = auth_dir / _SESSION_KEY_FILENAME
    if not session_path.is_file():
        return None
    try:
        if _has_unsafe_permissions(session_path):
            return None
        blob = json.loads(session_path.read_text(encoding="utf-8"))
        if not isinstance(blob, dict) or blob.get("version") != _SESSION_FORMAT_VERSION:
            # Not v3 (missing, malformed, or legacy v2): no migration of a
            # legacy session format happens from an upgrade step.
            return None
        if not key_path.is_file() or _has_unsafe_permissions(key_path):
            return None
        key = key_path.read_bytes()
        if len(key) != _SESSION_KEY_BYTES:
            return None
        nonce = bytes.fromhex(blob["nonce"])
        ciphertext = bytes.fromhex(blob["ciphertext"])
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
        session = StoredSession.from_json(plaintext.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 — any failure here is a silent no-op (D6); never logs payload
        _LOG.debug("Read-only session issuer probe failed: %s", type(exc).__name__)
        return None
    # Typed local: StoredSession resolves as Any under mypy's
    # follow_imports=skip for specify_cli.* — binding to str | None keeps the
    # declared return type honest without an ignore.
    issuer_url: str | None = session.issuer_url
    return issuer_url


def _backfillable_issuer_url() -> str | None:
    """The stored session's ``issuer_url``, unless it is retired (D5) or absent."""
    issuer_url = _read_only_session_issuer_url()
    if not issuer_url:
        return None
    if is_retired_first_party_url(issuer_url):
        return None
    return issuer_url


def _load_home_config_for_write(path: Path) -> dict[str, Any] | None:
    """Load ``config.toml`` for a mutating write, or ``None`` to refuse.

    ``{}`` for a missing file (a fresh ``config.toml`` is fine to create for
    a backfill). ``None`` — "cannot safely understand this file" — for three
    shapes this migration must never write over (review cycle 1, Issue 1):
    an existing-but-unparseable file, a document whose top level is not a
    table, and a document whose ``sync`` value is present but is not itself
    a table (e.g. ``sync = "oops"``). The last case previously silently
    replaced the non-table value with a freshly-built ``[sync]`` table
    instead of refusing — this now matches the sibling migration's
    ``_load_home_config`` fail-open-to-no-op contract for every unsafe
    shape, not just outright parse failures.
    """
    if not path.is_file():
        return {}
    try:
        data = toml.load(path)
    except (toml.TomlDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    sync_value = data.get(_SYNC_TABLE)
    if sync_value is not None and not isinstance(sync_value, dict):
        return None
    return data


@MigrationRegistry.register
class HostedEndpointSessionBackfillMigration(BaseMigration):
    """Backfill ``[sync].server_url`` from a stored session's ``issuer_url`` (D-6)."""

    migration_id = MIGRATION_ID
    description = (
        "Backfill config.toml sync.server_url from a stored session's "
        "issuer_url when no endpoint is configured (D-6): a prior login is "
        "opt-in to that endpoint. Never touches drain or a retired issuer; "
        "machine-scoped, idempotent."
    )
    target_version = TARGET_VERSION
    runs_on_worktrees = False

    def detect(self, project_path: Path) -> bool:
        # project_path is unused: config.toml and the session store both
        # live in the machine's runtime root (module docstring).
        del project_path
        if _is_endpoint_configured():
            return False
        if _load_home_config_for_write(home_config_path()) is None:
            # Cannot safely write here (unparseable config, or a non-table
            # `sync` value) — reporting "needed" would let the runner record
            # this migration as applied while nothing actually happened,
            # stranding the machine even after the file is fixed later
            # (review cycle 1, non-blocking item 7).
            return False
        return _backfillable_issuer_url() is not None

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if self.detect(project_path):
            return True, ""
        return False, _NOTHING_TO_BACKFILL

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        del project_path  # machine-scoped (module docstring)
        # Re-derive at apply time rather than trusting a stale detect() —
        # mirrors the sibling migration's own re-derivation pattern.
        if _is_endpoint_configured():
            return MigrationResult(success=True, changes_made=["endpoint already configured; nothing to backfill"])
        issuer_url = _backfillable_issuer_url()
        if issuer_url is None:
            return MigrationResult(success=True, changes_made=[_NOTHING_TO_BACKFILL])

        path = home_config_path()
        data = _load_home_config_for_write(path)
        if data is None:
            return MigrationResult(
                success=True,
                changes_made=[_CONFIG_UNSAFE_TO_WRITE],
                warnings=[_CONFIG_UNSAFE_TO_WRITE],
            )
        if dry_run:
            return MigrationResult(
                success=True,
                changes_made=[f"would backfill config.toml sync.server_url = {issuer_url} from the stored session"],
            )
        sync_table = data.get(_SYNC_TABLE)
        if not isinstance(sync_table, dict):
            sync_table = {}
            data[_SYNC_TABLE] = sync_table
        sync_table[_SERVER_URL_KEY] = issuer_url
        atomic_write(path, tomli_w.dumps(data))
        return MigrationResult(
            success=True,
            changes_made=[f"backfilled config.toml sync.server_url = {issuer_url} from the stored session (D-6)"],
        )


# Class-only ``__all__`` — mirrors the sibling migration's convention: the
# class is consumed through ``@MigrationRegistry.register`` auto-discovery,
# and the module constants/helpers above are module-private.
__all__ = [
    "HostedEndpointSessionBackfillMigration",
]
