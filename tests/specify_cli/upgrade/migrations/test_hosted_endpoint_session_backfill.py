"""Tests for ``m_4_0_0rc5_hosted_endpoint_session_backfill`` (D-6, WP07 T031).

Mirrors the sibling migration's test pattern
(``tests/specify_cli/upgrade/migrations/test_retired_hosted_target.py``):
unit tests call ``detect()``/``can_apply()``/``apply()`` directly on a
migration instance against a synthetic ``SPEC_KITTY_HOME``. A real
:class:`~specify_cli.auth.secure_storage.file_fallback.FileFallbackStorage`
writes the session fixtures so the on-disk ciphertext matches production
exactly, and every backfill test snapshots the whole ``<runtime-root>/auth/``
directory (file names + bytes) before and after to prove the D6 byte-
unchanged invariant: this migration reads ``issuer_url`` without ever
calling the mutating ``EncryptedFileStorage.read()``.
"""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

import pytest
import toml
from kernel.clock import now_utc, timedelta

from specify_cli.auth.config import DEFAULT_HOSTED_SAAS_URL, RETIRED_HOSTED_SAAS_URL
from specify_cli.auth.secure_storage.file_fallback import FileFallbackStorage
from specify_cli.auth.session import StoredSession, Team
from specify_cli.upgrade.migrations.m_4_0_0_retired_hosted_target import (
    MIGRATION_ID as SIBLING_MIGRATION_ID,
)
from specify_cli.upgrade.migrations.m_4_0_0rc5_hosted_endpoint_session_backfill import (
    MIGRATION_ID,
    TARGET_VERSION,
    HostedEndpointSessionBackfillMigration,
)
from specify_cli.upgrade.registry import MigrationRegistry

pytestmark = [pytest.mark.unit]

RETIRED_URL = RETIRED_HOSTED_SAAS_URL
CANONICAL_URL = DEFAULT_HOSTED_SAAS_URL
LIVE_ISSUER_URL = "https://selfhost.example.com"

