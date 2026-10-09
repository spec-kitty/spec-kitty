"""Content-hash cache for the charter freshness verdict (WP02).

**ELEVATED RISK surface** (research/post-tasks-squad-findings.md B1): this
module caches a governance verdict (:class:`CharterFreshness`). Serving a
stale ``"fresh"`` verdict is strictly worse than any stale projection
elsewhere in the CLI, so every design choice here is fail-closed by
construction:

* The cache key folds in ALL THREE inputs
  ``computer._compute_synthesized_drg`` reads — the charter bundle, the
  synthesized-DRG graph file, and the synthesis manifest
  (contracts/freshness-cache-contract.md, data-model.md). A
  ``(bundle, graph)``-only key served a stale verdict whenever the manifest
  alone drifted — the exact defect this cache must not reintroduce (B1).
* The key is CONTENT-based only — sha256 over normalized file bytes — never
  mtime. Touching a file without changing its content is a hit, not a miss.
* ANY of the three inputs being missing or unreadable is treated as a
  cache MISS, not a match against a possibly-stale prior entry: key
  computation itself fails closed to ``None``, which short-circuits both
  the read (never trust a stale entry once an input can no longer be
  independently verified) and the write (never persist an entry one of
  whose inputs could not actually be validated — never a poisoned entry).
* A read/write failure of the sidecar itself is silently swallowed —
  caching is a pure optimisation layered on top of
  ``computer.compute_freshness``; it must never be able to break, or change
  the outcome of, the freshness computation it accelerates.

Public entrypoint: :func:`compute_freshness_cached`, re-exported as
``compute_freshness`` from :mod:`specify_cli.charter_runtime.freshness`
(``freshness/__init__.py``) so every existing caller (``spec-kitty next``'s
preflight via ``charter_runtime.preflight.runner``, ``charter status
--json``) gets the cache transparently, with zero changes to their own
source. ``computer.py`` — the raw, uncached verdict computer — is untouched;
this module is a thin caching seam wrapped around it (T007/T008).

Location: a per-repo, gitignored runtime cache sidecar under
``.kittify/runtime/`` — the repo's existing per-repo runtime-state
convention (already gitignored; see e.g. ``.kittify/runtime/contexts/`` in
``specify_cli.context.store`` and ``.kittify/runtime/merge/`` in
``specify_cli.consolidation.state``). No new top-level directory is introduced.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from kernel.clock import now_utc_iso

from specify_cli.charter_runtime.freshness import computer as _computer
from specify_cli.charter_runtime.freshness.computer import (
    CharterFreshness,
    FreshnessSubState,
)
from specify_cli.charter_runtime.freshness.computer import (
    compute_freshness as _compute_freshness_uncached,
)
from specify_cli.core.atomic import atomic_write

# Only ``compute_freshness_cached`` is public API (re-exported as
# ``compute_freshness`` from the package ``__init__``). ``FreshnessCacheEntry``
# and ``compute_cache_key`` are module internals kept importable for the
# contract tests but deliberately NOT in ``__all__`` (dead-symbol gate).
__all__ = [
    "compute_freshness_cached",
]

_LOG = logging.getLogger(__name__)

#: Bump to invalidate every persisted entry on a format change (contract
#: guarantee 7). NEVER part of the content-hash key itself — a schema
#: mismatch is checked as a separate condition on read, independent of
#: whether the three content inputs are unchanged.
_SCHEMA_VERSION = 1

#: Per-repo cache sidecar location (see module docstring "Location").
_CACHE_RELPATH = Path(".kittify") / "runtime" / "charter" / "freshness-cache.json"


def _cache_path(repo_root: Path) -> Path:
    """Return the per-repo cache sidecar path for ``repo_root``."""
    return repo_root / _CACHE_RELPATH


# ---------------------------------------------------------------------------
# FreshnessCacheEntry (data-model.md)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FreshnessCacheEntry:
    """One persisted cache entry (data-model.md ``FreshnessCacheEntry``).

    Attributes:
        schema_version: Bumped to invalidate every prior entry on a format
            change.
        key: The composite :func:`compute_cache_key` digest this entry was
            written under.
        verdict: The exact :class:`CharterFreshness` ``compute_freshness``
            returned when this entry was written — deserialized identically
            on a hit, never semantically recomputed (T008).
        written_at: ISO-8601 diagnostic timestamp. NEVER part of the key or
            the invalidation decision (data-model.md).
    """

    schema_version: int
    key: str
    verdict: CharterFreshness
    written_at: str


# ---------------------------------------------------------------------------
# Composite key (contracts/freshness-cache-contract.md)
# ---------------------------------------------------------------------------


def _hash_file_content(path: Path) -> str | None:
    """Return a content-only ``"sha256:<hex>"`` digest of ``path``, or
    ``None`` (fail-closed) when it is missing or unreadable.

    Routes through :func:`charter.hasher.hash_content` — the repo's single
    canonical content-hashing chokepoint (directive 044) — so this shares
    the SAME BOM-strip / CRLF-normalize recipe
    :func:`charter.bundle.compute_bundle_content_hash` already applies to
    the charter bundle. The digest is content-only; mtime never enters it.

    ``OSError`` covers missing/unreadable (permission denied, is-a-directory,
    ...); ``UnicodeDecodeError`` covers non-UTF-8 content — not an
    ``OSError`` subclass, so it is caught explicitly (mirrors
    ``compute_bundle_content_hash``'s own fail-safe contract).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    from charter.hasher import hash_content  # noqa: PLC0415 — deferred per LD-3 hot-path discipline

    # `charter.*` is `follow_imports=skip`'d for this file's mypy invocation
    # (pyproject.toml `[[tool.mypy.overrides]]`), so `hash_content`'s declared
    # `str` return collapses to `Any` at this call site — cast it back,
    # matching the repo-wide pattern (see e.g.
    # tests/specify_cli/charter_preflight/_fixtures.py `_resolve_bundle_hash`).
    return cast("str", hash_content(text))


def compute_cache_key(repo_root: Path) -> str | None:
    """Compute the composite ``FreshnessCacheKey`` over the THREE inputs
    ``computer._compute_synthesized_drg`` reads: the charter bundle, the
    synthesized-DRG graph file (via ``computer._project_pack_graph_path``), and
    the synthesis manifest (via ``computer._synthesis_manifest_path``).

    Returns ``None`` (fail-closed) when ANY of the three cannot be computed
    — a missing or unreadable input is never treated as "unchanged"; it is
    treated as if no cache exists at all for this call, so a corrupted or
    absent input can never match a stale prior entry.

    Content-only, order-fixed, delimiter-separated composition — NEVER
    mtime (data-model.md ``FreshnessCacheKey``).
    """
    from charter.bundle import compute_bundle_content_hash  # noqa: PLC0415 — deferred per LD-3 hot-path discipline

    bundle_hash = compute_bundle_content_hash(repo_root)
    if bundle_hash is None:
        return None

    # Sibling module within charter_runtime/freshness/ — see module docstring.
    graph_hash = _hash_file_content(_computer._project_pack_graph_path(repo_root))
    if graph_hash is None:
        return None

    manifest_hash = _hash_file_content(_computer._synthesis_manifest_path(repo_root))
    if manifest_hash is None:
        return None

    composite = f"{bundle_hash}:{graph_hash}:{manifest_hash}"
    # Aggregating three ALREADY-charter-hashed digests into one cache key is a
    # file-integrity/cache-key composite, not a reimplementation of charter
    # CONTENT hashing (TID251's carved-out non-charter exception, pyproject.toml
    # banned-api message) — `hash_content()` would additionally BOM-strip /
    # CRLF-normalize / outer-strip, which is meaningless for a synthetic
    # ":"-delimited digest string, and its "sha256:" prefix would fight the
    # plain-hex `key` shape data-model.md declares for `FreshnessCacheEntry.key`.
    return hashlib.sha256(composite.encode("utf-8")).hexdigest()  # noqa: TID251 — cache-key composite over already-hashed components, not charter content


# ---------------------------------------------------------------------------
# Verdict (de)serialization (T008 — exact round-trip, no semantic change)
# ---------------------------------------------------------------------------


def _substate_from_dict(data: dict[str, Any]) -> FreshnessSubState:
    return FreshnessSubState(
        state=data["state"],
        last_change=data.get("last_change"),
        remediation=data.get("remediation"),
        detail=data.get("detail"),
    )


def _verdict_from_dict(data: dict[str, Any]) -> CharterFreshness:
    return CharterFreshness(
        charter_source=_substate_from_dict(data["charter_source"]),
        synced_bundle=_substate_from_dict(data["synced_bundle"]),
        synthesized_drg=_substate_from_dict(data["synthesized_drg"]),
    )


def _entry_to_json_dict(entry: FreshnessCacheEntry) -> dict[str, Any]:
    return {
        "schema_version": entry.schema_version,
        "key": entry.key,
        "verdict": entry.verdict.to_dict(),
        "written_at": entry.written_at,
    }


# ---------------------------------------------------------------------------
# Sidecar read/write (fail-closed; write failures never raise — T006)
# ---------------------------------------------------------------------------


def _read_cache_entry(repo_root: Path) -> FreshnessCacheEntry | None:
    """Read and validate the persisted cache entry.

    Fail-closed: ANY read, parse, or shape error returns ``None`` — a
    corrupt sidecar is silently treated as a miss, never trusted, and never
    allowed to raise out of the freshness computation it is layered under.
    """
    path = _cache_path(repo_root)
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        # UnicodeDecodeError: a non-UTF-8 (corrupt/tampered/latin-1) sidecar must
        # be a clean miss, never a raise — the cache may never break the freshness
        # computation it is layered under (fail-closed guarantee 5).
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    try:
        schema_version = data["schema_version"]
        key = data["key"]
        verdict_data = data["verdict"]
        written_at = data["written_at"]
        if not isinstance(schema_version, int) or not isinstance(key, str) or not isinstance(written_at, str) or not isinstance(verdict_data, dict):
            return None
        verdict = _verdict_from_dict(verdict_data)
    except (KeyError, TypeError, ValueError):
        return None
    return FreshnessCacheEntry(schema_version=schema_version, key=key, verdict=verdict, written_at=written_at)


#: A bare ``*`` inside a directory's own ``.gitignore`` ignores every file in
#: that directory, INCLUDING the ``.gitignore`` file itself: git consults a
#: ``.gitignore``'s on-disk content to compute ignore rules regardless of
#: whether that file is itself tracked, staged, or ignored. This is what
#: makes the recipe self-contained (T008) — it needs no edit to the
#: project's root ``.gitignore`` and no dependency on a migration having run
#: (verified empirically: a fresh nested ``.gitignore`` containing only
#: ``*`` produces an empty ``git status --porcelain`` for itself and every
#: sibling file, even though neither was ever committed).
_CACHE_DIR_GITIGNORE_CONTENT = "*\n"


def _ensure_cache_dir_gitignored(cache_dir: Path) -> None:
    """Best-effort: drop a self-contained ``.gitignore`` (``*``) inside the
    cache directory so this subsystem's artifacts never show up as
    untracked/dirty in ``git status`` — regardless of whether the wider
    project's root ``.gitignore`` already covers ``.kittify/runtime/``
    (older consumer projects predating the 3.2.4 backfill migration, and
    isolated test fixtures, may not; see module docstring "Location").

    Best-effort like :func:`_write_cache_entry`: any failure is logged and
    swallowed, never raised — a missing sidecar ``.gitignore`` degrades to
    "the cache file shows up as untracked", never to a broken freshness
    result.
    """
    gitignore_path = cache_dir / ".gitignore"
    try:
        if gitignore_path.read_text(encoding="utf-8") == _CACHE_DIR_GITIGNORE_CONTENT:
            return
    except OSError:
        pass
    try:
        atomic_write(gitignore_path, _CACHE_DIR_GITIGNORE_CONTENT, mkdir=True)
    except OSError:
        _LOG.debug("freshness cache .gitignore write failed for %s", gitignore_path, exc_info=True)


def _write_cache_entry(repo_root: Path, entry: FreshnessCacheEntry) -> None:
    """Persist ``entry`` atomically.

    Best-effort: a write failure (permission denied, read-only filesystem,
    ...) is logged and swallowed — the cache is a pure optimisation and must
    never be able to break the caller's freshness result.
    """
    path = _cache_path(repo_root)
    _ensure_cache_dir_gitignored(path.parent)
    payload = json.dumps(_entry_to_json_dict(entry), indent=2, sort_keys=True) + "\n"
    try:
        atomic_write(path, payload, mkdir=True)
    except OSError:
        _LOG.debug("freshness cache write failed for %s", path, exc_info=True)


# ---------------------------------------------------------------------------
# Public entrypoint (T007)
# ---------------------------------------------------------------------------


def compute_freshness_cached(repo_root: Path) -> CharterFreshness:
    """Compute the charter freshness verdict, serving a content-keyed cache
    hit when available and safe, else recomputing via
    ``computer.compute_freshness`` (the ruamel/manifest parse) and
    persisting the fresh entry.

    Re-exported as ``compute_freshness`` from
    :mod:`specify_cli.charter_runtime.freshness` (T007) — every existing
    caller (``next``'s preflight, ``charter status --json``) gets this
    transparently; the function signature and return type are unchanged.

    Fail-closed (C-005): when the composite key cannot be computed (any of
    the three inputs missing/unreadable), the cache is bypassed entirely —
    neither read nor written — and this call degrades to exactly the
    uncached ``compute_freshness`` behaviour.
    """
    key = compute_cache_key(repo_root)
    if key is not None:
        entry = _read_cache_entry(repo_root)
        if entry is not None and entry.schema_version == _SCHEMA_VERSION and entry.key == key:
            return entry.verdict  # HIT — the ruamel/manifest parse is skipped entirely.

    verdict = _compute_freshness_uncached(repo_root)

    if key is not None:
        _write_cache_entry(
            repo_root,
            FreshnessCacheEntry(
                schema_version=_SCHEMA_VERSION,
                key=key,
                verdict=verdict,
                written_at=now_utc_iso(),
            ),
        )

    return verdict
