"""ATDD: pending-batch-a fail-closed routing for meta.json corruption (FR-007 / #3162).

Exercises the REAL entry points of every ``pending-batch-a`` site under
``src/specify_cli/`` — not ``load_meta``/``load_meta_fail_closed`` directly —
so this test is genuinely red if a routed call site regresses back to the
unwrapped ``mission_metadata.load_meta`` call (a raw ``ValueError`` escaping
to the caller). Companion to ``test_meta_fail_closed_batch_a.py`` (which
covered WP08's owned subsystems); this file covers the remainder that neither
WP08 nor WP09 ever claimed, routed by the #3162 pass:

- ``bulk_edit/gate.py`` — typed raise.
- ``context/resolver.py`` (``_read_meta_json``) — typed raise.
- ``decisions/service.py`` (``_resolve_mission_id``) — typed read failure
  wrapped into the domain's ``DecisionError(MISSION_NOT_FOUND)``.
- ``missions/_read_path_resolver.py`` (``read_primary_meta``) — typed raise.
- ``missions/_resolve_planning_branch.py`` (``load_mission_target_branch``) —
  typed read failure wrapped into ``PlanningBranchResolutionFailed``.
- ``upgrade/feature_meta.py`` (``load_feature_meta``) — degrade to ``None``.

The ``pending-batch-a`` sites under ``src/mission_runtime/`` and
``src/runtime/next/`` are covered by sibling files named after this one in
``tests/mission_runtime/`` and ``tests/runtime/`` — split out there (PR #4008
fix round) because CI module shards select tests by directory and top-level
``tests/specify_cli/`` is in no module's ``test_dirs``, so those critical-path
roots' corrupt-meta arms were never executed in CI from here.

Both corrupt-meta and non-dict-meta cases are driven — the two shapes
``mission_metadata._parse_meta_text`` treats as "malformed" (json.JSONDecodeError
and non-object top level).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.core.paths import MissionMetaReadError

pytestmark = [pytest.mark.integration]

#: Corrupt: truncated, syntactically invalid JSON — genuinely unparseable.
_CORRUPT_META = '{"mission_id": "01JABCDEFGHJKMNPQRSTVWXYZ", '
#: Non-dict: parses cleanly but the top level is a list, not an object.
_NON_DICT_META = "[1, 2, 3]"

_SLUG = "probe-mission"

_CASES = [_CORRUPT_META, _NON_DICT_META]
_CASE_IDS = ["corrupt-json", "non-dict-json"]


def _seed(root: Path, meta_text: str) -> Path:
    """Create a minimal mission directory with a raw ``meta.json`` body."""
    mission_dir = root / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(meta_text, encoding="utf-8")
    return mission_dir


# ---------------------------------------------------------------------------
# bulk_edit/gate.py — typed raise (the gate must not crash raw).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("meta_text", _CASES, ids=_CASE_IDS)
def test_is_bulk_edit_mission_raises_typed(tmp_path: Path, meta_text: str) -> None:
    from specify_cli.bulk_edit.gate import _is_bulk_edit_mission

    mission_dir = _seed(tmp_path, meta_text)
    with pytest.raises(MissionMetaReadError, match="fail-closed"):
        _is_bulk_edit_mission(mission_dir)


@pytest.mark.parametrize("meta_text", _CASES, ids=_CASE_IDS)
def test_ensure_occurrence_classification_ready_raises_typed(tmp_path: Path, meta_text: str) -> None:
    from specify_cli.bulk_edit.gate import ensure_occurrence_classification_ready

    mission_dir = _seed(tmp_path, meta_text)
    with pytest.raises(MissionMetaReadError, match="fail-closed"):
        ensure_occurrence_classification_ready(mission_dir)


# ---------------------------------------------------------------------------
# context/resolver.py — the missing-file guard is preserved; malformed
# propagates the typed error instead of a raw ValueError.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("meta_text", _CASES, ids=_CASE_IDS)
def test_context_read_meta_json_raises_typed(tmp_path: Path, meta_text: str) -> None:
    from specify_cli.context.errors import MissingIdentityError
    from specify_cli.context.resolver import _read_meta_json

    mission_dir = _seed(tmp_path, meta_text)
    with pytest.raises(MissionMetaReadError, match="fail-closed"):
        _read_meta_json(mission_dir, tmp_path)
    # Missing meta.json keeps its own guard: MissingIdentityError, not the
    # typed read error (a missing file is field-absent, not a read failure).
    empty_root = tmp_path / "elsewhere"
    empty_root.mkdir()
    bare_dir = empty_root / "kitty-specs" / "bare-mission"
    bare_dir.mkdir(parents=True)
    with pytest.raises(MissingIdentityError, match="meta.json not found"):
        _read_meta_json(bare_dir, empty_root)


# ---------------------------------------------------------------------------
# decisions/service.py — typed read failure wraps into the domain error.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("meta_text", _CASES, ids=_CASE_IDS)
def test_decisions_resolve_mission_id_wraps_typed_into_domain(tmp_path: Path, meta_text: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The service's own read wraps the typed failure into MISSION_NOT_FOUND.

    ``_primary_metadata_dir`` (the dir ``_resolve_mission_id`` reads ``meta.json``
    from) is pinned to the seeded dir to isolate the service's own read arm
    deterministically; driven end-to-end below, the placement seam's
    readers degrade on corrupt meta by design and the same service read fires
    through the real path.
    """
    from specify_cli.decisions import service as decisions_service
    from specify_cli.decisions.models import DecisionErrorCode
    from specify_cli.decisions.service import DecisionError

    mission_dir = _seed(tmp_path, meta_text)
    monkeypatch.setattr(decisions_service, "_primary_metadata_dir", lambda repo_root, slug, *, owned=None: mission_dir)
    with pytest.raises(DecisionError) as excinfo:
        decisions_service._resolve_mission_id(tmp_path, _SLUG)
    assert excinfo.value.code == DecisionErrorCode.MISSION_NOT_FOUND
    assert excinfo.value.details == {"mission_slug": _SLUG}
    assert not isinstance(excinfo.value, ValueError)


