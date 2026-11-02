"""Bump the doc-kitty pin of the docsite (#6930; ADR 2026-10-31-1 D-2 steps 1 and 2).

Step 1 resolves a doc-kitty release tag (or a branch, or a commit) to its 40-character
commit, preferring the commit a tag points at. Step 2 rewrites the toolkit pin in
``site/package.json`` and aligns ``astro``, ``@astrojs/starlight`` and
``@astrojs/markdown-remark`` with the peer ranges the toolkit's ``src/package.json``
declares at that commit, then runs ``pnpm install`` in ``site/`` so the lockfile follows.

Steps 3 and 4 (build, gates, changelog reading, the pull request) stay with the
maintainer. Usage::

    python -m scripts.docs.site_bump v0.6.0
    make docs-site-bump REF=v0.6.0

The network reads (``git ls-remote``, the raw manifest) are injectable, so the
rewrite is tested offline.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Final

__all__ = [
    "PEERS",
    "REPOSITORY",
    "TOOLKIT",
    "BumpError",
    "bump_manifest",
    "fetch_toolkit_manifest",
    "main",
    "pin_spec",
    "resolve_ref",
]

TOOLKIT: Final[str] = "@spec-kitty/doc-toolkit"
REPOSITORY: Final[str] = "spec-kitty/doc-kitty"
#: The toolkit peers the site declares beside it (ADR D-2 step 2).
PEERS: Final[tuple[str, ...]] = ("astro", "@astrojs/starlight", "@astrojs/markdown-remark")

_SITE_DIR: Final[Path] = Path(__file__).resolve().parents[2] / "site"
_SHA: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{40}$")
_RAW_MANIFEST: Final[str] = "https://raw.githubusercontent.com/{repository}/{sha}/src/package.json"


class BumpError(Exception):
    """The bump cannot proceed; nothing has been written."""


def pin_spec(sha: str) -> str:
    """The ``package.json`` dependency spec pinning the toolkit to *sha* (ADR D-2)."""
    return f"github:{REPOSITORY}#{sha}&path:/src"


def _git_ls_remote(ref: str) -> str:
    result = subprocess.run(
        ["git", "ls-remote", f"https://github.com/{REPOSITORY}", f"refs/tags/{ref}", f"refs/tags/{ref}^{{}}", f"refs/heads/{ref}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise BumpError(f"git ls-remote failed: {result.stderr.strip()}")
    return result.stdout


def resolve_ref(ref: str, ls_remote: Callable[[str], str] | None = None) -> str:
    """Resolve *ref* to a 40-character commit: a commit as given, else a peeled tag, a tag, a branch."""
    candidate = ref.strip().lower()
    if _SHA.match(candidate):
        return candidate
    found: dict[str, str] = {}
    for line in (ls_remote or _git_ls_remote)(ref).splitlines():
        sha, _, name = line.strip().partition("\t")
        if _SHA.match(sha):
            found[name] = sha
    for name in (f"refs/tags/{ref}^{{}}", f"refs/tags/{ref}", f"refs/heads/{ref}"):
        if name in found:
            return found[name]
    raise BumpError(f"{ref!r} names no tag, branch or commit of {REPOSITORY}")


def _http_get(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - fixed https URL built from a validated SHA
        body: bytes = response.read()
    return body.decode("utf-8")


def fetch_toolkit_manifest(sha: str, fetch: Callable[[str], str] | None = None) -> dict[str, Any]:
    """The toolkit's ``src/package.json`` at commit *sha*."""
    if not _SHA.match(sha):
        raise BumpError(f"{sha!r} is not a 40-character commit")
    try:
        manifest = json.loads((fetch or _http_get)(_RAW_MANIFEST.format(repository=REPOSITORY, sha=sha)))
    except (OSError, ValueError) as error:
        raise BumpError(f"cannot read {REPOSITORY} src/package.json at {sha}: {error}") from error
    if not isinstance(manifest, dict):
        raise BumpError(f"{REPOSITORY} src/package.json at {sha} is not a JSON object")
    return manifest


def bump_manifest(site_manifest: Mapping[str, Any], sha: str, toolkit_manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Return *site_manifest* with the toolkit pinned to *sha* and the peers set to the toolkit's ranges."""
    peers = toolkit_manifest.get("peerDependencies")
    if not isinstance(peers, Mapping):
        raise BumpError("the toolkit manifest declares no peerDependencies")
    missing = [peer for peer in PEERS if not isinstance(peers.get(peer), str)]
    if missing:
        raise BumpError(f"the toolkit manifest declares no peer range for {', '.join(missing)}")
    dependencies = site_manifest.get("dependencies")
    if not isinstance(dependencies, Mapping) or TOOLKIT not in dependencies:
        raise BumpError(f"site/package.json does not depend on {TOOLKIT}")
    updated = dict(dependencies)
    updated[TOOLKIT] = pin_spec(sha)
    for peer in PEERS:
        updated[peer] = peers[peer]
    result = dict(site_manifest)
    result["dependencies"] = updated
    return result


def _install(site_dir: Path) -> None:
    subprocess.run(["pnpm", "install"], cwd=site_dir, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bump the doc-kitty pin of site/ (ADR 2026-10-31-1 D-2 steps 1-2).")
    parser.add_argument("ref", help="a doc-kitty release tag (preferred), branch or 40-character commit")
    parser.add_argument("--site-dir", type=Path, default=_SITE_DIR, help="the site project (default: site/)")
    parser.add_argument("--no-install", action="store_true", help="rewrite package.json only; skip pnpm install")
    args = parser.parse_args(argv)
    manifest_path = args.site_dir / "package.json"
    try:
        sha = resolve_ref(args.ref)
        bumped = bump_manifest(json.loads(manifest_path.read_text(encoding="utf-8")), sha, fetch_toolkit_manifest(sha))
    except BumpError as error:
        print(f"docs-site-bump: {error}; site/package.json is unchanged.", file=sys.stderr)
        return 1
    manifest_path.write_text(json.dumps(bumped, indent=2) + "\n", encoding="utf-8")
    print(f"docs-site-bump: pinned {TOOLKIT} to {sha}.")
    if not args.no_install:
        _install(args.site_dir)
    print("Next (ADR D-2 steps 3-4): make docs-site, read doc-kitty's CHANGELOG.md between the two pins, open the pull request.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
