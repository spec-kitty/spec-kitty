"""The pin-verified pack tree exemption (#7128), without the CLI.

The end-to-end proof lives in
``tests/specify_cli/cli/commands/agent/test_analysis_report_transaction.py``. This
module covers the branches that fixture cannot cheaply reach: an unverifiable or
misnamed pin, a missing pin, a pack root outside the repository, and the
component-wise prefix scoping that keeps a sibling tree from inheriting the
exemption.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.analysis_inputs import pack_pin_state

pytestmark = pytest.mark.git_repo

PACK_YAML = (
    "pack_id: 01ARWG13C000000000000000AB\n"
    "pack_version: 1.0.0\n"
    "parent_pack: null\n"
    "name: spec-kitty-internal\n"
    "pack_level: org\n"
    "active_charter: org-charter.yaml\n"
    "pack_drg: drg/fragment.yaml\n"
)
CONFIG_HEADER = "charter: .kittify/charter/charter.yaml\n"


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True).stdout


def _pack_tree(root: Path, relative: str) -> Path:
    """A minimal, schema-valid org pack tree at *relative*."""
    pack = root / relative
    (pack / "drg").mkdir(parents=True)
    (pack / "procedures").mkdir()
    (pack / "pack.yaml").write_text(PACK_YAML)
    (pack / "org-charter.yaml").write_text("org_name: spec-kitty-internal\nskill_namespace: kitty\n")
    (pack / "drg/fragment.yaml").write_text("nodes: []\n")
    (pack / "procedures/proof.procedure.yaml").write_text("id: proof\nname: Proof\n")
    return pack


def _write_pin(path: Path, pack: Path, *, subtree: str | None = None, verifiable: bool = True) -> Path:
    from charter.offering.packs.pack_clean_digest import clean_tree_digest
    from charter.offering.packs.pack_pin import (
        TREE_DIGEST_ALGORITHM,
        PackPin,
        TreeDigest,
        full_tree_digest,
        write_pack_pin,
    )

    write_pack_pin(
        PackPin(
            repository="https://github.com/spec-kitty/spec-kitty-open-packs.git",
            commit="e" * 40,
            subtree=subtree,
            tree_digest=TreeDigest(algorithm=TREE_DIGEST_ALGORITHM, value=clean_tree_digest(pack, level="org"), level="org"),
            snapshot_sha256=full_tree_digest(pack) if verifiable else None,
        ),
        path,
    )
    return path


def _pin(root: Path, pack: Path, *, subtree: str | None = None, verifiable: bool = True) -> Path:
    """Write the sibling lockfile of *pack* (``packs/internal`` -> ``packs/internal.source.yaml``)."""
    relative = pack.relative_to(root).as_posix()
    return _write_pin(root / f"{relative}.source.yaml", pack, subtree=relative if subtree is None else subtree, verifiable=verifiable)


def _repo(tmp_path: Path, packs: tuple[str, ...] = ("packs/internal",), *, pin: bool = True, verifiable: bool = True) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "work")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "commit.gpgsign", "false")
    charter = root / ".kittify/charter"
    charter.mkdir(parents=True)
    (charter / "charter.yaml").write_text("mission_type_activations: [software-dev]\n")
    entries = "".join(f"    - name: {Path(relative).name}\n      local_path: {relative}\n" for relative in packs)
    org_block = f"charter_packs:\n  org:\n    packs:\n{entries}" if packs else ""
    (root / ".kittify/config.yaml").write_text(f"{CONFIG_HEADER}{org_block}")
    (root / ".gitignore").write_text("".join(f"/{relative}/\n" for relative in packs))
    pinned = packs[:1] if pin else ()
    for relative in packs:
        tree = _pack_tree(root, relative)
        if relative in pinned:
            _pin(root, tree, verifiable=verifiable)
    # The trees are gitignored by design; only the pin lockfiles are tracked.
    git(root, "add", ".gitignore", ".kittify", *(f"{relative}.source.yaml" for relative in pinned))
    git(root, "commit", "-qm", "seed")
    return root


def test_verified_pinned_tree_is_exempt(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    assert pack_pin_state(root) == (("packs/internal",), ())


def test_pin_naming_another_subtree_grants_nothing(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "work")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "commit.gpgsign", "false")
    charter = root / ".kittify/charter"
    charter.mkdir(parents=True)
    (charter / "charter.yaml").write_text("mission_type_activations: [software-dev]\n")
    (root / ".kittify/config.yaml").write_text(f"{CONFIG_HEADER}charter_packs:\n  org:\n    packs:\n    - name: internal\n      local_path: packs/internal\n")
    (root / ".gitignore").write_text("/packs/internal/\n")
    _pin(root, _pack_tree(root, "packs/internal"), subtree="packs/elsewhere")
    git(root, "add", ".gitignore", ".kittify", "packs")
    git(root, "commit", "-qm", "seed")

    assert pack_pin_state(root).verified_roots == ()


def test_unverifiable_pin_grants_nothing(tmp_path: Path) -> None:
    root = _repo(tmp_path, verifiable=False)

    assert pack_pin_state(root).verified_roots == ()


def test_absent_pin_grants_nothing(tmp_path: Path) -> None:
    root = _repo(tmp_path, pin=False)

    assert pack_pin_state(root) == ((), ())


def test_dirty_pin_grants_nothing_and_is_named(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    pin = root / "packs/internal.source.yaml"
    pin.write_text(pin.read_text() + "# bumped, not committed\n")

    assert pack_pin_state(root) == ((), ("packs/internal.source.yaml",))


def test_untracked_pin_grants_nothing_and_is_named(tmp_path: Path) -> None:
    root = _repo(tmp_path, pin=False)
    _pin(root, root / "packs/internal")

    assert pack_pin_state(root) == ((), ("packs/internal.source.yaml",))


def test_pack_root_outside_the_repository_grants_nothing(tmp_path: Path) -> None:
    root = _repo(tmp_path, packs=())
    outside = tmp_path / "outside/internal"
    (outside / "drg").mkdir(parents=True)
    (outside / "procedures").mkdir()
    (outside / "pack.yaml").write_text(PACK_YAML)
    (outside / "org-charter.yaml").write_text("org_name: outside\nskill_namespace: kitty\n")
    (outside / "drg/fragment.yaml").write_text("nodes: []\n")
    (outside / "procedures/proof.procedure.yaml").write_text("id: proof\nname: Proof\n")
    (root / ".kittify/config.yaml").write_text(f"{CONFIG_HEADER}charter_packs:\n  org:\n    packs:\n    - name: outside\n      local_path: {outside}\n")

    assert pack_pin_state(root) == ((), ())


def test_sibling_tree_does_not_inherit_a_verified_root(tmp_path: Path) -> None:
    """Component-wise prefix only: a sibling whose *name starts with* the verified root is not covered."""
    from specify_cli.git.report_transaction import _under_any

    root = _repo(tmp_path, packs=("packs/internal", "packs/internal-extra"))

    roots = pack_pin_state(root).verified_roots
    assert roots == ("packs/internal",)
    assert _under_any("packs/internal-extra/procedures/proof.procedure.yaml", roots) is False
    assert _under_any("packs/intern/procedures/proof.procedure.yaml", roots) is False
    assert _under_any("packs/internal/procedures/proof.procedure.yaml", roots) is True


def test_unreadable_registry_grants_nothing(tmp_path: Path) -> None:
    """An unreadable config yields no exemption rather than an error out of the preflight."""
    root = _repo(tmp_path)
    (root / ".kittify/config.yaml").write_text("charter_packs: [not, a, mapping]\n")

    assert pack_pin_state(root) == ((), ())


def test_symlinked_pin_grants_nothing(tmp_path: Path) -> None:
    """A tracked, clean pin that is a symlink carries authority bytes from outside the repository."""
    root = _repo(tmp_path, pin=False)
    _write_pin(tmp_path / "elsewhere.source.yaml", root / "packs/internal", subtree="packs/internal")
    (root / "packs/internal.source.yaml").symlink_to(tmp_path / "elsewhere.source.yaml")
    git(root, "add", "packs/internal.source.yaml")
    git(root, "commit", "-qm", "pin by symlink")

    assert pack_pin_state(root) == ((), ("packs/internal.source.yaml",))


def test_malformed_pack_descriptor_grants_nothing(tmp_path: Path) -> None:
    """An unparseable pack.yaml must not escape the preflight as an exception."""
    root = _repo(tmp_path)
    (root / "packs/internal/pack.yaml").write_text("pack_level: [unclosed\n")

    assert pack_pin_state(root) == ((), ())


def test_symlinked_pack_root_is_never_a_candidate(tmp_path: Path) -> None:
    """A root that resolves outside the repository never becomes a candidate at all."""
    import shutil

    root = _repo(tmp_path, pin=False)
    outside = tmp_path / "outside-internal"
    shutil.copytree(root / "packs/internal", outside)
    shutil.rmtree(root / "packs/internal")
    (root / "packs/internal").symlink_to(outside, target_is_directory=True)
    _write_pin(root / "packs/internal.source.yaml", outside, subtree="packs/internal")
    git(root, "add", "packs/internal.source.yaml")
    git(root, "commit", "-qm", "pin the symlinked tree")

    assert pack_pin_state(root) == ((), ())


def test_symlink_inside_the_tree_grants_nothing(tmp_path: Path) -> None:
    """The digests refuse a symlink in the tree, so a link cannot pull in outside bytes."""
    root = _repo(tmp_path)
    (root / "packs/internal/linked").symlink_to(tmp_path / "elsewhere.procedure.yaml")
    (tmp_path / "elsewhere.procedure.yaml").write_text("id: elsewhere\nname: Elsewhere\n")

    assert pack_pin_state(root) == ((), ())
