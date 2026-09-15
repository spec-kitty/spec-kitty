"""Tests for ``specify_cli.auth.loopback.state`` + ``state_manager`` (feature 080, WP02 T015).

Covers:

- :class:`PKCEState` construction, TTL, and ``is_expired`` truth table
- :class:`StateManager.generate` produces a usable state with a 43-char verifier
- :class:`StateManager.validate_not_expired` raises ``StateExpiredError`` when
  the state is expired and does nothing otherwise
- :class:`StateManager.cleanup` is a safe no-op (present for API symmetry)
"""

from __future__ import annotations

from kernel.clock import now_utc, timedelta

import pytest

from specify_cli.auth.errors import StateExpiredError
from specify_cli.auth.loopback.pkce import generate_pkce_pair
from specify_cli.auth.loopback.state import PKCEState
from specify_cli.auth.loopback.state_manager import StateManager


pytestmark = [pytest.mark.integration]

def test_pkce_state_create_populates_all_fields() -> None:
    verifier, challenge = generate_pkce_pair()
    state = PKCEState.create(verifier, challenge)

    assert state.code_verifier == verifier
    assert state.code_challenge == challenge
    assert state.code_challenge_method == "S256"
    assert state.state  # non-empty CSRF nonce
    assert state.created_at.tzinfo is not None
    assert state.expires_at.tzinfo is not None


def test_pkce_state_ttl_is_five_minutes() -> None:
    verifier, challenge = generate_pkce_pair()
    state = PKCEState.create(verifier, challenge)
    assert state.expires_at - state.created_at == timedelta(minutes=5)


def test_pkce_state_is_not_expired_when_fresh() -> None:
    verifier, challenge = generate_pkce_pair()
    state = PKCEState.create(verifier, challenge)
    assert state.is_expired() is False


def test_pkce_state_is_expired_when_past_expiry() -> None:
    verifier, challenge = generate_pkce_pair()
    state = PKCEState.create(verifier, challenge)
    # Force expiry by rewriting expires_at into the past.
    state.expires_at = now_utc() - timedelta(seconds=1)
    assert state.is_expired() is True


def test_state_manager_generate_returns_fresh_state() -> None:
    manager = StateManager()
    state = manager.generate()

    assert isinstance(state, PKCEState)
    assert len(state.code_verifier) == 43
    assert state.code_challenge_method == "S256"
    assert state.is_expired() is False


def test_state_manager_generate_yields_unique_states() -> None:
    manager = StateManager()
    s1 = manager.generate()
    s2 = manager.generate()
    # Both the CSRF nonce and the verifier should differ between calls.
    assert s1.state != s2.state
    assert s1.code_verifier != s2.code_verifier


def test_state_manager_validate_not_expired_passes_for_fresh_state() -> None:
    manager = StateManager()
    state = manager.generate()
    # Should not raise.
    manager.validate_not_expired(state)


def test_state_manager_validate_not_expired_raises_on_expired() -> None:
    manager = StateManager()
    state = manager.generate()
    state.expires_at = now_utc() - timedelta(seconds=1)

    with pytest.raises(StateExpiredError) as exc_info:
        manager.validate_not_expired(state)

    # The error message should reference the expiry so operators can tell
    # whether the TTL was wrong or the flow was too slow.
    assert "expire" in str(exc_info.value).lower()


def test_state_manager_cleanup_is_noop() -> None:
    manager = StateManager()
    state = manager.generate()
    # cleanup should not raise and should not mutate the state in-place
    # (it's a hook for future persistent state).
    manager.cleanup(state)
    assert state.code_verifier  # still readable
