"""``spec-kitty charter pack vendor`` is a pin-bump helper (#6451, WP06; FR-010, FR-011).

Every test drives the REAL CLI against a real ``file://`` bare git repository
(``conftest_pack_remote``): the bump genuinely fetches the subtree, recomputes the
clean-tree digest and rewrites the ``<pack>.source.yaml`` pin. No tree under ``packs/`` is
ever copied or swapped; the ``--check`` leg is offline.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from charter.offering.packs.pack_clean_digest import clean_tree_digest
from charter.offering.packs.pack_pin import PackPin, TreeDigest, full_tree_digest, load_pack_pin, write_pack_pin
from kernel.pack_tiers import BUILT_IN, ORG
from specify_cli import app as cli_app
from specify_cli.cli.commands.charter import pack_vendor as pack_vendor_module
from tests.charter_offering.conftest_pack_remote import PackRemote, git, make_pack_remote, write_pack_tree

pytestmark = pytest.mark.fast

runner = CliRunner()
_OLD_SHA = "1" * 40
_OLD_DIGEST = "2" * 64


def _publish(remote: PackRemote, tmp_path: Path, *, marker: str, pack_yaml_extra: str = "") -> str:
    """Commit a changed subtree to the remote's work clone and push it to the bare repo."""
    work = tmp_path / "remote-work"
    write_pack_tree(work / remote.subtree, marker=marker)
    if pack_yaml_extra:
        with (work / remote.subtree / "pack.yaml").open("a", encoding="utf-8") as handle:
            handle.write(pack_yaml_extra)
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", marker)
    git(work, "push", "-q", str(remote.bare), "HEAD:refs/heads/main")
    return git(work, "rev-parse", "HEAD")


