"""Tests for ``charter.activation.consistency_check._check_graph_kind_parity`` (WP02, T007).

Mission ``drg-relation-parity-activation-gate-01KY48PD``. T007 re-points
``_check_graph_kind_parity`` from KIND-granular to per-ID, consuming the
WP01-corrected :func:`charter.activation.drg_activation.filter_graph_by_activation` gate directly
(plan.md IC-02) -- a deliberate **behavior upgrade**, not a pure refactor.

Covers:
- ``test_coherent_when_activated_stem_survives_in_graph``: sibling GREEN --
  a real, resolvable, kind-permitted stem survives -> ``graph_kind_gaps``
  empty, report coherent.
- ``test_per_id_gap_named_when_node_absent_from_graph``: a genuine per-ID
  graph<->doctrine desync (the stem resolves via doctrine file lookup, but
  its canonical node is absent from the DRG graph itself) -> a
  ``graph_kind_gaps`` entry naming ``{cli_kind}/{stem}``, not merely the
  kind. Distinct from the whole-kind exclusion already covered by
  ``tests/charter_offering/test_activation_parity_guard.py::
  test_config_kind_absent_from_graph_bites``.
- ``test_unresolvable_stem_names_the_id_in_verification_errors``: an unknown
  stem yields a **specific** ``verification_errors`` entry naming the
  unresolvable id -- not merely "an entry was appended" / "no exception
  raised".
- ``test_non_drift_error_propagates_not_swallowed_as_drift``: the hardened
  DoD guard -- a genuine non-``UnknownArtifactIdError`` failure during
  per-stem resolution (a programming bug, not config drift) is NOT silently
  converted into a ``verification_errors``/``graph_kind_gaps`` entry; it
  propagates, proving the catch is narrow (``except UnknownArtifactIdError``),
  never a broad ``except Exception``.
- ``test_drg_load_failure_still_fails_closed``: the pre-existing DRG-load
  fail-closed contract (#2530) survives the re-point unchanged -- this catch
  stays broad because it guards a structurally different failure mode
  (graph load/validate) from the narrow per-stem catch above.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import charter.activation._drg_helpers as drg_helpers
from charter.activation import consistency_check
from charter.activation.consistency_check import run_consistency_check
from charter.drg import DRGGraph
from charter.activation.invocation_context import ProjectContext

pytestmark = pytest.mark.unit

# A real, stable built-in directive whose canonical id (``DIRECTIVE_001``)
# differs from its config stem -- exercises the genuine stem<->canonical
# resolution path (not an ``id==stem`` fixture).
_REAL_DIRECTIVE_STEM = "001-architectural-integrity-standard"
_REAL_DIRECTIVE_URN = "directive:DIRECTIVE_001"


def _write_config(tmp_path: Path, content: str) -> None:
    """Write a .kittify/config.yaml with the given content."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(exist_ok=True)
    (kittify / "config.yaml").write_text(content, encoding="utf-8")


def _ctx_with_config(tmp_path: Path, config_yaml: str) -> ProjectContext:
    """Build a ProjectContext (real built-in pack) with the supplied config.

    ``mission_type_activations`` is appended unconditionally: every caller
    here supplies only ``activated_directives`` content (the kind under
    test), and ``ProjectContext.from_repo`` eagerly resolves
    ``PackContext.from_config()``, which now hard-fails (WP04, C-A1) when
    that key is absent. The mission-type kind is unrelated to the DRG
    graph-parity behavior these tests pin.
    """
    _write_config(tmp_path, config_yaml + "mission_type_activations:\n  - software-dev\n")
    return ProjectContext.from_repo(tmp_path)


def _empty_graph() -> DRGGraph:
    """A schema-valid DRG graph with zero nodes/edges (simulates a genuine
    graph<->doctrine desync: the stem resolves via file lookup, but no DRG
    node carries its canonical URN)."""
    return DRGGraph(
        schema_version="1.0",
        generated_at="TEST",
        generated_by="test",
        nodes=[],
        edges=[],
    )


# ---------------------------------------------------------------------------
# Sibling GREEN (proves the RED cases below are real assertions)
# ---------------------------------------------------------------------------


@pytest.mark.doctrine
def test_coherent_when_activated_stem_survives_in_graph(tmp_path: Path) -> None:
    """A real, resolvable stem whose kind is permitted -> no per-ID gap."""
    ctx = _ctx_with_config(
        tmp_path, f"activated_directives:\n  - {_REAL_DIRECTIVE_STEM}\n"
    )

    report = run_consistency_check(ctx)

    assert report.graph_kind_gaps == []
    assert report.verification_errors == []
    assert report.coherent is True


