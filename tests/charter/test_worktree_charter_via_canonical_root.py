"""FR-010 worktree transparency test: a reader invoked from a linked
worktree sees the main checkout's ``.kittify/charter/`` bundle, with no
files written inside the worktree's own ``.kittify/charter/`` tree.

This is the architectural payoff of the WP02 canonical-root resolver
stitched into the WP03 reader cutover: worktrees do NOT carry their own
charter bundle. A reader in a worktree calls ``ensure_charter_bundle_fresh``,
the resolver maps back to the main checkout, and any sync ran on the main
checkout's path. The worktree's ``.kittify/charter/`` stays empty.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.non_sandbox, pytest.mark.integration, pytest.mark.git_repo]
_GITIGNORE_BODY = """\
.kittify/charter/directives.yaml
.kittify/charter/governance.yaml
.kittify/charter/metadata.yaml
"""

_CHARTER_BODY = """\
# Project Charter

## Policy Summary

- Worktrees share the canonical charter.
"""


def _init_main_checkout(main_root: Path) -> Path:
    """Seed a main checkout with charter.md tracked + derivatives synced."""
    subprocess.run(["git", "init", "--quiet", "--initial-branch=main", str(main_root)], check=True)
    subprocess.run(
        ["git", "-C", str(main_root), "config", "user.email", "worktree@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(main_root), "config", "user.name", "Worktree Test"],
        check=True,
    )

    (main_root / ".gitignore").write_text(_GITIGNORE_BODY, encoding="utf-8")
    charter_dir = main_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    (charter_dir / "charter.md").write_text(_CHARTER_BODY, encoding="utf-8")

    # ``mission_type_activations`` is unrelated to the worktree/canonical-root
    # transparency this module pins, but WP04 (C-A1) made it a hard
    # construction precondition for ``PackContext.from_config`` -- provision
    # it so ``build_charter_context`` (which resolves a pack context under
    # the hood) can construct at all from either the main checkout or a
    # linked worktree.
    (main_root / ".kittify" / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )

    subprocess.run(
        [
            "git",
            "-C",
            str(main_root),
            "add",
            ".gitignore",
            ".kittify/charter/charter.md",
            ".kittify/config.yaml",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(main_root), "commit", "-q", "-m", "main checkout seed"],
        check=True,
    )
    return main_root


def _add_linked_worktree(main_root: Path, worktree_root: Path, branch: str) -> Path:
    subprocess.run(
        [
            "git",
            "-C",
            str(main_root),
            "worktree",
            "add",
            "-b",
            branch,
            str(worktree_root),
        ],
        check=True,
    )
    return worktree_root


def _clear_resolver_cache() -> None:
    from charter.resolution import resolve_canonical_repo_root

    resolve_canonical_repo_root.cache_clear()


def test_build_charter_context_from_worktree_uses_canonical_root(tmp_path: Path) -> None:
    """FR-010: ``build_charter_context`` called from a worktree anchors
    all charter reads at the main checkout's canonical root.

    consolidate-charter-bundle (IC-04 / WP04, T028c): ``sync()`` no longer
    materializes governance.yaml/directives.yaml/metadata.yaml (manifest
    v2's ``derived_files`` is ``[]``) -- ``ensure_charter_bundle_fresh``
    remains the canonical-root resolution chokepoint, but priming the
    bundle no longer means "these three files now exist"; it means the
    resolver correctly anchors at the main checkout regardless.
    """
    from charter.activation.context import build_charter_context
    from charter.activation.sync import ensure_charter_bundle_fresh

    main_root = _init_main_checkout(tmp_path / "main").resolve()
    worktree_root = _add_linked_worktree(
        main_root,
        (tmp_path / "worktree-a").resolve(),
        "feature/worktree-a",
    ).resolve()
    _clear_resolver_cache()

    # The chokepoint still resolves canonical root correctly, even though
    # it no longer writes any derivative there.
    main_sync = ensure_charter_bundle_fresh(main_root)
    assert main_sync is not None
    assert main_sync.canonical_root == main_root
    assert main_sync.synced is False

    _clear_resolver_cache()

    # Invoke the reader FROM THE WORKTREE.
    result = build_charter_context(worktree_root, action="implement")
    assert result is not None

    # None of the v1.0.0 manifest derivatives may appear inside the
    # worktree's .kittify/charter/ tree. ``charter.md`` is git-tracked and
    # may legitimately appear via worktree checkout; ``context-state.json``
    # is the C-012 carve-out (still anchored at repo_root per spec).
    worktree_charter_dir = worktree_root / ".kittify" / "charter"
    forbidden = {"governance.yaml", "directives.yaml", "metadata.yaml"}
    if worktree_charter_dir.exists():
        leaked = [
            p.name for p in worktree_charter_dir.iterdir() if p.name in forbidden
        ]
        assert not leaked, (
            f"Worktree charter dir leaked v1.0.0 derivatives: {leaked} — "
            "readers must anchor derivatives at canonical root"
        )


def test_chokepoint_from_worktree_points_at_main_checkout(tmp_path: Path) -> None:
    """FR-010 direct probe: ``SyncResult.canonical_root`` from a worktree
    invocation equals the main-checkout path, not the worktree path.
    """
    from charter.activation.sync import ensure_charter_bundle_fresh

    main_root = _init_main_checkout(tmp_path / "main").resolve()
    worktree_root = _add_linked_worktree(
        main_root,
        (tmp_path / "worktree-b").resolve(),
        "feature/worktree-b",
    ).resolve()
    _clear_resolver_cache()

    result = ensure_charter_bundle_fresh(worktree_root)
    assert result is not None
    assert result.canonical_root == main_root, (
        f"canonical_root={result.canonical_root} (expected main={main_root}); "
        f"worktree={worktree_root}"
    )


def test_worktree_bundle_never_materializes_locally(tmp_path: Path) -> None:
    """Regression guard: invoking the chokepoint from a worktree never
    writes anything into the worktree's own ``.kittify/charter/`` tree.

    consolidate-charter-bundle (IC-04 / WP04, T028c): the chokepoint no
    longer materializes derivatives ANYWHERE (manifest v2's
    ``derived_files`` is ``[]``) -- there is nothing left for it to write,
    at the main checkout or the worktree. This test now pins the narrower,
    still-real invariant: the worktree's charter dir gains no legacy
    derivative as a side effect of a chokepoint call routed through it.
    """
    from charter.activation.sync import ensure_charter_bundle_fresh

    main_root = _init_main_checkout(tmp_path / "main").resolve()
    worktree_root = _add_linked_worktree(
        main_root,
        (tmp_path / "worktree-d").resolve(),
        "feature/worktree-d",
    ).resolve()
    _clear_resolver_cache()

    result = ensure_charter_bundle_fresh(worktree_root)
    assert result is not None
    assert result.canonical_root == main_root
    assert result.synced is False

    # Post-condition: worktree's own charter dir must not hold a bundle.
    worktree_charter_dir = worktree_root / ".kittify" / "charter"
    if worktree_charter_dir.exists():
        for name in ("governance.yaml", "directives.yaml", "metadata.yaml"):
            local = worktree_charter_dir / name
            assert not local.exists(), (
                f"Worktree leak: {local} should not exist — canonical root writes only"
            )


def test_loaders_from_worktree_return_canonical_content(tmp_path: Path) -> None:
    """FR-010 content transparency: ``load_governance_config`` and
    ``load_directives_config`` invoked from a worktree return the SAME
    content as when invoked from the main checkout.

    Regression guard for a post-merge reviewer finding where the loaders
    called the chokepoint but then rebuilt paths from the caller's
    ``repo_root`` rather than from the ``SyncResult.canonical_root``.
    The chokepoint materialized the bundle in the main checkout, but the
    loader then checked ``worktree/.kittify/charter/governance.yaml``,
    found nothing, logged ``governance.yaml unavailable after charter
    auto-sync``, and returned an empty ``GovernanceConfig()``. Worktree
    readers therefore saw an empty charter even though the chokepoint
    itself was correct.
    """
    from charter.activation.sync import load_directives_config, load_governance_config

    main_root = _init_main_checkout(tmp_path / "main").resolve()
    worktree_root = _add_linked_worktree(
        main_root,
        (tmp_path / "worktree-loaders").resolve(),
        "feature/worktree-loaders",
    ).resolve()
    _clear_resolver_cache()

    # Populate the bundle from the main checkout first so we have a
    # known-good reference to compare against.
    gov_main = load_governance_config(main_root)
    dir_main = load_directives_config(main_root)

    _clear_resolver_cache()

    # Invoke the loaders from the WORKTREE path. The chokepoint maps back
    # to main and the loaders must anchor subsequent path construction on
    # the canonical root, not on ``worktree_root``.
    gov_worktree = load_governance_config(worktree_root)
    dir_worktree = load_directives_config(worktree_root)

    # Both configs must round-trip identically. An empty config would
    # indicate the loader read the wrong tree.
    assert gov_worktree.model_dump() == gov_main.model_dump(), (
        "load_governance_config(worktree) does not match load_governance_config(main); "
        "the loader is not consuming SyncResult.canonical_root."
    )
    assert dir_worktree.model_dump() == dir_main.model_dump(), (
        "load_directives_config(worktree) does not match load_directives_config(main); "
        "the loader is not consuming SyncResult.canonical_root."
    )
