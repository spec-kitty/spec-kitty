"""WP06 (#5965 / #5966): tool-owned tree deletions reach ``remove_tool_owned_tree``.

Per module group: the normal delete still happens, and a planted ``.git``
directory makes the run-time guard refuse (proving the helper is wired in).
"""

from __future__ import annotations

import ast
import atexit
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from kernel.tree_removal import ToolOwnedPathUnproven, remove_tool_owned_tree
from specify_cli.charter_packs import snapshot as snapshot_mod
from specify_cli.charter_packs.template_render import pipeline as pipeline_mod
from specify_cli.charter_packs.template_render import resolve as resolve_mod
from specify_cli.skills import catalog as catalog_mod
from specify_cli.template import asset_generator, manager

pytestmark = pytest.mark.fast

_REPO_SRC = Path(__file__).resolve().parents[2] / "src"


def _tree(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "a.txt").write_text("x", encoding="utf-8")
    return root


def _plant_git(root: Path) -> None:
    (root / ".git").mkdir()


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _init_clone(root: Path) -> Path:
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.org")
    _git(root, "config", "user.name", "t")
    (root / "f.txt").write_text("1", encoding="utf-8")
    _git(root, "add", "f.txt")
    _git(root, "commit", "-q", "-m", "init")
    return root


# --- charter_packs: snapshot ---------------------------------------------


def test_snapshot_discard_removes_staging(tmp_path: Path) -> None:
    local = tmp_path / "packs" / "org"
    staging = _tree(local.parent / ".tmp-abc")
    snapshot_mod._discard(staging, local)
    assert not staging.exists()


def test_snapshot_discard_refuses_git_checkout(tmp_path: Path) -> None:
    local = tmp_path / "packs" / "org"
    staging = _tree(local.parent / ".tmp-abc")
    _plant_git(staging)
    with pytest.raises(ToolOwnedPathUnproven):
        snapshot_mod._discard(staging, local)
    assert staging.exists()


# --- charter_packs: template_render ---------------------------------------


def test_cleanup_source_removes_temp_tree(tmp_path: Path) -> None:
    root = _tree(tmp_path / "src")
    pipeline_mod._cleanup_source(root, True)
    assert not root.exists()


def test_cleanup_source_keeps_tree_when_not_a_cleanup_source(tmp_path: Path) -> None:
    root = _tree(tmp_path / "src")
    pipeline_mod._cleanup_source(root, False)
    assert root.exists()


def test_discard_temp_source_removes_clean_clone(tmp_path: Path) -> None:
    clone = _init_clone(tmp_path / "clone")
    resolve_mod.discard_temp_source(clone)
    assert not clone.exists()


def test_discard_temp_source_keeps_clone_with_local_work(tmp_path: Path) -> None:
    clone = _init_clone(tmp_path / "clone")
    (clone / "only-copy.txt").write_text("precious", encoding="utf-8")
    resolve_mod.discard_temp_source(clone)
    assert (clone / "only-copy.txt").exists()


def test_force_swap_backup_removed(tmp_path: Path) -> None:
    pack = _tree(tmp_path / "pack")
    staging = _tree(tmp_path / "staging")
    assert pipeline_mod._force_swap(staging, pack) is None
    assert [p.name for p in tmp_path.iterdir()] == ["pack"]


# --- skills/catalog --------------------------------------------------------


def test_remove_node_deletes_stale_entry(tmp_path: Path) -> None:
    node = _tree(tmp_path / "stale")
    catalog_mod._remove_node(node)
    assert not node.exists()


def test_remove_node_refuses_git_checkout(tmp_path: Path) -> None:
    node = _tree(tmp_path / "stale")
    _plant_git(node)
    with pytest.raises(ToolOwnedPathUnproven):
        catalog_mod._remove_node(node)


def test_read_only_parent_registers_tool_owned_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    registered: list[tuple[Callable[..., object], tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(atexit, "register", lambda fn, *a, **kw: registered.append((fn, a, kw)))
    monkeypatch.setattr(catalog_mod, "_READ_ONLY_ROOT", None)
    root = catalog_mod._read_only_parent()
    try:
        ((fn, args, kwargs),) = registered
        assert fn == remove_tool_owned_tree
        assert args == (root,)
        assert kwargs["tool_root"] == root and kwargs["best_effort"] is True
        registered[0][0](*args, **kwargs)
        assert not root.exists()
    finally:
        monkeypatch.setattr(catalog_mod, "_READ_ONLY_ROOT", None)


# --- template ----------------------------------------------------------------


def test_copy_package_tree_replaces_regenerable_destination(tmp_path: Path) -> None:
    resource = _tree(tmp_path / "res")
    dest = _tree(tmp_path / "dest")
    (dest / "stale.txt").write_text("old", encoding="utf-8")
    manager.copy_package_tree(resource, dest)
    assert not (dest / "stale.txt").exists()
    assert (dest / "a.txt").read_text(encoding="utf-8") == "x"


def test_copy_package_tree_refuses_git_checkout_destination(tmp_path: Path) -> None:
    resource = _tree(tmp_path / "res")
    dest = _tree(tmp_path / "dest")
    _plant_git(dest)
    with pytest.raises(ToolOwnedPathUnproven):
        manager.copy_package_tree(resource, dest)
    assert (dest / ".git").exists()


def test_prepare_command_templates_replaces_merged_dir(tmp_path: Path) -> None:
    base = _tree(tmp_path / "base")
    (base / "x.md").write_text("base", encoding="utf-8")
    mission = tmp_path / "m1" / "templates"
    mission.mkdir(parents=True)
    merged = asset_generator.prepare_command_templates(base, mission)
    (merged / "leftover.txt").write_text("old", encoding="utf-8")
    again = asset_generator.prepare_command_templates(base, mission)
    assert again == merged and not (again / "leftover.txt").exists()


def test_prepare_command_templates_refuses_git_merged_dir(tmp_path: Path) -> None:
    base = _tree(tmp_path / "base")
    mission = tmp_path / "m1" / "templates"
    mission.mkdir(parents=True)
    merged = asset_generator.prepare_command_templates(base, mission)
    _plant_git(merged)
    with pytest.raises(ToolOwnedPathUnproven):
        asset_generator.prepare_command_templates(base, mission)


# --- runtime bridge + charter pack assembler ----------------------------------


def test_assemble_pack_force_refuses_git_output_dir(tmp_path: Path) -> None:
    from charter.offering.packs.pack_assembler import assemble_pack

    pack_in = tmp_path / "in"
    pack_in.mkdir()
    out = _tree(tmp_path / "out")
    (out / "pack-manifest.yaml").write_text(
        "pack_version: '1'\nartifact_counts: {}\nfetched_at: '2026-01-01T00:00:00Z'\nsource_type: assemble\nsource_url: ''\n",
        encoding="utf-8",
    )
    _plant_git(out)
    with pytest.raises(ToolOwnedPathUnproven):
        assemble_pack([pack_in], out, force=True)
    assert (out / ".git").exists()


@pytest.mark.parametrize(
    "relative",
    [
        "runtime/next/runtime_bridge_query.py",
        "runtime/next/runtime_bridge_io.py",
        "charter/offering/packs/pack_assembler.py",
    ],
)
def test_runtime_and_charter_modules_use_kernel_helper_not_bare_rmtree(relative: str) -> None:
    tree = ast.parse((_REPO_SRC / relative).read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "rmtree"]
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert calls == []
    assert "remove_tool_owned_tree" in names
