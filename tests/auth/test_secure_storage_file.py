"""Tests for ``specify_cli.auth.secure_storage.file_fallback`` (feature 080, WP01 T006).

Critical coverage (per decision D-8 / constraint C-011):

- Stable random 32-byte key stored at 0600.
- AES-256-GCM round-trip.
- v1 plaintext format is rejected with a clear error.
- Tampered ciphertext fails authentication → ``StorageDecryptionError``.
- Legacy v2 hostname-bound sessions migrate to v3 on read.
- Concurrent writes coordinated by the FileLock (no corruption).
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import stat
import threading
from kernel.clock import datetime, now_utc, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from specify_cli.auth.errors import SecureStorageError, StorageDecryptionError
from specify_cli.auth.secure_storage.file_fallback import FileFallbackStorage, _get_uid
from specify_cli.auth.session import StoredSession, Team


pytestmark = [pytest.mark.integration]


def _now() -> datetime:
    return now_utc()


def _make_session(access_token: str = "access") -> StoredSession:
    now = _now()
    return StoredSession(
        user_id="user-1",
        email="a@b.com",
        name="A B",
        teams=[Team(id="t1", name="T1", role="owner")],
        default_team_id="t1",
        access_token=access_token,
        refresh_token="refresh",
        session_id="sess",
        issued_at=now,
        access_token_expires_at=now + timedelta(hours=1),
        refresh_token_expires_at=None,
        scope="openid",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
    )


class FastFileFallback(FileFallbackStorage):
    """Subclass with a lower scrypt cost to keep test suite runtime reasonable."""

    _scrypt_n = 2**10
    _scrypt_r = 8
    _scrypt_p = 1


@pytest.fixture
def storage(tmp_path: Path) -> FastFileFallback:
    return FastFileFallback(base_dir=tmp_path)


def test_default_store_dir_uses_spec_kitty_auth_root(monkeypatch, tmp_path: Path):
    # WP03: default_store_dir() now resolves through get_runtime_root(); with
    # SPEC_KITTY_HOME unset on POSIX it still equals ``~/.spec-kitty/auth``.
    monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    storage = FastFileFallback()
    assert storage.store_path == tmp_path / ".spec-kitty" / "auth"


def test_get_uid_returns_zero_when_platform_has_no_getuid(monkeypatch):
    monkeypatch.delattr(os, "getuid", raising=False)
    assert _get_uid() == 0


def test_read_returns_none_when_no_file(storage: FastFileFallback):
    assert storage.read() is None


def test_roundtrip_write_read(storage: FastFileFallback):
    s = _make_session()
    storage.write(s)
    loaded = storage.read()
    assert loaded == s


def test_write_creates_key_file_with_0600(storage: FastFileFallback, tmp_path: Path):
    storage.write(_make_session())
    key_file = tmp_path / "session.key"
    assert key_file.exists()
    # Check permissions (POSIX only). Windows skips this.
    if hasattr(os, "getuid"):
        mode = stat.S_IMODE(key_file.stat().st_mode)
        assert mode == 0o600
    assert len(key_file.read_bytes()) == 32


def test_write_creates_credentials_file_with_0600(storage: FastFileFallback, tmp_path: Path):
    storage.write(_make_session())
    cred_file = tmp_path / "session.json"
    assert cred_file.exists()
    if hasattr(os, "getuid"):
        mode = stat.S_IMODE(cred_file.stat().st_mode)
        assert mode == 0o600


def test_credentials_dir_created_with_0700(storage: FastFileFallback, tmp_path: Path):
    sub = tmp_path / "new-subdir"
    storage = FastFileFallback(base_dir=sub)
    storage.write(_make_session())
    assert sub.exists()
    if hasattr(os, "getuid"):
        mode = stat.S_IMODE(sub.stat().st_mode)
        assert mode == 0o700


def test_key_is_random_across_instances(tmp_path: Path):
    # Two fresh storages in different dirs should produce different keys.
    s1 = FastFileFallback(base_dir=tmp_path / "a")
    s2 = FastFileFallback(base_dir=tmp_path / "b")
    s1.write(_make_session())
    s2.write(_make_session())
    key1 = (tmp_path / "a" / "session.key").read_bytes()
    key2 = (tmp_path / "b" / "session.key").read_bytes()
    assert key1 != key2


def test_encrypted_file_does_not_contain_plaintext(storage: FastFileFallback, tmp_path: Path):
    s = _make_session(access_token="SUPER_SECRET_TOKEN_VALUE")
    storage.write(s)
    raw_bytes = (tmp_path / "session.json").read_bytes()
    # The access token must not appear in the on-disk bytes.
    assert b"SUPER_SECRET_TOKEN_VALUE" not in raw_bytes


def test_file_format_is_version_3(storage: FastFileFallback, tmp_path: Path):
    storage.write(_make_session())
    blob = json.loads((tmp_path / "session.json").read_text())
    assert blob["version"] == 3
    assert "nonce" in blob
    assert "ciphertext" in blob


def test_v1_plaintext_is_rejected(storage: FastFileFallback, tmp_path: Path):
    # Simulate a stale v1 file.
    (tmp_path).mkdir(parents=True, exist_ok=True)
    (tmp_path / "session.json").write_text(json.dumps({"version": 1, "user_id": "old"}))
    os.chmod(tmp_path / "session.json", 0o600)
    with pytest.raises(StorageDecryptionError) as excinfo:
        storage.read()
    assert "v1" in str(excinfo.value) or "version" in str(excinfo.value).lower()


def test_missing_key_rejects_decryption_and_self_heals(storage: FastFileFallback, tmp_path: Path):
    storage.write(_make_session())
    (tmp_path / "session.key").unlink()
    with pytest.raises(StorageDecryptionError):
        storage.read()
    assert not (tmp_path / "session.json").exists()


def test_tampered_ciphertext_fails_authentication(storage: FastFileFallback, tmp_path: Path):
    storage.write(_make_session())
    cred_file = tmp_path / "session.json"
    blob = json.loads(cred_file.read_text())
    # Flip a byte of the ciphertext hex to break the AES-GCM tag.
    ct = bytearray(bytes.fromhex(blob["ciphertext"]))
    ct[0] ^= 0xFF
    blob["ciphertext"] = bytes(ct).hex()
    cred_file.write_text(json.dumps(blob))
    with pytest.raises(StorageDecryptionError):
        storage.read()
    assert not cred_file.exists()


def test_wrong_key_fails_decryption(storage: FastFileFallback, tmp_path: Path):
    """Replacing the stable key fails closed and removes stale ciphertext."""
    storage.write(_make_session())
    key_file = tmp_path / "session.key"
    import secrets

    key_file.write_bytes(secrets.token_bytes(32))
    with pytest.raises(StorageDecryptionError):
        storage.read()
    assert not (tmp_path / "session.json").exists()


def test_hostname_change_does_not_invalidate_v3_session(storage: FastFileFallback, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("specify_cli.auth.secure_storage.file_fallback.socket.gethostname", lambda: "host-a")
    session = _make_session()
    storage.write(session)
    monkeypatch.setattr("specify_cli.auth.secure_storage.file_fallback.socket.gethostname", lambda: "host-b")
    assert storage.read() == session


def test_legacy_v2_session_is_read_and_migrated(storage: FastFileFallback, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("specify_cli.auth.secure_storage.file_fallback.socket.gethostname", lambda: "legacy-host")
    session = _make_session()
    salt = storage._load_or_create_salt()
    key = storage._derive_legacy_key(salt)
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, session.to_json().encode(), None)
    (tmp_path / "session.json").write_text(json.dumps({"version": 2, "nonce": nonce.hex(), "ciphertext": ciphertext.hex()}))
    os.chmod(tmp_path / "session.json", 0o600)

    assert storage.read() == session
    assert json.loads((tmp_path / "session.json").read_text())["version"] == 3
    assert (tmp_path / "session.key").exists()
    assert not (tmp_path / "session.salt").exists()


def test_malformed_json_raises_decryption_error(storage: FastFileFallback, tmp_path: Path):
    (tmp_path).mkdir(parents=True, exist_ok=True)
    (tmp_path / "session.json").write_text("{not-json")
    os.chmod(tmp_path / "session.json", 0o600)
    with pytest.raises(StorageDecryptionError):
        storage.read()


def test_delete_removes_cred_key_and_legacy_salt(storage: FastFileFallback, tmp_path: Path):
    storage.write(_make_session())
    assert (tmp_path / "session.json").exists()
    assert (tmp_path / "session.key").exists()
    (tmp_path / "session.salt").write_bytes(os.urandom(16))
    storage.delete()
    assert not (tmp_path / "session.json").exists()
    assert not (tmp_path / "session.salt").exists()
    assert not (tmp_path / "session.key").exists()


def test_delete_is_idempotent(storage: FastFileFallback):
    storage.delete()
    storage.delete()


def test_concurrent_writes_do_not_corrupt(tmp_path: Path):
    """FileLock must serialize writes so the last one wins and the file stays valid."""
    storage = FastFileFallback(base_dir=tmp_path)
    # Pre-create so all workers reuse the same salt.
    storage.write(_make_session())

    def writer(i: int) -> None:
        worker = FastFileFallback(base_dir=tmp_path)
        worker.write(_make_session(access_token=f"token-{i}"))

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(writer, range(16)))

    loaded = storage.read()
    assert loaded is not None
    # The final access_token must match one of the worker tokens.
    assert loaded.access_token.startswith("token-")


def test_read_holds_lock_across_decrypt_while_session_rotates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A logout/login cannot make a reader delete the replacement session."""
    storage = FastFileFallback(base_dir=tmp_path)
    old_session = _make_session("old-token")
    new_session = _make_session("new-token")
    storage.write(old_session)

    decrypt_started = threading.Event()
    allow_decrypt = threading.Event()
    mutation_finished = threading.Event()
    original_decrypt = storage._decrypt

    def paused_decrypt(blob: dict[str, object]) -> bytes:
        decrypt_started.set()
        assert allow_decrypt.wait(timeout=2)
        return original_decrypt(blob)

    monkeypatch.setattr(storage, "_decrypt", paused_decrypt)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        read_future = pool.submit(storage.read)
        assert decrypt_started.wait(timeout=2)

        def rotate_session() -> None:
            storage.delete()
            storage.write(new_session)
            mutation_finished.set()

        mutation_future = pool.submit(rotate_session)
        assert not mutation_finished.wait(timeout=0.1)
        allow_decrypt.set()
        assert read_future.result(timeout=2) == old_session
        mutation_future.result(timeout=2)

    monkeypatch.setattr(storage, "_decrypt", original_decrypt)
    assert storage.read() == new_session


