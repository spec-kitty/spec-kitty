"""Atomic snapshot writer for non-git org doctrine sources.

The atomic-write pattern guarantees that ``local_path`` never observes a
partial snapshot:

1. Stage into ``<local_path>.parent/.tmp-<uuid>``.
2. Validate that the staged tree (or ``subdir`` within it, when configured)
   contains at least one recognised artifact subdirectory.
3. Write ``pack-manifest.yaml`` into the staged effective root.
4. Replace ``local_path`` with the complete staged tree using a single rename.

:class:`specify_cli.doctrine.sources.git_source.GitSource` deliberately
does NOT use this helper.  Git owns ``target_dir`` and provides its own
consistency story via ``fetch`` + ``reset --hard``.
"""

from __future__ import annotations

import hashlib
import hmac
import shutil
from dataclasses import replace
from kernel.clock import now_utc_stamp
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import SplitResult, urlsplit, urlunsplit
from uuid import uuid4

if TYPE_CHECKING:
    from .config import OrgPackConfig

import yaml

from charter.drg import CORE_KIND_PLURALS

from .sources.protocol import FetchResult, OrgDoctrineSource

# ``OrgPackConfig`` is imported lazily inside helpers to avoid a circular import
# at module load time (config.py lives in the same package).


# Recognised artifact subdirectories per the pack-layout contract.
_RECOGNISED_ARTIFACT_DIRS: frozenset[str] = frozenset(CORE_KIND_PLURALS) | {"drg"}

# Suffix → artifact-count bucket name for ``pack-manifest.yaml``.
_ARTIFACT_BUCKETS: dict[str, str] = {
    "directive.yaml": "directives",
    "tactic.yaml": "tactics",
    "styleguide.yaml": "styleguides",
    "toolguide.yaml": "toolguides",
    "paradigm.yaml": "paradigms",
    "procedure.yaml": "procedures",
    "agent.yaml": "agent_profiles",
    "contract.yaml": "mission_step_contracts",
    # Matches both the ``graph.yaml`` monolith and post-shard ``*.graph.yaml``
    # fragments (mission #2680, WP05) under ``endswith`` semantics.
    "graph.yaml": "drg_fragments",
}


def write_snapshot(
    source: OrgDoctrineSource,
    local_path: Path,
    *,
    source_url: str | None = None,
    source_type: str | None = None,
    subdir: str | None = None,
) -> FetchResult:
    """Fetch from ``source`` into a temp dir and atomically move into place.

    Args:
        source: Any object satisfying :class:`OrgDoctrineSource`.
        local_path: Destination directory.  Replaced atomically on success.
        source_url: Public URL recorded in ``pack-manifest.yaml`` (credentials
            stripped automatically).  Defaults to ``getattr(source, "url",
            None)``.
        source_type: Pack source classification (``git``, ``https``, ``api``,
            ``artifactory``); inferred from ``source`` class name when omitted.
        subdir: Optional relative path inside the fetched tree where the pack
            root lives (same semantics as ``OrgPackConfig.subdir``). Artifact
            validation and ``pack-manifest.yaml`` counts/write target the
            effective root (``local_path/subdir`` when set), matching FR-007
            and ``doctor doctrine`` which read from ``effective_root``.

    Returns:
        The :class:`FetchResult` produced by ``source.fetch`` (with extra
        validation errors appended if the staged tree is empty).  When the
        remote reports unchanged (HTTP 304), ``unchanged=True`` and the
        existing snapshot is left in place.
    """
    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)

    resolved_url = source_url if source_url is not None else getattr(source, "url", "")
    resolved_type = source_type or _infer_source_type(source)

    from .sources.https_source import HttpsBundleSource

    if isinstance(source, HttpsBundleSource):
        canonical_url = source.canonical_url
        if canonical_url is not None:
            source = replace(source, url=canonical_url)
            resolved_url = canonical_url

    source = _with_stored_etag(
        source,
        local_path,
        subdir,
        source_url=str(resolved_url or ""),
        source_type=resolved_type,
    )
    tmp_dir = local_path.parent / f".tmp-{uuid4().hex}"

    try:
        result = source.fetch(tmp_dir)
    except Exception as exc:  # pragma: no cover - defensive
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return FetchResult(
            ok=False,
            artifacts_written=0,
            pack_version=None,
            errors=[f"Unexpected error during fetch: {exc}"],
        )

    if not result.ok:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return result

    if result.unchanged:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return _finish_unchanged_snapshot(
            local_path,
            result,
            subdir=subdir,
        )

    try:
        validate_root = _resolve_snapshot_validate_root(tmp_dir, subdir)
    except ValueError as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return FetchResult(
            ok=False,
            artifacts_written=result.artifacts_written,
            pack_version=result.pack_version,
            etag=result.etag,
            errors=[str(exc)],
        )

    if not _has_recognised_artifacts(validate_root):
        shutil.rmtree(tmp_dir, ignore_errors=True)
        location = (
            f" at subdir {subdir!r}" if subdir else " at the snapshot root"
        )
        return FetchResult(
            ok=False,
            artifacts_written=result.artifacts_written,
            pack_version=result.pack_version,
            etag=result.etag,
            errors=[
                "No artifact directories found in fetched snapshot"
                f"{location}. Expected at least one of: "
                + ", ".join(sorted(_RECOGNISED_ARTIFACT_DIRS))
            ],
        )

    # Make metadata part of the staged snapshot. A manifest write failure must
    # leave the last-good installed tree untouched, just like a fetch or
    # validation failure.
    try:
        write_pack_manifest(
            validate_root,
            result,
            source_url=str(resolved_url or ""),
            source_type=resolved_type,
        )
    except OSError as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return FetchResult(
            ok=False,
            artifacts_written=result.artifacts_written,
            pack_version=result.pack_version,
            etag=result.etag,
            errors=[f"Failed to write staged snapshot manifest: {exc}"],
        )

    # Replace local_path by first moving the old snapshot aside. This avoids
    # the delete-then-move ENOENT window and preserves the old tree if promote
    # fails before the new snapshot is in place.
    old_dir: Path | None = None
    promoted = False
    try:
        if local_path.exists():
            old_dir = local_path.parent / f".old-{local_path.name}-{uuid4().hex}"
            local_path.replace(old_dir)
        tmp_dir.replace(local_path)
        promoted = True
    except OSError as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        errors = [f"Failed to replace snapshot: {exc}"]
        if old_dir is not None and old_dir.exists() and not local_path.exists():
            try:
                old_dir.replace(local_path)
            except OSError as restore_exc:
                errors.append(
                    "Automatic restore failed; the previous snapshot is preserved "
                    f"at {old_dir}: {restore_exc}"
                )
        return FetchResult(
            ok=False,
            artifacts_written=result.artifacts_written,
            pack_version=result.pack_version,
            etag=result.etag,
            errors=errors,
        )
    finally:
        if promoted and old_dir is not None and old_dir.exists():
            shutil.rmtree(old_dir, ignore_errors=True)
    return result


