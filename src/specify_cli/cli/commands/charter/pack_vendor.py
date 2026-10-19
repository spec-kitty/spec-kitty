"""``spec-kitty charter pack vendor`` -- the pin-bump helper for fetched packs (#6451, FR-010/FR-011).

``packs/<pack>/`` is no longer vendored by this command; the tree is fetched from the pinned
open-packs commit by ``scripts/sync_packs.py`` (``charter.offering.packs.pack_fetch``).
This command only moves the pin:

* ``vendor --ref <sha-or-branch> [--pack NAME] [--subtree PATH]`` resolves the ref to a 40-hex SHA,
  fetches that commit's subtree into a scratch directory, recomputes its clean-tree digest at the
  pin's level, enforces ``requires_core`` (#6364), and rewrites ``packs/<pack>.source.yaml``.
  No tree under ``packs/`` is touched. A ref is a resolution input only; the SHA is what is persisted.
* ``vendor --check`` is verify-only and OFFLINE: it compares the placed tree with the pin.

All remote contact belongs to ``kernel.git.remote``; this module spawns no git.
"""

from __future__ import annotations

import re
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Annotated, cast

import typer
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from ruamel.yaml.error import YAMLError

from charter.packs import (
    PackPin,
    PackPinError,
    PackTreeStatus,
    TreeDigest,
    check_pack,
    check_requires_core,
    clean_tree_digest,
    load_pack_descriptor,
    load_pack_pin,
    validate_subtree,
    write_pack_pin,
)
from charter.pack_paths import built_in_root
from kernel.git.remote import RemoteUnreachable, fetch_commit_subtree, remote_heads
from kernel.pack_tiers import PackTier, pin_filename
from specify_cli.cli.console import console
from specify_cli.version_utils import get_version

__all__ = ["pack_vendor"]

_DEFAULT_PACK = "built-in"
_PACK_NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
_SHA_RE = re.compile(r"[0-9a-f]{40}")
_DIGEST_ALGORITHM = "clean-tree-sha256"
_SCRATCH_PREFIX = "pin-bump-"

_DRIFT_REMEDY = (
    "packs/<pack>/ is fetched from spec-kitty-open-packs at the pinned commit and must not be hand-edited. "
    "Run `make sync-packs` to restore the pinned tree, or bump the pin "
    "(`spec-kitty charter pack vendor --ref <sha-or-branch>`); do not hand-edit packs/<pack>/."
)
_NOTHING_TO_BUMP = "nothing to bump: pass --ref (and/or --subtree). To restore the pinned tree run `make sync-packs`."


class VendorError(Exception):
    """A bump/verify step refused; no tree and no pin file was changed."""


def _pin_path(live: Path, pack: str) -> Path:
    return live.parent / pin_filename(pack)


def _load_pin(live: Path, pack: str) -> PackPin:
    try:
        return load_pack_pin(_pin_path(live, pack))
    except PackPinError as exc:
        raise VendorError(f"cannot load the pin lockfile: {exc}") from exc


def check_pack_pin(live: Path, pack: str = _DEFAULT_PACK) -> PackPin:
    """Offline drift check: raise :class:`VendorError` unless the placed tree matches its pin."""
    pin = _load_pin(live, pack)
    dest = live.parent / pack
    if check_pack(pin, dest) is not PackTreeStatus.OK:
        raise VendorError(f"packs/{pack}/ is missing or drifted from the pin (commit {pin.commit}). {_DRIFT_REMEDY}")
    return pin


def _resolve_sha(repository: str, ref: str, scratch: Path) -> str:
    """A 40-hex SHA passes through; anything else is resolved as a branch name on the remote."""
    if _SHA_RE.fullmatch(ref):
        return ref
    try:
        heads = remote_heads(scratch, repository, [ref])
    except RemoteUnreachable as exc:
        raise VendorError(f"cannot fetch the pinned ref: {exc}") from exc
    if ref not in heads:
        raise VendorError(f"cannot resolve {ref!r} to a commit: pass a 40-hex SHA or a branch name of {repository}")
    return heads[ref]


def _fetch_subtree(repository: str, sha: str, subtree: str, scratch: Path) -> Path:
    try:
        fetched = fetch_commit_subtree(repository, sha, subtree, scratch / "fetched")
    except RemoteUnreachable as exc:
        raise VendorError(f"cannot fetch the pinned ref: {exc}") from exc
    if not fetched.is_dir():
        raise VendorError(f"commit {sha} has no {subtree!r} subtree in {repository}")
    return fetched


