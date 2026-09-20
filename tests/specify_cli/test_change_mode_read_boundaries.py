"""Behavior-preservation enumeration for every ``change_mode`` reader (FR-012 / NFR-001).

The durable fix (WP03) makes normalizing a legacy ``change_mode`` value to
*absent* genuinely behavior-preserving. That only holds if **every** production
reader of ``change_mode`` treats a legacy value (any string that is not
``"bulk_edit"``) identically to the field being absent (``None``). The single
canonical check is ``change_mode == "bulk_edit"``; any reader that instead keys
on implicit *presence* (``is not None``) silently forks behavior between a
legacy value and absence, which is exactly the ``implement.py:1340`` defect this
work package closes.

This module enumerates each reader and asserts ``observe(legacy) == observe(absent)``
at each one. Before the WP03 fix the ``implement._run_bulk_edit_gate_and_inference``
probe is RED (a legacy value short-circuits before the inference scan, while an
absent value runs it and can ``typer.Exit(1)``); after the fix every probe is
GREEN.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from specify_cli.bulk_edit.gate import GateResult, _is_bulk_edit_mission

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# A plausible legacy ``change_mode`` value: any historical string that is not the
# one canonical token. Reads are permissive (``VALID_CHANGE_MODES == {"bulk_edit"}``
# is only enforced on writes), so such a value can still live in an old meta.json
# or, before WP03's gate collapse, ride through ``GateResult.change_mode``.
LEGACY_CHANGE_MODE = "regular"

# Enough bulk-edit signal for ``scan_spec_file`` to fire (a HIGH-weight phrase),
# so "ran the inference scan" is observably different from "skipped it".
_TRIGGERING_SPEC = "This mission will rename all occurrences of the old term across the code.\n"


def _base_meta(change_mode: str | None) -> dict[str, object]:
    meta: dict[str, object] = {
        "slug": "m",
        "mission_slug": "m",
        "friendly_name": "T",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01",
    }
    if change_mode is not None:
        meta["change_mode"] = change_mode
    return meta


def _write_meta(feature_dir: Path, change_mode: str | None) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(_base_meta(change_mode)), encoding="utf-8")


def _slug(change_mode: str | None) -> str:
    return change_mode if change_mode is not None else "absent"


# ---------------------------------------------------------------------------
# Reader probes: each returns an observable outcome for a given change_mode.
# ---------------------------------------------------------------------------


def _observe_gate_is_bulk_edit_mission(tmp_path: Path, change_mode: str | None) -> object:
    """Reader ``bulk_edit/gate.py:63`` — ``meta.get("change_mode") == "bulk_edit"``."""
    feature_dir = tmp_path / f"is_bulk_edit_{_slug(change_mode)}"
    _write_meta(feature_dir, change_mode)
    return _is_bulk_edit_mission(feature_dir)


def _observe_runtime_bridge_occurrence_gate(tmp_path: Path, change_mode: str | None) -> object:
    """Reader ``runtime/next/runtime_bridge.py:921`` — ``_occurrence_gate_failures``
    consumes ``GateResult.errors`` only, never ``.change_mode``."""
    from runtime.next.runtime_bridge import _occurrence_gate_failures

    feature_dir = tmp_path / f"occ_gate_{_slug(change_mode)}"
    _write_meta(feature_dir, change_mode)
    return _occurrence_gate_failures(feature_dir)


def _observe_workflow_executor_review_gate(tmp_path: Path, change_mode: str | None) -> object:
    """Reader ``workflow_executor.py:1609`` — ``gate_result.change_mode == "bulk_edit"``
    decides whether per-file diff compliance is enforced."""
    from specify_cli.cli.commands.agent import workflow_executor as wfx

    gate = GateResult(passed=True, change_mode=change_mode)
    dispatched: dict[str, bool] = {}

    fake_wf = MagicMock()
    fake_wf._enforce_bulk_edit_diff_compliance = MagicMock(side_effect=lambda **_kwargs: dispatched.setdefault("called", True))

    with (
        patch(
            "specify_cli.bulk_edit.gate.ensure_occurrence_classification_ready",
            return_value=gate,
        ),
        patch.object(wfx, "_wf", return_value=fake_wf),
    ):
        wfx.review_enforce_bulk_edit_gate(
            feature_dir=tmp_path,
            main_repo_root=tmp_path,
            mission_slug="m",
            target_branch="main",
            review_workspace=MagicMock(),
        )
    return dispatched.get("called", False)


def _observe_implement_gate_and_inference(tmp_path: Path, change_mode: str | None) -> object:
    """Reader ``implement.py:1340`` (the counterexample) — decides whether the
    bulk-edit inference scan runs. A legacy value must behave like absence: both
    fall through to the inference scan (which ``typer.Exit(1)``s on an
    un-acknowledged triggered spec)."""
    from specify_cli.cli.commands.implement import _run_bulk_edit_gate_and_inference

    feature_dir = tmp_path / f"impl_{_slug(change_mode)}"
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "spec.md").write_text(_TRIGGERING_SPEC, encoding="utf-8")
    wp_file = feature_dir / "WP01-work.md"
    wp_file.write_text(
        "---\nwork_package_id: WP01\ndependencies: []\nexecution_mode: code_change\nowned_files:\n  - src/foo/**\nauthoritative_surface: src/foo/\n---\n# WP01\n",
        encoding="utf-8",
    )

    gate = GateResult(passed=True, change_mode=change_mode)
    with patch(
        "specify_cli.bulk_edit.gate.ensure_occurrence_classification_ready",
        return_value=gate,
    ):
        try:
            _run_bulk_edit_gate_and_inference(
                feature_dir,
                wp_file,
                "m",
                "WP01",
                acknowledge_not_bulk_edit=False,
            )
        except typer.Exit:
            return "inference_scan_ran"
    return "inference_scan_skipped"


_READER_PROBES: list[tuple[str, Callable[[Path, str | None], object]]] = [
    ("bulk_edit.gate._is_bulk_edit_mission", _observe_gate_is_bulk_edit_mission),
    ("runtime_bridge._occurrence_gate_failures", _observe_runtime_bridge_occurrence_gate),
    ("workflow_executor.review_enforce_bulk_edit_gate", _observe_workflow_executor_review_gate),
    ("implement._run_bulk_edit_gate_and_inference", _observe_implement_gate_and_inference),
]


@pytest.mark.parametrize(
    "reader_name, probe",
    _READER_PROBES,
    ids=[name for name, _ in _READER_PROBES],
)
def test_change_mode_reader_treats_legacy_value_like_absent(
    tmp_path: Path,
    reader_name: str,
    probe: Callable[[Path, str | None], object],
) -> None:
    """NFR-001/FR-012: every ``change_mode`` reader is behavior-identical for a
    legacy value and for absence, so normalizing legacy → absent is
    behavior-preserving."""
    legacy_outcome = probe(tmp_path, LEGACY_CHANGE_MODE)
    absent_outcome = probe(tmp_path, None)
    assert legacy_outcome == absent_outcome, (
        f"{reader_name} forks behavior between a legacy change_mode "
        f"({LEGACY_CHANGE_MODE!r} -> {legacy_outcome!r}) and absence "
        f"(None -> {absent_outcome!r}); align it to the canonical "
        f'`change_mode == "bulk_edit"` check.'
    )