def _with_stored_etag(
    source: OrgDoctrineSource,
    local_path: Path,
    subdir: str | None,
    *,
    source_url: str,
    source_type: str,
) -> OrgDoctrineSource:
    """Attach a previously stored ETag as ``If-None-Match`` when supported."""
    from .sources.https_source import HttpsBundleSource

    if not isinstance(source, HttpsBundleSource):
        return source
    if source.if_none_match:
        return source
    if not _manifest_matches_source(local_path, subdir, source_url, source_type):
        return source
    # Legacy manifests stored an HTTPS ETag only as ``pack_version``. For
    # Artifactory downloads, do one unconditional migration fetch when the
    # dedicated ``etag`` field is absent so we can also read and persist the
    # artifact's JFrog ``version`` property.
    is_artifactory = source.is_artifactory
    if is_artifactory and _artifactory_manifest_needs_version_migration(
        local_path, subdir
    ):
        return source
    stored = _read_stored_etag(
        local_path,
        subdir,
        allow_pack_version_fallback=not is_artifactory and source.ref is None,
    )
    if not stored:
        return source
    return replace(source, if_none_match=stored)


def _artifactory_manifest_needs_version_migration(
    local_path: Path, subdir: str | None
) -> bool:
    """Return whether an existing JFrog snapshot lacks a distinct version.

    Before JFrog property support, ``pack_version`` was the HTTP ETag. Force
    one unconditional fetch when the version is absent or still equals the
    ETag; the next manifest records distinct ``pack_version`` and ``etag``
    fields and resumes conditional requests.
    """
    data = _read_existing_manifest(local_path, subdir)
    if data is None:
        return False
    version = data.get("pack_version")
    etag = data.get("etag")
    if not isinstance(version, str) or not version.strip():
        return True
    if not isinstance(etag, str) or not etag.strip():
        return True
    return version.strip() == etag.strip()


