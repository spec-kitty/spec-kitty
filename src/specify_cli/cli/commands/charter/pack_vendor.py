"""``spec-kitty charter pack vendor [--check]`` -- re-vendor / verify ``packs/built-in/`` (#3504).

* ``vendor --check`` is verify-only and OFFLINE: it recomputes the clean-tree digest of the
  committed ``packs/built-in/`` and compares it with the committed pin lockfile
  (``packs/built-in.source.yaml``). It never fetches and never mutates.
* ``vendor`` (default) resolves the pinned open-packs ref, copies its ``built-in`` subtree ONLY
  into a staging directory beside ``packs/built-in/``, verifies digest + ``requires_core``, and
  only then swaps the staged tree in. Every failure mode leaves the live tree untouched.

A tag supplied through ``--ref`` is a resolution input only: the resolved 40-hex SHA is what the
lockfile records (FR-002).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Annotated
from uuid import uuid4

import typer
from ruamel.yaml.error import YAMLError

from charter.pack_paths import built_in_root
from kernel.git.runner import GitCommandError, run_git
from kernel.pack_tiers import BUILT_IN
from kernel.tree_removal import remove_tool_owned_tree
from specify_cli.cli.console import console
from specify_cli.version_utils import get_version

if TYPE_CHECKING:
    from charter.packs import BuiltInPin

__all__ = ["pack_vendor"]

#: Pin lockfile name, a sibling of ``packs/built-in/`` (never digested).
PIN_FILENAME = "built-in.source.yaml"
#: Subtree of the open-packs repository that holds the built-in pack (C-006).
OPEN_PACKS_SUBTREE = "built-in"
_DIGEST_ALGORITHM = "clean-tree-sha256"
_FETCH_TIMEOUT = 120.0

_DRIFT_REMEDY = (
    "packs/built-in/ is vendored from spec-kitty-open-packs and must not be hand-edited. "
    "Run `spec-kitty charter pack vendor` to restore the pinned tree, or bump the pin "
    "(`spec-kitty charter pack vendor --ref <tag-or-sha>`); do not hand-edit packs/built-in/."
)


class VendorError(Exception):
    """A vendor/verify step refused; the live ``packs/built-in/`` is unchanged."""


def _pin_path(live: Path) -> Path:
    return live.parent / PIN_FILENAME


def _load_pin(live: Path) -> BuiltInPin:
    from charter.packs import BuiltInPinError, load_built_in_pin

    try:
        return load_built_in_pin(_pin_path(live))
    except BuiltInPinError as exc:
        raise VendorError(f"cannot load the pin lockfile: {exc}") from exc


def check_built_in_pin(live: Path) -> BuiltInPin:
    """Offline drift check: raise :class:`VendorError` unless *live* matches the committed pin."""
    from charter.packs import verify_built_in_pin

    pin = _load_pin(live)
    if not verify_built_in_pin(pin, live):
        raise VendorError(f"packs/built-in/ drifted from the pin (commit {pin.commit}). {_DRIFT_REMEDY}")
    return pin


def _resolve_sha(clone: Path) -> str:
    """The commit SHA the clone's checkout sits on (tag inputs are peeled to a commit)."""
    try:
        result = run_git(clone, "rev-parse", "HEAD^{commit}", timeout=_FETCH_TIMEOUT)
    except GitCommandError as exc:
        raise VendorError(f"cannot resolve the fetched ref to a commit SHA: {exc}") from exc
    return result.stdout.decode("utf-8", "replace").strip()


def _fetch_subtree(repository: str, ref: str, scratch: Path) -> tuple[str, Path]:
    """Clone *repository* at *ref* into *scratch*; return ``(resolved sha, built-in subtree)``."""
    from specify_cli.charter_packs.sources.git_source import GitSource

    clone = scratch / "clone"
    result = GitSource(url=repository, ref=ref).fetch(clone)
    if not result.ok:
        raise VendorError("cannot fetch the pinned ref: " + "; ".join(result.errors or ["unknown error"]))
    subtree = clone / OPEN_PACKS_SUBTREE
    if not subtree.is_dir():
        raise VendorError(f"the fetched ref has no {OPEN_PACKS_SUBTREE!r} subtree")
    return _resolve_sha(clone), subtree


def _copy_tree(source: Path, destination: Path) -> None:
    """Copy *source* (regular files only) into the new directory *destination*."""
    destination.mkdir(parents=True)
    for item in sorted(source.rglob("*")):
        rel = item.relative_to(source)
        if item.is_dir():
            (destination / rel).mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            target = destination / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(item.read_bytes())


