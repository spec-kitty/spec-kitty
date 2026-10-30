"""Resolve the org and project charter pack layer roots for a repository.

Layer-root discovery belongs in ``charter`` (C-007): the resolved paths are
handed to lower charter layers as data (C-008). ``roots["project"]`` is the
**project pack root** (``.kittify/charter-packs/``, resolved through
:mod:`kernel.charter_pack_paths`), so consumers join kind directories straight
onto it.
"""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

from charter.offering.drg.org_pack_config import (
    UnreadableOrgPackRegistry,
    require_declared_org_roots,
    resolve_existing_org_roots,
    resolve_org_roots,
)
from kernel.charter_pack_paths import project_pack_root

__all__ = ["resolve_layer_roots", "resolve_pack_chain"]


def resolve_layer_roots(repo_root: Path) -> dict[str, Path]:
    """Resolve the org and project charter pack roots for *repo_root*.

    ``roots["project"]`` is the project pack root, present only when it is a
    directory (:func:`kernel.charter_pack_paths.project_pack_root`; the
    retired pre-cutover project directory is never read, FR-011).
    """
    roots: dict[str, Path] = {}

    project = project_pack_root(repo_root)
    if project.is_dir():
        roots["project"] = project

    # FR-013: register the first resolved org pack root regardless of whether it
    # nests a ``doctrine/`` subdir. Runtime resolves org packs from the *flat*
    # ``<pack>/<plural>/`` layout (``resolve_org_roots`` → ``ActiveCharterService``),
    # which has no ``<pack>/doctrine/`` subdir; gating on ``doctrine/.is_dir()``
    # silently dropped those packs so flat-layout artifacts failed to activate
    # ("Unknown <kind> ID"). The layout-tolerant scan in
    # ``pack_manager._scan_layer_dirs`` accepts both flat and nested packs.
    for org_root in resolve_org_roots(repo_root):
        if org_root.is_dir():
            roots["org"] = org_root
            break

    return roots


def resolve_pack_chain(repo_root: Path, *, strict: bool, quiet: bool = False) -> list[Path]:
    """Return the ordered org-pack chain for *repo_root*: the single chain authority.

    Declaration order (last-declared-wins for consumers). ``strict`` toggles the
    posture over the same chain:

    * ``strict=False`` -- existing-filtered: a declared pack whose root is absent
      on disk is dropped (equivalent to ``resolve_existing_org_roots``). Only
      this lenient posture accepts ``quiet`` (forwarded to the registry read to
      demote the unparseable-config warning to debug); ``strict`` ignores it.
    * ``strict=True`` -- fail-closed: the registry is read strictly and a
      declared-but-unfetched pack raises ``ValueError`` naming the pack and the
      ``spec-kitty charter fetch`` remedy (equivalent to
      ``require_declared_org_roots``); an unreadable or malformed registry
      raises the typed ``OrgPackRegistryUnreadableError`` (an
      ``ActiveCharterConfigError`` carrying ``ACTIVE_CHARTER_CONFIG_INVALID``,
      still a ``ValueError`` — issue #6772).

    Zero declared packs yields ``[]`` in either posture; it never raises.

    The posture is intentionally chosen by each caller (governance surfaces use
    ``strict=True``, display and best-effort surfaces ``strict=False``); the
    per-call-site choice is deliberate, not accidental.
    """
    if strict:
        try:
            return list(require_declared_org_roots(repo_root))
        except UnreadableOrgPackRegistry as cause:
            raise _refuse_unreadable_registry(cause) from cause
    return list(resolve_existing_org_roots(repo_root, quiet=quiet))


def _refuse_unreadable_registry(cause: UnreadableOrgPackRegistry) -> NoReturn:
    """Map the offering-side unreadable-registry refusal onto the typed error (issue #6772).

    The typed refusal :class:`~charter.activation.activation_ledger.OrgPackRegistryUnreadableError`
    carries the ``ACTIVE_CHARTER_CONFIG_INVALID`` code, so ``charter activate``
    (whose strict org-chain read lands here) reports the malformed registry
    exactly like ``charter deactivate``'s strict required-floor read, and it
    stays a ``ValueError`` so every strict reader's ``except ValueError``
    contract keeps firing.

    This is the ONE point where the offering→activation seam maps the
    offering-owned :class:`~charter.offering.drg.org_pack_config.UnreadableOrgPackRegistry`
    onto the typed error, so ``charter.offering`` itself never imports
    ``charter.activation`` (the C-004 one-way boundary). The import is lazy
    because ``charter.activation.activation_ledger`` transitively imports this
    module — the same shape ``charter.activation.org_pack_discovery._strict_error``
    uses to keep the same-package import graph acyclic.
    """
    from charter.activation.activation_ledger import (  # noqa: PLC0415 — keeps the same-package import graph acyclic
        OrgPackRegistryUnreadableError,
    )

    raise OrgPackRegistryUnreadableError(cause.args[0]) from cause