def _manifest_matches_source(
    local_path: Path, subdir: str | None, source_url: str, source_type: str
) -> bool:
    data = _read_existing_manifest(local_path, subdir)
    if data is None:
        return False
    if data.get("source_type") != source_type:
        return False
    # Queries may select distinct resources or carry credentials. Never persist
    # them, and never reuse a validator when either side used one because a
    # secret-free comparison cannot prove resource identity.
    parsed_source = _safe_urlsplit(source_url)
    if (
        parsed_source is None
        or parsed_source.query
        or data.get("source_uses_query") is True
    ):
        return False
    if not _snapshot_manifest_is_intact(local_path, subdir, data):
        return False
    expected_url = _strip_credentials(source_url)
    fingerprint = data.get("source_fingerprint")
    if isinstance(fingerprint, str) and fingerprint:
        return fingerprint == _source_fingerprint(expected_url)
    return data.get("source_url") == expected_url


def _read_stored_etag(
    local_path: Path,
    subdir: str | None,
    *,
    allow_pack_version_fallback: bool = True,
) -> str | None:
    """Return the ETag recorded in an existing snapshot's pack-manifest.

    Prefers the dedicated ``etag`` field.  Falls back to ``pack_version`` for
    manifests written before ``etag`` was persisted (HTTPS historically stored
    the ETag as ``pack_version`` when no ``ref`` pin was set).
    """
    data = _read_existing_manifest(local_path, subdir)
    if data is None:
        return None
    etag = data.get("etag")
    if isinstance(etag, str) and etag.strip():
        return etag.strip()
    # Migration fallback: only when source_type is https-family and no ref
    # was used as pack_version — we cannot distinguish ref from etag reliably,
    # so only fall back when ``etag`` is absent and ``source_type`` is https.
    if allow_pack_version_fallback and data.get("source_type") in {
        "https",
        "artifactory",
    }:
        version = data.get("pack_version")
        if isinstance(version, str) and version.strip():
            return version.strip()
    return None


def _read_existing_manifest(
    local_path: Path, subdir: str | None
) -> dict[str, Any] | None:
    """Read an existing snapshot manifest without mutating the snapshot."""
    if not local_path.exists():
        return None
    try:
        manifest_root = _resolve_snapshot_validate_root(local_path, subdir)
    except ValueError:
        return None
    manifest_path = manifest_root / "pack-manifest.yaml"
    if not manifest_path.is_file():
        return None
    try:
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


def _stored_pack_version(local_path: Path, subdir: str | None) -> str | None:
    """Return the version label from the current immutable snapshot."""
    data = _read_existing_manifest(local_path, subdir)
    if data is None:
        return None
    version = data.get("pack_version")
    return version.strip() if isinstance(version, str) and version.strip() else None


def _finish_unchanged_snapshot(
    local_path: Path,
    result: FetchResult,
    *,
    subdir: str | None,
) -> FetchResult:
    """Keep the existing snapshot byte-for-byte unchanged and recount artifacts."""
    if not local_path.exists():
        return FetchResult(
            ok=False,
            artifacts_written=0,
            pack_version=result.pack_version,
            etag=result.etag,
            errors=[
                "Remote reported unchanged (HTTP 304) but no local snapshot "
                f"exists at {local_path}."
            ],
        )
    try:
        manifest_root = _resolve_snapshot_validate_root(local_path, subdir)
    except ValueError as exc:
        return FetchResult(
            ok=False,
            artifacts_written=0,
            pack_version=result.pack_version,
            etag=result.etag,
            errors=[str(exc)],
        )
    if not _has_recognised_artifacts(manifest_root):
        return FetchResult(
            ok=False,
            artifacts_written=0,
            pack_version=result.pack_version,
            etag=result.etag,
            errors=[
                "Remote reported unchanged (HTTP 304) but the local snapshot "
                "has no recognised artifact directories."
            ],
        )
    manifest = _read_existing_manifest(local_path, subdir)
    if manifest is None or not _snapshot_manifest_is_intact(
        local_path, subdir, manifest
    ):
        return FetchResult(
            ok=False,
            artifacts_written=0,
            pack_version=result.pack_version,
            etag=result.etag,
            errors=[
                "Remote reported unchanged (HTTP 304) but the local snapshot "
                "does not match its recorded integrity digest."
            ],
        )
    counts = _count_artifacts(manifest_root)
    return FetchResult(
        ok=True,
        artifacts_written=sum(counts.values()),
        pack_version=_stored_pack_version(local_path, subdir) or result.pack_version,
        unchanged=True,
        etag=result.etag,
    )


def _resolve_snapshot_validate_root(
    snapshot_dir: Path, subdir: str | None
) -> Path:
    """Return the directory to validate/count within a staged or installed snapshot.

    When ``subdir`` is set, joins it under ``snapshot_dir`` with the same
    containment guard used by :meth:`OrgPackConfig.effective_root`.
    """
    if subdir is None:
        return snapshot_dir
    from charter.offering.drg.org_pack_config import resolve_relative_path_within_root

    return resolve_relative_path_within_root(snapshot_dir, subdir)


