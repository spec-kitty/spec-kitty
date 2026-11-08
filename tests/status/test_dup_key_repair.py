"""WP03 / FR-008 (#3372): raw-text duplicate-key detect + batch-atomic repair.

The legacy write-path once emitted ``review_feedback`` twice in a WP artifact's
frontmatter (an empty ``''`` then a real ``review-cycle://`` pointer), producing
a duplicate-key, invalid-YAML file that the canonical frontmatter boundary fails
CLOSED on (ruamel ``DuplicateKeyError``). These tests pin:

* a RAW-TEXT detector that can find such artifacts (the boundary cannot);
* an opt-in repair that is NON-DESTRUCTIVE (NFR-002: the recorded pointer is
  preserved) and BATCH-ATOMIC (NFR-004: one un-repairable artifact aborts the
  whole run, leaving the corpus untouched);
* the ``doctor`` diagnostic surface and the ``--fix`` CLI wiring.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from specify_cli.frontmatter import FrontmatterError, FrontmatterManager
from specify_cli.migration.mission_state import repair_duplicate_key_artifacts
from specify_cli.status.dup_key_repair import (
    DuplicateKeyRepairError,
    detect_duplicate_key_artifacts,
    find_duplicate_keys_in_text,
    plan_artifact_repair,
)

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Fixtures (raw artifact text)
# ---------------------------------------------------------------------------

_DUAL_KEY_EMPTY_FIRST = (
    "---\n"
    "work_package_id: WP01\n"
    "title: Something\n"
    "review_feedback: ''\n"
    "subtasks:\n"
    "- T001\n"
    "review_feedback: review-cycle-1.md\n"
    "---\n"
    "Body content.\n"
)

_DUAL_KEY_EMPTY_LAST = (
    "---\n"
    "work_package_id: WP02\n"
    "review_feedback: docs/review-cycle-2.md\n"
    "title: Other\n"
    "review_feedback: ''\n"
    "---\n"
    "Body.\n"
)

_CLEAN_ARTIFACT = (
    "---\n"
    "work_package_id: WP09\n"
    "title: Clean\n"
    "review_feedback: review-cycle-9.md\n"
    "---\n"
    "Body.\n"
)

# After dropping the empty duplicate line the body STILL fails to parse (an
# unclosed flow sequence), so the planner must refuse this artifact.
_UNREPAIRABLE_STILL_INVALID = (
    "---\n"
    "work_package_id: WP03\n"
    "review_feedback: ''\n"
    "review_feedback: review-cycle-3.md\n"
    "broken: [unclosed\n"
    "---\n"
    "Body.\n"
)

# The duplicate whose losing occurrence opens a nested block cannot be removed
# line-wise without orphaning the block, so the planner refuses it.
_UNREPAIRABLE_BLOCK_OCCURRENCE = (
    "---\n"
    "work_package_id: WP04\n"
    "review_feedback:\n"
    "  nested: value\n"
    "review_feedback: review-cycle-4.md\n"
    "---\n"
    "Body.\n"
)


def _write_artifact(root: Path, slug: str, text: str) -> Path:
    path = root / slug / "tasks" / "WP.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _parse_frontmatter_strict(path: Path) -> dict[str, object]:
    """Parse a repaired file's frontmatter with duplicate keys forbidden."""
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    closing = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    yaml = YAML()
    yaml.allow_duplicate_keys = False
    loaded = yaml.load("\n".join(lines[1:closing]))
    return dict(loaded)


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


def test_raw_text_detector_finds_dual_key() -> None:
    duplicates = find_duplicate_keys_in_text(_DUAL_KEY_EMPTY_FIRST)
    assert "review_feedback" in duplicates
    assert [occ.line_index + 1 for occ in duplicates["review_feedback"]] == [4, 7]


def test_detector_ignores_clean_artifact() -> None:
    assert find_duplicate_keys_in_text(_CLEAN_ARTIFACT) == {}


def test_detector_ignores_file_without_frontmatter() -> None:
    assert find_duplicate_keys_in_text("no frontmatter here\nreview_feedback: a\n") == {}


def test_detect_walks_directory(tmp_path: Path) -> None:
    _write_artifact(tmp_path, "mission-a", _DUAL_KEY_EMPTY_FIRST)
    _write_artifact(tmp_path, "mission-b", _CLEAN_ARTIFACT)
    findings = detect_duplicate_key_artifacts(tmp_path)
    assert len(findings) == 1
    assert findings[0].key == "review_feedback"
    assert findings[0].path.parent.parent.name == "mission-a"


