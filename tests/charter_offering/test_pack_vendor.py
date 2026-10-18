"""``spec-kitty charter pack vendor [--check]`` acceptance tests (#3504, WP02).

Every test drives the REAL CLI (``charter pack vendor``) against a hermetic fixture: a local
git repository stands in for spec-kitty-open-packs (so ``GitSource`` really clones, checks out
a tag and resolves a SHA, with no network) and a tmp ``packs/`` directory, selected through the
``built_in_root`` seam of the command module, stands in for core's vendored tree + pin lockfile.

``test_stale_tree_is_rewritten`` is the positive control: it proves ``vendor`` mutates on this
very harness, which is what makes the "tree unchanged" fail-closed assertions non-vacuous.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from charter.offering.packs.built_in_pin import BuiltInPin, TreeDigest, load_built_in_pin, write_built_in_pin
from charter.offering.packs.pack_clean_digest import clean_tree_digest
from kernel.pack_tiers import BUILT_IN
from specify_cli import app as cli_app
from specify_cli.cli.commands.charter import pack_vendor as pack_vendor_module

pytestmark = pytest.mark.fast

runner = CliRunner()

_PACK_YAML = "pack_id: 01ARWG13C000000000000000FG\npack_version: 1.0.0\nparent_pack: null\nname: built-in\npack_level: built-in\n"


def _write_tree(root: Path, marker: str, pack_yaml: str = _PACK_YAML) -> None:
    (root / "directives").mkdir(parents=True, exist_ok=True)
    (root / "pack.yaml").write_text(pack_yaml, encoding="utf-8")
    (root / "directives" / "001-a.directive.yaml").write_text(f"id: a\nmarker: {marker}\n", encoding="utf-8")
    (root / "directive.graph.yaml").write_text(f"nodes: []\n# {marker}\n", encoding="utf-8")


def _git(repo: Path, *args: str) -> str:
    cmd = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args]
    return subprocess.run(cmd, cwd=repo, check=True, capture_output=True, text=True).stdout.strip()  # noqa: S603, S607 - fixed argv in a test fixture


def _commit_upstream(repo: Path, marker: str, pack_yaml: str = _PACK_YAML) -> str:
    """Commit a new built-in subtree (plus unrelated top-level content) to the fake open-packs repo."""
    _write_tree(repo / "built-in", marker, pack_yaml)
    (repo / "README.md").write_text(f"readme {marker}\n", encoding="utf-8")
    (repo / "packs" / "other").mkdir(parents=True, exist_ok=True)
    (repo / "packs" / "other" / "x.yaml").write_text(f"other: {marker}\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", marker)
    return _git(repo, "rev-parse", "HEAD")


def _digest(root: Path) -> str:
    value: str = clean_tree_digest(root, level=BUILT_IN)
    return value


def _tree_files(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


class Harness:
    """A fake open-packs repo plus a core ``packs/`` directory wired through the env seam."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.upstream = tmp_path / "open-packs"
        self.upstream.mkdir()
        _git(self.upstream, "init", "-q")
        self.packs = tmp_path / "core" / "packs"
        self.live = self.packs / "built-in"
        self.live.mkdir(parents=True)
        # The app bootstrap itself needs the real packs root, so redirect only this command's seam.
        monkeypatch.setattr(pack_vendor_module, "built_in_root", lambda: self.live)

    def upstream_commit(self, marker: str, pack_yaml: str = _PACK_YAML) -> tuple[str, str]:
        """Commit upstream; return ``(sha, digest of that commit's built-in subtree)``."""
        sha = _commit_upstream(self.upstream, marker, pack_yaml)
        return sha, _digest(self.upstream / "built-in")

    def pin(self, *, repository: str | None = None, commit: str, digest: str) -> None:
        write_built_in_pin(
            BuiltInPin(
                repository=repository or str(self.upstream),
                commit=commit,
                tree_digest=TreeDigest(algorithm="clean-tree-sha256", value=digest),
                requires_core=None,
            ),
            self.packs / "built-in.source.yaml",
        )

    def vendor(self, *args: str) -> tuple[int, str]:
        result = runner.invoke(cli_app, ["charter", "pack", "vendor", *args])
        if result.exception and not isinstance(result.exception, SystemExit):
            raise result.exception
        return result.exit_code, re.sub(r"\s+", " ", result.output)