@pytest.mark.skipif(not hasattr(os, "getuid"), reason="POSIX-only permission check")
def test_read_rejects_group_readable_credentials(storage: FastFileFallback, tmp_path: Path):
    """NFR-013: read() must reject credentials files that are not owner-only."""
    storage.write(_make_session())
    cred_file = tmp_path / "session.json"
    # Widen permissions to group-readable (0640).
    os.chmod(cred_file, 0o640)
    with pytest.raises(SecureStorageError, match="unsafe permissions"):
        storage.read()


@pytest.mark.skipif(not hasattr(os, "getuid"), reason="POSIX-only permission check")
def test_read_rejects_world_readable_credentials(storage: FastFileFallback, tmp_path: Path):
    """NFR-013: read() must reject world-readable credentials files."""
    storage.write(_make_session())
    cred_file = tmp_path / "session.json"
    os.chmod(cred_file, 0o644)
    with pytest.raises(SecureStorageError, match="unsafe permissions"):
        storage.read()


def test_backend_name_is_file(storage: FastFileFallback):
    assert storage.backend_name == "file"


def test_rewrite_reuses_existing_key(storage: FastFileFallback, tmp_path: Path):
    storage.write(_make_session())
    key_before = (tmp_path / "session.key").read_bytes()
    storage.write(_make_session(access_token="different"))
    key_after = (tmp_path / "session.key").read_bytes()
    assert key_before == key_after