def test_canonical_boundary_fails_closed_on_dual_key(tmp_path: Path) -> None:
    """Documents WHY a raw-text scanner is required: the boundary raises."""
    path = _write_artifact(tmp_path, "mission-a", _DUAL_KEY_EMPTY_FIRST)
    with pytest.raises(FrontmatterError):
        FrontmatterManager().read(path)


# ---------------------------------------------------------------------------
# Repair planner (pure)
# ---------------------------------------------------------------------------


def test_plan_keep_last_non_empty_when_empty_first(tmp_path: Path) -> None:
    path = _write_artifact(tmp_path, "m", _DUAL_KEY_EMPTY_FIRST)
    plan = plan_artifact_repair(path, _DUAL_KEY_EMPTY_FIRST)
    assert plan is not None
    assert plan.repaired_text.count("review_feedback:") == 1
    assert "review-cycle-1.md" in plan.repaired_text
    assert plan.removed_line_numbers == (4,)


def test_plan_keeps_recorded_value_when_empty_last(tmp_path: Path) -> None:
    path = _write_artifact(tmp_path, "m", _DUAL_KEY_EMPTY_LAST)
    plan = plan_artifact_repair(path, _DUAL_KEY_EMPTY_LAST)
    assert plan is not None
    assert plan.repaired_text.count("review_feedback:") == 1
    assert "docs/review-cycle-2.md" in plan.repaired_text


def test_plan_returns_none_for_clean_and_bodyless(tmp_path: Path) -> None:
    path = _write_artifact(tmp_path, "m", _CLEAN_ARTIFACT)
    assert plan_artifact_repair(path, _CLEAN_ARTIFACT) is None
    assert plan_artifact_repair(path, "plain text, no frontmatter\n") is None


def test_plan_refuses_still_invalid_after_dedup(tmp_path: Path) -> None:
    path = _write_artifact(tmp_path, "m", _UNREPAIRABLE_STILL_INVALID)
    with pytest.raises(DuplicateKeyRepairError):
        plan_artifact_repair(path, _UNREPAIRABLE_STILL_INVALID)


def test_plan_refuses_block_occurrence(tmp_path: Path) -> None:
    path = _write_artifact(tmp_path, "m", _UNREPAIRABLE_BLOCK_OCCURRENCE)
    with pytest.raises(DuplicateKeyRepairError):
        plan_artifact_repair(path, _UNREPAIRABLE_BLOCK_OCCURRENCE)


# ---------------------------------------------------------------------------
# Repair function — non-destructive + batch-atomic (the load-bearing invariants)
# ---------------------------------------------------------------------------


def test_repair_is_non_destructive_and_yields_valid_yaml(tmp_path: Path) -> None:
    scan_dir = tmp_path / "kitty-specs"
    path = _write_artifact(scan_dir, "mission-a", _DUAL_KEY_EMPTY_FIRST)

    report = repair_duplicate_key_artifacts(tmp_path, scan_root=scan_dir, allow_dirty=True)

    # Recorded state preserved: the real pointer survives, the empty noise is gone.
    frontmatter = _parse_frontmatter_strict(path)
    assert frontmatter["review_feedback"] == "review-cycle-1.md"
    assert frontmatter["work_package_id"] == "WP01"
    assert frontmatter["subtasks"] == ["T001"]
    assert path.read_text(encoding="utf-8").endswith("Body content.\n")
    # Report evidence records the change.
    assert sum(len(m.file_changes) for m in report.missions) == 1


def test_repair_is_idempotent(tmp_path: Path) -> None:
    scan_dir = tmp_path / "kitty-specs"
    path = _write_artifact(scan_dir, "mission-a", _DUAL_KEY_EMPTY_FIRST)
    repair_duplicate_key_artifacts(tmp_path, scan_root=scan_dir, allow_dirty=True)
    healed = path.read_text(encoding="utf-8")

    report = repair_duplicate_key_artifacts(tmp_path, scan_root=scan_dir, allow_dirty=True)
    assert path.read_text(encoding="utf-8") == healed
    assert sum(len(m.file_changes) for m in report.missions) == 0


