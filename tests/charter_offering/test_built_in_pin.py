"""WP01 -- built-in pin lockfile model (mission builtin-revendor-pin-gate, #3504).

Covers FR-001 / FR-002 / NFR-001 / C-006 / SC-002 / SC-004.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from charter.offering.pack_paths import resolve_pack_root
from charter.offering.packs.built_in_pin import (
    BuiltInPin,
    BuiltInPinError,
    load_built_in_pin,
    verify_built_in_pin,
    write_built_in_pin,
)
from charter.offering.packs.pack_clean_digest import clean_tree_digest
from charter.offering.packs.pack_pin import TreeDigest, full_tree_digest
from kernel.pack_tiers import BUILT_IN

_THIS = Path(__file__).resolve()
REPO_ROOT = _THIS.parents[2]
PACK_ROOT = REPO_ROOT / "packs" / "built-in"
LOCKFILE = REPO_ROOT / "packs" / "built-in.source.yaml"
SHA = "7f063aecbdede29d05cc4d5fc9a5b13f9c7434d7"
REPO_URL = "https://github.com/spec-kitty/spec-kitty-open-packs.git"


def _pin(
    commit: str = SHA,
    tree_digest: TreeDigest | None = None,
    requires_core: str | None = None,
    snapshot_sha256: str | None = None,
) -> BuiltInPin:
    return BuiltInPin(
        repository=REPO_URL,
        commit=commit,
        tree_digest=tree_digest or TreeDigest(algorithm="clean-tree-sha256", value="0" * 64),
        requires_core=requires_core,
        snapshot_sha256=snapshot_sha256,
    )


def _make_pack(root: Path) -> Path:
    pack = root / "built-in"
    (pack / "directives").mkdir(parents=True)
    (pack / "pack.yaml").write_text(
        "pack_id: 01ARWG13C000000000000000FG\npack_version: 1.0.0\nparent_pack: null\nname: built-in\npack_level: built-in\n",
        encoding="utf-8",
    )
    (pack / "directives" / "a.directive.yaml").write_text("id: a\n", encoding="utf-8")
    return pack


# --- T001 / SC-002 round trip -------------------------------------------------


def test_committed_tree_digest_matches_lockfile() -> None:
    pin = load_built_in_pin(LOCKFILE)
    assert clean_tree_digest(PACK_ROOT, level=BUILT_IN) == pin.tree_digest.value
    assert verify_built_in_pin(pin, PACK_ROOT) is True


def test_lockfile_is_sibling_of_not_inside_digested_tree() -> None:
    assert LOCKFILE.parent == PACK_ROOT.parent
    assert PACK_ROOT not in LOCKFILE.parents


def test_seeded_pin_provenance() -> None:
    pin = load_built_in_pin(LOCKFILE)
    assert pin.repository == REPO_URL
    assert re.fullmatch(r"[0-9a-f]{40}", pin.commit)  # a pin bump must not break this test
    assert pin.tree_digest.algorithm == "clean-tree-sha256"
    assert pin.requires_core == ">=4.0.0rc7,<5"


# --- T002 model ---------------------------------------------------------------


def test_write_load_round_trip(tmp_path: Path) -> None:
    pin = _pin(requires_core=">=4.0.0rc7,<5", snapshot_sha256="ab" * 32)
    target = tmp_path / "built-in.source.yaml"
    write_built_in_pin(pin, target)
    assert load_built_in_pin(target) == pin
    text = target.read_text(encoding="utf-8")
    assert "open-packs -> core" in text


def test_write_load_round_trip_without_optionals(tmp_path: Path) -> None:
    target = tmp_path / "pin.yaml"
    write_built_in_pin(_pin(), target)
    assert load_built_in_pin(target) == _pin()


def test_verify_false_on_digest_mismatch(tmp_path: Path) -> None:
    pack = _make_pack(tmp_path)
    assert verify_built_in_pin(_pin(), pack) is False
    good = _pin(
        tree_digest=TreeDigest("clean-tree-sha256", clean_tree_digest(pack, level=BUILT_IN)),
        snapshot_sha256=full_tree_digest(pack),
    )
    assert verify_built_in_pin(good, pack) is True


@pytest.mark.parametrize(
    "text",
    [
        "",
        "- a\n- b\n",
        "repository: x\n",
        f"repository: {REPO_URL}\ncommit: {SHA}\ntree_digest: nope\n",
        f"repository: {REPO_URL}\ncommit: {SHA}\ntree_digest: {{algorithm: a}}\n",
        f"repository: {REPO_URL}\ncommit: {SHA}\ntree_digest: {{algorithm: a, value: b}}\nrequires_core: 5\n",
    ],
)
def test_load_rejects_malformed(tmp_path: Path, text: str) -> None:
    target = tmp_path / "pin.yaml"
    target.write_text(text, encoding="utf-8")
    with pytest.raises(BuiltInPinError):
        load_built_in_pin(target)


def test_load_missing_file(tmp_path: Path) -> None:
    with pytest.raises(BuiltInPinError):
        load_built_in_pin(tmp_path / "absent.yaml")


# --- T004 FR-002 SHA not tag --------------------------------------------------


def test_committed_commit_is_40_hex() -> None:
    commit = load_built_in_pin(LOCKFILE).commit
    assert len(commit) == 40
    int(commit, 16)


@pytest.mark.parametrize("bad", ["v0.1.0", "main", SHA[:39], SHA.upper(), SHA + "0", ""])
def test_tag_like_commit_rejected(tmp_path: Path, bad: str) -> None:
    with pytest.raises(BuiltInPinError):
        _pin(commit=bad)
    target = tmp_path / "pin.yaml"
    target.write_text(
        f"repository: {REPO_URL}\ncommit: {bad!r}\ntree_digest: {{algorithm: a, value: b}}\n",
        encoding="utf-8",
    )
    with pytest.raises(BuiltInPinError):
        load_built_in_pin(target)


# --- T004 C-006 subtree scoping / NFR-001 determinism -------------------------


def test_digest_scoped_to_built_in_subtree(tmp_path: Path) -> None:
    pack = _make_pack(tmp_path)
    before = clean_tree_digest(pack, level=BUILT_IN)
    (tmp_path / "built-in.source.yaml").write_text("outside: 1\n", encoding="utf-8")
    (tmp_path / "sibling").mkdir()
    (tmp_path / "sibling" / "x.yaml").write_text("x: 1\n", encoding="utf-8")
    assert clean_tree_digest(pack, level=BUILT_IN) == before
    (pack / "directives" / "a.directive.yaml").write_text("id: changed\n", encoding="utf-8")
    assert clean_tree_digest(pack, level=BUILT_IN) != before


def test_digest_deterministic_across_pycache(tmp_path: Path) -> None:
    pack = _make_pack(tmp_path)
    first = clean_tree_digest(pack, level=BUILT_IN)
    assert clean_tree_digest(pack, level=BUILT_IN) == first
    cache = pack / "directives" / "__pycache__"
    cache.mkdir()
    (cache / "x.cpython-312.pyc").write_bytes(b"\x00junk")
    assert clean_tree_digest(pack, level=BUILT_IN) == first


# --- T015 SC-004 resolver probe + positive control ----------------------------


def test_resolver_resolves_to_pinned_bytes() -> None:
    pin = load_built_in_pin(LOCKFILE)
    assert clean_tree_digest(resolve_pack_root("built-in"), level=BUILT_IN) == pin.tree_digest.value


def test_resolver_probe_goes_red_on_mutated_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pin = load_built_in_pin(LOCKFILE)
    mutated = _make_pack(tmp_path)
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(tmp_path))
    resolved = resolve_pack_root("built-in")
    assert resolved == mutated
    assert clean_tree_digest(resolved, level=BUILT_IN) != pin.tree_digest.value