def _assert_core_compatible(pin_requires_core: str | None, fetched: Path) -> None:
    """Refuse when the carried pin range or the fetched pack's own ``requires_core`` excludes this core (#6364)."""
    core_version = get_version()
    if pin_requires_core is not None:
        try:
            carried_ok = core_version in SpecifierSet(pin_requires_core)
        except InvalidSpecifier as exc:
            raise VendorError(f"the pin's requires_core {pin_requires_core!r} is not a valid specifier: {exc}") from exc
        if not carried_ok:
            raise VendorError(f"incompatible requires_core: the pin requires {pin_requires_core!r} but core is {core_version}")
    try:
        descriptor = load_pack_descriptor(fetched / "pack.yaml")
    except (ValueError, OSError, YAMLError) as exc:
        raise VendorError(f"the fetched pack.yaml is unreadable: {exc}") from exc
    if not check_requires_core(descriptor, core_version):
        raise VendorError(f"incompatible requires_core: the fetched pack requires {descriptor.requires_core!r} but core is {core_version}")


def bump_pin(live: Path, pack: str = _DEFAULT_PACK, *, ref: str | None = None, subtree: str | None = None) -> PackPin:
    """Rewrite ``packs/<pack>.source.yaml`` for *ref* / *subtree*; fail-closed, no tree is copied.

    Returns the pin now in force. Raises :class:`VendorError` with the pin file untouched on any failure.
    """
    if ref is None and subtree is None:
        raise VendorError(_NOTHING_TO_BUMP)
    pin = _load_pin(live, pack)
    try:
        new_subtree = validate_subtree(subtree) if subtree is not None else pin.subtree
    except PackPinError as exc:
        raise VendorError(str(exc)) from exc
    if new_subtree is None:  # load_pack_pin requires a subtree; kept as a typed guard
        raise VendorError("the pin has no subtree; pass --subtree")
    level = pin.tree_digest.level
    with tempfile.TemporaryDirectory(prefix=_SCRATCH_PREFIX) as scratch_name:
        scratch = Path(scratch_name)
        sha = _resolve_sha(pin.repository, ref or pin.commit, scratch)
        fetched = _fetch_subtree(pin.repository, sha, new_subtree, scratch)
        _assert_core_compatible(pin.requires_core, fetched)
        digest: str = clean_tree_digest(fetched, level=cast(PackTier, level))
        new_pin = replace(pin, commit=sha, subtree=new_subtree, tree_digest=TreeDigest(algorithm=_DIGEST_ALGORITHM, value=digest, level=level))
        if check_pack(new_pin, fetched) is not PackTreeStatus.OK:
            raise VendorError("the fetched subtree is unusable (symlink or unreadable file); the pin was not changed")
    write_pack_pin(new_pin, _pin_path(live, pack))
    return new_pin


def pack_vendor(
    check: Annotated[
        bool,
        typer.Option("--check", help="Verify only (offline): compare packs/<pack>/ with its pin lockfile; exit 1 on drift. Mutates nothing."),
    ] = False,
    ref: Annotated[
        str | None,
        typer.Option("--ref", help="Bump the pin to this open-packs commit SHA or branch (resolved to a SHA; only the SHA is persisted)."),
    ] = None,
    pack: Annotated[str, typer.Option("--pack", help="Pack whose packs/<pack>.source.yaml pin to use.")] = _DEFAULT_PACK,
    subtree: Annotated[
        str | None,
        typer.Option("--subtree", help="Override the pin's subtree (the pack's path inside the open-packs repository)."),
    ] = None,
) -> None:
    """Bump (or verify) a pack pin; the pack tree itself is fetched by ``make sync-packs``."""
    if check and (ref is not None or subtree is not None):
        console.print("[red]--check is verify-only and cannot be combined with --ref or --subtree.[/red]")
        raise typer.Exit(2)
    if not _PACK_NAME_RE.fullmatch(pack):
        console.print(f"[red]invalid --pack {pack!r}: use a lowercase pack name such as built-in or internal.[/red]")
        raise typer.Exit(2)
    if not check and ref is None and subtree is None:
        console.print(f"[red]{_NOTHING_TO_BUMP}[/red]")
        raise typer.Exit(2)
    live = built_in_root()
    try:
        if check:
            pin = check_pack_pin(live, pack)
            console.print(f"[green]packs/{pack}/ matches the pin ({pin.commit}).[/green]")
            return
        pin = bump_pin(live, pack, ref=ref, subtree=subtree)
    except VendorError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"[green]Pinned packs/{pack}.source.yaml to {pin.commit} (tree_digest {pin.tree_digest.value}).[/green]")
