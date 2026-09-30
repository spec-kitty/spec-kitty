"""Validate explicit ownership claims for git checkouts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from mission_runtime import OwnedRefusalCode
from specify_cli.coordination.surface_resolver import (
    WorktreeRegistryUnavailable,
    read_worktree_registry,
)
from specify_cli.git.commit_helpers import is_worktree_of
from kernel.git_topology import (
    GitTopologyError,
    git_common_dir,
    git_toplevel,
)

from .errors import StructuredError

# review cycle 1: single authority. These two names stay exported here (T007
# asks for them), but bind to the mission_runtime.OwnedRefusalCode members
# instead of restating the strings as independent literals -- WP08's
# emit_owned_refusal validates against the registered enum, so a second copy
# could drift from it.
OWNED_CHECKOUT_IS_REPOSITORY_ROOT: Final = OwnedRefusalCode.OWNED_CHECKOUT_IS_REPOSITORY_ROOT
"""Minter-level refusal code (data-model.md registry): the claimed checkout
IS the repository root itself. Exported so :mod:`specify_cli.core.owned_mission`
imports the code rather than repeating the literal (Sonar S1192)."""

OWNED_CHECKOUT_IS_MISSION_WORKTREE: Final = OwnedRefusalCode.OWNED_CHECKOUT_IS_MISSION_WORKTREE
"""Minter-level refusal code: an explicit ``--owned-checkout`` names a
coordination worktree or a lane worktree already registered to the mission
being resolved. Exported for the same reason as
:data:`OWNED_CHECKOUT_IS_REPOSITORY_ROOT`."""


class OwnershipValidationResult(StrEnum):
    """Possible outcomes of validating an explicit checkout-ownership claim."""

    OWNED = "OWNED"
    UNOWNED_NO_OPT_IN = "UNOWNED_NO_OPT_IN"
    NESTED = "NESTED"
    FOREIGN_OR_MISMATCHED = "FOREIGN_OR_MISMATCHED"
    BROKEN_POINTER = "BROKEN_POINTER"


@dataclass(frozen=True)
class OwnershipClaim:
    """Structured result of checkout-ownership validation."""

    claimed_checkout: Path
    resolved_primary: Path
    validation_result: OwnershipValidationResult
    opted_in: bool
    detail: str | None = None


class CheckoutOwnershipError(StructuredError):
    """Base error for a rejected checkout-ownership claim."""

    error_code = "CHECKOUT_OWNERSHIP_REFUSED"

    def __init__(self, claim: OwnershipClaim) -> None:
        self.claim = claim
        self.validation_result = claim.validation_result
        super().__init__(claim.detail or claim.validation_result.value)


class UnownedNoOptInError(CheckoutOwnershipError):
    """The caller did not explicitly opt in to checkout ownership."""

    error_code = "WORKTREE_INVOCATION_REFUSED"


class NestedCheckoutError(CheckoutOwnershipError):
    """The claimed checkout is nested within another linked checkout."""

    error_code = "OWNERSHIP_NESTED"


class ForeignOrMismatchedCheckoutError(CheckoutOwnershipError):
    """The claimed checkout belongs to a different common repository."""

    error_code = "OWNERSHIP_FOREIGN"


class BrokenPointerCheckoutError(CheckoutOwnershipError):
    """Git topology could not be read safely for the claimed checkout."""

    error_code = "OWNERSHIP_BROKEN_POINTER"


class _GitTopologyUnavailable(RuntimeError):
    """An internal git common-dir probe failed."""


_ERROR_TYPES: dict[OwnershipValidationResult, type[CheckoutOwnershipError]] = {
    OwnershipValidationResult.UNOWNED_NO_OPT_IN: UnownedNoOptInError,
    OwnershipValidationResult.NESTED: NestedCheckoutError,
    OwnershipValidationResult.FOREIGN_OR_MISMATCHED: ForeignOrMismatchedCheckoutError,
    OwnershipValidationResult.BROKEN_POINTER: BrokenPointerCheckoutError,
}


def _claim(
    claimed_checkout: Path,
    resolved_primary: Path,
    result: OwnershipValidationResult,
    *,
    opted_in: bool,
    detail: str | None = None,
) -> OwnershipClaim:
    return OwnershipClaim(
        claimed_checkout=claimed_checkout,
        resolved_primary=resolved_primary,
        validation_result=result,
        opted_in=opted_in,
        detail=detail,
    )


def _git_common_dir(checkout: Path) -> Path:
    """Ownership-classifier common-dir probe (delegates to the unified primitive).

    Preserves this site's fail-closed contract: every topology-read failure —
    the primitive's typed :class:`GitTopologyError` (not-a-repo / unavailable)
    OR a raw ``OSError`` — folds into :class:`_GitTopologyUnavailable`, which the
    comparator maps to ``BROKEN_POINTER`` (mission
    write-path-integrity-01KZZD69 WP01, #3373).
    """
    try:
        return git_common_dir(checkout)
    except (GitTopologyError, OSError) as exc:
        raise _GitTopologyUnavailable(str(exc)) from exc


def _git_toplevel(checkout: Path) -> Path:
    """Ownership-classifier toplevel probe (delegates to the unified primitive).

    Same fail-closed mapping as :func:`_git_common_dir`: the ``toplevel`` value
    feeds the NESTED-vs-comparator classification, while any probe failure folds
    into :class:`_GitTopologyUnavailable` (-> ``BROKEN_POINTER``).
    """
    try:
        return git_toplevel(checkout)
    except (GitTopologyError, OSError) as exc:
        raise _GitTopologyUnavailable(str(exc)) from exc


def _rejected_comparator_claim(claimed_checkout: Path, resolved_primary: Path) -> OwnershipClaim:
    try:
        claimed_toplevel = _git_toplevel(claimed_checkout)
        claimed_common = _git_common_dir(claimed_checkout)
        primary_common = _git_common_dir(resolved_primary)
    except (OSError, _GitTopologyUnavailable) as exc:
        return _claim(
            claimed_checkout,
            resolved_primary,
            OwnershipValidationResult.BROKEN_POINTER,
            opted_in=True,
            detail=(f"Cannot validate claimed checkout {claimed_checkout} against resolved primary {resolved_primary}: {exc}"),
        )
    if claimed_toplevel != claimed_checkout:
        return _claim(
            claimed_checkout,
            resolved_primary,
            OwnershipValidationResult.NESTED,
            opted_in=True,
            detail=(f"Claimed checkout {claimed_checkout} is nested inside checkout root {claimed_toplevel}."),
        )
    if claimed_common == primary_common:
        return _claim(
            claimed_checkout,
            resolved_primary,
            OwnershipValidationResult.BROKEN_POINTER,
            opted_in=True,
            detail=(f"Git rejected claimed checkout {claimed_checkout} despite common dir {claimed_common} matching resolved primary {resolved_primary}."),
        )
    return _claim(
        claimed_checkout,
        resolved_primary,
        OwnershipValidationResult.FOREIGN_OR_MISMATCHED,
        opted_in=True,
        detail=(f"Claimed checkout {claimed_checkout} uses common dir {claimed_common}; resolved primary {resolved_primary} uses common dir {primary_common}."),
    )


def resolve_ownership_claim(claimed_checkout: Path | None, *, resolved_primary: Path) -> OwnershipClaim:
    """Validate an explicit checkout-ownership request against git topology.

    No git subprocess runs when ``claimed_checkout`` is ``None``. Opted-in
    validation fails closed into a structured result whenever git topology
    cannot be read.
    """
    primary = resolved_primary.resolve()
    if claimed_checkout is None:
        return _claim(
            primary,
            primary,
            OwnershipValidationResult.UNOWNED_NO_OPT_IN,
            opted_in=False,
            detail=f"No checkout ownership was requested for resolved primary {primary}.",
        )

    claimed = claimed_checkout.resolve()
    try:
        belongs_to_primary = is_worktree_of(primary, claimed)
    except OSError as exc:
        return _claim(
            claimed,
            primary,
            OwnershipValidationResult.BROKEN_POINTER,
            opted_in=True,
            detail=(f"Cannot validate claimed checkout {claimed} against resolved primary {primary}: {exc}"),
        )
    if not belongs_to_primary:
        return _rejected_comparator_claim(claimed, primary)
    if claimed == primary:
        return _claim(
            claimed,
            primary,
            OwnershipValidationResult.OWNED,
            opted_in=True,
        )

    try:
        registry = read_worktree_registry(primary)
    except WorktreeRegistryUnavailable as exc:
        return _claim(
            claimed,
            primary,
            OwnershipValidationResult.BROKEN_POINTER,
            opted_in=True,
            detail=(f"Cannot inspect worktree registry for claimed checkout {claimed} and resolved primary {primary}: {exc}"),
        )

    for registered in registry:
        if registered in {claimed, primary}:
            continue
        if claimed.is_relative_to(registered):
            return _claim(
                claimed,
                primary,
                OwnershipValidationResult.NESTED,
                opted_in=True,
                detail=(f"Claimed checkout {claimed} is nested inside registered worktree {registered}."),
            )
    return _claim(
        claimed,
        primary,
        OwnershipValidationResult.OWNED,
        opted_in=True,
    )


def error_for_claim(claim: OwnershipClaim) -> CheckoutOwnershipError | None:
    """Return the structured refusal for ``claim``, or ``None`` when owned."""
    error_type = _ERROR_TYPES.get(claim.validation_result)
    return error_type(claim) if error_type is not None else None


def claims_repository_root(claim: OwnershipClaim) -> bool:
    """True when ``claim`` names the repository root itself as the checkout.

    A pure predicate over the already-resolved claim (data-model.md
    §Validator). ``resolve_ownership_claim`` intentionally keeps returning
    ``OWNED`` for self-ownership (``test_primary_self_ownership_is_owned``
    pins that primitive behaviour) — the repository-root refusal is a
    minter-level policy layered on top, not a change to the claim primitive.
    """
    return claim.claimed_checkout == claim.resolved_primary
