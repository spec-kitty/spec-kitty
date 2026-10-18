"""Release parity: the BUILT wheel's ``packs/built-in/`` tree digest equals the pin.

Mission ``builtin-revendor-pin-gate-01M55MX7`` (#3504), FR-009 / SC-003 / NFR-003.
The committed pin (``packs/built-in.source.yaml``) records the clean-tree digest of
``packs/built-in/``. This test extracts that tree from the real built wheel and
asserts the same digest, so a release cannot ship a tree that differs from the pin.

A positive control proves the assertion is live: a mutated copy of the extracted
tree must NOT match the pin.

Run explicitly (builds a wheel; not part of the fast tier)::

    pytest tests/cross_cutting/packaging/test_built_in_release_parity.py -m distribution -v
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

import pytest

from charter.offering.packs.built_in_pin import load_built_in_pin
from charter.offering.packs.pack_clean_digest import clean_tree_digest
from kernel.pack_tiers import BUILT_IN

pytestmark = [pytest.mark.distribution, pytest.mark.integration]

REPO_ROOT = Path(__file__).resolve().parents[3]
PIN_PATH = REPO_ROOT / "packs" / "built-in.source.yaml"
_WHEEL_PREFIX = "packs/built-in/"


@pytest.fixture(scope="module")
def wheel_pack_root(build_artifacts: dict[str, Path], tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Extract the built wheel's ``packs/built-in/`` into a temp dir; return its root."""
    out = tmp_path_factory.mktemp("built-in-release-parity")
    with zipfile.ZipFile(build_artifacts["wheel"]) as zf:
        members = [n for n in zf.namelist() if n.startswith(_WHEEL_PREFIX) and not n.endswith("/")]
        assert members, "wheel ships no packs/built-in/ files"
        for name in members:
            target = out / name[len(_WHEEL_PREFIX) :]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(name))
    return out


def test_built_wheel_built_in_digest_equals_pin(wheel_pack_root: Path) -> None:
    pin = load_built_in_pin(PIN_PATH)
    actual = clean_tree_digest(wheel_pack_root, level=BUILT_IN)
    assert actual == pin.tree_digest.value, f"built wheel packs/built-in digest {actual} != committed pin {pin.tree_digest.value}"


def test_mutated_wheel_tree_does_not_match_pin(wheel_pack_root: Path, tmp_path: Path) -> None:
    """Positive control: a drifted tree reds the digest comparison (non-vacuity)."""
    pin = load_built_in_pin(PIN_PATH)
    mutated = tmp_path / "mutated"
    shutil.copytree(wheel_pack_root, mutated)
    descriptor = mutated / "pack.yaml"
    descriptor.write_bytes(descriptor.read_bytes() + b"\n# drift\n")
    assert clean_tree_digest(mutated, level=BUILT_IN) != pin.tree_digest.value
