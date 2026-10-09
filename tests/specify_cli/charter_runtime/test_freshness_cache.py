"""Tests for the charter-freshness content-hash cache (WP02).

Proves all SEVEN contract guarantees in
``kitty-specs/next-latency-durable-fix-01M14RM3/contracts/freshness-cache-contract.md``:

1. hit-correctness (the ruamel parse is skipped on a hit)
2. bundle-invalidation
3. DRG-graph-invalidation
4. manifest-invalidation (the B1 stale-``"fresh"`` guard)
5. fail-closed (any of the three inputs unreadable -> miss, no poisoned entry)
6. content-only key (an mtime-only touch is still a hit)
7. schema-version invalidation

...plus NFR-004 (T010): a cache-served verdict is byte-identical to a
freshly computed one on an unchanged charter-bearing checkout. Written as a
direct dict-serialization comparison, NOT the masked ``canonical()`` oracle
used elsewhere in this mission's suite.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from kernel.clock import now_epoch
from specify_cli.charter_runtime.freshness import CharterFreshness, computer as _computer_module
from specify_cli.charter_runtime.freshness.cache import (
    _cache_path,
    compute_cache_key,
    compute_freshness_cached,
)
from specify_cli.charter_runtime.freshness.computer import compute_freshness as _compute_freshness_uncached

from tests.specify_cli.charter_preflight._fixtures import (
    init_git_repo,
    make_fresh_repo,
    seed_charter_yaml,
    seed_graph,
    seed_manifest,
)

pytestmark = [pytest.mark.git_repo]


def _charter_yaml_path(repo: Path) -> Path:
    return repo / ".kittify" / "charter" / "charter.yaml"


def _graph_path(repo: Path) -> Path:
    # The shared ``seed_graph`` fixture (tests/specify_cli/charter_preflight/_fixtures.py,
    # used by ~15 suites) still seeds the retired root; freshness reads it through
    # the temporary read fallback (FR-011) until WP14 removes it.
    return repo / ".kittify" / "charter-packs" / "graph.yaml"


def _manifest_path(repo: Path) -> Path:
    return repo / ".kittify" / "charter" / "synthesis-manifest.yaml"


# ---------------------------------------------------------------------------
# Guarantee 1: hit correctness — the parse is genuinely skipped on a hit
# ---------------------------------------------------------------------------


def test_hit_correctness_skips_the_parse(tmp_path: Path) -> None:
    make_fresh_repo(tmp_path)

    with patch.object(_computer_module, "_safe_load_yaml", wraps=_computer_module._safe_load_yaml) as cold_spy:
        cold = compute_freshness_cached(tmp_path)
    cold_spy.assert_called()  # sanity: the cold path genuinely parses
    assert cold.synthesized_drg.state == "fresh"

    with patch.object(_computer_module, "_safe_load_yaml") as warm_spy:
        warm = compute_freshness_cached(tmp_path)

    warm_spy.assert_not_called()  # THE load-bearing assertion: a hit skips the parse entirely
    assert warm == cold


# ---------------------------------------------------------------------------
# Guarantee 2: bundle invalidation
# ---------------------------------------------------------------------------


def test_bundle_invalidation_forces_recompute(tmp_path: Path) -> None:
    make_fresh_repo(tmp_path)
    first = compute_freshness_cached(tmp_path)
    assert first.synthesized_drg.state == "fresh"

    charter_yaml_path = _charter_yaml_path(tmp_path)
    charter_yaml_path.write_text(charter_yaml_path.read_text(encoding="utf-8") + "# drift-marker\n", encoding="utf-8")

    with patch.object(_computer_module, "_safe_load_yaml", wraps=_computer_module._safe_load_yaml) as spy:
        second = compute_freshness_cached(tmp_path)

    spy.assert_called()  # a bundle-only edit forces a genuine recompute, not a stale hit
    assert second.synthesized_drg.state == "stale"


# ---------------------------------------------------------------------------
# Guarantee 3: DRG-graph invalidation — mutate ONLY graph.yaml
# ---------------------------------------------------------------------------


def test_graph_invalidation_forces_recompute(tmp_path: Path) -> None:
    """Mutate graph.yaml only (bundle + manifest untouched) -> the next
    lookup MISSES and a genuine recompute occurs. This is the load-bearing
    proof reviewers must confirm (WP02 risk note): a ``(bundle, manifest)``
    -only key would silently ignore this edit and keep serving the stale
    entry.
    """
    make_fresh_repo(tmp_path)
    first = compute_freshness_cached(tmp_path)
    assert first.synthesized_drg.state == "fresh"

    graph_path = _graph_path(tmp_path)
    graph_path.write_text(graph_path.read_text(encoding="utf-8") + "# graph content mutated only\n", encoding="utf-8")

    with patch.object(_computer_module, "_safe_load_yaml", wraps=_computer_module._safe_load_yaml) as spy:
        second = compute_freshness_cached(tmp_path)

    spy.assert_called()  # proves the graph-only edit genuinely forced a recompute
    # The freshness computer never inspects graph.yaml CONTENT (only
    # existence/mtime), so the recomputed STATE is unaffected -- the point of
    # this test is that a genuine recompute happened at all, not that the
    # state value moved.
    assert second.synthesized_drg.state == "fresh"


# ---------------------------------------------------------------------------
# Guarantee 4: manifest invalidation (the B1 stale-"fresh" guard)
# ---------------------------------------------------------------------------


def test_manifest_invalidation_forces_recompute(tmp_path: Path) -> None:
    """B1 guard (research/post-tasks-squad-findings.md): a manifest-only
    mutation (bundle + graph untouched) must still force a genuine
    recompute -- the exact stale-"fresh" bug class the post-tasks squad
    caught for a ``(bundle, graph)``-only key.
    """
    make_fresh_repo(tmp_path)
    first = compute_freshness_cached(tmp_path)
    assert first.synthesized_drg.state == "fresh"

    # Flip built_in_only only -- charter.yaml and graph.yaml are untouched.
    seed_manifest(tmp_path, built_in_only=True)

    with patch.object(_computer_module, "_safe_load_yaml", wraps=_computer_module._safe_load_yaml) as spy:
        second = compute_freshness_cached(tmp_path)

    spy.assert_called()  # THE B1 guard: a manifest-only edit must not serve a stale cached verdict
    assert second.synthesized_drg.state == "built_in_only"
    assert second.synthesized_drg.state != first.synthesized_drg.state


# ---------------------------------------------------------------------------
# Guarantee 5: fail-closed
# ---------------------------------------------------------------------------


def test_fail_closed_missing_manifest_never_writes_a_poisoned_entry(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    seed_charter_yaml(tmp_path)
    seed_graph(tmp_path)
    # No synthesis-manifest.yaml at all -- one of the three inputs is missing.

    assert compute_cache_key(tmp_path) is None  # sanity: key computation fails closed

    first = compute_freshness_cached(tmp_path)  # must not raise
    assert isinstance(first, CharterFreshness)
    assert not _cache_path(tmp_path).exists()  # never poisoned

    second = compute_freshness_cached(tmp_path)  # must recompute again, not crash
    assert second == first
    assert not _cache_path(tmp_path).exists()


def test_fail_closed_graph_becomes_unreadable_after_a_valid_hit(tmp_path: Path) -> None:
    make_fresh_repo(tmp_path)
    baseline = compute_freshness_cached(tmp_path)
    assert _cache_path(tmp_path).exists()  # a valid entry now exists

    graph_path = _graph_path(tmp_path)
    graph_path.unlink()
    graph_path.mkdir()  # replace the file with a directory -> unreadable as a file

    assert compute_cache_key(tmp_path) is None  # fail-closed: cannot hash a directory

    # Must not raise, must not serve the now-unverifiable prior entry, and
    # must match a genuine uncached recompute (graph.yaml content is never
    # parsed by the computer, only existence/mtime, so this does not crash
    # the raw path either).
    result = compute_freshness_cached(tmp_path)
    assert isinstance(result, CharterFreshness)
    assert result == _compute_freshness_uncached(tmp_path)
    assert result.synthesized_drg.state == baseline.synthesized_drg.state == "fresh"


def test_fail_closed_non_utf8_sidecar_is_a_clean_miss(tmp_path: Path) -> None:
    # A corrupt/tampered/non-UTF-8 sidecar (e.g. FS corruption, a tool writing
    # latin-1) must be a clean MISS, never a raise: freshness runs on every
    # `spec-kitty next` / `charter status`, so a raise here would brick both.
    # Regression guard for the fail-closed read path (guarantee 5) — a bare
    # ``except OSError`` would let UnicodeDecodeError escape.
    make_fresh_repo(tmp_path)
    baseline = compute_freshness_cached(tmp_path)
    cache_path = _cache_path(tmp_path)
    assert cache_path.exists()  # a valid entry now exists

    cache_path.write_bytes(b"\xff\xfe not valid utf-8 \x80\x81")

    result = compute_freshness_cached(tmp_path)  # must NOT raise
    assert isinstance(result, CharterFreshness)
    assert result == _compute_freshness_uncached(tmp_path)  # genuine recompute
    assert result == baseline
    # The recompute overwrites the corrupt sidecar with a valid entry.
    assert json.loads(cache_path.read_text(encoding="utf-8"))["key"] is not None


# ---------------------------------------------------------------------------
# Guarantee 6: content-only key (an mtime-only touch is still a hit)
# ---------------------------------------------------------------------------


def test_content_only_key_mtime_touch_alone_is_still_a_hit(tmp_path: Path) -> None:
    make_fresh_repo(tmp_path)
    first = compute_freshness_cached(tmp_path)

    charter_yaml_path = _charter_yaml_path(tmp_path)
    future = now_epoch() + 10_000
    os.utime(charter_yaml_path, (future, future))

    with patch.object(_computer_module, "_safe_load_yaml") as spy:
        second = compute_freshness_cached(tmp_path)

    spy.assert_not_called()  # still a HIT: proves the key is content-based, not mtime-based
    assert second == first


# ---------------------------------------------------------------------------
# Guarantee 7: schema-version invalidation
# ---------------------------------------------------------------------------


def test_schema_version_bump_invalidates_all_prior_entries(tmp_path: Path) -> None:
    make_fresh_repo(tmp_path)
    first = compute_freshness_cached(tmp_path)

    cache_file = _cache_path(tmp_path)
    assert cache_file.exists()

    # Simulate a stale on-disk entry from a prior cache format.
    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    original_schema_version = payload["schema_version"]
    payload["schema_version"] = original_schema_version + 1000
    cache_file.write_text(json.dumps(payload), encoding="utf-8")

    with patch.object(_computer_module, "_safe_load_yaml", wraps=_computer_module._safe_load_yaml) as spy:
        second = compute_freshness_cached(tmp_path)

    spy.assert_called()  # a schema mismatch forces a genuine recompute, not a stale-shaped hit
    assert second == first  # same underlying repo state -> same verdict, just recomputed

    # The recompute re-stamps the sidecar with the CURRENT schema_version.
    refreshed = json.loads(cache_file.read_text(encoding="utf-8"))
    assert refreshed["schema_version"] == original_schema_version
    assert refreshed["schema_version"] != payload["schema_version"]


# ---------------------------------------------------------------------------
# NFR-004 (T010): byte-identical cache-served vs freshly-computed verdict
# ---------------------------------------------------------------------------


def test_nfr004_cache_served_verdict_is_byte_identical_to_a_fresh_compute(tmp_path: Path) -> None:
    """A cache-served verdict must be byte-identical to a freshly computed
    one on an unchanged charter-bearing checkout. Direct dict-serialization
    comparison -- deliberately NOT the masked ``canonical()`` oracle used
    elsewhere in this mission's test suite (T010)."""
    make_fresh_repo(tmp_path)

    raw_uncached = _compute_freshness_uncached(tmp_path)  # never touches the cache
    cache_cold = compute_freshness_cached(tmp_path)  # MISS -> recomputes + persists
    cache_warm = compute_freshness_cached(tmp_path)  # HIT -> served from the sidecar

    payload_raw = json.dumps(raw_uncached.to_dict(), sort_keys=True)
    payload_cold = json.dumps(cache_cold.to_dict(), sort_keys=True)
    payload_warm = json.dumps(cache_warm.to_dict(), sort_keys=True)

    assert payload_raw == payload_cold == payload_warm
