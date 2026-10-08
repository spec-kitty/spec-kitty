"""The validated ownership fact for an owned checkout (owned-checkout-lifecycle-authority WP01).

:class:`OwnedCheckout` is the ONE proof that an owned checkout ``P`` has been
validated for a mission: the ownership claim was resolved, ``P`` is not the
repository root, ``P``'s mission directory and branch have been checked
against the command's allowed topology set. It is minted exactly once per
command, by ``specify_cli.core.owned_mission`` (the sole minter — see
``contracts/owned-checkout-carrier.md``), and then threaded down, immutable,
for the whole command. It is never persisted.

This module owns no I/O other than the one-time path canonicalisation inside
:meth:`OwnedCheckout._mint`; every invariant checked in ``__post_init__`` is
pure path logic. Direct construction — anything that does not go through
``_mint`` — raises ``TypeError``; the private ``_token`` sentinel is the
enforcement mechanism, and gates G1-G3 (``contracts/architectural-gate.md``)
police every *reference* to ``_mint``/the claim primitives at the AST level.

Import-cycle note: this module imports ``mission_runtime.resolution`` for
``ActionContextError`` at module scope, which is an intra-package edge and is
allowed. If ``resolution.py`` ever needs an ``OwnedCheckout`` annotation, it
must do so under ``TYPE_CHECKING`` or lazily, to avoid a cycle back into this
module.

Consumers outside the ``mission_runtime`` package import ``OwnedCheckout``
(and ``OwnedRefusalCode``) from the package root only — ``from mission_runtime
import OwnedCheckout`` — never from this submodule (MR-1/MR-2,
``tests/architectural/test_mission_runtime_surface.py``). Tests may import
this submodule directly (for ``OwnedCheckoutPathRefused`` or internals);
MR-1/MR-2 scan ``src/`` only.
"""

from __future__ import annotations

import ntpath
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import kernel.paths as kernel_paths
from kernel.resolution import resolve_commit_path, resolve_rejecting_loops
from mission_runtime.context import MissionTopology
from mission_runtime.resolution import ActionContextError

__all__ = [
    "OwnedCheckout",
    "OwnedRefusalCode",
]


class OwnedRefusalCode(StrEnum):
    """Every error code an owned-checkout operation may raise (data-model.md registry).

    Each member's value equals its name — the strings are ``do_not_change``
    (occurrence map, ``logs_telemetry``) — so a ``StrEnum`` member compares
    equal to the literal string existing ``error_code`` assertions already
    check. Later WPs and tests import codes from here instead of repeating
    the literal (Sonar S1192); existing literal call sites are converted by
    the WP that owns their file.
    """

    # The four claim-primitive codes (defined by the error classes in
    # ``specify_cli.core.checkout_ownership``; their strings are
    # ``do_not_change`` and pass through the minter unchanged).
    WORKTREE_INVOCATION_REFUSED = "WORKTREE_INVOCATION_REFUSED"
    OWNERSHIP_NESTED = "OWNERSHIP_NESTED"
    OWNERSHIP_FOREIGN = "OWNERSHIP_FOREIGN"
    OWNERSHIP_BROKEN_POINTER = "OWNERSHIP_BROKEN_POINTER"
    # Existing owned-checkout codes.
    OWNED_MISSION_PATH_REFUSED = "OWNED_MISSION_PATH_REFUSED"
    OWNED_TOPOLOGY_UNSUPPORTED = "OWNED_TOPOLOGY_UNSUPPORTED"
    OWNED_BRANCH_REFUSED = "OWNED_BRANCH_REFUSED"
    OWNED_INDEX_REFUSED = "OWNED_INDEX_REFUSED"
    # New codes minted by this mission.
    OWNED_CHECKOUT_IS_REPOSITORY_ROOT = "OWNED_CHECKOUT_IS_REPOSITORY_ROOT"
    OWNED_CHECKOUT_IS_MISSION_WORKTREE = "OWNED_CHECKOUT_IS_MISSION_WORKTREE"
    OWNED_ACTION_UNSUPPORTED = "OWNED_ACTION_UNSUPPORTED"
    OWNED_REVIEW_BASE_UNAVAILABLE = "OWNED_REVIEW_BASE_UNAVAILABLE"
    OWNED_COORDINATION_WORKSPACE_UNAVAILABLE = "OWNED_COORDINATION_WORKSPACE_UNAVAILABLE"
    WORK_PACKAGE_UNRESOLVED = "WORK_PACKAGE_UNRESOLVED"
    # Pre-existing wire strings promoted to members (registered in data-model.md).
    OWNED_OPTION_UNSUPPORTED = "OWNED_OPTION_UNSUPPORTED"
    OWNED_INPUT_INVALID = "OWNED_INPUT_INVALID"


class OwnedCheckoutPathRefused(ActionContextError):
    """A path requested via :meth:`OwnedCheckout.files` escapes the mission directory.

    Subclasses ``ActionContextError`` (rather than introducing a new base) so
    every existing ``except ActionContextError`` caller keeps working
    unchanged (``logs_telemetry``: ``do_not_change``).
    """

    def __init__(self, message: str) -> None:
        super().__init__(OwnedRefusalCode.OWNED_MISSION_PATH_REFUSED.value, message)


# Module-private sentinel: the only way ``__post_init__`` accepts construction.
# Never exported; a forged ``_token=object()`` cannot match it by identity.
_MINT_TOKEN = object()


