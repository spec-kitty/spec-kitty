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
from ruamel.yaml import YAML

from charter.activation import kind_vocabulary
from charter.activation.kind_vocabulary import ResolutionPass, UnknownArtifactIdError, resolve_config_id

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

    Returns ``(offering_root, org_roots)`` for direct keyword-argument use --
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
    offering_root, org_roots = _colliding_layers(tmp_path)

    resolved_stem = resolve_config_id("directive:CHOSEN-POLICY", offering_root=offering_root, org_roots=org_roots)

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
    offering_root = tmp_path / "builtin"
    org_roots = [tmp_path / "org"]

    assert resolve_config_id("directive:OLD-POLICY", offering_root=offering_root, org_roots=org_roots) == "policy"

    # Overwrite the same file with new content (bumps mtime, changes the
    # declared id) -- simulating an on-disk edit between resolutions.
    _directive(directory, "policy", "NEW-POLICY")

    assert resolve_config_id("directive:NEW-POLICY", offering_root=offering_root, org_roots=org_roots) == "policy"
    with pytest.raises(UnknownArtifactIdError):
        resolve_config_id("directive:OLD-POLICY", offering_root=offering_root, org_roots=org_roots)


# ---------------------------------------------------------------------------
# resolve_config_id input-guard coverage (#4239 follow-up F2): the malformed-URN
# and unknown-kind guards run before any filesystem scan, so they need no corpus.
# ---------------------------------------------------------------------------


def test_malformed_urn_without_separator_raises() -> None:
    with pytest.raises(ValueError, match="Malformed URN"):
        resolve_config_id("no-colon-here", offering_root=Path("/nonexistent"))


def test_malformed_urn_with_empty_artifact_id_raises() -> None:
    with pytest.raises(ValueError, match="Malformed URN"):
        resolve_config_id("directive:", offering_root=Path("/nonexistent"))


def test_urn_with_unknown_kind_raises() -> None:
    with pytest.raises(ValueError, match="unknown kind"):
        resolve_config_id("notakind:DIRECTIVE_001", offering_root=Path("/nonexistent"))


def test_non_directive_kind_returns_first_matching_stem(tmp_path: Path) -> None:
    """A non-directive kind resolves by first id match with no round-trip check.

    Covers the early-return path in `resolve_config_id` for the non-directive
    case (the directive round-trip/ambiguity logic applies to directives only).
    """
    org = tmp_path / "org"
    tactics = org / "tactics"
    tactics.mkdir(parents=True)
    (tactics / "adversarial-squad.tactic.yaml").write_text('schema_version: "1.0"\nid: TACTIC_ADVERSARIAL\ntitle: Adversarial squad\nintent: Review.\n')

    stem = resolve_config_id("tactic:TACTIC_ADVERSARIAL", offering_root=tmp_path / "builtin", org_roots=[org])

    assert stem == "adversarial-squad"


# ---------------------------------------------------------------------------
# Shared resolution pass (#5526): a CLI render loop maps many URNs back to
# config stems in one read-only pass. Before the pass also memoized ID reads,
# every URN re-parsed every artifact file in every layer.
# ---------------------------------------------------------------------------


@pytest.fixture
def parsed_files(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Counted-parse seam: record every artifact file whose YAML is parsed."""
    calls: list[Path] = []
    original = kind_vocabulary._parse_id

    def _counted(path: Path, id_field: str, yaml: YAML) -> str | None:
        calls.append(path)
        return original(path, id_field, yaml)

    monkeypatch.setattr(kind_vocabulary, "_parse_id", _counted)
    return calls


def test_shared_resolution_pass_parses_each_file_once(tmp_path: Path, parsed_files: list[Path]) -> None:
    offering_root, org_roots = _colliding_layers(tmp_path)
    shared = ResolutionPass()

    for _ in range(3):
        assert resolve_config_id("directive:CHOSEN-POLICY", offering_root=offering_root, org_roots=org_roots, resolution_pass=shared) == "original"

    # The scan also covers the shipped built-in directives; what matters is
    # that no file is parsed twice across the three resolutions.
    assert len(set(parsed_files)) >= 3
    assert len(parsed_files) == len(set(parsed_files)), parsed_files


def test_independent_resolutions_reparse(tmp_path: Path, parsed_files: list[Path]) -> None:
    """Without a shared pass each top-level call reads the files afresh (FR-002)."""
    offering_root, org_roots = _colliding_layers(tmp_path)

    resolve_config_id("directive:CHOSEN-POLICY", offering_root=offering_root, org_roots=org_roots)
    first_call = len(parsed_files)
    resolve_config_id("directive:CHOSEN-POLICY", offering_root=offering_root, org_roots=org_roots)

    assert first_call >= 3
    assert len(parsed_files) == 2 * first_call


def test_a_new_resolution_pass_observes_on_disk_changes(tmp_path: Path) -> None:
    directory = tmp_path / "org" / "directives"
    _directive(directory, "policy", "OLD-POLICY")
    offering_root = tmp_path / "builtin"
    org_roots = [tmp_path / "org"]

    assert resolve_config_id("directive:OLD-POLICY", offering_root=offering_root, org_roots=org_roots, resolution_pass=ResolutionPass()) == "policy"
    _directive(directory, "policy", "NEW-POLICY")

    assert resolve_config_id("directive:NEW-POLICY", offering_root=offering_root, org_roots=org_roots, resolution_pass=ResolutionPass()) == "policy"
    with pytest.raises(UnknownArtifactIdError):
        resolve_config_id("directive:OLD-POLICY", offering_root=offering_root, org_roots=org_roots, resolution_pass=ResolutionPass())
