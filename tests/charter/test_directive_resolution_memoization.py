"""Scan-count + mtime-invalidation coverage for directive resolver memoization (#4239).

`resolve_config_id`'s directive branch performs a per-stem round-trip check
(`resolve_artifact_urn`) for every candidate path that matches the target
identity. Pre-memoization, each of those round-trip checks re-invoked
`_iter_artifact_paths`, which walks every doctrine layer from scratch --
O(candidates x layers) filesystem scans for a single resolution pass. This
module pins the fix: a single `resolve_config_id` pass performs at most one
scan per distinct layer, and a *later*, independent resolution still observes
on-disk changes (a resolution-pass-scoped memo never survives past its own
call, so there is nothing to go stale).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from charter.activation import kind_vocabulary
from charter.activation.kind_vocabulary import UnknownArtifactIdError, resolve_config_id

pytestmark = pytest.mark.fast


def _directive(directory: Path, stem: str, identity: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{stem}.directive.yaml").write_text(f'schema_version: "1.0"\nid: {identity}\ntitle: {stem}\nintent: Apply policy.\nenforcement: required\n')


@pytest.fixture
def scan_calls(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[Path]]:
    """Counted-scan seam: record every per-layer directory scan performed.

    Wraps `_scan_dir_matches`, the single call site `_iter_artifact_paths`
    uses to walk one `(scan_dir, recursive)` layer entry, so every recorded
    call corresponds to exactly one layer scan.
    """
    calls: list[Path] = []
    original = kind_vocabulary._scan_dir_matches

    def _counted(scan_dir: Path, pattern: str, *, recursive: bool) -> list[Path]:
        calls.append(scan_dir)
        return original(scan_dir, pattern, recursive=recursive)

    monkeypatch.setattr(kind_vocabulary, "_scan_dir_matches", _counted)
    yield calls


def _colliding_layers(tmp_path: Path) -> tuple[Path, list[Path]]:
    """Two org layers whose ``shared`` stem collides across layers.

    ``team`` (highest org precedence) declares ``shared`` under one identity;
    ``company`` (lower precedence) declares the *target* identity under both
    a colliding ``shared`` stem and a clean, non-colliding ``original`` stem.
    Resolving the target identity therefore forces `resolve_config_id`'s
    directive branch through more than one per-stem round-trip check before
    it lands on the representable ``original`` stem -- the exact N-stems
    x L-layers shape this WP eliminates.

    Returns ``(doctrine_root, org_roots)`` for direct keyword-argument use --
    a mixed-type kwargs dict unpacked via ``**`` defeats mypy's per-parameter
    checking of `resolve_config_id`'s keyword-only signature.
    """
    orgs = [tmp_path / "company", tmp_path / "team"]
    _directive(orgs[0] / "directives", "original", "CHOSEN-POLICY")
    _directive(orgs[0] / "directives", "shared", "OTHER-POLICY")
    _directive(orgs[1] / "directives", "shared", "CHOSEN-POLICY")
    return tmp_path / "builtin", orgs


def test_single_resolution_pass_scans_each_layer_at_most_once(tmp_path: Path, scan_calls: list[Path]) -> None:
    """FR-001: one `resolve_config_id` pass performs <=1 scan per distinct layer.

    Pre-memoization this is provably false for the colliding fixture: the
    first two candidate stems each trigger their own `_iter_artifact_paths`
    walk, so every layer gets scanned once per round-trip check instead of
    once for the whole pass.
    """
    doctrine_root, org_roots = _colliding_layers(tmp_path)

    resolved_stem = resolve_config_id("directive:CHOSEN-POLICY", doctrine_root=doctrine_root, org_roots=org_roots)

    assert resolved_stem == "original"
    distinct_layers = set(scan_calls)
    # Sanity: the fixture must actually exercise more than one layer, or the
    # <=1-scan-per-layer assertion below would be vacuously satisfiable.
    assert len(distinct_layers) >= 2, f"fixture only touched {distinct_layers!r}; collision scenario did not engage"
    assert len(scan_calls) <= len(distinct_layers), (
        f"expected <=1 scan per layer ({len(distinct_layers)} layers), but observed {len(scan_calls)} scans: {scan_calls!r}"
    )


def test_fresh_resolution_after_file_change_observes_new_content(tmp_path: Path) -> None:
    """FR-002: a later, independent resolution must see on-disk changes.

    A resolution-pass-scoped memo (or an mtime-keyed one) must never leak
    stale results across separate top-level `resolve_config_id` calls.
    """
    directory = tmp_path / "org" / "directives"
    _directive(directory, "policy", "OLD-POLICY")
    doctrine_root = tmp_path / "builtin"
    org_roots = [tmp_path / "org"]

    assert resolve_config_id("directive:OLD-POLICY", doctrine_root=doctrine_root, org_roots=org_roots) == "policy"

    # Overwrite the same file with new content (bumps mtime, changes the
    # declared id) -- simulating an on-disk edit between resolutions.
    _directive(directory, "policy", "NEW-POLICY")

    assert resolve_config_id("directive:NEW-POLICY", doctrine_root=doctrine_root, org_roots=org_roots) == "policy"
    with pytest.raises(UnknownArtifactIdError):
        resolve_config_id("directive:OLD-POLICY", doctrine_root=doctrine_root, org_roots=org_roots)