@pytest.fixture
def h(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Harness:
    return Harness(tmp_path, monkeypatch)


# -- T005: --check through the real CLI ------------------------------------------------------


def test_check_in_sync_exits_zero(h: Harness) -> None:
    sha, digest = h.upstream_commit("v1")
    _write_tree(h.live, "v1")
    h.pin(commit=sha, digest=digest)
    before = _digest(h.live)

    code, out = h.vendor("--check")

    assert code == 0, out
    assert _digest(h.live) == before


def test_check_one_byte_edit_fails_with_vendor_remedy(h: Harness) -> None:
    sha, digest = h.upstream_commit("v1")
    _write_tree(h.live, "v1")
    h.pin(commit=sha, digest=digest)
    edited = h.live / "directives" / "001-a.directive.yaml"
    edited.write_text(edited.read_text(encoding="utf-8") + "x", encoding="utf-8")
    drifted = _digest(h.live)

    code, out = h.vendor("--check")

    assert code != 0
    assert "charter pack vendor" in out
    assert "do not hand-edit" in out
    assert "bump the pin" in out
    assert _digest(h.live) == drifted, "--check must not mutate"


def test_check_is_offline(h: Harness) -> None:
    """An unreachable repository is irrelevant to --check (no fetch)."""
    sha, digest = h.upstream_commit("v1")
    _write_tree(h.live, "v1")
    h.pin(repository=str(h.upstream / "does-not-exist"), commit=sha, digest=digest)

    code, out = h.vendor("--check")

    assert code == 0, out


def test_check_with_ref_is_refused(h: Harness) -> None:
    sha, digest = h.upstream_commit("v1")
    _write_tree(h.live, "v1")
    h.pin(commit=sha, digest=digest)

    code, _ = h.vendor("--check", "--ref", "v1")

    assert code == 2


# -- T006/T008: vendor mutating path (positive control) --------------------------------------


def test_stale_tree_is_rewritten(h: Harness) -> None:
    """Positive control: a stale live tree IS rewritten to the pinned content, subtree only."""
    sha, digest = h.upstream_commit("v1")
    _write_tree(h.live, "stale")
    (h.live / "stray.txt").write_text("hand edit\n", encoding="utf-8")
    h.pin(commit=sha, digest=digest)
    assert _digest(h.live) != digest

    code, out = h.vendor()

    assert code == 0, out
    assert _digest(h.live) == digest
    assert _tree_files(h.live) == _tree_files(h.upstream / "built-in")  # subtree only, stray removed
    assert not (h.live / "README.md").exists()
    assert not (h.live / "packs").exists()
    assert not [p for p in h.packs.iterdir() if p.name.startswith(".built-in.")], "no scratch dirs left behind"


def test_in_sync_vendor_is_a_noop_on_content(h: Harness) -> None:
    sha, digest = h.upstream_commit("v1")
    _write_tree(h.live, "v1")
    h.pin(commit=sha, digest=digest)

    code, out = h.vendor()

    assert code == 0, out
    assert _digest(h.live) == digest


def test_tag_ref_is_resolved_to_sha_and_only_sha_persisted(h: Harness) -> None:
    sha1, digest1 = h.upstream_commit("v1")
    sha2, digest2 = h.upstream_commit("v2")
    _git(h.upstream, "tag", "-a", "-m", "release", "v0.2.0", sha2)
    _write_tree(h.live, "v1")
    h.pin(commit=sha1, digest=digest1)

    code, out = h.vendor("--ref", "v0.2.0")

    assert code == 0, out
    lock = h.packs / "built-in.source.yaml"
    pin = load_built_in_pin(lock)
    assert pin.commit == sha2  # the commit SHA, not the annotated tag object, not the tag name
    assert re.fullmatch(r"[0-9a-f]{40}", pin.commit)
    assert "v0.2.0" not in lock.read_text(encoding="utf-8")
    assert pin.tree_digest.value == digest2
    assert _digest(h.live) == digest2


# -- T008: fail-closed controls (tree byte-identical) ----------------------------------------


def _assert_refused_unchanged(h: Harness, code: int, out: str, snapshot: tuple[str, set[str], str]) -> None:
    assert code != 0, out
    assert (_digest(h.live), _tree_files(h.live), (h.packs / "built-in.source.yaml").read_text(encoding="utf-8")) == snapshot
    assert not [p for p in h.packs.iterdir() if p.name.startswith(".built-in.")]


def _snapshot(h: Harness) -> tuple[str, set[str], str]:
    return _digest(h.live), _tree_files(h.live), (h.packs / "built-in.source.yaml").read_text(encoding="utf-8")


def test_unreachable_ref_fails_closed(h: Harness) -> None:
    sha, digest = h.upstream_commit("v1")
    _write_tree(h.live, "stale")
    h.pin(repository=str(h.upstream / "does-not-exist"), commit=sha, digest=digest)
    snap = _snapshot(h)

    code, out = h.vendor()

    _assert_refused_unchanged(h, code, out, snap)
    assert "cannot fetch" in out


def test_unknown_ref_fails_closed(h: Harness) -> None:
    sha, digest = h.upstream_commit("v1")
    _write_tree(h.live, "stale")
    h.pin(commit=sha, digest=digest)
    snap = _snapshot(h)

    code, out = h.vendor("--ref", "no-such-tag")

    _assert_refused_unchanged(h, code, out, snap)


def test_digest_mismatch_fails_closed(h: Harness) -> None:
    sha, _ = h.upstream_commit("v1")
    _write_tree(h.live, "stale")
    h.pin(commit=sha, digest="0" * 64)
    snap = _snapshot(h)

    code, out = h.vendor()

    _assert_refused_unchanged(h, code, out, snap)
    assert "digest mismatch" in out


def test_incompatible_requires_core_fails_closed(h: Harness) -> None:
    incompatible = _PACK_YAML + "requires_core: '>=99'\n"
    sha, digest = h.upstream_commit("v1", incompatible)
    _write_tree(h.live, "stale")
    h.pin(commit=sha, digest=digest)
    snap = _snapshot(h)

    code, out = h.vendor()

    _assert_refused_unchanged(h, code, out, snap)
    assert "requires_core" in out


def test_incompatible_requires_core_on_bump_does_not_rewrite_pin(h: Harness) -> None:
    sha1, digest1 = h.upstream_commit("v1")
    sha2, _ = h.upstream_commit("v2", _PACK_YAML + "requires_core: '>=99'\n")
    _write_tree(h.live, "v1")
    h.pin(commit=sha1, digest=digest1)
    snap = _snapshot(h)

    code, out = h.vendor("--ref", sha2)

    _assert_refused_unchanged(h, code, out, snap)


def test_missing_lockfile_fails_closed(h: Harness) -> None:
    _write_tree(h.live, "v1")
    before = _digest(h.live)

    code, out = h.vendor()

    assert code != 0, out
    assert _digest(h.live) == before
    assert "pin lockfile" in out