def _assert_core_compatible(staged: Path) -> None:
    from charter.packs import check_requires_core, load_pack_descriptor

    try:
        descriptor = load_pack_descriptor(staged / "pack.yaml")
    except (ValueError, OSError, YAMLError) as exc:
        raise VendorError(f"the vendored pack.yaml is unreadable: {exc}") from exc
    core_version = get_version()
    if not check_requires_core(descriptor, core_version):
        raise VendorError(f"incompatible requires_core: the vendored pack requires {descriptor.requires_core!r} but core is {core_version}")


def _swap_in(staged: Path, live: Path) -> None:
    """Replace *live* with *staged* (same filesystem), restoring *live* if the swap fails."""
    old = live.parent / f".built-in.old-{uuid4().hex}"
    live.replace(old)
    try:
        staged.replace(live)
    except OSError as exc:
        old.replace(live)
        raise VendorError(f"cannot install the vendored tree: {exc}") from exc
    remove_tool_owned_tree(old, tool_root=live.parent, reason="superseded built-in tree", best_effort=True)


def _verified_pin(pin: BuiltInPin, staged: Path, sha: str, bump: bool) -> BuiltInPin:
    """The pin to persist: the existing one (verified) or, for a bump, a fresh SHA + digest."""
    from charter.packs import BuiltInPin, TreeDigest, clean_tree_digest, verify_built_in_pin

    if bump:
        value: str = clean_tree_digest(staged, level=BUILT_IN)
        return BuiltInPin(
            repository=pin.repository,
            commit=sha,
            tree_digest=TreeDigest(algorithm=_DIGEST_ALGORITHM, value=value),
            # requires_core is carried forward from the existing pin, NOT read from the
            # vendored pack.yaml: the built-in pack.yaml declares no requires_core (the
            # range is provenance recorded in open-packs' built-in.source.yaml). Sourcing
            # it from descriptor.requires_core would drop the range to None. Refreshing it
            # from the open-packs pin file at the bumped ref is a follow-up (#3504).
            requires_core=pin.requires_core,
            snapshot_sha256=None,
        )
    if sha != pin.commit:
        raise VendorError(f"fetched commit {sha} does not match the pinned commit {pin.commit}")
    if not verify_built_in_pin(pin, staged):
        raise VendorError("digest mismatch: the fetched built-in subtree does not match the pinned tree_digest; packs/built-in/ left unchanged")
    return pin


def vendor_built_in(live: Path, *, ref: str | None = None) -> BuiltInPin:
    """Re-vendor *live* from the pinned (or ``ref``-bumped) open-packs commit, fail-closed.

    Returns the pin now in force. Raises :class:`VendorError` with *live* byte-identical on
    any failure (unreachable ref, digest mismatch, incompatible ``requires_core``).
    """
    from charter.packs import write_built_in_pin

    pin = _load_pin(live)
    bump = ref is not None
    staged = live.parent / f".built-in.staging-{uuid4().hex}"
    try:
        with tempfile.TemporaryDirectory(prefix="vendor-built-in-") as scratch:
            sha, subtree = _fetch_subtree(pin.repository, ref or pin.commit, Path(scratch))
            _copy_tree(subtree, staged)
        new_pin = _verified_pin(pin, staged, sha, bump)
        _assert_core_compatible(staged)
        _swap_in(staged, live)
    finally:
        remove_tool_owned_tree(staged, tool_root=live.parent, reason="vendor staging tree", best_effort=True)
    if bump:
        write_built_in_pin(new_pin, _pin_path(live))
    return new_pin


def pack_vendor(
    check: Annotated[
        bool,
        typer.Option("--check", help="Verify only (offline): compare packs/built-in/ with the pin lockfile; exit 1 on drift. Mutates nothing."),
    ] = False,
    ref: Annotated[
        str | None,
        typer.Option("--ref", help="Bump the pin to this open-packs tag or SHA (resolved to a SHA; a tag is never persisted)."),
    ] = None,
) -> None:
    """Re-vendor ``packs/built-in/`` from the pinned spec-kitty-open-packs commit, or verify it."""
    if check and ref is not None:
        console.print("[red]--check is verify-only and cannot be combined with --ref.[/red]")
        raise typer.Exit(2)
    live = built_in_root()
    try:
        if check:
            pin = check_built_in_pin(live)
            console.print(f"[green]packs/built-in/ matches the pin ({pin.commit}).[/green]")
            return
        pin = vendor_built_in(live, ref=ref)
    except VendorError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"[green]Vendored packs/built-in/ from {pin.commit}.[/green]")
