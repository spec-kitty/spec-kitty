"""Seam-B checkout-identity refusal (write-path-integrity WP03, #3128 / FR-005).

A WP-execution write (``implement`` / ``review``) must be invoked from a checkout
the mission actually owns — its own lane worktree, the repository-root/primary
checkout it legitimately allocates from, or (owned-checkout-lifecycle-authority
WP05, FR-011) the owned checkout itself for an owned single_branch mission.
Invoking such a write from a *foreign* checkout (canonically another mission's
lane worktree in the same registry, or the repository root for an owned
mission) is refused.

This module is the ONE authority for that refusal. Two design constraints shape it:

* **Distinct exception, NOT ``ActionContextError`` (FR-005 / MF-4).**
  :class:`CheckoutIdentityError` deliberately does not subclass
  ``ActionContextError`` so the audited ``except ActionContextError: return None``
  fallbacks on the write path cannot degrade a refusal to the legacy
  meta-derived placement path.
* **Pure path comparison — zero git subprocesses (NFR-004).**
  :func:`enforce_checkout_identity` compares already-resolved paths with
  ``Path.resolve()`` canonicalization only. It never invokes the git-topology
  primitive; patching that primitive shows the refusal path calls it zero
  additional times. The single nested/toplevel classifier (:func:`_checkout_root`,
  SC-008) is a pure ``.worktrees`` segment inspection so a foreign lane nested
  physically under the primary checkout is still refused (the NESTED case holds).
"""

from __future__ import annotations

from pathlib import Path

# The canonical parent directory for lane worktrees (mirrors
# ``specify_cli.lanes.lifecycle_sync.WORKTREES_DIRNAME``). Kept as a local
# constant so this module carries zero spec-kitty imports (no import cycle,
# no heavy dependency on the refusal hot path).
_WORKTREES_DIRNAME = ".worktrees"

# The ``ResolvedWorkspace.resolution_kind`` value that denotes a real, separate
# lane worktree. Planning-lane / planning-artifact / single-branch missions
# resolve to ``"repo_root"`` (routed to primary, CWD-invariant, R3) and are
# never gated.
_LANE_WORKSPACE_KIND = "lane_workspace"

# The ``ResolvedWorkspace.resolution_kind`` value for an owned single_branch
# mission's workspace (owned-checkout-lifecycle-authority WP05, FR-011): the
# owned checkout itself, gated with NO repository-root allowance (unlike the
# lane arm, R is not a legitimate allocation point for an owned checkout).
_OWNED_CHECKOUT_KIND = "owned_checkout"


class CheckoutIdentityError(Exception):
    """A WP-execution write was invoked from a checkout the mission does not own.

    Subclasses ``Exception`` **directly** — deliberately NOT ``ActionContextError``
    (FR-005 / MF-4) and NOT ``RuntimeError``. The audited fallbacks on the write
    path narrow to ``except ActionContextError`` (implement placement read) and to
    the concrete commit-failure ``RuntimeError``/``subprocess``/``OSError`` set
    (record-analysis best-effort commit); a direct-``Exception`` base means this
    refusal escapes every one of those narrowed handlers and cannot be degraded
    or swallowed.
    """

    def __init__(
        self,
        *,
        expected: Path,
        actual: Path,
        mission_slug: str,
        wp_id: str,
        owned: bool = False,
    ) -> None:
        self.expected = expected
        self.actual = actual
        self.mission_slug = mission_slug
        self.wp_id = wp_id
        if owned:
            super().__init__(
                f"Refusing a WP-execution write for {mission_slug} {wp_id}: the "
                f"invoking checkout does not own this mission's owned checkout.\n"
                f"  invoked from : {actual}\n"
                f"  expected     : {expected}\n"
                f"There is no repository-root allowance for an owned checkout. "
                f"cd into the owned checkout {expected} and retry."
            )
        else:
            super().__init__(
                f"Refusing a WP-execution write for {mission_slug} {wp_id}: the "
                f"invoking checkout does not own this mission's execution workspace.\n"
                f"  invoked from : {actual}\n"
                f"  expected     : {expected}\n"
                f"    (or this mission's repository-root/primary checkout).\n"
                f"You are most likely inside another mission's lane worktree. "
                f"cd into {expected} (or the repository root) and retry."
            )


def _checkout_root(path: Path, primary_root: Path) -> Path:
    """Classify which working-tree root owns ``path`` — pure path inspection.

    A path under ``<primary>/.worktrees/<X>/…`` belongs to lane worktree ``<X>``;
    anything else (including paths outside the primary tree entirely) is treated
    as the primary checkout. This is the single nested/toplevel classifier
    (SC-008): it needs no git subprocess (NFR-004), and by collapsing a foreign
    lane path to its ``.worktrees/<X>`` root it keeps the NESTED refusal holding
    even though the lane physically lives under the primary root.

    Both inputs are expected to be already ``.resolve()``-canonicalized.
    """
    worktrees_root = primary_root / _WORKTREES_DIRNAME
    if worktrees_root in path.parents:
        rel = path.relative_to(worktrees_root)
        if rel.parts:
            return worktrees_root / rel.parts[0]
    return primary_root


def enforce_checkout_identity(
    *,
    current_cwd: Path,
    workspace_path: Path,
    primary_root: Path,
    resolution_kind: str,
    mission_slug: str,
    wp_id: str,
) -> None:
    """Refuse a WP-execution write from a foreign checkout (FR-005 / SC-004).

    Two kinds are gated:

    - ``lane_workspace``: proceeds when the invoking checkout's working-tree
      root is either the mission's declared lane worktree (or any subdir of
      it) OR the primary checkout (the legitimate allocation/launch point).
      Refuses otherwise, canonically when the invoker sits inside another
      mission's lane worktree.
    - ``owned_checkout`` (owned-checkout-lifecycle-authority WP05, FR-011):
      proceeds only when the invoking cwd is inside the owned checkout itself.
      There is **no** repository-root allowance here — unlike a lane
      workspace, the repository root is not a legitimate allocation point for
      an owned checkout.

    Planning-lane / planning-artifact / single-branch (non-owned) resolutions
    route to the primary checkout, are CWD-invariant, and MUST proceed from any
    checkout (R3) — they are exempt, along with every other kind. Pure reads
    never reach here (their callers pass ``write_intent=False``).

    Pure path comparison: no git subprocess is invoked (NFR-004).
    """
    if resolution_kind == _OWNED_CHECKOUT_KIND:
        cwd = current_cwd.resolve()
        owned_root = workspace_path.resolve()
        if _is_within(cwd, owned_root):
            return
        raise CheckoutIdentityError(
            expected=workspace_path,
            actual=current_cwd,
            mission_slug=mission_slug,
            wp_id=wp_id,
            owned=True,
        )
    if resolution_kind != _LANE_WORKSPACE_KIND:
        return
    primary = primary_root.resolve()
    cwd_root = _checkout_root(current_cwd.resolve(), primary)
    declared_root = _checkout_root(workspace_path.resolve(), primary)
    if cwd_root in (declared_root, primary):
        return
    raise CheckoutIdentityError(
        expected=workspace_path,
        actual=current_cwd,
        mission_slug=mission_slug,
        wp_id=wp_id,
    )


__all__ = [
    "CheckoutIdentityError",
    "enforce_checkout_identity",
]