def write_pack_manifest(
    local_path: Path,
    result: FetchResult,
    *,
    source_url: str,
    source_type: str,
) -> None:
    """Write ``pack-manifest.yaml`` to ``local_path``.

    The manifest is read-only metadata for tooling and humans. Credentials,
    query parameters, and fragments in ``source_url`` are stripped before
    persistence.
    """
    local_path = Path(local_path)
    manifest_path = local_path / "pack-manifest.yaml"
    safe_source_url = _strip_credentials(source_url)
    from .pack_manifest import (
        PackManifest,
        dump_pack_manifest_bytes,
        finalize_pack_manifest,
    )

    manifest = finalize_pack_manifest(
        PackManifest(
            pack_version=result.pack_version,
            fetched_at=_iso_now(),
            source_type=source_type,
            source_url=safe_source_url,
            source_fingerprint=_source_fingerprint(safe_source_url),
            source_uses_query=_source_uses_query(source_url),
            snapshot_sha256=_snapshot_sha256(local_path),
            artifact_counts=_manifest_artifact_counts(local_path),
            etag=result.etag,
        )
    )
    manifest_path.write_bytes(dump_pack_manifest_bytes(manifest))


def _manifest_artifact_counts(local_path: Path) -> dict[str, int]:
    """Resolve manifest counts through the canonical derived-view seam."""
    from .pack_manifest import resolve_counts

    return resolve_counts(None, _count_artifacts(local_path))


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------
def _has_recognised_artifacts(snapshot_dir: Path) -> bool:
    if not snapshot_dir.exists():
        return False
    return any(
        entry.is_dir() and entry.name in _RECOGNISED_ARTIFACT_DIRS
        for entry in snapshot_dir.iterdir()
    )


