"""Shared fixtures for ``tests/auth/integration/``.

These fixtures install a deterministic ``SPEC_KITTY_SAAS_URL`` and provide
an in-memory :class:`SecureStorage` that every integration test can inject
via ``patch("specify_cli.auth.secure_storage.SecureStorage.from_environment")``.

Per WP11 (feature 080), integration tests exercise the real Typer app via
:class:`typer.testing.CliRunner`. They must never hit a real network or the
real ``~/.spec-kitty/auth`` directory — both are mocked.

Security note: the fake URL deliberately uses ``https://saas.test`` so a
test that accidentally escapes its mocks fails with a DNS/connection error
rather than hitting any production or staging SaaS.
"""

from __future__ import annotations

from typing import Any

import pytest

from specify_cli.auth import reset_token_manager
from specify_cli.auth.flows.client_credentials import (
    CLIENT_ID_ENV_VAR,
    CLIENT_SECRET_ENV_VAR,
    CLIENT_SECRET_FILE_ENV_VAR,
)
from specify_cli.auth.secure_storage.abstract import SecureStorage
from specify_cli.auth.session import StoredSession


_TEST_SAAS_URL = "https://saas.test"


class FakeSecureStorage(SecureStorage):
    """In-memory :class:`SecureStorage` used across integration tests.

    Captures writes and deletes so tests can assert that
    ``tm.set_session`` / ``tm.clear_session`` reached the backend.
    Tests inject this via
    ``patch("specify_cli.auth.secure_storage.SecureStorage.from_environment",
    return_value=FakeSecureStorage(...))``.
    """

    def __init__(self, initial: StoredSession | None = None) -> None:
        self._session: StoredSession | None = initial
        self.writes: list[StoredSession] = []
        self.deletes: int = 0

    def read(self) -> StoredSession | None:
        return self._session

    def write(self, session: StoredSession) -> None:
        self._session = session
        self.writes.append(session)

    def delete(self) -> None:
        self._session = None
        self.deletes += 1

    @property
    def backend_name(self) -> str:
        return "file"


@pytest.fixture
def fake_storage() -> FakeSecureStorage:
    """Return a fresh :class:`FakeSecureStorage` instance per test."""
    return FakeSecureStorage()


@pytest.fixture(autouse=True)
def _isolate_auth_env(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Guarantee a clean auth environment for each integration test.

    - Sets ``SPEC_KITTY_SAAS_URL`` to a sentinel value that cannot resolve.
    - Resets the process-wide ``TokenManager`` before and after the test.
    - Clears the machine-credential variables, so a mis-dispatch into the
      client-credentials flow on a runner that exports them cannot reach the
      network with real credentials.
    """
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", _TEST_SAAS_URL)
    for name in (CLIENT_ID_ENV_VAR, CLIENT_SECRET_ENV_VAR, CLIENT_SECRET_FILE_ENV_VAR):
        monkeypatch.delenv(name, raising=False)
    reset_token_manager()
    yield
    reset_token_manager()