_UNSAFE_KEY_MODE = 0o644
_POSIX_ONLY = pytest.mark.skipif(not hasattr(os, "getuid"), reason="POSIX-only file-permission semantics")


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An isolated ``SPEC_KITTY_HOME`` with no env target leakage."""
    root = tmp_path / "spec-kitty-home"
    root.mkdir()
    monkeypatch.setenv("SPEC_KITTY_HOME", str(root))
    monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
    return root


def _write_home_config(root: Path, text: str) -> Path:
    path = root / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


def _auth_dir(home_root: Path) -> Path:
    auth_dir = home_root / "auth"
    return auth_dir


def _build_session(*, issuer_url: str | None) -> StoredSession:
    now = now_utc()
    return StoredSession(
        user_id="user-1",
        email="a@b.com",
        name="A B",
        teams=[Team(id="t1", name="T1", role="owner", is_private_teamspace=True)],
        default_team_id="t1",
        access_token="at-secret-do-not-log",
        refresh_token="rt-secret-do-not-log",
        session_id="sess-1",
        issued_at=now,
        access_token_expires_at=now + timedelta(seconds=900),
        refresh_token_expires_at=None,
        scope="openid",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
        issuer_url=issuer_url,
    )


def _write_session(home_root: Path, *, issuer_url: str | None) -> Path:
    """Write a real v3-encrypted session, then strip write()'s own side files.

    ``FileFallbackStorage.write()`` creates ``session.lock`` (via
    ``machine_file_lock``) and publishes ``session.hot-path.json`` as part of
    an ordinary write — neither is part of the D6 "session directory" the
    read-only helper must leave untouched, and leaving them in place would
    make every "before" snapshot already contain a lock file, silently
    defeating the "no lock file created" assertion (review cycle 1, Issue 5).
    Stripping them here means a fixture-using test's before/after snapshot
    is a true proof: only ``session.json``/``session.key`` exist before, and
    neither a lock nor a hot-path file may appear after.
    """
    auth_dir = _auth_dir(home_root)
    storage = FileFallbackStorage(base_dir=auth_dir)
    storage.write(_build_session(issuer_url=issuer_url))
    for side_file in ("session.lock", "session.hot-path.json"):
        (auth_dir / side_file).unlink(missing_ok=True)
    return auth_dir


def _snapshot_dir(directory: Path) -> dict[str, bytes]:
    """Byte-exact snapshot of every file directly under ``directory``.

    ``{}`` (not an error) when the directory does not exist — the D6
    byte-unchanged assertion still holds: a probe that never touched a
    nonexistent directory leaves it nonexistent.
    """
    if not directory.is_dir():
        return {}
    return {p.name: p.read_bytes() for p in sorted(directory.iterdir()) if p.is_file()}


def _assert_auth_dir_byte_unchanged(before: dict[str, bytes], after: dict[str, bytes]) -> None:
    assert after == before


# ---------------------------------------------------------------------------
# Registration + version pin
# ---------------------------------------------------------------------------


def test_migration_is_registered() -> None:
    found = MigrationRegistry.get_by_id(MIGRATION_ID)
    assert found is not None
    assert found.migration_id == MIGRATION_ID
    assert found.runs_on_worktrees is False


def test_migration_id_does_not_collide_with_sibling() -> None:
    """The single most important structural check for this WP (reviewer
    guidance): this is a distinct MIGRATION_ID from the retired-target
    migration, so the already-applied-migration skip trap cannot make the
    backfill inert on a machine that already ran the sibling."""
    assert MIGRATION_ID != SIBLING_MIGRATION_ID


def test_target_version_does_not_exceed_package_version() -> None:
    """Guards the module docstring's own stated invariant directly (the
    ``m_4_0_0_retired_hosted_target`` pin precedent; belt-and-suspenders
    alongside the repo-wide
    ``test_discovered_migration_targets_do_not_exceed_package_version``
    gate). ``TARGET_VERSION`` is pinned to the installed package version at
    authoring time (``pyproject.toml`` was ``"4.0.0rc5"``)."""
    from packaging.version import Version

    migration = HostedEndpointSessionBackfillMigration()
    assert Version(migration.target_version) == Version(TARGET_VERSION)
    assert Version(TARGET_VERSION) <= Version("4.0.0rc5")


# ---------------------------------------------------------------------------
# detect() / can_apply()
# ---------------------------------------------------------------------------


class TestDetect:
    def test_detect_true_when_unconfigured_and_session_has_issuer(self, home: Path) -> None:
        auth_dir = _write_session(home, issuer_url=LIVE_ISSUER_URL)
        before = _snapshot_dir(auth_dir)

        assert HostedEndpointSessionBackfillMigration().detect(Path("/any/project")) is True

        _assert_auth_dir_byte_unchanged(before, _snapshot_dir(auth_dir))

    def test_detect_false_when_env_already_configured(self, home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPEC_KITTY_SAAS_URL", LIVE_ISSUER_URL)
        auth_dir = _write_session(home, issuer_url=LIVE_ISSUER_URL)
        before = _snapshot_dir(auth_dir)

        assert HostedEndpointSessionBackfillMigration().detect(Path("/any/project")) is False

        _assert_auth_dir_byte_unchanged(before, _snapshot_dir(auth_dir))

    def test_detect_false_when_config_already_configured(self, home: Path) -> None:
        _write_home_config(home, f'[sync]\nserver_url = "{CANONICAL_URL}"\n')
        auth_dir = _write_session(home, issuer_url=LIVE_ISSUER_URL)
        before = _snapshot_dir(auth_dir)

        assert HostedEndpointSessionBackfillMigration().detect(Path("/any/project")) is False

        _assert_auth_dir_byte_unchanged(before, _snapshot_dir(auth_dir))

    def test_detect_false_when_config_server_url_is_non_string(self, home: Path) -> None:
        """DIRECTIVE_044 regression (review cycle 1, Issue 4): the canonical
        resolver (`resolve_server_target_or_none`) treats a non-string
        `server_url` as configured via `str(value)` — a local private-reader
        copy that instead treated it as unset would wrongly consider the
        endpoint unconfigured and clobber this value with the session's
        issuer_url."""
        _write_home_config(home, "[sync]\nserver_url = 42\n")
        auth_dir = _write_session(home, issuer_url=LIVE_ISSUER_URL)
        before = _snapshot_dir(auth_dir)

        assert HostedEndpointSessionBackfillMigration().detect(Path("/any/project")) is False

        _assert_auth_dir_byte_unchanged(before, _snapshot_dir(auth_dir))

    def test_detect_false_when_no_session_file(self, home: Path) -> None:
        auth_dir = _auth_dir(home)

        assert HostedEndpointSessionBackfillMigration().detect(Path("/any/project")) is False

        # No mkdir anywhere in the read-only path: the auth dir must not
        # spring into existence just because detect() looked for a session.
        assert not auth_dir.exists()

    def test_detect_false_when_session_issuer_url_is_none(self, home: Path) -> None:
        auth_dir = _write_session(home, issuer_url=None)
        before = _snapshot_dir(auth_dir)

        assert HostedEndpointSessionBackfillMigration().detect(Path("/any/project")) is False

        _assert_auth_dir_byte_unchanged(before, _snapshot_dir(auth_dir))

    def test_detect_false_when_session_issuer_is_retired_first_party(self, home: Path) -> None:
        """D5: a retired issuer must never be backfilled — that would
        resurrect exactly the stale target the sibling migration deletes."""
        auth_dir = _write_session(home, issuer_url=RETIRED_URL)
        before = _snapshot_dir(auth_dir)

        assert HostedEndpointSessionBackfillMigration().detect(Path("/any/project")) is False

        _assert_auth_dir_byte_unchanged(before, _snapshot_dir(auth_dir))

    def test_detect_false_on_corrupt_session_json(self, home: Path) -> None:
        auth_dir = _write_session(home, issuer_url=LIVE_ISSUER_URL)
        (auth_dir / "session.json").write_text("{not valid json", encoding="utf-8")
        before = _snapshot_dir(auth_dir)

        assert HostedEndpointSessionBackfillMigration().detect(Path("/any/project")) is False

        _assert_auth_dir_byte_unchanged(before, _snapshot_dir(auth_dir))

    def test_detect_false_on_wrong_length_session_key(self, home: Path) -> None:
        auth_dir = _write_session(home, issuer_url=LIVE_ISSUER_URL)
        (auth_dir / "session.key").write_bytes(b"too-short")
        before = _snapshot_dir(auth_dir)

        assert HostedEndpointSessionBackfillMigration().detect(Path("/any/project")) is False

        _assert_auth_dir_byte_unchanged(before, _snapshot_dir(auth_dir))

    def test_detect_false_on_missing_session_key(self, home: Path) -> None:
        auth_dir = _write_session(home, issuer_url=LIVE_ISSUER_URL)
        (auth_dir / "session.key").unlink()
        before = _snapshot_dir(auth_dir)

        assert HostedEndpointSessionBackfillMigration().detect(Path("/any/project")) is False

        _assert_auth_dir_byte_unchanged(before, _snapshot_dir(auth_dir))

    def test_detect_false_on_legacy_v2_session_blob(self, home: Path) -> None:
        """No legacy-v2 migration happens from an upgrade step (Context §2,
        documented limitation) — a v2 blob is a silent no-op, not upgraded."""
        auth_dir = _write_session(home, issuer_url=LIVE_ISSUER_URL)
        raw = json.loads((auth_dir / "session.json").read_text(encoding="utf-8"))
        raw["version"] = 2
        (auth_dir / "session.json").write_text(json.dumps(raw), encoding="utf-8")
        before = _snapshot_dir(auth_dir)

        assert HostedEndpointSessionBackfillMigration().detect(Path("/any/project")) is False

        _assert_auth_dir_byte_unchanged(before, _snapshot_dir(auth_dir))

    @_POSIX_ONLY
    def test_detect_false_on_unsafe_session_key_permissions(self, home: Path) -> None:
        """NFR-013: mirrors ``FileFallbackStorage._decrypt``'s v3-branch
        ``_check_file_permissions(key_file)`` call — a group/world-readable
        ``session.key`` is refused by production decrypt, so this read-only
        mirror must refuse it too rather than back-fill from a session the
        CLI itself would not trust."""
        auth_dir = _write_session(home, issuer_url=LIVE_ISSUER_URL)
        os.chmod(auth_dir / "session.key", _UNSAFE_KEY_MODE)
        before = _snapshot_dir(auth_dir)

        assert HostedEndpointSessionBackfillMigration().detect(Path("/any/project")) is False

        _assert_auth_dir_byte_unchanged(before, _snapshot_dir(auth_dir))

    @_POSIX_ONLY
    def test_detect_false_on_unsafe_session_json_permissions(self, home: Path) -> None:
        """Mirrors ``FileFallbackStorage.read()``'s own
        ``_check_file_permissions(cred_file)`` call on the session file
        itself, not just the key."""
        auth_dir = _write_session(home, issuer_url=LIVE_ISSUER_URL)
        os.chmod(auth_dir / "session.json", _UNSAFE_KEY_MODE)
        before = _snapshot_dir(auth_dir)

        assert HostedEndpointSessionBackfillMigration().detect(Path("/any/project")) is False

        _assert_auth_dir_byte_unchanged(before, _snapshot_dir(auth_dir))

    def test_detect_false_on_wrong_key_correct_length(self, home: Path) -> None:
        """The real ``InvalidTag`` decrypt-failure path: a key of the right
        length (32 bytes) that is simply not the key the session was
        encrypted with. Distinct from the wrong-*length* case above, which
        never reaches AES-GCM at all."""
        auth_dir = _write_session(home, issuer_url=LIVE_ISSUER_URL)
        (auth_dir / "session.key").write_bytes(secrets.token_bytes(32))
        before = _snapshot_dir(auth_dir)

        assert HostedEndpointSessionBackfillMigration().detect(Path("/any/project")) is False

        _assert_auth_dir_byte_unchanged(before, _snapshot_dir(auth_dir))

    def test_can_apply(self, home: Path) -> None:
        _write_session(home, issuer_url=LIVE_ISSUER_URL)
        migration = HostedEndpointSessionBackfillMigration()
        assert migration.can_apply(Path("/any/project")) == (True, "")

    def test_can_apply_false_when_nothing_to_backfill(self, home: Path) -> None:
        can_apply, reason = HostedEndpointSessionBackfillMigration().can_apply(Path("/any/project"))
        assert can_apply is False
        assert "backfillable" in reason


# ---------------------------------------------------------------------------
# apply()
# ---------------------------------------------------------------------------


class TestApply:
    def test_apply_backfills_server_url_from_issuer(self, home: Path) -> None:
        auth_dir = _write_session(home, issuer_url=LIVE_ISSUER_URL)
        before = _snapshot_dir(auth_dir)

        result = HostedEndpointSessionBackfillMigration().apply(Path("/any/project"))

        assert result.success is True
        data = toml.load(home / "config.toml")
        assert data["sync"]["server_url"] == LIVE_ISSUER_URL
        _assert_auth_dir_byte_unchanged(before, _snapshot_dir(auth_dir))

    def test_apply_preserves_unrelated_configuration(self, home: Path) -> None:
        _write_home_config(home, '[telemetry]\nenabled = false\n\n[ui]\ntheme = "dark"\n')
        _write_session(home, issuer_url=LIVE_ISSUER_URL)

        HostedEndpointSessionBackfillMigration().apply(Path("/any/project"))

        data = toml.load(home / "config.toml")
        assert data["sync"]["server_url"] == LIVE_ISSUER_URL
        assert data["telemetry"] == {"enabled": False}
        assert data["ui"] == {"theme": "dark"}

    def test_apply_creates_config_toml_when_absent(self, home: Path) -> None:
        _write_session(home, issuer_url=LIVE_ISSUER_URL)
        assert not (home / "config.toml").exists()

        result = HostedEndpointSessionBackfillMigration().apply(Path("/any/project"))

        assert result.success is True
        data = toml.load(home / "config.toml")
        assert data["sync"]["server_url"] == LIVE_ISSUER_URL

    def test_apply_is_no_op_when_env_already_configured(self, home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPEC_KITTY_SAAS_URL", CANONICAL_URL)
        auth_dir = _write_session(home, issuer_url=LIVE_ISSUER_URL)
        before = _snapshot_dir(auth_dir)

        result = HostedEndpointSessionBackfillMigration().apply(Path("/any/project"))

        assert result.success is True
        assert not (home / "config.toml").exists()
        _assert_auth_dir_byte_unchanged(before, _snapshot_dir(auth_dir))

    def test_apply_is_no_op_when_config_already_configured(self, home: Path) -> None:
        """D-6 never overwrites an explicit value — the explicit config wins."""
        path = _write_home_config(home, f'[sync]\nserver_url = "{CANONICAL_URL}"\n')
        before = path.read_text(encoding="utf-8")
        _write_session(home, issuer_url=LIVE_ISSUER_URL)

        result = HostedEndpointSessionBackfillMigration().apply(Path("/any/project"))

        assert result.success is True
        assert path.read_text(encoding="utf-8") == before

    def test_apply_is_no_op_when_config_server_url_is_non_string(self, home: Path) -> None:
        """DIRECTIVE_044 regression (review cycle 1, Issue 4): see the
        matching ``TestDetect`` case — the canonical resolver treats a
        non-string ``server_url`` as configured, so ``apply()`` must never
        clobber it with the session's ``issuer_url``."""
        path = _write_home_config(home, "[sync]\nserver_url = 42\n")
        before = path.read_text(encoding="utf-8")
        _write_session(home, issuer_url=LIVE_ISSUER_URL)

        result = HostedEndpointSessionBackfillMigration().apply(Path("/any/project"))

        assert result.success is True
        assert path.read_text(encoding="utf-8") == before

    def test_apply_is_no_op_when_no_session_file(self, home: Path) -> None:
        auth_dir = _auth_dir(home)

        result = HostedEndpointSessionBackfillMigration().apply(Path("/any/project"))

        assert result.success is True
        assert not (home / "config.toml").exists()
        # No mkdir anywhere in the read-only path (module docstring).
        assert not auth_dir.exists()

    def test_apply_is_no_op_when_session_issuer_url_is_none(self, home: Path) -> None:
        auth_dir = _write_session(home, issuer_url=None)
        before = _snapshot_dir(auth_dir)

        result = HostedEndpointSessionBackfillMigration().apply(Path("/any/project"))

        assert result.success is True
        assert not (home / "config.toml").exists()
        _assert_auth_dir_byte_unchanged(before, _snapshot_dir(auth_dir))

    def test_apply_is_no_op_when_session_issuer_is_retired(self, home: Path) -> None:
        """D5: never backfill the retired first-party endpoint."""
        auth_dir = _write_session(home, issuer_url=RETIRED_URL)
        before = _snapshot_dir(auth_dir)

        result = HostedEndpointSessionBackfillMigration().apply(Path("/any/project"))

        assert result.success is True
        assert not (home / "config.toml").exists()
        _assert_auth_dir_byte_unchanged(before, _snapshot_dir(auth_dir))

    def test_apply_never_touches_hosted_drain_table(self, home: Path) -> None:
        """A backfilled endpoint is not a backfilled drain consent (spec D-5):
        any pre-seeded ``[hosted]`` table is carried through unchanged."""
        _write_home_config(home, "[hosted]\ndrain = false\n")
        _write_session(home, issuer_url=LIVE_ISSUER_URL)

        HostedEndpointSessionBackfillMigration().apply(Path("/any/project"))

        data = toml.load(home / "config.toml")
        assert data["hosted"] == {"drain": False}
        assert data["sync"]["server_url"] == LIVE_ISSUER_URL

    def test_apply_no_op_on_corrupt_session_and_dir_byte_unchanged(self, home: Path) -> None:
        auth_dir = _write_session(home, issuer_url=LIVE_ISSUER_URL)
        (auth_dir / "session.json").write_text("{not valid json", encoding="utf-8")
        before = _snapshot_dir(auth_dir)

        result = HostedEndpointSessionBackfillMigration().apply(Path("/any/project"))

        assert result.success is True
        assert not (home / "config.toml").exists()
        _assert_auth_dir_byte_unchanged(before, _snapshot_dir(auth_dir))

    def test_apply_no_op_on_legacy_v2_blob_and_dir_byte_unchanged(self, home: Path) -> None:
        auth_dir = _write_session(home, issuer_url=LIVE_ISSUER_URL)
        raw = json.loads((auth_dir / "session.json").read_text(encoding="utf-8"))
        raw["version"] = 2
        (auth_dir / "session.json").write_text(json.dumps(raw), encoding="utf-8")
        before = _snapshot_dir(auth_dir)

        result = HostedEndpointSessionBackfillMigration().apply(Path("/any/project"))

        assert result.success is True
        assert not (home / "config.toml").exists()
        _assert_auth_dir_byte_unchanged(before, _snapshot_dir(auth_dir))

    def test_apply_no_op_on_wrong_key_correct_length(self, home: Path) -> None:
        """The real ``InvalidTag`` decrypt-failure path (review cycle 1,
        Issue 5): a 32-byte key that is not the one the session was
        encrypted with must degrade the same as every other failure mode."""
        auth_dir = _write_session(home, issuer_url=LIVE_ISSUER_URL)
        (auth_dir / "session.key").write_bytes(secrets.token_bytes(32))
        before = _snapshot_dir(auth_dir)

        result = HostedEndpointSessionBackfillMigration().apply(Path("/any/project"))

        assert result.success is True
        assert not (home / "config.toml").exists()
        _assert_auth_dir_byte_unchanged(before, _snapshot_dir(auth_dir))

    @_POSIX_ONLY
    def test_apply_no_op_on_unsafe_session_key_permissions(self, home: Path) -> None:
        """NFR-013 (review cycle 1, Issue 3): mirrors
        ``FileFallbackStorage._decrypt``'s v3-branch permission check on
        ``session.key`` — a group/world-readable key is refused, never
        decrypted, so the endpoint is never backfilled from it."""
        auth_dir = _write_session(home, issuer_url=LIVE_ISSUER_URL)
        os.chmod(auth_dir / "session.key", _UNSAFE_KEY_MODE)
        before = _snapshot_dir(auth_dir)

        result = HostedEndpointSessionBackfillMigration().apply(Path("/any/project"))

        assert result.success is True
        assert not (home / "config.toml").exists()
        _assert_auth_dir_byte_unchanged(before, _snapshot_dir(auth_dir))

    @_POSIX_ONLY
    def test_apply_no_op_on_unsafe_session_json_permissions(self, home: Path) -> None:
        """NFR-013 (review cycle 1, Issue 3): mirrors
        ``FileFallbackStorage.read()``'s own permission check on the session
        file itself."""
        auth_dir = _write_session(home, issuer_url=LIVE_ISSUER_URL)
        os.chmod(auth_dir / "session.json", _UNSAFE_KEY_MODE)
        before = _snapshot_dir(auth_dir)

        result = HostedEndpointSessionBackfillMigration().apply(Path("/any/project"))

        assert result.success is True
        assert not (home / "config.toml").exists()
        _assert_auth_dir_byte_unchanged(before, _snapshot_dir(auth_dir))

    def test_apply_no_op_on_unparseable_config_with_valid_session(self, home: Path) -> None:
        """Review cycle 1, Issue 1(a): T031 step 3 says to treat an
        unparseable config as "not configured" but never clobber the file.
        A valid, backfillable session must not make this migration rewrite
        (or replace) a config.toml it cannot safely parse."""
        path = _write_home_config(home, "this is = = not valid toml")
        before_config = path.read_text(encoding="utf-8")
        auth_dir = _write_session(home, issuer_url=LIVE_ISSUER_URL)
        before_auth = _snapshot_dir(auth_dir)

        result = HostedEndpointSessionBackfillMigration().apply(Path("/any/project"))

        assert result.success is True
        assert path.read_text(encoding="utf-8") == before_config
        assert "unparseable" in " ".join(result.changes_made) or "unparseable" in " ".join(result.warnings)
        _assert_auth_dir_byte_unchanged(before_auth, _snapshot_dir(auth_dir))

    def test_detect_false_on_unparseable_config_with_valid_session(self, home: Path) -> None:
        """Companion to the apply-side no-op above: ``detect()`` must not
        claim this migration is needed when it cannot safely act on it —
        otherwise the runner records it as applied and a later fix to
        config.toml never gets a chance to be backfilled (non-blocking
        item 7)."""
        _write_home_config(home, "this is = = not valid toml")
        _write_session(home, issuer_url=LIVE_ISSUER_URL)

        assert HostedEndpointSessionBackfillMigration().detect(Path("/any/project")) is False

    def test_apply_no_op_on_non_table_sync_with_valid_session(self, home: Path) -> None:
        """Review cycle 1, Issue 1(b): a ``sync`` value that parses but is
        not a table (e.g. a stray string) is a file this migration cannot
        safely understand — same disposition as unparseable TOML: refuse,
        preserve, warn. Never silently replace the non-table value with a
        freshly-built ``[sync]`` table."""
        path = _write_home_config(home, 'sync = "not-a-table"\n')
        before_config = path.read_text(encoding="utf-8")
        auth_dir = _write_session(home, issuer_url=LIVE_ISSUER_URL)
        before_auth = _snapshot_dir(auth_dir)

        result = HostedEndpointSessionBackfillMigration().apply(Path("/any/project"))

        assert result.success is True
        assert path.read_text(encoding="utf-8") == before_config
        joined = " ".join(result.changes_made) + " ".join(result.warnings)
        assert "not a table" in joined or "unparseable" in joined
        _assert_auth_dir_byte_unchanged(before_auth, _snapshot_dir(auth_dir))

    def test_detect_false_on_non_table_sync_with_valid_session(self, home: Path) -> None:
        _write_home_config(home, 'sync = "not-a-table"\n')
        _write_session(home, issuer_url=LIVE_ISSUER_URL)

        assert HostedEndpointSessionBackfillMigration().detect(Path("/any/project")) is False

    def test_apply_dry_run_leaves_everything_untouched(self, home: Path) -> None:
        auth_dir = _write_session(home, issuer_url=LIVE_ISSUER_URL)
        before_auth = _snapshot_dir(auth_dir)

        result = HostedEndpointSessionBackfillMigration().apply(Path("/any/project"), dry_run=True)

        assert result.success is True
        assert not (home / "config.toml").exists()
        assert any("would backfill" in change for change in result.changes_made)
        _assert_auth_dir_byte_unchanged(before_auth, _snapshot_dir(auth_dir))

    def test_apply_is_idempotent(self, home: Path) -> None:
        _write_session(home, issuer_url=LIVE_ISSUER_URL)
        migration = HostedEndpointSessionBackfillMigration()

        first = migration.apply(Path("/any/project"))
        second = migration.apply(Path("/any/project"))

        assert first.success is True
        assert second.success is True
        data = toml.load(home / "config.toml")
        assert data["sync"]["server_url"] == LIVE_ISSUER_URL
        assert "endpoint already configured" in " ".join(second.changes_made)

    def test_apply_never_calls_encrypted_file_storage_read(self, home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """D6: the backfill must never call the mutating public read API."""
        from specify_cli.auth.secure_storage.file_fallback import FileFallbackStorage as _Storage

        _write_session(home, issuer_url=LIVE_ISSUER_URL)

        def _boom(self: object) -> None:
            raise AssertionError("EncryptedFileStorage.read() must never be called by this migration")

        monkeypatch.setattr(_Storage, "read", _boom)

        result = HostedEndpointSessionBackfillMigration().apply(Path("/any/project"))

        assert result.success is True
        data = toml.load(home / "config.toml")
        assert data["sync"]["server_url"] == LIVE_ISSUER_URL

    def test_apply_changes_made_never_names_token_material(self, home: Path) -> None:
        """Only ``issuer_url`` (a bare URL) may appear in operator-facing
        text — never an access/refresh token value."""
        _write_session(home, issuer_url=LIVE_ISSUER_URL)

        result = HostedEndpointSessionBackfillMigration().apply(Path("/any/project"))

        joined = " ".join(result.changes_made) + " ".join(result.warnings) + " ".join(result.errors)
        assert "at-secret-do-not-log" not in joined
        assert "rt-secret-do-not-log" not in joined


# ---------------------------------------------------------------------------
# Sequencing with the sibling delete migration (review cycle 1, Issue 2)
# ---------------------------------------------------------------------------


class TestMigrationSequencing:
    """WP Risks section: "confirm ... that the delete-migration's
    target_version sorts before ... the backfill migration's, and add an
    integration-style test exercising both in sequence within one upgrade
    run to confirm the end state is 'backfilled from session,' not 'stuck
    deleted.'" Drives both migrations through the real
    ``MigrationRegistry.get_applicable`` ordering rather than hand-calling
    each ``apply()`` independently, so a future reordering of
    ``target_version`` values would fail this test instead of silently
    reversing the two migrations' effect."""

    def test_delete_then_backfill_ends_backfilled_not_stuck_deleted(self, home: Path) -> None:
        _write_home_config(home, f'[sync]\nserver_url = "{RETIRED_URL}"\npoll_interval = 30\n\n[hosted]\ndrain = false\n')
        _write_session(home, issuer_url=LIVE_ISSUER_URL)

        applicable = MigrationRegistry.get_applicable("3.2.6", "4.0.0rc5", project_path=Path("/any/project"))
        applicable_ids = [m.migration_id for m in applicable]
        assert SIBLING_MIGRATION_ID in applicable_ids
        assert MIGRATION_ID in applicable_ids
        # Sorted by target_version (4.0.0rc1 < 4.0.0rc5): the delete
        # migration must run before the backfill, never the reverse, or the
        # backfill would see the retired value as "still configured" and
        # never fire.
        assert applicable_ids.index(SIBLING_MIGRATION_ID) < applicable_ids.index(MIGRATION_ID)

        for migration in applicable:
            result = migration.apply(Path("/any/project"))
            assert result.success is True

        data = toml.load(home / "config.toml")
        assert data["sync"]["server_url"] == LIVE_ISSUER_URL
        assert data["sync"]["poll_interval"] == 30
        assert data["hosted"] == {"drain": False}

    def test_retired_config_and_retired_issuer_ends_unconfigured_not_resurrected(self, home: Path) -> None:
        """D5 interacting with FR-013: a retired config value AND a retired
        session issuer must never resurrect the retired target — the delete
        migration removes it, and D5 refuses to let the backfill bring it
        back."""
        _write_home_config(home, f'[sync]\nserver_url = "{RETIRED_URL}"\n')
        _write_session(home, issuer_url=RETIRED_URL)

        applicable = MigrationRegistry.get_applicable("3.2.6", "4.0.0rc5", project_path=Path("/any/project"))
        for migration in applicable:
            migration.apply(Path("/any/project"))

        data = toml.load(home / "config.toml")
        assert "server_url" not in data.get("sync", {})
