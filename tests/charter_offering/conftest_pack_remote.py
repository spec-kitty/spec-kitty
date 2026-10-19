"""A real ``file://`` bare git remote holding a pack subtree, for ``pack_fetch`` tests (WP02 / T006)."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from charter.offering.packs.pack_clean_digest import clean_tree_digest
from charter.offering.packs.pack_pin import PackPin, TreeDigest, full_tree_digest
from kernel.pack_tiers import BUILT_IN

__all__ = ["PackRemote", "git", "make_pack_remote", "write_pack_tree"]

PACK_ID = "01ARWG13C000000000000000FG"


@dataclass(frozen=True)
class PackRemote:
    """A bare remote plus the pin that describes the pack committed in it."""

    bare: Path
    url: str
    sha: str
    digest: str
    subtree: str
    snapshot: str

    def pin(self, *, digest: str | None = None, sha: str | None = None, url: str | None = None, snapshot: str | None = None) -> PackPin:
        return PackPin(
            repository=url or self.url,
            commit=sha or self.sha,
            tree_digest=TreeDigest(algorithm="clean-tree-sha256", value=digest or self.digest, level=BUILT_IN),
            subtree=self.subtree,
            snapshot_sha256=snapshot or self.snapshot,
        )


def _env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@example.invalid",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@example.invalid",
    )
    return env


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, env=_env(), check=True, capture_output=True, text=True).stdout.strip()


def write_pack_tree(root: Path, *, marker: str = "hello") -> None:
    """Write a minimal valid built-in pack under *root*."""
    (root / "directives").mkdir(parents=True, exist_ok=True)
    (root / "pack.yaml").write_text(f"pack_id: {PACK_ID}\nname: sample\npack_level: built-in\npack_version: 1.0.0\n", encoding="utf-8")
    (root / "directive.graph.yaml").write_text("schema_version: '1.0'\nnodes: []\n", encoding="utf-8")
    (root / "directives" / "001-x.directive.yaml").write_text(f"id: X\nbody: {marker}\n", encoding="utf-8")


def make_pack_remote(tmp_path: Path, *, subtree: str = "built-in", allow_filter: bool = True, symlink: str | None = None) -> PackRemote:
    """Commit a pack at ``<subtree>`` (plus an unrelated ``other/`` tree) and publish it as a bare repo.

    *symlink*, when given, adds a symlink of that name inside the subtree.
    """
    work = tmp_path / "remote-work"
    work.mkdir()
    git(work, "init", "-q", "-b", "main")
    write_pack_tree(work / subtree)
    (work / "other").mkdir()
    (work / "other" / "noise.txt").write_text("noise\n", encoding="utf-8")
    digest = clean_tree_digest(work / subtree, level=BUILT_IN)
    snapshot = full_tree_digest(work / subtree)
    if symlink is not None:
        (work / subtree / symlink).symlink_to("directives")
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "pack")
    sha = git(work, "rev-parse", "HEAD")
    bare = tmp_path / "remote.git"
    git(tmp_path, "clone", "-q", "--bare", str(work), str(bare))
    git(bare, "config", "uploadpack.allowFilter", "true" if allow_filter else "false")
    git(bare, "config", "uploadpack.allowAnySHA1InWant", "true")
    return PackRemote(bare=bare, url=bare.as_uri(), sha=sha, digest=digest, subtree=subtree, snapshot=snapshot)
