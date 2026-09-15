"""Authored-only contract for the built-in pack's two-file split (WP04, T016).

IC-06 (pack-metadata-manifest-unification-01M052PT, FR-008/NFR-004):
``packs/built-in/pack.yaml`` + ``pack.md`` are **authored, hand-edited**
data; the sibling ``pack-manifest.yaml`` is **generated** and must never be
hand-authored, and conversely nothing must ever machine-write the authored
pair. This file pins the half of that contract available on WP04's lane:

* the authored files exist and are shaped like a ``PackDescriptor``
  (data-model.md) -- not generated-manifest fields (``constituents``,
  ``schema_version``, hashes) leaking in;
* neither of this WP's owned source modules
  (``src/specify_cli/doctrine/pack_assembler.py``,
  ``src/specify_cli/cli/commands/_doctrine_collect.py``) contains a write
  call targeting the authored filenames.

**Consolidated-branch note:** the *full* NFR-004 guarantee -- "regenerate the
built-in pack's manifest and assert ``pack.yaml``/``pack.md`` are
byte-unchanged, and the generator writes only ``pack-manifest.yaml``" -- needs
WP01's ``builtin_manifest.py`` generator. On this consolidated branch that
generator IS present, so
:func:`test_regenerate_leaves_authored_files_byte_unchanged` below runs the
real check against the real committed corpus (no stub): regenerating writes
only ``pack-manifest.yaml``, leaves the authored pair byte-identical, and
fails loudly on a stale committed manifest so CI catches future drift.

This module reads the real, wheel-shipped ``packs/built-in/`` corpus (via
:func:`charter.offering.pack_paths.built_in_root`), so it carries
``pytest.mark.corpus`` (see ``tests/architectural/test_ci_corpus_trigger_completeness.py``'s
curated registry, updated alongside this file).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

from charter.offering.pack_paths import built_in_root
from specify_cli.doctrine.builtin_manifest import (
    MANIFEST_FILENAME,
    generate_builtin_manifest,
)

pytestmark = [pytest.mark.architectural, pytest.mark.corpus]

_REPO_ROOT = Path(__file__).resolve().parents[2]

# This WP's owned source scope (tasks/WP04-authored-generated-split.md
# owned_files) -- the only modules this test can attest write nothing to the
# authored files. Other owned_files entries in that WP (packs/built-in/pack.*
# themselves, and the two test files) are data/tests, not writers.
_OWNED_SOURCE_MODULES = (
    _REPO_ROOT / "src" / "specify_cli" / "doctrine" / "pack_assembler.py",
    _REPO_ROOT / "src" / "specify_cli" / "cli" / "commands" / "_doctrine_collect.py",
)

_AUTHORED_FILENAMES = frozenset({"pack.yaml", "pack.md"})

# The exact PackDescriptor field set (data-model.md) -- authored pack.yaml
# must carry exactly these keys, no more (a generated-manifest field like
# ``constituents``/``schema_version``/``manifest_hash`` leaking in would be a
# split-boundary violation) and no fewer.
_PACK_DESCRIPTOR_FIELDS = frozenset(
    {"pack_id", "pack_version", "parent_pack", "accompanies_doctrine_pack", "name"}
)


def test_authored_pack_yaml_exists_and_is_shaped_as_a_pack_descriptor() -> None:
    pack_root = built_in_root()
    descriptor_path = pack_root / "pack.yaml"
    assert descriptor_path.is_file(), "packs/built-in/pack.yaml must exist (authored, FR-008)"

    data = yaml.safe_load(descriptor_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "pack.yaml must parse to a mapping"
    assert set(data) == _PACK_DESCRIPTOR_FIELDS, (
        f"pack.yaml field set {sorted(data)} does not match the authored "
        f"PackDescriptor contract {sorted(_PACK_DESCRIPTOR_FIELDS)} -- a "
        "generated-manifest field would mean the split boundary leaked"
    )

    pack_id = data["pack_id"]
    assert isinstance(pack_id, str) and len(pack_id) == 26, "pack_id must be a 26-char ULID"

    pack_version = data["pack_version"]
    assert isinstance(pack_version, str) and pack_version, "pack_version must be authored (non-empty)"

    # The built-in pack is the root of every lineage chain (no built-in-of-a-
    # built-in), and does not itself accompany a doctrine pack (that field is
    # only meaningful for charter/synthesized packs).
    assert data["parent_pack"] is None
    assert data["accompanies_doctrine_pack"] is None
    assert data["name"] == "built-in"


def test_authored_pack_md_exists_and_is_non_empty() -> None:
    pack_root = built_in_root()
    description_path = pack_root / "pack.md"
    assert description_path.is_file(), "packs/built-in/pack.md must exist (authored, FR-008)"
    assert description_path.read_text(encoding="utf-8").strip(), "pack.md must not be an empty placeholder"


def _iter_string_constants(node: ast.AST) -> set[str]:
    return {n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def _is_write_mode(value: str) -> bool:
    return any(flag in value for flag in ("w", "a", "+"))


def _write_calls(tree: ast.AST) -> list[ast.Call]:
    """Return every AST ``Call`` node that plausibly writes a file.

    Covers ``<expr>.write_text(...)`` / ``.write_bytes(...)`` and
    ``open(..., "w"/"a"/"...+"...)``. This is a decisive proxy, not an
    exhaustive taint analysis (e.g. it would not follow a path built via
    string concatenation through an intermediate variable across
    statements) -- sufficient for a lane-scoped regression ratchet over two
    known, currently write-free modules, and re-checked by the reviewer
    against the real diff (WP04 reviewer guidance).
    """
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in {"write_text", "write_bytes"}:
            calls.append(node)
            continue
        if isinstance(func, ast.Name) and func.id == "open":
            mode_literals = {
                arg.value
                for arg in (*node.args, *(kw.value for kw in node.keywords))
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
            }
            if any(_is_write_mode(m) for m in mode_literals):
                calls.append(node)
    return calls


def test_owned_scope_modules_have_no_write_call_targeting_the_authored_files() -> None:
    """No code in this WP's owned scope writes ``pack.yaml``/``pack.md``.

    ``pack_assembler.py`` and ``_doctrine_collect.py`` both gained a
    ``_read_authored_pack_version`` helper (T015) that *reads* ``pack.yaml``
    (via ``.load(descriptor)`` / ``.read_text()``, never a write call) -- this
    scan is deliberately scoped to write-shaped calls only, so those
    legitimate reads do not false-positive here.
    """
    for module_path in _OWNED_SOURCE_MODULES:
        assert module_path.is_file(), f"expected owned module missing: {module_path}"
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
        for call in _write_calls(tree):
            hit = _iter_string_constants(call) & _AUTHORED_FILENAMES
            assert not hit, (
                f"{module_path}:{call.lineno} writes to a literal matching the "
                f"authored pack descriptor filename(s) {sorted(hit)} -- the "
                "no-author-edit contract (NFR-004) forbids owned-scope code "
                "from writing packs/built-in/pack.yaml or pack.md"
            )


def _snapshot_tree(root: Path) -> dict[str, bytes]:
    """Return ``{relative_posix_path: file_bytes}`` for every file under *root*."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_regenerate_leaves_authored_files_byte_unchanged() -> None:
    """Full NFR-004 guarantee against the real committed built-in corpus.

    WP01's generator is present on this consolidated branch, so the check is
    no longer a stub. Regenerating ``pack-manifest.yaml`` over the real
    ``built_in_root()`` must:

    * (a) leave the authored ``pack.yaml`` and ``pack.md`` byte-for-byte
      identical;
    * (b) write **only** ``pack-manifest.yaml`` -- no other file in the pack
      tree is created or mutated;
    * (c) already match what is committed -- a stale committed manifest (the
      FIX-1 drift class) fails this test so CI catches it.

    The committed ``pack-manifest.yaml`` is restored afterwards so a stale
    corpus never leaves the working tree dirty.
    """
    pack_root = built_in_root()
    manifest_path = pack_root / MANIFEST_FILENAME

    before = _snapshot_tree(pack_root)
    assert "pack.yaml" in before and "pack.md" in before, "real built-in corpus not found"
    assert MANIFEST_FILENAME in before, "committed pack-manifest.yaml must exist before regen"

    original_manifest = manifest_path.read_bytes()
    try:
        generate_builtin_manifest(pack_root)
        after = _snapshot_tree(pack_root)
    finally:
        manifest_path.write_bytes(original_manifest)

    # (a) the authored pair is byte-unchanged by regeneration.
    for authored in ("pack.yaml", "pack.md"):
        assert after[authored] == before[authored], (
            f"regenerating the manifest mutated authored file {authored!r} -- "
            "NFR-004 forbids the generator from touching the authored pair"
        )

    # (b) the generator writes ONLY pack-manifest.yaml.
    changed = {rel for rel in before if before[rel] != after.get(rel)}
    created = set(after) - set(before)
    assert changed <= {MANIFEST_FILENAME}, (
        "generator mutated files other than pack-manifest.yaml: "
        f"{sorted(changed - {MANIFEST_FILENAME})}"
    )
    assert not created, f"generator created unexpected files: {sorted(created)}"

    # (c) the committed manifest is already fresh (stale => FIX-1-class drift).
    assert after[MANIFEST_FILENAME] == before[MANIFEST_FILENAME], (
        "committed packs/built-in/pack-manifest.yaml is stale; run "
        "`spec-kitty doctrine regenerate-graph` and commit the result"
    )
