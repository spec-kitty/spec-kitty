"""Checkout-identity guard — the single canonical authority for invocation
ownership and the single fail-closed write-refusal seam.

Mission ``worktree-root-resolution-01M0B59R`` WP01 (FR-001, FR-008; C-1, C-2;
data-model INV-1…INV-6).

Reframe (post-plan squad, 2026-08-18): the discarded
``CheckoutKind {PRIMARY, LINKED_WORKTREE, STANDALONE_CLONE}`` classifier is
gone. A standalone clone already resolves to itself and the clone-vs-primary
split is undecidable from local git state — and *moot*, because a clone owns
itself. The decidable, load-bearing distinction is **invocation ownership**:
does this invocation own the checkout it is about to write, or is it a foreign
lane worktree whose canonical write deliberately lives on the primary?

Ownership is decided by parsing ``.git`` **DIRECTLY** (INV-4):

* ``cwd``'s own ``.git`` is a **directory** ⇒ this checkout is its own root.
  It owns itself. This covers the primary checkout *and* a nested standalone
  clone alike — both are their own canonical target. Crucially, the guard does
  **not** re-anchor a nested clone to the outer primary; that re-anchoring is
  exactly the WP07 ``find_repo_root`` defect, and routing this decision through
  ``get_main_repo_root`` / ``locate_project_root`` / ``resolve_canonical_root``
  would couple this foundation to WP07 and make the nested-clone ownership
  assertion unsatisfiable.
* ``cwd``'s ``.git`` is a **worktree-pointer file** (``gitdir:`` naming
  ``…/.git/worktrees/<name>``) ⇒ this is a linked worktree. Its
  ``canonical_target`` is the primary repo root the pointer names (the
  deliberate #2320/#3328 anchor), and it does **not** own that primary: a
  ``WRITE`` from here fails closed.

Read/write intent keeps the deliberate primary reads intact (INV-2): a
``PRIMARY_READ`` returns ``canonical_target`` unchanged regardless of ``cwd`` —
the must-not-flip anchors (``get_feature_target_branch``,
``resolve_merge_target_branch``, ``mission_runtime`` primary-metadata reads) are
never redirected to the invoking worktree.

The module is deliberately dependency-light (stdlib only) so it stays genuinely
independent of the ``paths.py`` re-anchoring resolvers. The worktree-pointer
parsing mirrors ``core/paths.py`` (``_is_worktree_gitdir`` /
``get_main_repo_root``) rather than importing it, to keep that independence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from kernel.ancestor_walk import iter_ancestors

__all__ = [
    "CheckoutIdentity",
    "FailClosedRefusal",
    "Intent",
    "resolve_checkout_identity",
]

_GITDIR_PREFIX = "gitdir:"


class Intent(Enum):
    """Why the invocation consults the guard.

    ``WRITE`` — ownership decides fail-closed vs proceed (INV-1).
    ``PRIMARY_READ`` — a deliberate primary anchor that is never flipped to the
    invoking checkout (INV-2); ``is_owner`` is informational only.
    """

    WRITE = "write"
    PRIMARY_READ = "primary_read"


@dataclass(frozen=True)
class FailClosedRefusal:
    """The #3128 fail-closed refusal shape — the SINGLE write-refusal seam.

    Emitted (via :meth:`CheckoutIdentity.write_refusal`) when a ``WRITE``
    invocation does not own its ``canonical_target``. Every in-scope write
    refusal in the codebase is constructed here and nowhere else (NFR-003);
    :meth:`message` embeds ``refusal_path`` verbatim so 100% of refusals name
    the checkout they declined to act on (INV-5).
    """

    refusal_path: Path

    def message(self) -> str:
        """Return the operator-facing refusal, naming ``refusal_path`` verbatim."""
        return (
            "Refusing to write: this invocation does not own the canonical target "
            f"checkout {self.refusal_path}. Run the command from that checkout, or "
            "target a checkout this invocation owns."
        )


@dataclass(frozen=True)
class CheckoutIdentity:
    """Invocation ownership for a single command, carrying intent.

    * ``invoking_root`` — the checkout root the command was invoked from
      (``cwd``'s own checkout root; for a linked worktree this is the worktree
      itself, not the primary).
    * ``canonical_target`` — where the command's canonical write/read
      deliberately lives (the invoking checkout when it owns itself; the primary
      the worktree pointer names for a linked worktree — the #2320/#3328 anchor).
    * ``is_owner`` — ``True`` when ``invoking_root`` owns/equals
      ``canonical_target``; ``False`` for a foreign lane worktree.
    * ``intent`` — see :class:`Intent`.
    """

    invoking_root: Path
    canonical_target: Path
    is_owner: bool
    intent: Intent

    def write_refusal(self) -> FailClosedRefusal | None:
        """Return the fail-closed refusal, or ``None`` when the write may proceed.

        A refusal is produced **only** for ``intent == WRITE`` and
        ``is_owner is False`` (INV-1). Owner writes and every ``PRIMARY_READ``
        are silent (INV-2, INV-6). This is the single constructor of a
        write-refusal outside the value object itself.
        """
        if self.intent is Intent.WRITE and not self.is_owner:
            return FailClosedRefusal(refusal_path=self.canonical_target)
        return None


def _read_worktree_gitdir(git_file: Path) -> Path | None:
    """Return the pointed gitdir when ``git_file`` is a real worktree pointer.

    Mirrors ``core/paths._read_worktree_gitdir`` / ``_is_worktree_gitdir``: a
    true linked worktree points at ``…/.git/worktrees/<name>`` (or, for a bare
    repo, ``…<repo>.git/worktrees/<name>``). Submodules
    (``…/.git/modules/<mod>``) and separate-git-dir clones point elsewhere and
    are NOT worktrees — they own themselves.
    """
    try:
        content = git_file.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if not content.startswith(_GITDIR_PREFIX):
        return None
    gitdir = Path(content.split(":", 1)[1].strip())
    if gitdir.parent.name != "worktrees" or not gitdir.parent.parent.name.endswith(".git"):
        return None
    return gitdir


def _resolve_invocation(cwd: Path) -> tuple[Path, Path]:
    """Return ``(invoking_root, canonical_target)`` by parsing ``.git`` directly.

    Walks up from ``cwd`` to the nearest ``.git`` entry:

    * a ``.git`` **directory** ⇒ own root: ``invoking_root == canonical_target``
      (primary or nested clone — owns itself; no re-anchoring, INV-4).
    * a ``.git`` **worktree-pointer file** ⇒ linked worktree: ``invoking_root``
      is the worktree, ``canonical_target`` is the primary the pointer names.
    * a ``.git`` file that is not a worktree pointer (submodule / separate git
      dir) ⇒ own root.

    When no ``.git`` is found the resolved ``cwd`` is its own (degenerate) root.
    """
    resolved = cwd.resolve()
    for candidate in iter_ancestors(resolved):
        git_path = candidate / ".git"
        if git_path.is_dir():
            return candidate, candidate
        if git_path.is_file():
            gitdir = _read_worktree_gitdir(git_path)
            if gitdir is None:
                return candidate, candidate
            # gitdir = <primary>/.git/worktrees/<name>
            #   gitdir.parent.parent == <primary>/.git ; its parent == <primary>
            primary_root = gitdir.parent.parent.parent.resolve()
            return candidate, primary_root
    return resolved, resolved


def resolve_checkout_identity(cwd: Path, intent: Intent) -> CheckoutIdentity:
    """Resolve invocation ownership for ``cwd`` under ``intent``.

    Ownership is decided purely from decidable local git state — the direct
    ``.git`` parse in :func:`_resolve_invocation` — never from an undecidable
    clone-vs-primary guess and never by re-anchoring through the ``paths.py``
    resolvers (INV-4; keeps this WP independent of WP07).

    ``is_owner`` is ``True`` exactly when the invoking checkout owns/equals its
    ``canonical_target``. For ``PRIMARY_READ`` the returned ``canonical_target``
    is unchanged regardless of ``cwd`` (INV-2) — ``is_owner`` is informational
    and never redirects the target.
    """
    invoking_root, canonical_target = _resolve_invocation(cwd)
    is_owner = invoking_root == canonical_target
    return CheckoutIdentity(
        invoking_root=invoking_root,
        canonical_target=canonical_target,
        is_owner=is_owner,
        intent=intent,
    )