def _count_artifacts(snapshot_dir: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not snapshot_dir.exists():
        return counts
    for entry in snapshot_dir.iterdir():
        if not entry.is_dir() or entry.name not in _RECOGNISED_ARTIFACT_DIRS:
            continue
        bucket = entry.name if entry.name != "drg" else "drg_fragments"
        counts[bucket] = sum(1 for _ in entry.rglob("*.yaml"))
    # FR-014: the sharded built-in layout (mission #2680, WP05) ships DRG
    # fragments as top-level ``*.graph.yaml`` files rather than under a ``drg/``
    # directory. Fold them into the same ``drg_fragments`` bucket so a sharded
    # doctrine tree categorises identically to the monolith / ``drg/``-dir
    # layouts. Additive: no current snapshot ships top-level fragments.
    fragment_count = sum(1 for _ in snapshot_dir.glob("*.graph.yaml"))
    if fragment_count:
        counts["drg_fragments"] = counts.get("drg_fragments", 0) + fragment_count
    return counts


def _strip_credentials(url: str) -> str:
    """Return a remote URL safe for durable metadata and comparisons."""
    if not url:
        return ""
    parsed = _safe_urlsplit(url)
    if parsed is None:
        return ""
    if parsed.scheme not in {"http", "https"}:
        return url
    hostname = parsed.hostname or ""
    if ":" in hostname:
        hostname = f"[{hostname}]"
    try:
        port = parsed.port
    except ValueError:
        port = None
    netloc = f"{hostname}:{port}" if port is not None else hostname
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def _safe_urlsplit(url: str) -> SplitResult | None:
    """Parse one URL without leaking malformed-authority exceptions."""
    try:
        return urlsplit(url)
    except ValueError:
        return None


def _source_uses_query(url: str) -> bool:
    """Return query presence without raising for malformed source URLs."""
    parsed = _safe_urlsplit(url)
    return bool(parsed is not None and parsed.query)


def _source_fingerprint(safe_url: str) -> str:
    """Return a stable non-secret identity for a sanitized source URL."""
    return hashlib.sha256(  # noqa: TID251 - URL identity fingerprint, not charter freshness
        safe_url.encode("utf-8")
    ).hexdigest()


def _snapshot_sha256(snapshot_root: Path) -> str:
    """Hash installed snapshot files, excluding the manifest itself."""
    digest = hashlib.sha256()  # noqa: TID251 - local snapshot integrity checksum
    for path in sorted(
        snapshot_root.rglob("*"),
        key=lambda candidate: candidate.relative_to(snapshot_root).as_posix(),
    ):
        relative = path.relative_to(snapshot_root)
        if path.is_symlink():
            raise OSError(f"Snapshot contains unsupported symlink: {relative}")
        if relative == Path("pack-manifest.yaml"):
            continue
        if path.is_dir():
            continue
        if not path.is_file():
            raise OSError(f"Snapshot contains unsupported file type: {relative}")
        relative_bytes = relative.as_posix().encode("utf-8")
        digest.update(len(relative_bytes).to_bytes(8, "big"))
        digest.update(relative_bytes)
        size = path.stat().st_size
        digest.update(size.to_bytes(8, "big"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(64 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _snapshot_manifest_is_intact(
    local_path: Path,
    subdir: str | None,
    manifest: dict[str, Any],
) -> bool:
    """Return whether installed files match the manifest's safe digest."""
    stored = manifest.get("snapshot_sha256")
    if (
        not isinstance(stored, str)
        or len(stored) != 64
        or any(character not in "0123456789abcdef" for character in stored)
    ):
        return False
    try:
        snapshot_root = _resolve_snapshot_validate_root(local_path, subdir)
        current = _snapshot_sha256(snapshot_root)
    except (OSError, ValueError):
        return False
    return hmac.compare_digest(stored, current)


def _infer_source_type(source: OrgDoctrineSource) -> str:
    declared = getattr(source, "source_type", None)
    if declared in {"git", "https", "artifactory", "api"}:
        return cast(str, declared)
    cls_name = type(source).__name__.lower()
    if "git" in cls_name:
        return "git"
    if "https" in cls_name or "bundle" in cls_name:
        return "https"
    if "api" in cls_name:
        return "api"
    return "unknown"


def _iso_now() -> str:
    return now_utc_stamp()


# ----------------------------------------------------------------------
# Pack-level fetch entry point (consumed by `spec-kitty charter fetch`).
# ----------------------------------------------------------------------
def _build_source(pack: OrgPackConfig) -> OrgDoctrineSource:
    """Construct the fetch-source adapter for *pack*.

    Raises:
        ValueError: When ``source_type`` is unset/unknown or required fields
            (``url``) are missing.
    """
    if pack.source_type is None:
        raise ValueError(
            f"Pack '{pack.name}' has no source_type configured; "
            "set doctrine.org.packs[].source_type to one of: git, https, artifactory, api."
        )
    if not pack.url:
        raise ValueError(
            f"Pack '{pack.name}' has source_type={pack.source_type!r} "
            "but no url; set doctrine.org.packs[].url."
        )

    if pack.source_type == "git":
        from .sources.git_source import GitSource

        return cast(OrgDoctrineSource, GitSource(url=pack.url, ref=pack.ref))
    if pack.source_type in {"https", "artifactory"}:
        from .sources.https_source import HttpsBundleSource

        return HttpsBundleSource(
            url=pack.url, ref=pack.ref, source_type=pack.source_type
        )
    if pack.source_type == "api":
        from .sources.api_source import ApiSource

        return cast(OrgDoctrineSource, ApiSource(url=pack.url, ref=pack.ref))

    raise ValueError(
        f"Unknown source_type: {pack.source_type!r} for pack '{pack.name}'"
    )


def fetch_pack(pack: OrgPackConfig, repo_root: Path) -> FetchResult:
    """Fetch a single configured pack using its declared source type.

    Git sources manage their own working directory; all other sources go
    through :func:`write_snapshot` for atomic-replace semantics.

    ``repo_root`` is needed to compute :meth:`OrgPackConfig.effective_root`
    for post-fetch artifact counting (FR-007), and to compute
    :meth:`OrgPackConfig.local_path_root` for the clone/write target itself
    (adversarial-squad follow-up: the target must go through the SAME
    env-var/tilde expansion seam as every read, or a templated ``local_path``
    like ``${SPEC_KITTY_PACK_HOME}/acme-doctrine`` gets cloned into a literal
    directory named that template string while reads resolve the real path).
    """
    try:
        source = _build_source(pack)
        target = pack.local_path_root(repo_root)
    except ValueError as exc:
        return FetchResult(
            ok=False,
            artifacts_written=0,
            pack_version=None,
            errors=[str(exc)],
        )

    from .sources.git_source import GitSource

    result = (
        source.fetch(target)
        if isinstance(source, GitSource)
        else write_snapshot(
            source,
            target,
            source_url=pack.url or "",
            source_type=pack.source_type,
            subdir=pack.subdir,
        )
    )

    if result.ok:
        effective = pack.effective_root(repo_root)
        result = FetchResult(
            ok=result.ok,
            artifacts_written=sum(_count_artifacts(effective).values()),
            pack_version=result.pack_version,
            errors=result.errors,
            unchanged=result.unchanged,
            etag=result.etag,
        )
    return result
