"""Charter-activation-aware org-profile resolver (FR-003 / FR-007).

This module exposes :func:`resolve_activated_org_profiles` — the single seam
every org-honouring consumer (WP03 dispatch/context routing, WP04 projection)
calls to obtain the **charter-activated** ∩ **org-provenance** subset of agent
profiles.  Consumers MUST NOT splice raw ``resolve_org_roots`` output: doing so
surfaces declared-but-de-activated org profiles, bypassing the charter
activation gate (C-008).

How the gate is honoured (C-006: reuse, never re-implement)
----------------------------------------------------------
The activation gate lives two layers above ``resolve_org_roots`` — on
:attr:`charter.activation.resolver.ActiveCharterService.agent_profiles`, which filters the
merged profile set by ``PackContext.activated_agent_profiles`` (three-state:
``None`` → all admitted; ``frozenset()`` → none; explicit set → only those).
This resolver builds that activation-aware service via
:func:`specify_cli.doctrine_service_factory.build_active_charter_service`
and reads its already-gated ``agent_profiles`` mapping.  It then narrows the
result to org-provenance members by consulting the inner repository's
``get_provenance`` / ``get_source_path`` (provenance lives on the repository,
not on :class:`~charter.offering.agent_profiles.profile.AgentProfile`).

Fail-closed (NFR-004)
---------------------
The org subset is computed as ``activated_ids ∩ org_provenance``.  A malformed
allowlist entry, a corrupt sibling profile, or a malformed DRG can never flip a
de-activated profile to admitted: membership is gated by the activation filter
first, and provenance is read per-id from the inner repository.

Layer rule
----------
This helper lives in ``specify_cli.*`` precisely because it imports the
``specify_cli`` factory (allowed direction ``specify_cli → charter →
doctrine``).  It must never be placed inside ``charter.*`` or ``doctrine.*``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from specify_cli.doctrine_service_factory import build_active_charter_service

if TYPE_CHECKING:
    from charter.profiles import AgentProfile, SkippedProfile

# ``ResolvedOrgProfile`` is the return-record type — consumed by-value by the
# routing/projection callers, not imported by name — so it stays a module-level
# symbol off the ``import *`` surface (dead-public-symbol gate; cf. WP09 Option A).
__all__ = ["resolve_activated_org_profiles"]

_ORG_LAYER = "org"


def _existing_org_roots(repo_root: Path) -> list[Path]:
    """Return on-disk org-pack roots declared in ``.kittify/config.yaml``.

    Best-effort: a missing/corrupt config yields an empty list so the caller
    takes the no-org-packs fast path. Mirrors
    :func:`charter.activation.context._existing_org_roots`.
    """
    from charter.drg import resolve_org_roots

    try:
        return [root for root in resolve_org_roots(repo_root) if root.exists()]
    except Exception:  # noqa: BLE001 — org-root discovery stays best-effort
        return []


@dataclass(frozen=True)
class ResolvedOrgProfile:
    """An activated, org-provenance agent profile with its source provenance.

    A bare :class:`AgentProfile` carries no ``source_layer``/``source_path``;
    provenance lives on the repository.  This record threads it through so
    downstream consumers (e.g. WP04 projection) can set a non-builtin
    ``source_layer`` without re-deriving org roots (FR-007, C-002).
    """

    profile: AgentProfile
    source_layer: str
    source_path: Path | None


class OrgProfileResolution(list[ResolvedOrgProfile]):
    """List-compatible admitted profiles plus independent source diagnostics.

    ``skipped_profiles`` retains canonical org-layer load failures, including
    files excluded by activation. List truthiness/equality describe admission
    only; consumers assessing source health must inspect the diagnostics even
    when the list is empty. Copying/slicing as a plain list drops diagnostics.
    """

    def __init__(
        self,
        profiles: Iterable[ResolvedOrgProfile] = (),
        *,
        skipped_profiles: Iterable[SkippedProfile] = (),
    ) -> None:
        super().__init__(profiles)
        self.skipped_profiles = tuple(skipped_profiles)


def resolve_activated_org_profiles(repo_root: Path) -> OrgProfileResolution:
    """Return the charter-activated, org-provenance agent profiles for ``repo_root``.

    Composes :func:`build_active_charter_service` (the canonical
    activation gate, C-006/C-008) with org-provenance filtering:

    1. Build the activation-aware service for ``repo_root``.
    2. Read its already-gated ``agent_profiles`` mapping (the three-state
       ``activated_agent_profiles`` filter is applied by the wrapper).
    3. Keep only members whose inner-repository provenance is ``"org"``,
       discarding built-in and project profiles (C-002).
    4. Return them deterministically ordered by ``profile_id`` (NFR-002).

    Parameters
    ----------
    repo_root:
        Repository root containing ``.kittify/config.yaml``.

    Returns
    -------
    OrgProfileResolution
        List-compatible activated org profiles, sorted by ``profile_id``, with
        canonical org-only ``skipped_profiles`` sorted by path, profile ID and
        error summary. Diagnostics are independent of the activation filter;
        no built-in or project failures are attributed to the org layer.
    """
    # Short-circuit (perf): with zero configured org roots the org-provenance
    # subset is necessarily empty, so skip the full activation-aware service
    # build. Mirrors ``charter.activation.context._existing_org_roots`` (best-effort).
    if not _existing_org_roots(repo_root):
        return OrgProfileResolution()

    service = build_active_charter_service(repo_root)
    activated_profiles: dict[str, AgentProfile] = service.agent_profiles
    inner_repository = service.agent_profile_repository

    resolved: list[ResolvedOrgProfile] = []
    for profile_id, profile in activated_profiles.items():
        if inner_repository.get_provenance(profile_id) != _ORG_LAYER:
            continue
        resolved.append(
            ResolvedOrgProfile(
                profile=profile,
                source_layer=_ORG_LAYER,
                source_path=inner_repository.get_source_path(profile_id),
            )
        )

    skipped = sorted(
        (item for item in inner_repository.skipped_profiles() if item.layer == _ORG_LAYER),
        key=lambda item: (item.path, item.profile_id or "", item.error_summary),
    )
    return OrgProfileResolution(
        sorted(resolved, key=lambda item: item.profile.profile_id),
        skipped_profiles=skipped,
    )
