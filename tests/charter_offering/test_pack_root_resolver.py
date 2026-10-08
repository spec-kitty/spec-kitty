"""Resolution matrix for :func:`charter.offering.pack_paths.resolve_pack_root` (WP02).

Covers the three-step ``built-in`` resolution order (env override, ancestor
walk, fail-closed -- FR-004) plus the ``org`` / ``project`` pass-through seam.
"Editable" and "Installed" below are both exercised through the same
ancestor-walk step; there is no separate installed-wheel branch (see
:mod:`kernel.sibling_paths`'s module docstring):

* **Editable** — the nearest ancestor of the anchor file holding ``packs/built-in/``
  is returned.
* **Installed** — a *faithful filesystem simulation* of the site-packages layout
  (``<site>/kernel`` package dir with a sibling ``<site>/packs/built-in``) is
  resolved via the shared kernel primitive's ancestor walk (FR-004; there is no
  separate "installed" branch -- the walk started at the module's own file
  reaches the site-packages ancestor naturally). We simulate rather than build
  and ``pip install`` a wheel into a clean venv: the simulation exercises the
  same walk deterministically and in milliseconds; a real wheel install would
  add minutes of CI cost for the same code path. This trade-off is documented
  per the WP02 task allowance.
* **Symlinked checkout** — with the anchor file reached through a directory symlink,
  ``.resolve()`` (called before walking ``.parents``) still finds the *real*
  repo-root ``packs/``.
* **Env override** — ``SPEC_KITTY_PACKS_ROOT`` wins over an otherwise-resolvable
  editable tree.
* **Fail-closed** — with no packs anywhere and no env, :class:`PackRootNotFound`
  is raised and no ``src/doctrine`` path is returned.

Re-pinned for mission ``resolution-activation-foundation-01KZ9FKG`` WP02
(charter DIRECTIVE_041, test-remediation/re-pin discipline): before this
mission, ``charter.offering.pack_paths._resolve_built_in`` read
``SPEC_KITTY_PACKS_ROOT`` and anchored its own ancestor walk on
``pack_paths.__file__`` directly. WP02 collapsed that onto the single kernel
floor primitive, :func:`kernel.paths.get_built_in_pack_root` -- the env read
and the ancestor-walk anchor now live there, not on ``charter.offering.pack_paths``.
The behavior under test (env override, ancestor walk, fail-closed ->
``PackRootNotFound`` translation at the doctrine boundary) is unchanged and
still meaningful, so every case below is re-pointed at the relocated seam
rather than dropped: the env var is set/cleared directly (a plain literal,
matching ``tests/kernel/test_paths.py``'s own convention) and ``__file__`` is
patched on :mod:`kernel.paths` instead of ``charter.offering.pack_paths``. ``files``
stays patched on ``pack_paths`` for symmetry with
:func:`charter.offering.pack_paths.offering_package_dir` callers, even though
``_resolve_built_in`` has not called it directly since FR-004 -- so the
resolver's inputs stay fully controlled and hermetic (the real repository
tree is never consulted).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import kernel.paths as kernel_paths
from charter.offering import pack_paths
from charter.offering.pack_paths import PackRootNotFound, resolve_pack_root

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

#: WP02 relocated the ``SPEC_KITTY_PACKS_ROOT`` env read from
#: ``charter.offering.pack_paths`` onto :func:`kernel.paths.get_built_in_pack_root` (the
#: kernel-floor primitive ``_resolve_built_in`` now delegates to wholesale) --
#: pinned here as a plain literal (matching ``tests/kernel/test_paths.py``'s own
#: convention) rather than reaching into either module's private constant.
_PACKS_ROOT_ENV = "SPEC_KITTY_PACKS_ROOT"


def _make_anchor_file(pkg_dir: Path) -> Path:
    """Create ``pkg_dir`` and return the path ``kernel/paths.py`` would occupy in it.

    The returned path is what :func:`_isolate` binds onto
    ``kernel.paths.__file__`` -- the real anchor
    :func:`kernel.paths.get_built_in_pack_root`'s ancestor walk starts from
    post-WP02 delegation (previously this bound ``charter.offering.pack_paths.__file__``).
    """
    pkg_dir.mkdir(parents=True, exist_ok=True)
    return pkg_dir / "paths.py"


def _isolate(
    monkeypatch: pytest.MonkeyPatch,
    *,
    module_file: Path,
    doctrine_dir: Path | None,
) -> None:
    """Pin the resolver's discovery inputs at the relocated kernel seam.

    ``charter.offering.pack_paths._resolve_built_in`` (WP02, mission
    ``resolution-activation-foundation-01KZ9FKG``) now delegates wholesale to
    :func:`kernel.paths.get_built_in_pack_root`, so both the
    ``SPEC_KITTY_PACKS_ROOT`` env read and the ancestor-walk anchor
    (``kernel.paths.__file__``) live at the kernel floor, not on
    ``charter.offering.pack_paths`` anymore -- ``pack_paths.__file__`` is no longer
    consulted by ``_resolve_built_in`` at all. ``files`` stays patched on
    ``pack_paths`` for symmetry with
    :func:`charter.offering.pack_paths.offering_package_dir` callers, though
    ``_resolve_built_in`` itself never calls it (has not since FR-004).
    """
    monkeypatch.delenv(_PACKS_ROOT_ENV, raising=False)
    monkeypatch.setattr(kernel_paths, "__file__", str(module_file))

    def fake_files(_name: str) -> Path:
        if doctrine_dir is None:
            raise ModuleNotFoundError(_name)
        return doctrine_dir

    monkeypatch.setattr(pack_paths, "files", fake_files)


def test_editable_resolves_repo_root_packs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Editable checkout: the ancestor holding ``packs/built-in/`` is returned."""
    repo = tmp_path / "repo"
    module_file = _make_anchor_file(repo / "src" / "kernel")
    packs_built_in = repo / "packs" / "built-in"
    packs_built_in.mkdir(parents=True)

    _isolate(monkeypatch, module_file=module_file, doctrine_dir=None)

    assert resolve_pack_root("built-in") == packs_built_in