def test_repair_is_batch_atomic_on_partial_failure(tmp_path: Path) -> None:
    """One un-repairable artifact aborts the run; the repairable one is untouched."""
    scan_dir = tmp_path / "kitty-specs"
    good = _write_artifact(scan_dir, "mission-good", _DUAL_KEY_EMPTY_FIRST)
    bad = _write_artifact(scan_dir, "mission-bad", _UNREPAIRABLE_STILL_INVALID)
    good_before = good.read_text(encoding="utf-8")
    bad_before = bad.read_text(encoding="utf-8")

    with pytest.raises(DuplicateKeyRepairError):
        repair_duplicate_key_artifacts(tmp_path, scan_root=scan_dir, allow_dirty=True)

    # Nothing was partially repaired — both files are byte-identical to before.
    assert good.read_text(encoding="utf-8") == good_before
    assert bad.read_text(encoding="utf-8") == bad_before


def test_repair_no_findings_returns_empty_report(tmp_path: Path) -> None:
    scan_dir = tmp_path / "kitty-specs"
    _write_artifact(scan_dir, "mission-a", _CLEAN_ARTIFACT)
    report = repair_duplicate_key_artifacts(tmp_path, scan_root=scan_dir, allow_dirty=True)
    assert report.missions == []


# ---------------------------------------------------------------------------
# Doctor diagnostic surface (read-only)
# ---------------------------------------------------------------------------


def test_doctor_check_surfaces_finding(tmp_path: Path) -> None:
    from specify_cli.status.doctor import Category, check_duplicate_frontmatter_keys

    _write_artifact(tmp_path, "mission-a", _DUAL_KEY_EMPTY_FIRST)
    findings = check_duplicate_frontmatter_keys(tmp_path)
    assert len(findings) == 1
    assert findings[0].category == Category.DUPLICATE_FRONTMATTER_KEY
    assert "review_feedback" in findings[0].message


def test_doctor_check_clean_repo_no_findings(tmp_path: Path) -> None:
    from specify_cli.status.doctor import check_duplicate_frontmatter_keys

    _write_artifact(tmp_path, "mission-a", _CLEAN_ARTIFACT)
    assert check_duplicate_frontmatter_keys(tmp_path) == []


# ---------------------------------------------------------------------------
# CLI --fix wiring (opt-in; doctor itself is unconditionally SAFE)
# ---------------------------------------------------------------------------


def test_cli_fix_heals_duplicate_key_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.migration.mission_state as mission_state
    from specify_cli.cli.commands import _mission_state_doctor as cmd

    scan_dir = tmp_path / "kitty-specs"
    path = _write_artifact(scan_dir, "mission-a", _DUAL_KEY_EMPTY_FIRST)

    # Isolate the dup-key wiring from the mission-state canonicalization pass.
    def _fake_repair_repo(*_args: object, **_kwargs: object) -> object:
        from specify_cli.migration.mission_state import RepairReport

        return RepairReport(
            run_id="x", repo_head=None, target_missions=[], manifest_path="m", missions=[]
        )

    monkeypatch.setattr(mission_state, "repair_repo", _fake_repair_repo)

    cmd.run_mission_state(
        audit=False,
        fix=True,
        json_output=False,
        mission=None,
        fail_on=None,
        fixture_dir=scan_dir,
        include_fixtures=False,
        manifest_path=None,
        allow_dirty=True,
        repo_root=tmp_path,
    )

    frontmatter = _parse_frontmatter_strict(path)
    assert frontmatter["review_feedback"] == "review-cycle-1.md"


def test_cli_fix_aborts_on_unrepairable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import typer

    import specify_cli.migration.mission_state as mission_state
    from specify_cli.cli.commands import _mission_state_doctor as cmd

    scan_dir = tmp_path / "kitty-specs"
    good = _write_artifact(scan_dir, "mission-good", _DUAL_KEY_EMPTY_FIRST)
    _write_artifact(scan_dir, "mission-bad", _UNREPAIRABLE_STILL_INVALID)
    good_before = good.read_text(encoding="utf-8")

    monkeypatch.setattr(mission_state, "repair_repo", lambda *a, **k: None)

    with pytest.raises(typer.Exit) as excinfo:
        cmd.run_mission_state(
            audit=False,
            fix=True,
            json_output=False,
            mission=None,
            fail_on=None,
            fixture_dir=scan_dir,
            include_fixtures=False,
            manifest_path=None,
            allow_dirty=True,
            repo_root=tmp_path,
        )
    assert excinfo.value.exit_code == 1
    # Batch-atomic through the CLI too: the repairable artifact is untouched.
    assert good.read_text(encoding="utf-8") == good_before
