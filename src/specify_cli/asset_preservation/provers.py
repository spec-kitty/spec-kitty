"""Ownership provers for the asset-preservation guard.

Each prover answers one question — *does the Spec Kitty package own this exact
path right now?* — and returns a concrete :class:`OwnershipProof` (reused from
``tool_surface.operations``) when it can prove ownership, or ``None`` when it
cannot. A ``None`` verdict means "unprovable ⇒ preserve" (charter L470/L472):
name/directory identity is never, by itself, proof of ownership.

Three signals, one per ``OwnershipProof.kind``:

* ``manifest`` — a skills/command manifest entry maps to the path and its
  recorded content hash matches the bytes on disk (copy delivery). The two
  manifest shapes differ (managed-skills carries ``sha256:``-prefixed hashes and
  a ``delivery_mode``; command-skills carries a bare 64-hex fingerprint), so
  :class:`ManifestProver` checks each with its own predicate — mirroring
  ``skills.installer._replacement_is_owned`` (managed) and
  ``skills.manifest_store.fingerprint_file`` (command). Both are imported
  lazily, function-local (not at module import time), to avoid an
  import-TIME cycle between this package and ``specify_cli.skills``.
* ``managed_path`` — the path is a declared package-managed / regenerable
  location, or was created by this invocation. Used where no manifest exists
  (e.g. the legacy ``.kittify/templates`` / ``.scratch`` resolver scratch).
* ``canonical_content`` — the file carries the package version marker
  (``<!-- spec-kitty-command-version: -->`` — the only command marker syntax,
  used in ``.md`` and inside ``.toml`` prompt bodies alike) or byte-matches a
  supplied shipped canonical. Modeled on
  ``m_3_1_2_globalize_commands._is_generated_file`` and
  ``m_2_0_7._matches_package_default``.

:class:`AnyProver` composes provers in order (first non-``None`` proof wins) so
a dual-signal site expresses its fallback as data, not call-site branching.

Fail-closed everywhere: any read error, a symlink, or a directory with an
untracked member yields ``None`` (preserve), never a false ``owned``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from specify_cli.tool_surface.operations import OwnershipProof

__all__ = [
    "AnyProver",
    "CanonicalContentProver",
    "ManagedPathProver",
    "ManifestProver",
    "OwnershipProver",
]

#: The single command version marker. ``asset_generator`` injects it as an HTML
#: comment into ``.md`` files and inside ``.toml`` prompt bodies alike; there is
#: no ``#``-comment command marker.
_VERSION_MARKER = b"<!-- spec-kitty-command-version:"


@runtime_checkable
class OwnershipProver(Protocol):
    """Prove package ownership of ``path``, or return ``None`` (preserve)."""

    def prove(self, path: Path, project_path: Path) -> OwnershipProof | None: ...


def _relposix(path: Path, project_path: Path) -> str | None:
    try:
        return path.relative_to(project_path).as_posix()
    except ValueError:
        return None


class ManifestProver:
    """Prove ownership from the managed-skills and/or command-skills manifests.

    A file is owned when a manifest entry maps to its project-relative path and
    the entry's recorded content hash matches the bytes on disk. A directory is
    owned only when every regular-file member is manifest-owned and there are no
    untracked members (fail-closed on any untracked or unreadable member).
    """

    def __init__(self, *, check_managed: bool = True, check_command: bool = True) -> None:
        self._check_managed = check_managed
        self._check_command = check_command

    def prove(self, path: Path, project_path: Path) -> OwnershipProof | None:
        rel = _relposix(path, project_path)
        if rel is None or path.is_symlink():
            return None
        if path.is_dir():
            return self._prove_dir(path, project_path)
        if path.is_file():
            return self._prove_file(path, rel, project_path)
        return None

    def _prove_file(self, path: Path, rel: str, project_path: Path) -> OwnershipProof | None:
        if self._check_managed and self._managed_owned(path, rel, project_path):
            return OwnershipProof("manifest", f".kittify/skills-manifest.json:{rel}")
        if self._check_command and self._command_owned(path, rel, project_path):
            return OwnershipProof("manifest", f".kittify/command-skills-manifest.json:{rel}")
        return None

    def _prove_dir(self, path: Path, project_path: Path) -> OwnershipProof | None:
        members = [child for child in path.rglob("*") if child.is_file() or child.is_symlink()]
        if not members:
            return None  # empty / no tracked content ⇒ preserve (fail closed)
        for member in members:
            if member.is_symlink() or not member.is_file():
                return None
            member_rel = _relposix(member, project_path)
            if member_rel is None or self._prove_file(member, member_rel, project_path) is None:
                return None
        rel = _relposix(path, project_path)
        return OwnershipProof("manifest", f"manifest-dir:{rel}")

    def _managed_owned(self, path: Path, rel: str, project_path: Path) -> bool:
        # Mirrors skills.installer._replacement_is_owned: entry maps to this path,
        # copy delivery, and the recorded sha256 matches the current bytes.
        from specify_cli.skills.manifest import compute_content_hash, load_manifest

        # load_manifest(strict=False) already returns None on a missing/corrupt
        # manifest, so a None result is the fail-closed (preserve) path.
        manifest = load_manifest(project_path)
        if manifest is None:
            return False
        try:
            current = compute_content_hash(path)
        except OSError:
            return False
        return any(entry.installed_path == rel and entry.delivery_mode == "copy" and entry.content_hash == current for entry in manifest.entries)

    def _command_owned(self, path: Path, rel: str, project_path: Path) -> bool:
        from specify_cli.skills import manifest_store
        from specify_cli.skills.manifest_errors import ManifestError

        if not (project_path / ".kittify" / "command-skills-manifest.json").exists():
            return False
        try:
            manifest = manifest_store.load(project_path)
            current = manifest_store.fingerprint_file(path)
        except (ManifestError, OSError):
            return False
        return any(entry.path == rel and entry.content_hash == current for entry in manifest.entries)


class ManagedPathProver:
    """Prove ownership for manifest-less package-managed / regenerable paths.

    Ownership is a declared contract: a project-relative path in
    ``managed_relpaths`` (package regenerable scratch, e.g. ``.kittify/templates``
    or ``.kittify/.scratch``) or an absolute path this invocation created
    (``run_created``). A path outside both is user-authorable and never owned by
    name (e.g. the legacy ``.kittify/command-templates`` resolver tier).
    """

    def __init__(
        self,
        *,
        managed_relpaths: Iterable[str] = (),
        run_created: Iterable[Path] = (),
    ) -> None:
        self._managed = frozenset(managed_relpaths)
        self._run_created = frozenset(Path(p) for p in run_created)

    def prove(self, path: Path, project_path: Path) -> OwnershipProof | None:
        if path in self._run_created:
            return OwnershipProof("managed_path", f"run-created:{path.name}")
        rel = _relposix(path, project_path)
        if rel is not None and rel in self._managed:
            return OwnershipProof("managed_path", f"package-managed:{rel}")
        return None


class CanonicalContentProver:
    """Prove ownership from a package version marker or a shipped canonical.

    ``marker`` defaults to the single ``<!-- spec-kitty-command-version:`` marker.
    ``scan_bytes`` bounds the search window (``None`` scans the whole file — the
    marker can sit past a 15-line head inside a ``.toml`` prompt body).
    ``canonical`` optionally supplies shipped bytes to match exactly. No marker
    and no canonical match ⇒ ``None`` (preserve) — this is why the markerless,
    no-longer-shipped ``m_0_10_0`` scripts preserve-all.

    ``check_marker`` (default ``True``) gates the version-marker branch. Set it
    ``False`` for a canonical-**bytes-only** ownership decision, where ownership
    must mean "byte-identical to the shipped counterpart" and the presence of
    the marker literal must NOT by itself prove ownership (#4961/#5050): a
    *differing* operator file that merely embeds the marker string would
    otherwise be proven owned and deleted, silently destroying a customisation.
    """

    def __init__(
        self,
        *,
        marker: bytes = _VERSION_MARKER,
        scan_bytes: int | None = None,
        canonical: bytes | None = None,
        check_marker: bool = True,
    ) -> None:
        self._marker = marker
        self._scan_bytes = scan_bytes
        self._canonical = canonical
        self._check_marker = check_marker

    def prove(self, path: Path, project_path: Path) -> OwnershipProof | None:
        rel = _relposix(path, project_path)
        if rel is None or path.is_symlink() or not path.is_file():
            return None
        try:
            content = path.read_bytes()
        except OSError:
            return None
        window = content if self._scan_bytes is None else content[: self._scan_bytes]
        if self._check_marker and self._marker in window:
            return OwnershipProof("canonical_content", f"version-marker:{rel}")
        if self._canonical is not None and content == self._canonical:
            return OwnershipProof("canonical_content", f"canonical-bytes:{rel}")
        return None


class AnyProver:
    """Ordered composite: the first component to prove ownership wins."""

    def __init__(self, provers: Sequence[OwnershipProver]) -> None:
        self._provers = tuple(provers)

    def prove(self, path: Path, project_path: Path) -> OwnershipProof | None:
        for prover in self._provers:
            proof = prover.prove(path, project_path)
            if proof is not None:
                return proof
        return None