def test_installed_layout_resolves_site_packages_sibling_via_ancestor_walk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Installed layout: the module's own package dir's parent/packs/built-in is returned.

    Reimplemented for FR-004 (mission
    doctrine-consumer-surface-missions-extraction-01KZ6G6H), then re-pinned for
    mission ``resolution-activation-foundation-01KZ9FKG`` WP02:
    ``_resolve_built_in`` no longer resolves this via a distinct step 3
    (``files("charter.offering")`` or a ``Path(__file__).resolve().parent.parent`` probe
    of its own) -- it delegates entirely to :func:`kernel.paths.get_built_in_pack_root`,
    whose *ancestor walk* reaches the site-packages level naturally because
    ``anchor.parent.parent`` is always one of ``anchor.parents``. ``module_file``
    is placed *inside* ``doctrine_dir`` itself here, matching how
    ``kernel.paths.__file__`` genuinely behaves in a real installed wheel (a
    ``paths.py`` file always lives inside the ``kernel`` package directory);
    the walk started at that file answers at the site-packages ancestor --
    there is no separate "step 3" branch left to exercise (see
    ``kernel.sibling_paths``'s module docstring).
    """
    site = tmp_path / "site-packages"
    kernel_dir = site / "kernel"
    packs_built_in = site / "packs" / "built-in"
    packs_built_in.mkdir(parents=True)

    # Realistic module location: paths.py lives inside the kernel package dir
    # itself, so its parent.parent is the site-packages level.
    module_file = _make_anchor_file(kernel_dir)

    _isolate(monkeypatch, module_file=module_file, doctrine_dir=None)

    assert resolve_pack_root("built-in") == packs_built_in


def test_symlinked_checkout_resolves_real_repo_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A dir-symlinked package still resolves the real repo-root ``packs/`` via ``.resolve()``."""
    real_repo = tmp_path / "real-repo"
    real_pkg = real_repo / "src" / "kernel"
    real_pkg.mkdir(parents=True)
    packs_built_in = real_repo / "packs" / "built-in"
    packs_built_in.mkdir(parents=True)

    # Symlinked "site" view onto the real package dir; the symlink's own parent
    # (site/) has NO packs -- only .resolve() to the real tree finds them.
    site = tmp_path / "site"
    site.mkdir()
    link = site / "kernel"
    link.symlink_to(real_pkg, target_is_directory=True)
    module_file = link / "paths.py"

    _isolate(monkeypatch, module_file=module_file, doctrine_dir=None)

    resolved = resolve_pack_root("built-in")
    assert resolved == packs_built_in.resolve()


def test_env_override_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``SPEC_KITTY_PACKS_ROOT`` wins over an otherwise-resolvable editable tree."""
    repo = tmp_path / "repo"
    module_file = _make_anchor_file(repo / "src" / "kernel")
    editable_packs = repo / "packs" / "built-in"
    editable_packs.mkdir(parents=True)

    env_root = tmp_path / "env-packs"
    env_built_in = env_root / "built-in"
    env_built_in.mkdir(parents=True)

    _isolate(monkeypatch, module_file=module_file, doctrine_dir=None)
    monkeypatch.setenv(_PACKS_ROOT_ENV, str(env_root))

    resolved = resolve_pack_root("built-in")
    assert resolved == env_built_in
    assert resolved != editable_packs


def test_env_override_missing_dir_falls_through_to_editable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An env value that has no ``built-in/`` subdir does not short-circuit resolution."""
    repo = tmp_path / "repo"
    module_file = _make_anchor_file(repo / "src" / "kernel")
    editable_packs = repo / "packs" / "built-in"
    editable_packs.mkdir(parents=True)

    _isolate(monkeypatch, module_file=module_file, doctrine_dir=None)
    monkeypatch.setenv(_PACKS_ROOT_ENV, str(tmp_path / "empty"))

    assert resolve_pack_root("built-in") == editable_packs


def test_fail_closed_when_no_packs_anywhere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No env, no editable, no installed -> PackRootNotFound; never a src/doctrine path."""
    module_file = _make_anchor_file(tmp_path / "isolated" / "kernel")
    empty_site = tmp_path / "site" / "doctrine"
    empty_site.mkdir(parents=True)  # sibling packs/ deliberately absent

    _isolate(monkeypatch, module_file=module_file, doctrine_dir=empty_site)

    with pytest.raises(PackRootNotFound) as excinfo:
        resolve_pack_root("built-in")
    assert excinfo.value.tier == "built-in"


def test_fail_closed_when_files_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No candidate anywhere in the ancestor walk -> fails closed.

    The ``doctrine_dir=None`` isolation (``files("charter.offering")`` raising) is
    kept for symmetry with ``_isolate``'s other callers but is not actually
    consulted here: ``_resolve_built_in`` no longer calls ``files()`` at all
    (FR-004) -- what makes this fail closed is that the ancestor walk from
    ``module_file`` finds no ``packs/built-in/`` anywhere.
    """
    module_file = _make_anchor_file(tmp_path / "isolated" / "kernel")

    _isolate(monkeypatch, module_file=module_file, doctrine_dir=None)

    with pytest.raises(PackRootNotFound):
        resolve_pack_root("built-in")


@pytest.mark.parametrize(
    ("tier", "kwarg"),
    [("org", "org_root"), ("project", "project_root")],
)
def test_org_and_project_return_caller_root(tmp_path: Path, tier: str, kwarg: str) -> None:
    """``org`` / ``project`` return the caller-supplied root unchanged (shared seam)."""
    supplied = tmp_path / tier
    supplied.mkdir()
    resolved = resolve_pack_root(tier, **{kwarg: supplied})  # type: ignore[arg-type]
    assert resolved == supplied


@pytest.mark.parametrize("tier", ["org", "project"])
def test_org_and_project_fail_closed_without_root(tier: str) -> None:
    """A missing caller root for ``org`` / ``project`` fails closed."""
    with pytest.raises(PackRootNotFound) as excinfo:
        resolve_pack_root(tier)  # type: ignore[arg-type]
    assert excinfo.value.tier == tier