@pytest.mark.parametrize("meta_text", _CASES, ids=_CASE_IDS)
def test_decisions_resolve_mission_id_end_to_end_never_raw_valueerror(tmp_path: Path, meta_text: str) -> None:
    """End-to-end (no seam patching): corrupt meta wraps into MISSION_NOT_FOUND.

    The placement seam's own readers degrade on corrupt meta by design (the
    husk gate and ``_stored_topology_best_effort``), so the service's own
    routed read is the one that fires — wrapping the typed
    ``MissionMetaReadError`` into the domain's ``DecisionError(MISSION_NOT_
    FOUND)``. Never a raw ``ValueError`` on this path, which is the NFR-003
    contract the #3162 routing establishes.
    """
    from specify_cli.decisions.models import DecisionErrorCode
    from specify_cli.decisions.service import DecisionError, _resolve_mission_id

    _seed(tmp_path, meta_text)
    with pytest.raises(DecisionError) as excinfo:
        _resolve_mission_id(tmp_path, _SLUG)
    assert excinfo.value.code == DecisionErrorCode.MISSION_NOT_FOUND
    assert not isinstance(excinfo.value, ValueError)


# ---------------------------------------------------------------------------
# missions/_read_path_resolver.py — typed raise at the shared read primitive.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("meta_text", _CASES, ids=_CASE_IDS)
def test_read_primary_meta_raises_typed(tmp_path: Path, meta_text: str) -> None:
    from specify_cli.missions._read_path_resolver import read_primary_meta

    _seed(tmp_path, meta_text)
    with pytest.raises(MissionMetaReadError, match="fail-closed"):
        read_primary_meta(tmp_path, _SLUG)


# ---------------------------------------------------------------------------
# missions/_resolve_planning_branch.py — typed read failure wraps into the
# domain error with the --target-branch escape hatch preserved.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("meta_text", _CASES, ids=_CASE_IDS)
def test_load_mission_target_branch_wraps_typed_into_domain(tmp_path: Path, meta_text: str) -> None:
    from specify_cli.missions._resolve_planning_branch import (
        PlanningBranchResolutionFailed,
        load_mission_target_branch,
    )

    mission_dir = _seed(tmp_path, meta_text)
    with pytest.raises(PlanningBranchResolutionFailed, match="unreadable"):
        load_mission_target_branch(mission_dir)


def test_load_mission_target_branch_missing_keeps_not_found_diagnostic(
    tmp_path: Path,
) -> None:
    """A missing meta.json keeps its own diagnostic (not the unreadable one)."""
    from specify_cli.missions._resolve_planning_branch import (
        PlanningBranchResolutionFailed,
        load_mission_target_branch,
    )

    mission_dir = tmp_path / "kitty-specs" / "absent-mission"
    mission_dir.mkdir(parents=True)
    with pytest.raises(PlanningBranchResolutionFailed, match="not found"):
        load_mission_target_branch(mission_dir)


# ---------------------------------------------------------------------------
# upgrade/feature_meta.py — degrade site: unreadable meta reads as "needs
# repair" (None), same as missing.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("meta_text", _CASES, ids=_CASE_IDS)
def test_load_feature_meta_degrades_to_none(tmp_path: Path, meta_text: str) -> None:
    from specify_cli.upgrade.feature_meta import load_feature_meta

    mission_dir = _seed(tmp_path, meta_text)
    assert load_feature_meta(mission_dir) is None
