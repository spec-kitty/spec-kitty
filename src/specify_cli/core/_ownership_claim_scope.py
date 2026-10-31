"""Request lifetime for immutable basic ownership claims; no custody decisions."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specify_cli.core.checkout_ownership import OwnershipClaim

_claims: ContextVar[dict[tuple[Path, Path], OwnershipClaim] | None] = ContextVar("owned_command_claims", default=None)


def command_claims() -> dict[tuple[Path, Path], OwnershipClaim] | None:
    return _claims.get()


@contextmanager
def owned_claim_scope() -> Iterator[None]:
    """Use a fresh scope per root invocation and restore it on every exit."""
    token = _claims.set({})
    try:
        yield
    finally:
        _claims.reset(token)