def _same_path(a: Path, b: Path) -> bool:
    """True when ``a`` and ``b`` name the same checkout.

    Case-sensitive comparison everywhere except Windows, where the
    filesystem is case-insensitive by default (``kernel.paths.is_windows``,
    the one canonical, patchable OS-detection seam). Called through the
    ``kernel_paths`` module attribute, never a module-scope-bound name, so a
    test's ``monkeypatch.setattr(kernel_paths, "is_windows", ...)`` on
    ``kernel.paths`` is observed here too.

    Folds case with ``ntpath.normcase`` -- never ``str.casefold()`` (full
    Unicode case folding, e.g. ``"ß"`` -> ``"ss"``, which is NOT what
    Windows/NTFS or ``PureWindowsPath`` do -- a fail-open regression cycle-2
    review caught) and never the bare ``os.path.normcase`` (itself gated on
    the *real* ``os.name``, a no-op on POSIX regardless of what
    ``is_windows()`` returns, which would make this branch untestable and
    un-forceable on a Linux CI runner). ``ntpath.normcase`` is pure-Python,
    OS-independent, and IS exactly ``os.path.normcase`` on real Windows, so
    it gives the correct semantics while staying forceable on Linux.
    """
    if kernel_paths.is_windows():
        return ntpath.normcase(str(a)) == ntpath.normcase(str(b))
    return a == b


def _is_within(path: Path, ancestor: Path) -> bool:
    """True when ``path`` is ``ancestor`` itself or nested beneath it.

    A local two-line predicate rather than an import of
    ``mission_runtime.checkout_identity._is_within`` (a private name) — see
    module docstring / T001 edge cases. Windows case-insensitivity is
    applied the same way as :func:`_same_path` (``ntpath.normcase``, looked
    up through ``kernel_paths`` -- see that function's docstring for why not
    ``str.casefold()`` or the bare ``os.path.normcase``).
    """
    if kernel_paths.is_windows():
        norm_path = ntpath.normcase(str(path))
        norm_ancestor = ntpath.normcase(str(ancestor))
        if norm_path == norm_ancestor:
            return True
        return any(ntpath.normcase(str(parent)) == norm_ancestor for parent in path.parents)
    return path == ancestor or ancestor in path.parents


@dataclass(frozen=True)
class OwnedCheckout:
    """The validated ownership fact for an owned checkout ``P`` (data-model.md).

    Minted exactly once per command by ``specify_cli.core.owned_mission`` and
    threaded down immutably. Never persisted. Construct only through
    :meth:`_mint`; direct construction raises ``TypeError``.
    """

    repository_root: Path
    owned_root: Path
    mission_dir: Path
    mission_slug: str
    topology: MissionTopology
    #: The branch every owned write lands on and the checkout must be ON:
    #: ``expected_write_branch(meta)`` -- the #5100 minted ``mission_branch``
    #: for a protected-target single_branch mission, else the mission's
    #: ``target_branch``. It is NOT the landing (merge) branch; display
    #: surfaces read that from the mission's own ``meta.json`` in ``mission_dir``.
    write_branch: str
    # Private construction token (do not pass a real value; only `_mint` may).
    _token: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._token is not _MINT_TOKEN:
            raise TypeError("OwnedCheckout is minted only by specify_cli.core.owned_mission")
        if _same_path(self.owned_root, self.repository_root):
            raise ValueError("OwnedCheckout invariant violated: owned_root must not be the repository root checkout")
        if not _is_within(self.mission_dir, self.owned_root / "kitty-specs"):
            raise ValueError("OwnedCheckout invariant violated: mission_dir must be inside owned_root/kitty-specs")
        if self.mission_dir.name != self.mission_slug:
            raise ValueError("OwnedCheckout invariant violated: mission_dir.name must equal mission_slug")

    @classmethod
    def _mint(
        cls,
        *,
        repository_root: Path,
        owned_root: Path,
        mission_dir: Path,
        mission_slug: str,
        topology: MissionTopology,
        write_branch: str,
    ) -> OwnedCheckout:
        """Canonicalise the three paths and construct the fact.

        The only I/O in this module: each path is resolved with
        :func:`kernel.resolution.resolve_rejecting_loops` so symlink aliases
        collapse to one identity (spec Edge Cases, "Path aliases").
        """
        resolved_repository_root = resolve_rejecting_loops(repository_root)
        resolved_owned_root = resolve_rejecting_loops(owned_root)
        resolved_mission_dir = resolve_rejecting_loops(mission_dir)
        return cls(
            repository_root=resolved_repository_root,
            owned_root=resolved_owned_root,
            mission_dir=resolved_mission_dir,
            mission_slug=mission_slug,
            topology=topology,
            write_branch=write_branch,
            _token=_MINT_TOKEN,
        )

    def files(self, paths: list[Path]) -> list[Path]:
        """Validate a batch of paths against ``mission_dir`` (whole-batch containment before any staging).

        A relative path is joined to ``owned_root``. Any ``..`` part is
        refused. Each candidate is resolved with
        :func:`kernel.resolution.resolve_commit_path` (parents resolved, a link
        leaf kept; a symlink loop is refused too) and must lie inside
        ``mission_dir`` by the link's own location: a link inside the mission is
        committed as a link even if it points elsewhere (#5671).
        """
        resolved: list[Path] = []
        for path in paths:
            candidate = self.owned_root / path if not path.is_absolute() else path
            if ".." in path.parts:
                raise OwnedCheckoutPathRefused(f"Path is outside the selected mission: {path}")
            try:
                resolved_candidate = resolve_commit_path(self.owned_root, candidate)
            except OSError as exc:
                raise OwnedCheckoutPathRefused(f"Path is outside the selected mission: {path}") from exc
            if not _is_within(resolved_candidate, self.mission_dir):
                raise OwnedCheckoutPathRefused(f"Path is outside the selected mission: {path}")
            resolved.append(resolved_candidate)
        return resolved
