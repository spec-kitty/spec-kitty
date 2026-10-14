"""Unit tests for specify_cli.invocation.adapters.

Covers the seam's degradation contract, the register/dispatch round-trip,
idempotency by qualified name, and exception suppression.

``get_saas_client`` degrades to ``None`` — no transport, so nothing can leave.
The former egress-consent seam that shared this module retired with the sync
transport (issue #5); what remains is a deliberately empty slot that no
production code registers into, which is why absence here is the safe state and
not a fault.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from specify_cli.invocation.adapters import (
    get_saas_client,
    register_saas_client_factory,
    reset_adapters,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# A dummy repo path — never touched on disk; only fed through the in-memory
# adapter registry (to mocked factories). A rooted non-temp literal keeps it
# clear of the test-tree tmp-literal ratchet.
_DUMMY_PATH = Path("/repo")


@pytest.fixture(autouse=True)
def _clean_adapters() -> None:  # type: ignore[return]
    """Reset the adapter registry before and after every test."""
    reset_adapters()
    yield
    reset_adapters()


# ---------------------------------------------------------------------------
# get_saas_client — safe-degrade when no factory is registered
# ---------------------------------------------------------------------------


def test_get_saas_client_returns_none_when_unregistered() -> None:
    """Dispatching with no registered factory must return None."""
    result = get_saas_client(_DUMMY_PATH)
    assert result is None


# ---------------------------------------------------------------------------
# register_saas_client_factory — dispatch round-trip
# ---------------------------------------------------------------------------


def test_get_saas_client_calls_registered_factory() -> None:
    """After registration the factory is called with the path and result is returned."""
    fake_client = MagicMock()
    mock_factory = MagicMock(return_value=fake_client)
    register_saas_client_factory(mock_factory, confirms_request_text_admission_gate=True)

    result = get_saas_client(_DUMMY_PATH)

    mock_factory.assert_called_once_with(_DUMMY_PATH)
    assert result is fake_client


# ---------------------------------------------------------------------------
# Idempotency — re-registering the same qualified name replaces the entry
# ---------------------------------------------------------------------------


def test_register_saas_client_factory_idempotent_by_qualname() -> None:
    """Re-registering a factory with the same qualname replaces it."""
    call_log: list[str] = []

    def _factory_v1(path: Path) -> object:  # noqa: ARG001
        call_log.append("v1")
        return object()

    def _factory_v2(path: Path) -> object:  # noqa: ARG001
        call_log.append("v2")
        return object()

    _factory_v2.__qualname__ = _factory_v1.__qualname__
    _factory_v2.__module__ = _factory_v1.__module__

    register_saas_client_factory(_factory_v1, confirms_request_text_admission_gate=True)
    register_saas_client_factory(_factory_v2, confirms_request_text_admission_gate=True)

    get_saas_client(_DUMMY_PATH)

    assert call_log == ["v2"]


# ---------------------------------------------------------------------------
# Exception suppression — a raising factory degrades to "no transport"
# ---------------------------------------------------------------------------


def test_get_saas_client_returns_none_on_factory_exception() -> None:
    """An exception in the factory is caught; dispatch returns None."""

    def _exploding_factory(_path: Path) -> object:
        raise RuntimeError("boom")

    register_saas_client_factory(_exploding_factory, confirms_request_text_admission_gate=True)

    result = get_saas_client(_DUMMY_PATH)

    assert result is None


# ---------------------------------------------------------------------------
# Registration-time assertion (issue #117) — a future registrant cannot ship
# ``request_text`` off-machine by merely calling the function; it must
# affirmatively assert the admission gate it owns.
# ---------------------------------------------------------------------------


def test_register_saas_client_factory_requires_explicit_gate_confirmation() -> None:
    """Omitting the mandatory kwarg is a ``TypeError`` — no silent default."""

    def _factory(_path: Path) -> object:
        return object()

    with pytest.raises(TypeError):
        register_saas_client_factory(_factory)  # type: ignore[call-arg]


def test_register_saas_client_factory_rejects_false_confirmation() -> None:
    """Passing ``False`` (or anything but ``True``) is refused, not silently accepted."""

    def _factory(_path: Path) -> object:
        return object()

    with pytest.raises(ValueError, match="confirms_request_text_admission_gate"):
        register_saas_client_factory(_factory, confirms_request_text_admission_gate=False)

    # The registry must remain empty — the rejected call must not have landed.
    assert get_saas_client(_DUMMY_PATH) is None


# ---------------------------------------------------------------------------
# register_saas_client_factory — export pin (SC-008, #3109 seam, Decision D-1)
# ---------------------------------------------------------------------------


def test_register_saas_client_factory_is_exported_from_invocation_package() -> None:
    """Pins the *export* half of the `#3109` seam (SC-008).

    D-1 keeps ``register_saas_client_factory`` rather than deleting it: the read
    side (``get_saas_client``) has a live production consumer inside the
    propagator, so the write side stays too, to keep the empty seam legible as a
    decision rather than an oversight. A decision to keep something is not
    self-enforcing — nothing else in the diff would notice if the re-export
    quietly disappeared, so the keep half needs its own pin.

    This is the *export* half specifically, not the definition: deleting the
    ``def`` in ``adapters.py`` would be a collection-time ``ImportError`` here,
    so it is not a discriminating before-state. What is genuinely unpinned is
    ``invocation/__init__.py``'s re-export and its ``__all__`` entry —
    ``adapters.py`` itself declares no ``__all__``, nothing in ``src/`` imports
    the symbol via the package (``from specify_cli.invocation import ...``), and
    ``test_all_declarations_required.py`` gates only ``src/charter/`` and
    ``src/kernel/``, not this package.
    """
    import specify_cli.invocation as invocation_pkg

    assert "register_saas_client_factory" in invocation_pkg.__all__
    # Identity, not just presence: the re-exported name must be the *same*
    # callable as the one this module already imports directly from
    # ``adapters`` — proof the package re-export is wired, not shadowed by an
    # unrelated same-named object.
    assert invocation_pkg.register_saas_client_factory is register_saas_client_factory


# ---------------------------------------------------------------------------
# Propagator safe-degrade via the seam (integration-style unit test)
# ---------------------------------------------------------------------------


def test_propagator_safe_degrades_when_seam_unregistered(tmp_path: Path) -> None:
    """propagator._propagate_one must not raise when no adapters are registered.

    With nothing registered the client lookup answers ``None`` and ``_propagate_one``
    returns before any policy lookup or send — the no-op that used to come from the
    auth gate, and before FR-025 from an unanswered consent gate read as permission.
    This test imports propagator directly to verify the wiring without requiring
    any transport package.
    """
    from specify_cli.invocation import propagator
    from specify_cli.invocation.record import OpStartedEvent

    record = OpStartedEvent(
        invocation_id="01HXYZABCDEFGH1JK2MN3PQRST",
        profile_id="test-profile",
        action="implement",
        request_text="",
        actor="claude",
        mode_of_work="task_execution",
        governance_context_hash="abcdef0123456789",
        governance_context_available=False,
        started_at="2026-01-01T00:00:00Z",
    )

    # Must not raise; should silently return (no transport registered).
    propagator._propagate_one(record, tmp_path)


# ---------------------------------------------------------------------------
# No production registration (NFR-003 / Degradation Contract)
# These tests exercise the ACTUAL registry state — NOT a patched seam — proving
# no transport is wired up in production.
# ---------------------------------------------------------------------------


def test_no_saas_client_factory_is_registered_anywhere() -> None:
    """No transport is registered, even with a fully connected token manager.

    Replaces three cases that pinned the behaviour of a factory since deleted
    (``..._returns_none_when_not_authenticated``,
    ``..._returns_none_when_ws_client_not_connected``,
    ``..._returns_existing_client_when_connected``). All three drove that factory by
    setting ``token_manager._ws_client`` — and setting it in a test was the **only**
    way that attribute has ever been assigned. ``src/`` contains no ``=`` and no
    ``setattr`` for it, and ``specify_cli/auth/`` does not declare it, so the factory
    returned ``None`` in every real process and ``invocation/propagator.py``'s send
    has never executed outside this suite. Two of the three were passing for the
    wrong reason (a ``None`` that agreed with their assertion by accident) and the
    third asserted a production behaviour that did not exist.

    The pin is inverted and kept live: a connected client on the token manager still
    yields no transport, because there is no factory to find it. (The sync package
    that once held the registration retired with the transport, issue #5.) This reds
    if anyone registers one — which opens the propagator's egress path carrying
    ``request_text`` verbatim, the hazard FR-032 removed.
    """
    # No token-manager scaffolding: the hosted ``specify_cli.auth`` surface was
    # removed (#6164), and ``get_saas_client`` consults no token manager — it
    # returns None purely because no factory is registered. That None is exactly
    # the invariant under test, so the call stands alone (the former
    # connected-token-manager mock could never change the outcome).
    result = get_saas_client(_DUMMY_PATH)

    assert result is None, (
        "a SaaS-client factory is registered. That opens the invocation "
        "propagator's egress path, which carries request_text verbatim; #3030 FR-032 "
        "removed it deliberately and issue #5 deleted the registering package. If "
        "this is intended, prove the propagator's disclosure policy holds against "
        "the new transport first."
    )