# ---------------------------------------------------------------------------
# Per-ID gap: node genuinely absent from the DRG graph (T007 behavior upgrade)
# ---------------------------------------------------------------------------


@pytest.mark.doctrine
def test_per_id_gap_named_when_node_absent_from_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A resolvable stem whose canonical node is absent from the DRG graph
    itself -> ``graph_kind_gaps`` names the specific id, not just the kind.

    This is the T007 per-ID upgrade's headline case: the stem resolves fine
    (the artifact file exists in doctrine), the kind is fully permitted
    (default-allow ``activated_kinds``), yet the graph the gate filters has
    no node carrying that canonical URN -- a genuine graph<->doctrine
    desync a KIND-level check could never distinguish from "some other id of
    this kind is missing".
    """
    ctx = _ctx_with_config(
        tmp_path, f"activated_directives:\n  - {_REAL_DIRECTIVE_STEM}\n"
    )
    monkeypatch.setattr(
        drg_helpers, "load_validated_graph", lambda repo_root: _empty_graph()
    )

    report = run_consistency_check(ctx)

    assert report.coherent is False
    assert f"directive/{_REAL_DIRECTIVE_STEM}" in report.graph_kind_gaps
    assert any(
        f"directive/{_REAL_DIRECTIVE_STEM}" in s
        and "does not survive in the activation-filtered DRG graph" in s
        for s in report.suggestions
    )


# ---------------------------------------------------------------------------
# Unresolvable stem: named verification_errors entry (T007 hardened DoD)
# ---------------------------------------------------------------------------


@pytest.mark.doctrine
def test_unresolvable_stem_names_the_id_in_verification_errors(
    tmp_path: Path,
) -> None:
    """An unknown stem yields a SPECIFIC verification_errors entry naming it.

    Not merely "an entry was appended" or "no exception raised" -- the entry
    must name the exact unresolvable id, distinguishing "could not verify
    graph parity for this id" from a generic failure.
    """
    fake_stem = "totally-fake-directive-zzz"
    ctx = _ctx_with_config(tmp_path, f"activated_directives:\n  - {fake_stem}\n")

    report = run_consistency_check(ctx)

    assert report.coherent is False
    assert any(
        entry.startswith(f"directive/{fake_stem}:")
        for entry in report.verification_errors
    ), f"Expected a 'directive/{fake_stem}:...' entry, got: {report.verification_errors}"


# ---------------------------------------------------------------------------
# Hardened DoD guard: non-drift errors must NOT be silently converted (T007)
# ---------------------------------------------------------------------------


def test_non_drift_error_propagates_not_swallowed_as_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A genuine programming-bug exception during per-stem resolution must
    propagate, never be silently reported as an ordinary drift finding.

    Proves the per-stem catch is narrow (``except UnknownArtifactIdError``),
    never a broad ``except Exception`` -- a broad catch here would let this
    exact scenario masquerade as "just another divergence" in
    ``verification_errors``/``graph_kind_gaps``, defeating the whole point of
    a fail-closed *report* contract (silence would hide a real bug, not
    surface a config problem).
    """
    ctx = _ctx_with_config(
        tmp_path, f"activated_directives:\n  - {_REAL_DIRECTIVE_STEM}\n"
    )

    def _boom(*_args: object, **_kwargs: object) -> str:
        raise TypeError("simulated programming bug, not a config-drift condition")

    monkeypatch.setattr(consistency_check, "resolve_artifact_urn", _boom)

    with pytest.raises(TypeError, match="simulated programming bug"):
        run_consistency_check(ctx)


# ---------------------------------------------------------------------------
# Pre-existing DRG-load fail-closed contract (#2530) survives the re-point
# ---------------------------------------------------------------------------


def test_drg_load_failure_still_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A DRG load/validate failure still surfaces a verification error.

    This is a distinct, structurally different failure mode from the
    per-stem resolution catch above (graph load vs one stem's resolution)
    and stays a broad ``except Exception`` -- collapsing the two would let a
    per-stem programming bug masquerade as a DRG-load failure, or vice
    versa.
    """
    ctx = _ctx_with_config(
        tmp_path, f"activated_directives:\n  - {_REAL_DIRECTIVE_STEM}\n"
    )

    def _raise_corrupt_drg(*_args: object, **_kwargs: object) -> None:
        raise ValueError("simulated corrupt/invalid DRG graph")

    monkeypatch.setattr(drg_helpers, "load_validated_graph", _raise_corrupt_drg)

    report = run_consistency_check(ctx)

    assert report.coherent is False
    assert any(
        "could not verify config<->graph kind parity" in entry.lower()
        for entry in report.verification_errors
    )
