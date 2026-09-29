"""Focused per-helper tests for the ``_identity_audit`` cluster (WP04, #2059).

Covers each decomposed helper of the ``identity`` command (scope resolution,
dup/ambig rendering, ``--fail-on`` gating, JSON payload build) and the topology
collectors (stored-topology read, row collection, human render), exercising the
exit-code contract of both entrypoints.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer

from specify_cli.cli.commands import _identity_audit as ia

pytestmark = [pytest.mark.fast]
from specify_cli.status import IdentityState


def _state(slug: str, state: str, mission_id: str | None = "01ABC") -> IdentityState:
    return IdentityState(
        path=Path("/tmp") / slug,
        slug=slug,
        mission_id=mission_id,
        mission_number=1 if state == "assigned" else None,
        state=state,  # type: ignore[arg-type]
    )


class _StubSeam:
    """Stand-in for ``mission_runtime.PlacementSeam`` -- WP05 read-routing tests.

    ``_identity_audit`` now calls ``placement_seam(repo_root, mission).read_dir(kind)``
    (routed through the kind-aware seam, FR-001/NFR-001) instead of the retired
    kind-blind ``resolve_feature_dir_for_mission``. Tests that previously stubbed
    the retired resolver directly now stub ``placement_seam`` to return this
    fixed-target fake, which ignores the requested ``kind`` (these tests do not
    exercise kind-branching -- only "does the resolved dir exist").
    """

    def __init__(self, target: Path) -> None:
        self._target = target

    def read_dir(self, kind: object) -> Path:
        return self._target


def _stub_placement_seam(monkeypatch: pytest.MonkeyPatch, target: Path) -> None:
    monkeypatch.setattr(ia, "placement_seam", lambda *_a, **_kw: _StubSeam(target))


# --- _scope_prefixes ---------------------------------------------------------


def test_scope_prefixes_matches_prefix() -> None:
    dup = {"083": [_state("083-a", "assigned")]}
    assert ia._scope_prefixes(dup, "083-foo") == dup


def test_scope_prefixes_no_numeric_prefix() -> None:
    dup = {"083": [_state("083-a", "assigned")]}
    assert ia._scope_prefixes(dup, "my-mission-slug") == {}


def test_scope_prefixes_prefix_absent() -> None:
    dup = {"083": [_state("083-a", "assigned")]}
    assert ia._scope_prefixes(dup, "099-foo") == {}


# --- _scope_to_mission -------------------------------------------------------


def test_scope_to_mission_matches_existing_state(tmp_path: Path) -> None:
    states = [_state("083-a", "assigned"), _state("084-b", "legacy")]
    result = ia._scope_to_mission(tmp_path, states, "083-a")
    assert [s.slug for s in result] == ["083-a"]


def test_scope_to_mission_unmatched_resolves_existing_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # When the slug is not in all_states but a matching dir exists, the mission
    # is classified directly. Stub the resolver + classifier to the dir.
    target = tmp_path / "kitty-specs" / "084-b"
    target.mkdir(parents=True)
    _stub_placement_seam(monkeypatch, target)
    import specify_cli.status as status_mod

    monkeypatch.setattr(status_mod, "classify_mission", lambda d: _state("084-b", "legacy"))
    states = [_state("083-a", "assigned")]
    result = ia._scope_to_mission(tmp_path, states, "084-b")
    assert [s.slug for s in result] == ["084-b"]


def test_scope_to_mission_unmatched_missing_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Resolver yields a non-existent path → no scoped states.
    _stub_placement_seam(monkeypatch, tmp_path / "nope")
    states = [_state("083-a", "assigned")]
    result = ia._scope_to_mission(tmp_path, states, "999-nope")
    assert result == []


# --- _compute_fail_on --------------------------------------------------------


def test_compute_fail_on_empty() -> None:
    states = [_state("a", "assigned")]
    fail_on_states, triggered = ia._compute_fail_on(None, states)
    assert fail_on_states == set()
    assert triggered is False


def test_compute_fail_on_triggered() -> None:
    states = [_state("a", "legacy")]
    fail_on_states, triggered = ia._compute_fail_on("legacy,orphan", states)
    assert fail_on_states == {"legacy", "orphan"}
    assert triggered is True


def test_compute_fail_on_not_triggered() -> None:
    states = [_state("a", "assigned")]
    _states, triggered = ia._compute_fail_on("legacy", states)
    assert triggered is False


# --- _build_identity_json ----------------------------------------------------


def test_build_identity_json_shape() -> None:
    states = [_state("083-a", "assigned")]
    summary = {"counts": {"assigned": 1}}
    payload = ia._build_identity_json(states, summary, {}, {}, False)
    assert payload["summary"] == {"assigned": 1}
    assert payload["fail_on_triggered"] is False
    assert payload["missions"][0]["slug"] == "083-a"
    assert payload["duplicate_prefixes"] == {}
    assert payload["ambiguous_selectors"] == {}


# --- render helpers (smoke: must not crash, cover branches) ------------------


def test_print_dup_and_ambig_all_branches(capsys: pytest.CaptureFixture[str]) -> None:
    dup = {"083": [_state("083-a", "assigned")]}
    ambig = {"a": [_state("083-a", "assigned"), _state("084-a", "legacy")]}
    ia._print_dup_and_ambig(dup, ambig)
    ia._print_dup_and_ambig({}, {})  # clean branch


def test_print_identity_human_full(capsys: pytest.CaptureFixture[str]) -> None:
    states = [_state("083-a", "legacy")]
    summary = {
        "counts": {"legacy": 1},
        "legacy_paths": ["kitty-specs/083-a"],
        "orphan_paths": ["kitty-specs/084-b"],
    }
    ia._print_identity_human(states, {}, {}, summary, {"legacy"}, True, "legacy")


# --- _read_stored_topology ---------------------------------------------------


def test_read_stored_topology_missing_meta(tmp_path: Path) -> None:
    row = ia._read_stored_topology(tmp_path / "m")
    assert row["topology"] is None
    assert row["error"] == "meta.json not found"


def test_read_stored_topology_valid(tmp_path: Path) -> None:
    d = tmp_path / "083-a"
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"topology": "lanes", "flattened": True}), encoding="utf-8")
    row = ia._read_stored_topology(d)
    assert row["topology"] == "lanes"
    assert row["flattened"] is True
    assert row["error"] is None


def test_read_stored_topology_corrupt(tmp_path: Path) -> None:
    d = tmp_path / "083-a"
    d.mkdir()
    (d / "meta.json").write_text("not json", encoding="utf-8")
    row = ia._read_stored_topology(d)
    assert row["topology"] is None
    assert "corrupt json" in (row["error"] or "")


def test_read_stored_topology_non_object(tmp_path: Path) -> None:
    d = tmp_path / "083-a"
    d.mkdir()
    (d / "meta.json").write_text("[1, 2, 3]", encoding="utf-8")
    row = ia._read_stored_topology(d)
    assert "corrupt json" in (row["error"] or "")


def _write_lanes(feature_dir: Path, lanes: list[dict[str, object]]) -> None:
    manifest = {
        "version": 1,
        "mission_slug": feature_dir.name,
        "mission_branch": f"kitty/mission-{feature_dir.name}",
        "target_branch": "main",
        "lanes": lanes,
        "computed_at": "2026-09-28T00:00:00+00:00",
        "computed_from": "dependency_graph+ownership",
    }
    (feature_dir / "lanes.json").write_text(json.dumps(manifest), encoding="utf-8")


# --- T014 (#5100 IC-02): SINGLE_BRANCH_CODE_LANES_UNMIGRATED finding --------


def test_read_stored_topology_flags_single_branch_with_code_lane(tmp_path: Path) -> None:
    """Positive: single_branch + a code lane in lanes.json flags the finding."""
    d = tmp_path / "083-a"
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"topology": "single_branch"}), encoding="utf-8")
    _write_lanes(d, [{"lane_id": "lane-a", "wp_ids": ["WP01"]}])

    row = ia._read_stored_topology(d)

    assert row["finding"] == "SINGLE_BRANCH_CODE_LANES_UNMIGRATED"


def test_read_stored_topology_clean_single_branch_has_no_finding(tmp_path: Path) -> None:
    """Negative control: single_branch + only lane-planning -> no finding."""
    d = tmp_path / "083-a"
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"topology": "single_branch"}), encoding="utf-8")
    _write_lanes(d, [{"lane_id": "lane-planning", "wp_ids": ["WP01"]}])

    row = ia._read_stored_topology(d)

    assert row["finding"] is None


def test_read_stored_topology_single_branch_no_lanes_json_has_no_finding(tmp_path: Path) -> None:
    """Negative control: single_branch with no lanes.json at all -> no finding."""
    d = tmp_path / "083-a"
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"topology": "single_branch"}), encoding="utf-8")

    row = ia._read_stored_topology(d)

    assert row["finding"] is None


def test_read_stored_topology_non_single_branch_topology_has_no_finding(tmp_path: Path) -> None:
    """A ``lanes`` (or any non-single_branch) mission is never flagged, even with code lanes."""
    d = tmp_path / "083-a"
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"topology": "lanes"}), encoding="utf-8")
    _write_lanes(d, [{"lane_id": "lane-a", "wp_ids": ["WP01"]}])

    row = ia._read_stored_topology(d)

    assert row["finding"] is None


def _write_legacy_feature_slug_lanes(feature_dir: Path) -> None:
    """A legacy manifest keyed ``feature_slug`` (no ``mission_slug``), one code lane.

    Mirrors ``064-complete-mission-identity-cutover``'s real on-disk shape --
    ``read_lanes_json`` rejects it with ``CorruptLanesError``.
    """
    manifest = {
        "version": 1,
        "feature_slug": feature_dir.name,
        "mission_id": feature_dir.name,
        "mission_branch": f"kitty/mission-{feature_dir.name}",
        "target_branch": "main",
        "lanes": [{"lane_id": "lane-a", "wp_ids": [f"WP{n:02d}" for n in range(1, 10)]}],
        "computed_at": "2026-04-06T00:00:00+00:00",
        "computed_from": "dependency_graph+ownership",
    }
    (feature_dir / "lanes.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_read_stored_topology_unreadable_lanes_flags_lanes_manifest_unreadable(tmp_path: Path) -> None:
    """Review cycle-1 blocker: an unreadable lanes.json is NEVER reported as clean.

    A stored single_branch mission whose lanes.json exists but the canonical
    reader rejects it (the 064 repro) must surface a distinct, non-None
    finding -- never fold silently into "no finding", which would let a
    genuine Invariant T-1 violation report as clean.
    """
    d = tmp_path / "064-complete-mission-identity-cutover"
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"topology": "single_branch"}), encoding="utf-8")
    _write_legacy_feature_slug_lanes(d)

    row = ia._read_stored_topology(d)

    assert row["finding"] == "LANES_MANIFEST_UNREADABLE"
    assert row["finding"] != "SINGLE_BRANCH_CODE_LANES_UNMIGRATED"


# --- Operator decision (PR #5398 handoff): doctor skips TERMINAL (archived) --
# missions. A completed single_branch + code-lane mission is never run again, so
# reporting SINGLE_BRANCH_CODE_LANES_UNMIGRATED on it is pointless churn on a
# frozen dossier. The skip keys on the same canonical completion predicate
# (:func:`specify_cli.status.lifecycle.is_mission_completed`) the re-stamp
# migration uses, so the finding and the migration's selection never drift
# apart. A LIVE mission is still flagged -- the guard still applies to it.


def test_read_stored_topology_archived_single_branch_code_lane_has_no_finding(tmp_path: Path) -> None:
    """A completed (merged) single_branch + code-lane mission produces no finding."""
    d = tmp_path / "archived-sb"
    d.mkdir()
    (d / "meta.json").write_text(
        json.dumps({"topology": "single_branch", "merged_at": "2026-09-25T14:19:52.098680+00:00"}),
        encoding="utf-8",
    )
    _write_lanes(d, [{"lane_id": "lane-a", "wp_ids": ["WP01"]}])

    row = ia._read_stored_topology(d)

    assert row["finding"] is None
    assert row["remedy"] is None


def test_read_stored_topology_live_single_branch_code_lane_still_flags(tmp_path: Path) -> None:
    """Twin control: a LIVE (un-merged, non-terminal) mission is still flagged."""
    d = tmp_path / "live-sb"
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"topology": "single_branch"}), encoding="utf-8")
    _write_lanes(d, [{"lane_id": "lane-a", "wp_ids": ["WP01"]}])

    row = ia._read_stored_topology(d)

    assert row["finding"] == "SINGLE_BRANCH_CODE_LANES_UNMIGRATED"


# --- _collect_topology_rows --------------------------------------------------


def test_collect_topology_rows_no_specs_dir(tmp_path: Path) -> None:
    assert ia._collect_topology_rows(tmp_path, None) == []


def test_collect_topology_rows_all(tmp_path: Path) -> None:
    specs = tmp_path / "kitty-specs"
    specs.mkdir()
    for slug in ("083-a", "084-b"):
        d = specs / slug
        d.mkdir()
        (d / "meta.json").write_text(json.dumps({"topology": "single"}), encoding="utf-8")
    rows = ia._collect_topology_rows(tmp_path, None)
    assert {r["slug"] for r in rows} == {"083-a", "084-b"}


def test_print_topology_human_smoke() -> None:
    rows = [
        {"slug": "083-a", "topology": "lanes", "flattened": True, "error": None},
        {"slug": "084-b", "topology": None, "flattened": None, "error": None},
    ]
    ia._print_topology_human(rows)


# --- entrypoints: exit-code contract -----------------------------------------


def test_run_identity_audit_mission_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status as status_mod

    monkeypatch.setattr(status_mod, "audit_repo", lambda *_a: [])
    # Resolver yields a non-existent dir → scoped is empty → exit(1).
    _stub_placement_seam(monkeypatch, tmp_path / "nope")
    with pytest.raises(typer.Exit) as exc:
        ia.run_identity_audit(tmp_path, False, "999-nope", None)
    assert exc.value.exit_code == 1


def test_run_identity_audit_json_fail_on_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status as status_mod

    states = [_state("083-a", "legacy")]
    monkeypatch.setattr(status_mod, "audit_repo", lambda *_a: states)
    monkeypatch.setattr(status_mod, "find_duplicate_prefixes", lambda *_a: {})
    monkeypatch.setattr(status_mod, "find_ambiguous_selectors", lambda *_a: {})
    monkeypatch.setattr(status_mod, "summarize", lambda *_a: {"counts": {"legacy": 1}})
    with pytest.raises(typer.Exit) as exc:
        ia.run_identity_audit(tmp_path, True, None, "legacy")
    assert exc.value.exit_code == 1


def test_run_identity_audit_human_clean_exits_0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status as status_mod

    states = [_state("083-a", "assigned")]
    monkeypatch.setattr(status_mod, "audit_repo", lambda *_a: states)
    monkeypatch.setattr(status_mod, "find_duplicate_prefixes", lambda *_a: {})
    monkeypatch.setattr(status_mod, "find_ambiguous_selectors", lambda *_a: {})
    monkeypatch.setattr(
        status_mod,
        "summarize",
        lambda *_a: {"counts": {"assigned": 1}, "legacy_paths": [], "orphan_paths": []},
    )
    with pytest.raises(typer.Exit) as exc:
        ia.run_identity_audit(tmp_path, False, None, None)
    assert exc.value.exit_code == 0


def test_run_topology_audit_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "kitty-specs").mkdir()
    # Resolver yields a non-existent dir → no rows → exit(1).
    _stub_placement_seam(monkeypatch, tmp_path / "nope")
    with pytest.raises(typer.Exit) as exc:
        ia.run_topology_audit(tmp_path, False, "999-nope")
    assert exc.value.exit_code == 1


def test_run_topology_audit_json_returns_clean(tmp_path: Path) -> None:
    specs = tmp_path / "kitty-specs"
    specs.mkdir()
    d = specs / "083-a"
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"topology": "single"}), encoding="utf-8")
    # JSON path returns (no Exit) for the all-missions report.
    ia.run_topology_audit(tmp_path, True, None)


def test_run_topology_audit_human(tmp_path: Path) -> None:
    specs = tmp_path / "kitty-specs"
    specs.mkdir()
    d = specs / "083-a"
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"topology": "lanes"}), encoding="utf-8")
    ia.run_topology_audit(tmp_path, False, None)


def _seed_topology_mission(root: Path, slug: str, *, lanes: list[dict[str, object]] | None, legacy: bool = False) -> None:
    d = root / "kitty-specs" / slug
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({"topology": "single_branch"}), encoding="utf-8")
    if legacy:
        _write_legacy_feature_slug_lanes(d)
    elif lanes is not None:
        _write_lanes(d, lanes)


_RESTAMP_REMEDY = "spec-kitty migrate backfill-topology --restamp-single-branch"
# Probed end to end in a clone: `finalize-tasks` REFUSES a corrupt lanes.json, so the
# honest remedy is restore-from-git, or delete + rebuild (finalize-tasks before any
# WP starts; `doctor mission-state --fix` once execution has begun).
_UNREADABLE_RESTORE = "git checkout <ref> -- kitty-specs/084-b/lanes.json"
_UNREADABLE_REBUILD_PLANNED = "spec-kitty agent mission finalize-tasks"
_UNREADABLE_REBUILD_STARTED = "spec-kitty doctor mission-state --fix --mission 084-b"


def test_run_topology_audit_json_carries_remedy(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """FR-015: each finding row carries its remedy; a clean mission carries none."""
    _seed_topology_mission(tmp_path, "083-a", lanes=[{"lane_id": "lane-a", "wp_ids": ["WP01"]}])
    _seed_topology_mission(tmp_path, "084-b", lanes=None, legacy=True)
    _seed_topology_mission(tmp_path, "085-c", lanes=[{"lane_id": "lane-planning", "wp_ids": ["WP01"]}])

    ia.run_topology_audit(tmp_path, True, None)

    rows = {r["slug"]: r for r in json.loads(capsys.readouterr().out)["missions"]}
    assert rows["083-a"]["finding"] == "SINGLE_BRANCH_CODE_LANES_UNMIGRATED"
    assert _RESTAMP_REMEDY in rows["083-a"]["remedy"]
    assert rows["084-b"]["finding"] == "LANES_MANIFEST_UNREADABLE"
    for needle in (_UNREADABLE_RESTORE, _UNREADABLE_REBUILD_PLANNED, _UNREADABLE_REBUILD_STARTED):
        assert needle in rows["084-b"]["remedy"]
    assert "delete" in rows["084-b"]["remedy"]  # finalize-tasks alone cannot repair a corrupt file
    assert rows["085-c"]["finding"] is None
    assert rows["085-c"].get("remedy") is None


def test_run_topology_audit_human_prints_remedy(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _seed_topology_mission(tmp_path, "083-a", lanes=[{"lane_id": "lane-a", "wp_ids": ["WP01"]}])
    _seed_topology_mission(tmp_path, "084-b", lanes=None, legacy=True)

    ia.run_topology_audit(tmp_path, False, None)

    out = " ".join(capsys.readouterr().out.split())
    assert _RESTAMP_REMEDY in out
    assert _UNREADABLE_RESTORE in out
    assert _UNREADABLE_REBUILD_STARTED in out


def test_run_topology_audit_human_clean_prints_no_remedy(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _seed_topology_mission(tmp_path, "085-c", lanes=[{"lane_id": "lane-planning", "wp_ids": ["WP01"]}])

    ia.run_topology_audit(tmp_path, False, None)

    out = capsys.readouterr().out
    assert "spec-kitty migrate" not in out
    assert "finalize-tasks" not in out


def test_identity_audit_does_not_import_doctor() -> None:
    import ast

    source = Path(ia.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    relative: list[str] = []
    absolute: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                relative.append(node.module or "")
            elif node.module:
                absolute.append(node.module)
        elif isinstance(node, ast.Import):
            absolute.extend(alias.name for alias in node.names)
    assert "doctor" not in [m.split(".")[-1] for m in absolute]
    assert set(relative) <= {"_doctor_shared"}
