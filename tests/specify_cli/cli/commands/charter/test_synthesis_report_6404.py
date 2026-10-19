"""Report-shaping tests for stripped legacy edges (#6404)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from charter.activation.synthesizer.reconcile import NodeOrEdgeRef, ReconciliationDelta
from specify_cli.cli.commands.charter import _synthesis

pytestmark = pytest.mark.fast

LEGACY = NodeOrEdgeRef(
    ref_kind="edge",
    urn="directive:a--applies-->tactic:b",
    backing_artifact=None,
    reason="legacy applies edge replaced by suggests",
)
ORPHAN = NodeOrEdgeRef(ref_kind="node", urn="tactic:gone", backing_artifact=None)
BACKED = NodeOrEdgeRef(ref_kind="node", urn="tactic:kept", backing_artifact="doctrine/tactics/kept.tactic.yaml")


def _result() -> Any:
    return SimpleNamespace(
        effective_adapter_id="fixture",
        effective_adapter_version="1",
        target_kind="tactic",
        target_slug="x",
        inputs_hash="h",
    )


def test_orphan_check_excludes_stripped_legacy_edge_without_backing_artifact() -> None:
    delta = ReconciliationDelta(removable=(LEGACY,))
    assert _synthesis._orphaned_removals(delta) == ()


def test_orphan_check_still_flags_real_orphan_next_to_legacy_edge() -> None:
    delta = ReconciliationDelta(removable=(LEGACY, ORPHAN, BACKED))
    assert _synthesis._orphaned_removals(delta) == (ORPHAN,)


def test_real_run_json_reports_stripped_legacy_edges(capsys: pytest.CaptureFixture[str]) -> None:
    delta = ReconciliationDelta(removable=(LEGACY, BACKED))
    result = _result()
    result.reconciliation = delta
    from pathlib import Path

    _synthesis._emit_real_run_report(
        json_output=True,
        result=result,
        written_artifacts_real=[],
        warnings_collected=[],
        prune=False,
        repo_root=Path("."),
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["stripped_legacy_edges"] == [
        {
            "ref_kind": "edge",
            "urn": LEGACY.urn,
            "backing_artifact": None,
            "reason": LEGACY.reason,
        }
    ]


def test_dry_run_labels_legacy_edges_as_replaced_not_prune(monkeypatch: pytest.MonkeyPatch) -> None:
    printed: list[str] = []
    monkeypatch.setattr(_synthesis.console, "print", lambda msg="", *a, **k: printed.append(str(msg)))
    delta = ReconciliationDelta(removable=(LEGACY, BACKED))
    _synthesis._emit_dry_run_report(
        json_output=False,
        adapter_name="fixture",
        syn_adapter=None,
        warnings_collected=[],
        staged_files=[],
        written_artifacts_dr=[],
        delta=delta,
    )
    text = "\n".join(printed)
    legacy_idx = text.index("Replaced legacy edges")
    prune_idx = text.index("would run under --prune")
    assert text.index(LEGACY.urn) < prune_idx
    assert legacy_idx < text.index(LEGACY.urn)
    assert text.index(BACKED.urn) > prune_idx


def test_dry_run_only_legacy_edges_has_no_prune_section(monkeypatch: pytest.MonkeyPatch) -> None:
    printed: list[str] = []
    monkeypatch.setattr(_synthesis.console, "print", lambda msg="", *a, **k: printed.append(str(msg)))
    _synthesis._emit_dry_run_report(
        json_output=False,
        adapter_name="fixture",
        syn_adapter=None,
        warnings_collected=[],
        staged_files=[],
        written_artifacts_dr=[],
        delta=ReconciliationDelta(removable=(LEGACY,)),
    )
    text = "\n".join(printed)
    assert "would run under --prune" not in text
    assert "No divergence" not in text
