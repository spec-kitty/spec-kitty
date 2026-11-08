"""Anti-drift guard for the ``status.json`` audit shape registry (#6111).

The audit registry's ``status.json`` known-key set MUST cover every top-level key
the snapshot writer can emit — derived from ``StatusSnapshot`` (the single writer
behind ``materialize``), never a hand-rolled second copy that can silently drift.
The hand-rolled copy drifted once already: it lacked ``schema_version``, which
the reducer stamps on every ``materialize`` output since #4786, so
``doctor mission-state --audit`` reported an info-level ``UNKNOWN_SHAPE``
finding for Spec Kitty's own key (~90 on the corpus at the time).

These tests fail loudly the moment the writer grows a key the audit registry
does not know about, so the two can never re-diverge (the ``meta.json`` side
carries the same guard in ``test_shape_registry_writer_parity.py``).
"""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest

from specify_cli.audit.classifiers.status_json import classify_status_json
from specify_cli.audit.shape_registry import KNOWN_TOP_LEVEL_KEYS_BY_ARTIFACT
from specify_cli.status import materialize, seed_scratch_event_log
from specify_cli.status.models import StatusSnapshot

pytestmark = [pytest.mark.fast]

_MISSION_SLUG = "qw6-status-json-shape-probe"


def _seed_event() -> dict[str, object]:
    """Return one canonical ``genesis -> planned`` transition row."""
    return {
        "actor": "tester",
        "at": "2026-11-08T10:00:00+00:00",
        "event_id": "01JQZ00000000000000000001",
        "execution_mode": "worktree",
        "force": False,
        "from_lane": "genesis",
        "mission_slug": _MISSION_SLUG,
        "reason": None,
        "review_ref": None,
        "to_lane": "planned",
        "wp_id": "WP01",
    }


def test_freshly_reduced_status_json_audits_with_no_unknown_shape(tmp_path: Path) -> None:
    """A reducer-written ``status.json`` carries no key the audit calls unknown (#6111).

    ``materialize`` is the writer; ``classify_status_json`` is the audit read.
    The reducer stamps ``schema_version`` on the snapshot, so a snapshot the
    audit calls malformed is the audit drifting from its own writer.
    """
    mission_dir = tmp_path / _MISSION_SLUG
    mission_dir.mkdir()
    seed_scratch_event_log(mission_dir, (json.dumps(_seed_event()) + "\n").encode("utf-8"))
    materialize(mission_dir)

    written = json.loads((mission_dir / "status.json").read_text(encoding="utf-8"))
    assert "schema_version" in written, "the reducer no longer stamps schema_version; re-derive the audit keys"

    findings = [finding for finding in classify_status_json(mission_dir) if finding.code == "UNKNOWN_SHAPE"]
    assert findings == [], "the audit reports the reducer's own keys as UNKNOWN_SHAPE: " + ", ".join(finding.detail for finding in findings)


def test_every_snapshot_writer_key_is_a_known_audit_key() -> None:
    """Snapshot writer keys ⊆ audit known keys — the anti-drift invariant."""
    audit_keys = KNOWN_TOP_LEVEL_KEYS_BY_ARTIFACT["status.json"]
    writer_keys = frozenset(field_.name for field_ in fields(StatusSnapshot))
    missing = writer_keys - audit_keys
    assert missing == set(), f"status.json writer keys missing from the audit shape registry (would be reported as UNKNOWN_SHAPE): {sorted(missing)}"
