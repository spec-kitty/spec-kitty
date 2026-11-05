"""Shared production-shaped pack bytes and canonical pin writer for analysis tests."""

from pathlib import Path

PACK_YAML = (
    "pack_id: 01ARWG13C000000000000000AB\n"
    "pack_version: 1.0.0\n"
    "parent_pack: null\n"
    "name: spec-kitty-internal\n"
    "pack_level: org\n"
    "active_charter: org-charter.yaml\n"
    "pack_drg: drg/fragment.yaml\n"
)


def make_pack_tree(root: Path, relative: str) -> Path:
    """Create a minimal schema-valid org pack, without a second pin codec/digest."""
    pack = root / relative
    (pack / "drg").mkdir(parents=True)
    (pack / "procedures").mkdir()
    (pack / "pack.yaml").write_text(PACK_YAML)
    (pack / "org-charter.yaml").write_text("org_name: spec-kitty-internal\nskill_namespace: kitty\n")
    (pack / "drg/fragment.yaml").write_text("nodes: []\n")
    (pack / "procedures/proof.procedure.yaml").write_text("id: proof\nname: Proof\n")
    return pack


def write_pin(path: Path, pack: Path, *, subtree: str | None = None, verifiable: bool = True) -> Path:
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
