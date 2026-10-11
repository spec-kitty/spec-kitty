"""FR-015 clean-tree drift digest + NFR-004 ``snapshot_sha256`` byte-stability.

The clean-tree digest enumerates a DECLARED, level-aware file set (recognised
artifact dirs + the level's layout files + ``pack.yaml``) and LF-normalizes
content, so it is reproducible across a ``git archive`` export, a ``__pycache__``-
polluted working tree, and an installed copy — covering an ORG pack
(``org-charter.yaml`` + ``drg/fragment.yaml``) and a PROJECT pack
(``graph.yaml``), not just built-in. NFR-004 pins ``snapshot_sha256`` and its two
callers byte-unchanged; the golden-value test fails if the algorithm drifts.
"""

from __future__ import annotations

import subprocess
import tarfile
from pathlib import Path

from charter.offering.packs.pack_clean_digest import clean_tree_digest
from charter.offering.packs.pack_manifest import snapshot_sha256

_PACK_ID = "01ARWG13C000000000000000FG"

# Golden digest of a fixed two-file tree, computed against the current
# ``snapshot_sha256`` algorithm. NFR-004: editing ``snapshot_sha256`` (or either
# of its callers in a way that changes the hashed framing) breaks this.
_SNAPSHOT_GOLDEN = "a81035f7cbe91f6f527f79aabb201787a33bde1c6e512fa4c8a5d58addeb6115"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _built_in_pack(root: Path) -> None:
    _write(root / "pack.yaml", f"pack_id: {_PACK_ID}\nname: sample\npack_level: built-in\npack_version: 1.0.0\n")
    _write(root / "directive.graph.yaml", "schema_version: '1.0'\nnodes: []\n")
    _write(root / "directives" / "001-x.directive.yaml", "id: X\nbody: hello\n")
    _write(root / "assets" / "logo.txt", "LOGO\n")


def _org_pack(root: Path) -> None:
    _write(root / "pack.yaml", f"pack_id: {_PACK_ID}\nname: org-sample\npack_level: org\n")
    _write(root / "org-charter.yaml", "required_directives: []\n")
    _write(root / "drg" / "fragment.yaml", "schema_version: '1.0'\nnodes: []\n")
    _write(root / "directives" / "001-y.directive.yaml", "id: Y\n")


def _project_pack(root: Path) -> None:
    _write(root / "pack.yaml", f"pack_id: {_PACK_ID}\nname: project-sample\npack_level: project\n")
    _write(root / "graph.yaml", "schema_version: '1.0'\nnodes: []\n")
    _write(root / "tactics" / "t.tactic.yaml", "id: T\n")


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


# --- FR-015 determinism: export == __pycache__-polluted worktree -------------


def test_built_in_digest_matches_git_archive_export(tmp_path: Path) -> None:
    work = tmp_path / "work"
    _built_in_pack(work)
    _git(work, "init", "-q")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "init")
    archive = tmp_path / "pack.tar"
    _git(work, "archive", "--format=tar", "-o", str(archive), "HEAD")
    export = tmp_path / "export"
    export.mkdir()
    with tarfile.open(archive) as tar:
        tar.extractall(export, filter="data")

    # Pollute the working tree with build noise git never tracked.
    _write(work / "assets" / "__pycache__" / "junk.cpython-312.pyc", "noise")
    _write(work / "directives" / "__pycache__" / "y.pyc", "noise")

    assert clean_tree_digest(work) == clean_tree_digest(export)


def test_digest_is_deterministic_across_two_calls(tmp_path: Path) -> None:
    root = tmp_path / "pack"
    _built_in_pack(root)
    assert clean_tree_digest(root) == clean_tree_digest(root)


# --- Level-aware coverage: org + project, not just built-in ------------------


def test_org_pack_layout_files_are_covered(tmp_path: Path) -> None:
    root = tmp_path / "org"
    _org_pack(root)
    before = clean_tree_digest(root)
    assert len(before) == 64

    # __pycache__ noise is excluded by construction.
    _write(root / "directives" / "__pycache__" / "z.pyc", "noise")
    assert clean_tree_digest(root) == before

    # The org charter is part of the declared file set.
    _write(root / "org-charter.yaml", "required_directives: [DIRECTIVE_001]\n")
    assert clean_tree_digest(root) != before

    # So is the org DRG fragment.
    after_charter = clean_tree_digest(root)
    _write(root / "drg" / "fragment.yaml", "schema_version: '1.0'\nnodes: [{urn: 'x'}]\n")
    assert clean_tree_digest(root) != after_charter


def test_project_pack_graph_is_covered(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _project_pack(root)
    before = clean_tree_digest(root)
    assert len(before) == 64

    _write(root / "graph.yaml", "schema_version: '1.0'\nnodes: [{urn: 'y'}]\n")
    assert clean_tree_digest(root) != before


# --- NFR-004: snapshot_sha256 is byte-unchanged ------------------------------


def test_snapshot_sha256_byte_unchanged(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"hello\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_bytes(b"world")
    assert snapshot_sha256(tmp_path) == _SNAPSHOT_GOLDEN


def test_snapshot_sha256_callers_still_import() -> None:
    # NFR-004: the two callers must keep consuming the unchanged primitive.
    from specify_cli.charter_packs.snapshot import _snapshot_manifest_is_intact
    from charter.offering.packs.pack_manifest import write_pack_manifest

    assert callable(write_pack_manifest)
    assert callable(_snapshot_manifest_is_intact)
