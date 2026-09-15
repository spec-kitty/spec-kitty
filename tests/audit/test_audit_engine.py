"""Tests for src/specify_cli/audit/engine.py (T023).

8 test cases covering the audit engine scan loop, mission filtering,
determinism, corrupt-JSONL resilience, repo-summary counts, performance,
and empty-scan-root behavior.

Fixture layout (for tests that need identity functions to work):
    tmp_path/               ← repo_root
      kitty-specs/          ← scan_root = tmp_path / "kitty-specs"
        mission-a/
          meta.json         ← {"mission_id": "<valid ULID>", ...}
        mission-b/
          meta.json
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from charter.hasher import hash_content
import pytest

from specify_cli.audit import AuditOptions, RepoAuditReport, run_audit
from specify_cli.audit.serializer import build_report_json
from tests._perf_helpers import assert_timing_budget
from tests._support.eacces import mode_bits_enforced

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A set of distinct valid ULIDs (26 chars, Crockford Base32: 0-9 A-H J-N P-T V-Z)

pytestmark = [pytest.mark.integration]

_ULID_A = "01KQHRB8GCFJAX7HM4ZY52AQGR"
_ULID_B = "01KQHRB9GCFJAX7HM4ZY52AQGR"
_ULID_C = "01KQHRB7GCFJAX7HM4ZY52AQGR"
_ULID_D = "01KQHRC0GCFJAX7HM4ZY52AQGR"
_ULID_E = "01KQHRC1GCFJAX7HM4ZY52AQGR"


def _write_meta(mission_dir: Path, mission_id: str, mission_number: int | None = None) -> None:
    """Write a minimal valid meta.json to the mission directory."""
    mission_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "mission_id": mission_id,
        "mission_slug": mission_dir.name,
        "friendly_name": f"Test mission {mission_dir.name}",
    }
    if mission_number is not None:
        meta["mission_number"] = mission_number
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _make_mission(parent: Path, slug: str, mission_id: str, mission_number: int | None = None) -> Path:
    """Create a minimal mission directory with a valid meta.json."""
    mission_dir = parent / slug
    _write_meta(mission_dir, mission_id, mission_number)
    return mission_dir


def _options(tmp_path: Path, *, mission_filter: str | None = None) -> AuditOptions:
    """Create AuditOptions with tmp_path as repo_root and kitty-specs as scan_root."""
    return AuditOptions(
        repo_root=tmp_path,
        scan_root=tmp_path / "kitty-specs",
        mission_filter=mission_filter,
        fail_on=None,
    )


# ---------------------------------------------------------------------------
# Test 1: test_scan_visits_all_missions
# ---------------------------------------------------------------------------


def test_scan_visits_all_missions(tmp_path: Path) -> None:
    """Engine visits all mission directories and returns them sorted by slug."""
    specs_dir = tmp_path / "kitty-specs"
    _make_mission(specs_dir, "mission-a", _ULID_A)
    _make_mission(specs_dir, "mission-b", _ULID_B)
    _make_mission(specs_dir, "mission-c", _ULID_C)

    report = run_audit(_options(tmp_path))

    assert isinstance(report, RepoAuditReport)
    slugs = [m.mission_slug for m in report.missions]
    assert slugs == ["mission-a", "mission-b", "mission-c"]
    assert report.repo_summary["total_missions"] == 3


# ---------------------------------------------------------------------------
# Test 2: test_fixture_dir_substitution
# ---------------------------------------------------------------------------


def test_fixture_dir_substitution(tmp_path: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    """scan_root override causes the engine to scan a different directory."""
    # Primary fixture: tmp_path/kitty-specs/fixture-mission
    specs_dir = tmp_path / "kitty-specs"
    _make_mission(specs_dir, "fixture-mission", _ULID_A)

    # Engine with default scan_root should find fixture-mission
    report_a = run_audit(_options(tmp_path))
    assert any(m.mission_slug == "fixture-mission" for m in report_a.missions)

    # Alternate fixture in a different tmp directory
    alt_root = tmp_path_factory.mktemp("alt")
    alt_specs = alt_root / "kitty-specs"
    _make_mission(alt_specs, "alt-mission", _ULID_B)

    # Override scan_root to alt_specs — should find alt-mission, NOT fixture-mission
    alt_options = AuditOptions(
        repo_root=alt_root,
        scan_root=alt_specs,
        mission_filter=None,
        fail_on=None,
    )
    report_b = run_audit(alt_options)
    slugs_b = [m.mission_slug for m in report_b.missions]
    assert "alt-mission" in slugs_b
    assert "fixture-mission" not in slugs_b


# ---------------------------------------------------------------------------
# Test 3: test_mission_filter_scoping
# ---------------------------------------------------------------------------


def test_mission_filter_scoping(tmp_path: Path) -> None:
    """--mission filter restricts the scan to exactly one mission."""
    specs_dir = tmp_path / "kitty-specs"
    _make_mission(specs_dir, "001-alpha", _ULID_A, mission_number=1)
    _make_mission(specs_dir, "002-beta", _ULID_B, mission_number=2)
    _make_mission(specs_dir, "003-gamma", _ULID_C, mission_number=3)

    # Filter by full slug — should return only 001-alpha
    report = run_audit(
        AuditOptions(
            repo_root=tmp_path,
            scan_root=tmp_path / "kitty-specs",
            mission_filter="001-alpha",
            fail_on=None,
        )
    )

    assert frozenset(m.mission_slug for m in report.missions) == frozenset({"001-alpha"})
    assert report.repo_summary["total_missions"] == 1


# ---------------------------------------------------------------------------
# Test 4: test_determinism
# ---------------------------------------------------------------------------


def test_determinism(tmp_path: Path) -> None:
    """Two successive run_audit() calls produce byte-identical JSON output."""
    specs_dir = tmp_path / "kitty-specs"
    _make_mission(specs_dir, "mission-x", _ULID_A, mission_number=1)
    _make_mission(specs_dir, "mission-y", _ULID_B, mission_number=2)
    _make_mission(specs_dir, "mission-z", _ULID_C, mission_number=3)

    opts = _options(tmp_path)
    report_1 = run_audit(opts)
    report_2 = run_audit(opts)

    json_1 = build_report_json(report_1)
    json_2 = build_report_json(report_2)

    assert json_1 == json_2, "Two identical run_audit() calls produced different JSON"


def test_json_stable_across_checkout_roots(tmp_path: Path) -> None:
    """Identical audit input in different roots serializes byte-identically."""
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    _make_mission(repo_a / "kitty-specs", "mission-x", _ULID_A, mission_number=1)
    _make_mission(repo_b / "kitty-specs", "mission-x", _ULID_A, mission_number=1)

    json_a = build_report_json(run_audit(_options(repo_a)))
    json_b = build_report_json(run_audit(_options(repo_b)))

    assert json_a == json_b
    assert str(tmp_path) not in json_a


# ---------------------------------------------------------------------------
# Test 5: test_corrupt_jsonl_does_not_crash_engine
# ---------------------------------------------------------------------------


def test_corrupt_jsonl_does_not_crash_engine(tmp_path: Path) -> None:
    """Engine handles a corrupt status.events.jsonl without raising.

    The corrupt line causes CORRUPT_JSONL to appear in findings.
    SNAPSHOT_DRIFT must NOT appear because skip_drift=True was applied.
    """
    specs_dir = tmp_path / "kitty-specs"
    mission_dir = specs_dir / "bad-events-mission"
    _write_meta(mission_dir, _ULID_A)

    # Write a valid status.json (minimal) so the drift check would normally run
    (mission_dir / "status.json").write_text(
        json.dumps({"wps": {}}) + "\n", encoding="utf-8"
    )

    # Write a corrupt status.events.jsonl
    events_path = mission_dir / "status.events.jsonl"
    events_path.write_text("THIS IS NOT JSON {{{\n", encoding="utf-8")

    report = run_audit(_options(tmp_path))

    assert frozenset(m.mission_slug for m in report.missions) == frozenset(
        {"bad-events-mission"}
    )
    result = report.missions[0]
    codes = {f.code for f in result.findings}

    assert "CORRUPT_JSONL" in codes, f"Expected CORRUPT_JSONL in {codes}"
    assert "SNAPSHOT_DRIFT" not in codes, f"SNAPSHOT_DRIFT should be suppressed, got {codes}"


def test_non_object_meta_and_status_json_do_not_crash_engine(tmp_path: Path) -> None:
    """Engine emits findings for valid non-object meta/status JSON roots."""
    specs_dir = tmp_path / "kitty-specs"
    mission_dir = specs_dir / "non-object-json-mission"
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text("[]", encoding="utf-8")
    (mission_dir / "status.json").write_text("true", encoding="utf-8")

    report = run_audit(_options(tmp_path))

    assert frozenset(m.mission_slug for m in report.missions) == frozenset(
        {"non-object-json-mission"}
    )
    result = report.missions[0]
    findings_by_artifact = {
        (finding.artifact_path, finding.code): finding for finding in result.findings
    }
    assert ("meta.json", "CORRUPT_JSON") in findings_by_artifact
    assert ("status.json", "CORRUPT_JSON") in findings_by_artifact
    assert (
        findings_by_artifact[("meta.json", "CORRUPT_JSON")].detail
        == "top-level JSON value must be an object"
    )
    assert (
        findings_by_artifact[("status.json", "CORRUPT_JSON")].detail
        == "top-level JSON value must be an object"
    )


# ---------------------------------------------------------------------------
# Test 6: test_repo_summary_counts
# ---------------------------------------------------------------------------


def test_repo_summary_counts(tmp_path: Path) -> None:
    """Repo summary correctly counts missions with errors/warnings."""
    specs_dir = tmp_path / "kitty-specs"

    # Clean mission: valid meta.json with mission_id + mission_number
    _make_mission(specs_dir, "001-clean", _ULID_A, mission_number=1)

    # Mission with a LEGACY_KEY warning: add feature_slug to meta.json
    legacy_dir = specs_dir / "002-legacy"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    legacy_meta: dict[str, object] = {
        "mission_id": _ULID_B,
        "mission_slug": "002-legacy",
        "mission_number": 2,
        "friendly_name": "Legacy mission",
        "feature_slug": "old-slug",  # LEGACY_KEY → WARNING
    }
    (legacy_dir / "meta.json").write_text(json.dumps(legacy_meta), encoding="utf-8")

    report = run_audit(_options(tmp_path))

    summary = report.repo_summary
    assert summary["total_missions"] == 2
    assert summary["missions_with_errors"] == 0
    assert summary["missions_with_warnings"] == 1  # only 002-legacy has a warning
    assert summary["missions_with_teamspace_blockers"] == 1
    assert summary["total_findings"] >= 1
    assert summary["teamspace_blockers"] >= 1
    assert summary["findings_by_severity"]["warning"] >= 1
    assert summary["findings_by_severity"]["error"] == 0


# ---------------------------------------------------------------------------
# Test 7: test_performance_204_missions
# ---------------------------------------------------------------------------


def _build_204_mission_specs_dir(tmp_path: Path) -> Path:
    """Build 204 minimal missions under ``tmp_path/kitty-specs`` (shared #4015 split fixture)."""
    specs_dir = tmp_path / "kitty-specs"
    specs_dir.mkdir(parents=True, exist_ok=True)

    # Use a pool of valid ULIDs, cycling through them with a suffix to make unique
    _BASE_ULID = "01KQHRB8GCFJAX7HM4ZY52AQ"
    valid_suffix_chars = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

    # Generate 204 distinct valid ULIDs
    def _make_ulid(i: int) -> str:
        # Encode i as 2 chars from the valid Crockford Base32 alphabet
        high = i // len(valid_suffix_chars)
        low = i % len(valid_suffix_chars)
        return _BASE_ULID + valid_suffix_chars[high] + valid_suffix_chars[low]

    for i in range(204):
        slug = f"mission-{i:04d}"
        mission_dir = specs_dir / slug
        mission_dir.mkdir()
        meta = {
            "mission_id": _make_ulid(i),
            "mission_slug": slug,
            "friendly_name": f"Mission {i}",
            "mission_number": i,
        }
        (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    return specs_dir


def test_scan_204_missions(tmp_path: Path) -> None:
    """204 minimal missions are all scanned (functional, #4015 split)."""
    specs_dir = _build_204_mission_specs_dir(tmp_path)
    opts = AuditOptions(repo_root=tmp_path, scan_root=specs_dir, fail_on=None)

    report = run_audit(opts)

    assert len(report.missions) == 204, (
        f"Expected 204 missions, got {len(report.missions)}"
    )


@pytest.mark.performance
def test_performance_204_missions(tmp_path: Path) -> None:
    """204 minimal missions complete in under 30 seconds (NFR-003, #4015 split)."""
    specs_dir = _build_204_mission_specs_dir(tmp_path)
    opts = AuditOptions(repo_root=tmp_path, scan_root=specs_dir, fail_on=None)

    start = time.perf_counter()
    run_audit(opts)
    elapsed = time.perf_counter() - start

    assert_timing_budget(elapsed, 30.0, name="elapsed")


# ---------------------------------------------------------------------------
# Test 8: test_empty_scan_root
# ---------------------------------------------------------------------------


def test_empty_scan_root(tmp_path: Path) -> None:
    """An empty scan_root produces an empty report with zero missions."""
    # Create an empty kitty-specs directory
    specs_dir = tmp_path / "kitty-specs"
    specs_dir.mkdir(parents=True)

    report = run_audit(_options(tmp_path))

    assert report.missions == []
    assert report.repo_summary["total_missions"] == 0
    assert report.repo_summary["total_findings"] == 0


# ---------------------------------------------------------------------------
# Test 9: `#3194` — an unstattable mission candidate must not crash the audit
# ---------------------------------------------------------------------------


def test_unstattable_mission_candidate_does_not_crash_the_audit(tmp_path: Path) -> None:
    """`#3194`: `_scan_missions`'s `candidate.is_dir()` filter must not use the
    EACCES-divergent predicate — and here specifically must not let a bare
    predicate-turned-raise crash this read-only, best-effort audit engine either.

    Before this fix, on Python 3.11-3.13 `Path.is_dir()` on an unstattable
    candidate RAISES uncaught (no per-candidate `try`/`except` existed in
    `_scan_missions`'s loop), crashing the whole audit for every mission because
    of ONE unreadable directory; on 3.14 it silently returns `False` (masking
    the EACCES as "not a directory"). `safe_is_dir`, wrapped in the local
    `try/except OSError: continue` this fix adds, makes the answer the SAME on
    every interpreter — skip that one candidate — matching the fail-soft
    posture `_scan_missions` already had for `scan_root` enumeration failures,
    while still auditing every OTHER mission in the corpus.
    """
    specs_dir = tmp_path / "kitty-specs"
    specs_dir.mkdir(parents=True)
    _make_mission(specs_dir, "mission-readable", _ULID_A)

    vault = tmp_path / "vault"
    (vault / "m-target").mkdir(parents=True)
    (specs_dir / "m-link").symlink_to(vault / "m-target", target_is_directory=True)

    canary = vault / "canary"
    canary.write_text("{}", encoding="utf-8")
    os.chmod(vault, 0o000)
    try:
        if not mode_bits_enforced(canary):
            pytest.skip(
                "SKIPPED HONESTLY, not passed: this process can stat through a "
                "0o000 directory (running as root, or a filesystem that ignores "
                "mode bits), so the branch cannot be constructed here."
            )
        report = run_audit(_options(tmp_path))
    finally:
        os.chmod(vault, 0o700)

    slugs = {m.mission_slug for m in report.missions}
    assert "mission-readable" in slugs, (
        "the unstattable candidate must not have aborted the scan of the rest "
        f"of the corpus: {slugs!r}"
    )
    assert "m-link" not in slugs, "the unstattable candidate itself cannot be audited"


# ---------------------------------------------------------------------------
# Test 10: `invoking_cwd` — invoking-checkout-vs-primary disagreement (#251)
# ---------------------------------------------------------------------------


def _make_primary_and_lane(
    tmp_path: Path, slug: str, mission_id: str, *, primary_status: str, lane_status: str
) -> tuple[Path, Path]:
    """Fabricate a primary checkout and a linked lane worktree pointing at it.

    Mirrors ``tests/specify_cli/migration/test_mission_state_identity.py``'s
    fixture: ``_linked_worktree_primary`` parses ``.git`` directly (stdlib
    only, no real git needed), so a ``.git`` directory on the primary plus a
    ``gitdir:`` pointer file on the lane is enough.
    """
    primary = (tmp_path / "primary").resolve()
    lane = (tmp_path / "lane-d").resolve()
    (primary / ".git" / "worktrees" / "lane-d").mkdir(parents=True, exist_ok=True)
    lane.mkdir(parents=True, exist_ok=True)
    (lane / ".git").write_text(f"gitdir: {primary}/.git/worktrees/lane-d\n", encoding="utf-8")
    _write_meta(primary / "kitty-specs" / slug, mission_id)
    (primary / "kitty-specs" / slug / "status.json").write_text(primary_status, encoding="utf-8")
    lane_mission = lane / "kitty-specs" / slug
    lane_mission.mkdir(parents=True, exist_ok=True)
    (lane_mission / "status.json").write_text(lane_status, encoding="utf-8")
    return primary, lane


def test_invoking_cwd_disagreement_adds_checkout_disagreement_finding(tmp_path: Path) -> None:
    """From a foreign lane worktree, invoking-vs-primary disagreement surfaces as a finding.

    Without wiring ``AuditOptions.invoking_cwd`` into the engine, ``--audit``
    anchored to the primary reads the primary's own ``status.json`` at both
    ends and reports a false green even when the invoking lane's mission
    state has diverged (#251).
    """
    slug = "checkout-disagreement-mission"
    primary, lane = _make_primary_and_lane(
        tmp_path, slug, _ULID_D, primary_status='{"v": "primary"}', lane_status='{"v": "lane"}'
    )

    report = run_audit(
        AuditOptions(repo_root=primary, scan_root=primary / "kitty-specs", invoking_cwd=lane)
    )

    result = next(m for m in report.missions if m.mission_slug == slug)
    assert "CHECKOUT_DISAGREEMENT" in {f.code for f in result.findings}
    finding = next(f for f in result.findings if f.code == "CHECKOUT_DISAGREEMENT")
    invoking_sha256 = hash_content(
        (lane / "kitty-specs" / slug / "status.json").read_text(encoding="utf-8")
    ).removeprefix("sha256:")
    primary_sha256 = hash_content(
        (primary / "kitty-specs" / slug / "status.json").read_text(encoding="utf-8")
    ).removeprefix("sha256:")
    assert finding.detail == (
        "status.json disagrees with primary "
        f"(invoking sha256 {invoking_sha256}, "
        f"primary sha256 {primary_sha256})"
    )


def test_invoking_cwd_owner_reports_no_disagreement(tmp_path: Path) -> None:
    """An owner invocation (``invoking_cwd`` IS the primary) never false-reds."""
    slug = "checkout-agreement-mission"
    primary, _lane = _make_primary_and_lane(
        tmp_path, slug, _ULID_E, primary_status='{"v": "primary"}', lane_status='{"v": "lane"}'
    )

    report = run_audit(
        AuditOptions(repo_root=primary, scan_root=primary / "kitty-specs", invoking_cwd=primary)
    )

    result = next(m for m in report.missions if m.mission_slug == slug)
    assert "CHECKOUT_DISAGREEMENT" not in {f.code for f in result.findings}


def test_invoking_cwd_omitted_skips_disagreement_check(tmp_path: Path) -> None:
    """Omitting ``invoking_cwd`` (the default) never adds the finding — existing callers unaffected."""
    slug = "checkout-disagreement-mission-no-invoking-cwd"
    primary, _lane = _make_primary_and_lane(
        tmp_path, slug, _ULID_A, primary_status='{"v": "primary"}', lane_status='{"v": "lane"}'
    )

    report = run_audit(AuditOptions(repo_root=primary, scan_root=primary / "kitty-specs"))

    result = next(m for m in report.missions if m.mission_slug == slug)
    assert "CHECKOUT_DISAGREEMENT" not in {f.code for f in result.findings}


def test_invoking_cwd_disagreement_survives_non_slug_mission_filter(tmp_path: Path) -> None:
    """``--mission`` scoped by a non-slug handle must still surface the disagreement.

    Regression pin: the merge helper resolves ``--mission`` through the
    engine's already-resolved ``allowed_dirs``, never by re-matching the raw
    handle against directory slugs — a ``mission_id`` handle never
    string-matches a slug in ``_compare_checkout_mission_state``, so passing
    the raw handle through would silently drop the finding for any
    non-slug ``--mission`` filter.
    """
    slug = "checkout-disagreement-by-id"
    mission_id = _ULID_B
    primary, lane = _make_primary_and_lane(
        tmp_path, slug, mission_id, primary_status='{"v": "primary"}', lane_status='{"v": "lane"}'
    )

    report = run_audit(
        AuditOptions(
            repo_root=primary,
            scan_root=primary / "kitty-specs",
            mission_filter=mission_id,
            invoking_cwd=lane,
        )
    )

    assert [m.mission_slug for m in report.missions] == [slug]
    assert "CHECKOUT_DISAGREEMENT" in {f.code for f in report.missions[0].findings}
