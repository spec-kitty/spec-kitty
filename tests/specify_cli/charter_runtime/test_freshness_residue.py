"""Read-time stale-graph-residue contract (WP04 / FR-006, C2-f).

The manifest is the declared authority over ``graph.yaml`` presence (#083).
When the synthesis manifest declares ``built_in_only=true`` while a project
``.kittify/charter-packs/graph.yaml`` is still present (e.g. left behind after a
branch checkout), the graph is **residue**, not a contradiction:

* the freshness computer MUST report the authoritative ``built_in_only`` state
  and attach a non-blocking "stale graph residue" diagnostic, and
* charter preflight MUST therefore PASS (``built_in_only`` is in
  ``_PASS_STATES``) rather than blocking on a terminal ``invalid`` state.

T030 originally pinned the *bug* (the residue returned ``invalid`` and blocked
preflight) as a RED test; after the FR-006 downgrade it pins the *contract*.
A genuine-``invalid`` guard (F5) lives alongside it to prove the downgrade did
not over-fire onto a real inconsistency.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.charter_runtime.freshness import compute_freshness
from specify_cli.charter_runtime.preflight import run_charter_preflight

pytestmark = [pytest.mark.git_repo]

from ..charter_preflight._fixtures import (
    init_git_repo,
    seed_bundle_files,
    seed_charter,
    seed_charter_yaml,
    seed_graph,
    seed_manifest,
    write_metadata,
)

_RESIDUE_PHRASE = "stale graph residue"


def _seed_residue_repo(repo: Path) -> None:
    """Materialise the topology-true residue state.

    A fully-synced charter + bundle, a manifest that authoritatively declares
    ``built_in_only=true``, AND a stray ``graph.yaml`` the manifest disowns.
    """
    init_git_repo(repo)
    charter_path, metadata_path = seed_charter(repo)
    write_metadata(metadata_path, charter_path)
    seed_bundle_files(repo)
    # consolidate-charter-bundle WP06 (Landmine 2): charter_source/
    # synced_bundle now resolve over charter.yaml.
    seed_charter_yaml(repo)
    seed_manifest(repo, built_in_only=True)
    seed_graph(repo)  # residue: manifest disowns this graph.yaml


# ---------------------------------------------------------------------------
# FR-006: residue is read-time, non-blocking
# ---------------------------------------------------------------------------


def test_residue_reports_built_in_only_not_invalid(tmp_path: Path) -> None:
    """built_in_only ∧ graph.yaml present → authoritative ``built_in_only``."""
    _seed_residue_repo(tmp_path)

    result = compute_freshness(tmp_path)

    assert result.synthesized_drg.state == "built_in_only"
    # The blocking ``invalid`` state is unreachable for this residue condition.
    assert result.synthesized_drg.state != "invalid"


def test_residue_carries_non_blocking_diagnostic(tmp_path: Path) -> None:
    """The residue is surfaced as a diagnostic, with no synthesize remediation."""
    _seed_residue_repo(tmp_path)

    sub = compute_freshness(tmp_path).synthesized_drg

    assert sub.detail is not None
    assert _RESIDUE_PHRASE in sub.detail
    # Read-time normalization is structural, NOT a reactive self-heal: the
    # reader must NOT push the operator at ``charter synthesize`` for residue.
    assert sub.remediation is None


def test_residue_passes_preflight(tmp_path: Path) -> None:
    """SC-003: the residue state yields a PASSING preflight, not a block."""
    _seed_residue_repo(tmp_path)

    result = run_charter_preflight(tmp_path, auto_refresh=False)

    assert result.passed is True
    assert result.blocked_reason is None
    drg = next(c for c in result.checks if c.name == "synthesized_drg")
    assert drg.state == "built_in_only"
    assert drg.detail is not None
    assert _RESIDUE_PHRASE in drg.detail


# ---------------------------------------------------------------------------
# F5: genuine-`invalid` guard — the downgrade must not over-fire
# ---------------------------------------------------------------------------


def test_genuine_invalid_still_blocks_preflight(tmp_path: Path) -> None:
    """A real inconsistency (charter.yaml present but unparseable) stays
    ``invalid``.

    consolidate-charter-bundle WP06 (Landmine 2) re-pins this test: the
    genuine ``invalid`` producer moved from ``charter.md`` (unhashable) to
    ``charter.yaml`` (unparseable) — the retired ``_charter_hash_of``
    producer no longer exists. This guards FR-006 against over-downgrading:
    an unparseable ``charter.yaml`` is NOT covered by a ``built_in_only``
    manifest declaration and MUST remain a terminal, preflight-blocking
    ``invalid`` state.
    """
    init_git_repo(tmp_path)
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_yaml_path = charter_dir / "charter.yaml"
    # Write a valid charter.yaml, then replace it with a directory so the
    # genuine ``invalid`` producer (unparseable, not merely absent) fires.
    seed_charter_yaml(tmp_path)
    charter_yaml_path.unlink()
    charter_yaml_path.mkdir()  # a directory where a file is expected → unparseable

    result = compute_freshness(tmp_path)
    assert result.charter_source.state == "invalid"

    preflight = run_charter_preflight(tmp_path, auto_refresh=False)
    assert preflight.passed is False