class Harness:
    """A core ``packs/`` directory (live trees + pin lockfiles) wired through the command's seam."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.tmp_path = tmp_path
        self.remote = make_pack_remote(tmp_path)
        self.packs = tmp_path / "core" / "packs"
        self.live = self.packs / "built-in"
        self.live.mkdir(parents=True)
        write_pack_tree(self.live, marker="live")
        monkeypatch.setattr(pack_vendor_module, "built_in_root", lambda: self.live)

    def write_pin(self, name: str = "built-in", **overrides: object) -> Path:
        fields: dict[str, object] = {
            "repository": self.remote.url,
            "commit": _OLD_SHA,
            "tree_digest": TreeDigest(algorithm="clean-tree-sha256", value=_OLD_DIGEST, level=BUILT_IN),
            "subtree": self.remote.subtree,
        }
        fields.update(overrides)
        path = self.packs / f"{name}.source.yaml"
        write_pack_pin(PackPin(**fields), path)
        return path

    def vendor(self, *args: str) -> tuple[int, str]:
        result = runner.invoke(cli_app, ["charter", "pack", "vendor", *args])
        if result.exception and not isinstance(result.exception, SystemExit):
            raise result.exception
        return result.exit_code, re.sub(r"\s+", " ", result.output)

    def live_snapshot(self) -> dict[str, bytes]:
        return {str(p.relative_to(self.live)): p.read_bytes() for p in sorted(self.live.rglob("*")) if p.is_file()}


@pytest.fixture
def h(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Harness:
    return Harness(tmp_path, monkeypatch)


# -- the headline: a bump rewrites the pin and copies no tree ---------------------------------


def test_ref_bump_rewrites_pin_and_copies_no_tree(h: Harness) -> None:
    pin_path = h.write_pin()
    before = h.live_snapshot()
    packs_entries = sorted(p.name for p in h.packs.iterdir())

    code, out = h.vendor("--ref", h.remote.sha)

    assert code == 0, out
    pin = load_pack_pin(pin_path)
    assert pin.commit == h.remote.sha
    assert pin.subtree == "built-in"
    assert pin.tree_digest.value == h.remote.digest
    assert h.live_snapshot() == before, "packs/built-in/ must not be touched"
    assert sorted(p.name for p in h.packs.iterdir()) == packs_entries, "no scratch/staging dirs left in packs/"


def test_written_digest_matches_a_fresh_recompute_of_the_fetched_tree(h: Harness, tmp_path: Path) -> None:
    pin_path = h.write_pin()
    new_sha = _publish(h.remote, tmp_path, marker="v2")

    code, out = h.vendor("--ref", new_sha)

    assert code == 0, out
    pin = load_pack_pin(pin_path)
    assert pin.commit == new_sha != h.remote.sha
    clone = tmp_path / "recompute"
    git(tmp_path, "clone", "-q", h.remote.url, str(clone))
    assert pin.tree_digest.value == clean_tree_digest(clone / "built-in", level=BUILT_IN)
    assert pin.tree_digest.value != h.remote.digest
    assert pin.snapshot_sha256 == full_tree_digest(clone / "built-in")


def test_branch_ref_is_resolved_to_a_sha(h: Harness, tmp_path: Path) -> None:
    pin_path = h.write_pin()
    new_sha = _publish(h.remote, tmp_path, marker="v3")

    code, out = h.vendor("--ref", "main")

    assert code == 0, out
    assert load_pack_pin(pin_path).commit == new_sha
    assert "main" not in pin_path.read_text(encoding="utf-8").replace("remote", "")


# -- --pack / --subtree ------------------------------------------------------------------------


def test_pack_internal_writes_org_level_pin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    h = Harness(tmp_path, monkeypatch)
    (tmp_path / "nested").mkdir()
    nested = make_pack_remote(tmp_path / "nested", subtree="packs/internal")
    org_digest = clean_tree_digest(tmp_path / "nested" / "remote-work" / "packs" / "internal", level=ORG)
    pin_path = h.write_pin(
        "internal",
        repository=nested.url,
        subtree="packs/internal",
        tree_digest=TreeDigest(algorithm="clean-tree-sha256", value=_OLD_DIGEST, level=ORG),
    )

    code, out = h.vendor("--pack", "internal", "--ref", nested.sha)

    assert code == 0, out
    pin = load_pack_pin(pin_path)
    assert pin.tree_digest.level == "org"
    assert pin.tree_digest.value == org_digest
    assert pin.commit == nested.sha
    assert "level: org" in pin_path.read_text(encoding="utf-8")


def test_subtree_option_overrides_the_pins_subtree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    h = Harness(tmp_path, monkeypatch)
    (tmp_path / "other").mkdir()
    moved = make_pack_remote(tmp_path / "other", subtree="packs/built-in")
    pin_path = h.write_pin(repository=moved.url, subtree="built-in")

    code, out = h.vendor("--ref", moved.sha, "--subtree", "packs/built-in")

    assert code == 0, out
    pin = load_pack_pin(pin_path)
    assert pin.subtree == "packs/built-in"
    assert pin.tree_digest.value == moved.digest


def test_bump_without_ref_or_subtree_is_refused(h: Harness) -> None:
    pin_path = h.write_pin()
    before = pin_path.read_text(encoding="utf-8")

    code, out = h.vendor()

    assert code == 2, out
    assert "sync-packs" in out
    assert pin_path.read_text(encoding="utf-8") == before


# -- requires_core (#6364) ---------------------------------------------------------------------


def test_fetched_pack_requires_core_excluding_current_core_is_refused(h: Harness, tmp_path: Path) -> None:
    pin_path = h.write_pin()
    before = pin_path.read_text(encoding="utf-8")
    bad_sha = _publish(h.remote, tmp_path, marker="v9", pack_yaml_extra="requires_core: '>=99'\n")

    code, out = h.vendor("--ref", bad_sha)

    assert code == 1, out
    assert "requires_core" in out
    assert pin_path.read_text(encoding="utf-8") == before, "a refused bump leaves the pin untouched"


def test_pins_carried_requires_core_excluding_current_core_is_refused(h: Harness) -> None:
    pin_path = h.write_pin(requires_core=">=99")
    before = pin_path.read_text(encoding="utf-8")

    code, out = h.vendor("--ref", h.remote.sha)

    assert code == 1, out
    assert "requires_core" in out
    assert pin_path.read_text(encoding="utf-8") == before


def test_compatible_pin_requires_core_is_carried_forward(h: Harness) -> None:
    pin_path = h.write_pin(requires_core=">=0.1")

    code, out = h.vendor("--ref", h.remote.sha)

    assert code == 0, out
    assert load_pack_pin(pin_path).requires_core == ">=0.1"


# -- fail-closed -------------------------------------------------------------------------------


def test_unreachable_repository_fails_closed(h: Harness) -> None:
    pin_path = h.write_pin(repository=(h.tmp_path / "missing.git").as_uri())
    before = pin_path.read_text(encoding="utf-8")

    code, out = h.vendor("--ref", h.remote.sha)

    assert code == 1, out
    assert pin_path.read_text(encoding="utf-8") == before


def test_unknown_commit_fails_closed(h: Harness) -> None:
    pin_path = h.write_pin()
    before = pin_path.read_text(encoding="utf-8")

    code, out = h.vendor("--ref", "f" * 40)

    assert code == 1, out
    assert pin_path.read_text(encoding="utf-8") == before


def test_symlink_in_fetched_tree_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    h = Harness(tmp_path, monkeypatch)
    (tmp_path / "linky").mkdir()
    linked = make_pack_remote(tmp_path / "linky", symlink="evil")
    pin_path = h.write_pin(repository=linked.url)
    before = pin_path.read_text(encoding="utf-8")

    code, out = h.vendor("--ref", linked.sha)

    assert code == 1, out
    assert pin_path.read_text(encoding="utf-8") == before


def test_missing_pin_fails_closed(h: Harness) -> None:
    code, out = h.vendor("--ref", h.remote.sha)

    assert code == 1, out
    assert "pin" in out


def test_unknown_pack_name_is_refused(h: Harness) -> None:
    code, out = h.vendor("--pack", "../etc", "--ref", h.remote.sha)

    assert code == 2, out


# -- --check (offline) -------------------------------------------------------------------------


def test_check_in_sync_exits_zero_offline(h: Harness) -> None:
    digest = clean_tree_digest(h.live, level=BUILT_IN)
    h.write_pin(
        repository=(h.tmp_path / "unreachable.git").as_uri(),
        tree_digest=TreeDigest(algorithm="clean-tree-sha256", value=digest, level=BUILT_IN),
        snapshot_sha256=full_tree_digest(h.live),
    )

    code, out = h.vendor("--check")

    assert code == 0, out


def test_check_pin_without_snapshot_sha256_fails_with_pin_invalid(h: Harness) -> None:
    digest = clean_tree_digest(h.live, level=BUILT_IN)
    h.write_pin(tree_digest=TreeDigest(algorithm="clean-tree-sha256", value=digest, level=BUILT_IN))

    code, out = h.vendor("--check")

    assert code == 1, out
    assert "PACK_PIN_INVALID" in out


def test_check_drift_fails_with_remedy_and_does_not_mutate(h: Harness) -> None:
    h.write_pin(snapshot_sha256="3" * 64)
    before = h.live_snapshot()

    code, out = h.vendor("--check")

    assert code == 1
    assert "charter pack vendor" in out
    assert "do not hand-edit" in out
    assert "bump the pin" in out
    assert h.live_snapshot() == before


def test_check_missing_tree_fails(h: Harness) -> None:
    h.write_pin(snapshot_sha256="3" * 64)
    for item in sorted(h.live.rglob("*"), reverse=True):
        item.unlink() if item.is_file() else item.rmdir()
    h.live.rmdir()

    code, out = h.vendor("--check")

    assert code == 1, out


def test_check_with_ref_is_refused(h: Harness) -> None:
    h.write_pin()

    code, _ = h.vendor("--check", "--ref", h.remote.sha)

    assert code == 2
