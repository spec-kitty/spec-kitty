"""Tests for the mission-identity audit (WP03 / T013-T017).

Covers:
- T013: four-state classifier (assigned, pending, legacy, orphan)
- T014: duplicate-prefix report
- T015: ambiguous-selector report
- T016: JSON schema contract via typer.testing.CliRunner
- T017: NFR-002 timing: 200 missions in < 3 seconds

Do NOT add ``# type: ignore`` to this file — it must pass ``mypy --strict``
cleanly where possible.  (typer.testing imports require some flexibility.)
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from specify_cli.status.identity_audit import (
    IdentityState,
    audit_repo,
    classify_mission,
    find_ambiguous_selectors,
    find_duplicate_prefixes,
    summarize,
)
from tests._perf_helpers import assert_timing_budget


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.integration]

_ULID_A = "01KNXQS9ATWWFXS3K5ZJ9E5008"
_ULID_B = "01KNS7C9AZP1MPCFZWM25KV6TM"
_ULID_C = "01KNS7RB1V9R3VSYD910HCAMTR"


def _write_meta(feature_dir: Path, meta: dict[str, Any]) -> None:
    """Write a minimal meta.json for test fixtures."""
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _mission_dir(specs: Path, slug: str, mission_id: str | None, mission_number: int | None) -> Path:
    """Create a mission directory with the given identity fields."""
    d = specs / slug
    meta: dict[str, Any] = {
        "slug": slug,
        "mission_slug": slug,
        "friendly_name": slug,
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    if mission_id is not None:
        meta["mission_id"] = mission_id
    if mission_number is not None:
        meta["mission_number"] = mission_number
    _write_meta(d, meta)
    return d


# ---------------------------------------------------------------------------
# T013: Four-state classifier (one parametrized test per state)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mission_id, mission_number, expected_state",
    [
        (_ULID_A, 83, "assigned"),
        (_ULID_A, None, "pending"),
        (None, 83, "legacy"),
        (None, None, "orphan"),
    ],
    ids=["assigned", "pending", "legacy", "orphan"],
)
def test_classify_mission_four_states(
    tmp_path: Path,
    mission_id: str | None,
    mission_number: int | None,
    expected_state: str,
) -> None:
    """classify_mission returns correct state for each of the four cases."""
    d = _mission_dir(tmp_path / "kitty-specs", "083-test", mission_id, mission_number)
    state = classify_mission(d)
    assert state.state == expected_state
    assert state.slug == "083-test"
    assert state.mission_id == mission_id
    assert state.mission_number == mission_number


def test_classify_mission_missing_meta_json(tmp_path: Path) -> None:
    """A directory without meta.json is classified as orphan with error field."""
    d = tmp_path / "kitty-specs" / "083-no-meta"
    d.mkdir(parents=True)
    state = classify_mission(d)
    assert state.state == "orphan"
    assert state.error is not None
    assert "meta.json" in state.error


def test_classify_mission_corrupt_meta_json(tmp_path: Path) -> None:
    """A corrupt meta.json is classified as orphan, not an exception."""
    d = tmp_path / "kitty-specs" / "083-corrupt"
    d.mkdir(parents=True)
    (d / "meta.json").write_text("{not valid json", encoding="utf-8")
    state = classify_mission(d)
    assert state.state == "orphan"
    assert state.error is not None


def test_classify_mission_non_object_meta_json(tmp_path: Path) -> None:
    """A non-object JSON document is classified as orphan with an error."""
    d = tmp_path / "kitty-specs" / "083-list-meta"
    d.mkdir(parents=True)
    (d / "meta.json").write_text('["not", "an", "object"]', encoding="utf-8")

    state = classify_mission(d)

    assert state.state == "orphan"
    assert state.error is not None
    assert "Expected JSON object" in state.error


def test_classify_mission_invalid_number_with_mission_id_is_pending(tmp_path: Path) -> None:
    """A bad mission_number is coerced to None, keeping mission_id-backed rows pending."""
    d = tmp_path / "kitty-specs" / "083-bad-number"
    _write_meta(d, {"mission_id": _ULID_A, "mission_number": {"bad": "shape"}})

    state = classify_mission(d)

    assert state.state == "pending"
    assert state.mission_id == _ULID_A
    assert state.mission_number is None


def test_classify_mission_invalid_number_without_mission_id_is_orphan(tmp_path: Path) -> None:
    """A bad mission_number without mission_id becomes an orphan."""
    d = tmp_path / "kitty-specs" / "083-bad-legacy"
    _write_meta(d, {"mission_number": {"bad": "shape"}})

    state = classify_mission(d)

    assert state.state == "orphan"
    assert state.mission_id is None
    assert state.mission_number is None


# ---------------------------------------------------------------------------
# audit_repo
# ---------------------------------------------------------------------------


def test_audit_repo_empty_specs(tmp_path: Path) -> None:
    """audit_repo over empty kitty-specs returns empty list."""
    (tmp_path / "kitty-specs").mkdir()
    result = audit_repo(tmp_path)
    assert result == []


def test_audit_repo_no_specs_dir(tmp_path: Path) -> None:
    """audit_repo when kitty-specs does not exist returns empty list."""
    result = audit_repo(tmp_path)
    assert result == []


def test_audit_repo_skips_non_directories(tmp_path: Path) -> None:
    """audit_repo ignores files like README.md in kitty-specs/."""
    specs = tmp_path / "kitty-specs"
    specs.mkdir()
    (specs / "README.md").write_text("ignore me", encoding="utf-8")
    _mission_dir(specs, "001-hello", _ULID_A, 1)
    result = audit_repo(tmp_path)
    assert len(result) == 1
    assert result[0].slug == "001-hello"


def test_audit_repo_unstattable_entry_is_skipped_not_crashed(tmp_path: Path) -> None:
    """`#3194`: an unstattable candidate must be skipped like a non-directory,
    not crash `audit_repo` (nor silently vanish only on some interpreters).

    `Path.is_dir()` answers `False` for an unreadable candidate on Python 3.14
    only (RAISES on 3.11-3.13, uncaught here before this fix — there was no
    per-entry ``try``/``except`` at all). ``safe_is_dir``, wrapped in a local
    ``try/except OSError: continue``, folds an unstattable entry into the SAME
    "skip it" bucket this function already documents for non-directory entries
    (``README.md``, templates, ...) — on every interpreter, and it still audits
    every OTHER mission in the corpus.
    """
    import os

    from tests._support.eacces import mode_bits_enforced

    specs = tmp_path / "kitty-specs"
    specs.mkdir()
    _mission_dir(specs, "001-hello", _ULID_A, 1)

    vault = tmp_path / "vault"
    (vault / "m-target").mkdir(parents=True)
    (specs / "m-link").symlink_to(vault / "m-target", target_is_directory=True)

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
        result = audit_repo(tmp_path)
    finally:
        os.chmod(vault, 0o700)

    slugs = {s.slug for s in result}
    assert slugs == {"001-hello"}, (
        f"the unstattable candidate must be skipped and the readable one kept: {slugs!r}"
    )


def test_audit_repo_all_four_states(tmp_path: Path) -> None:
    """audit_repo correctly classifies a repo with one mission per state."""
    specs = tmp_path / "kitty-specs"
    _mission_dir(specs, "001-assigned", _ULID_A, 1)
    _mission_dir(specs, "002-pending", _ULID_B, None)
    _mission_dir(specs, "003-legacy", None, 3)
    _mission_dir(specs, "004-orphan", None, None)
    result = audit_repo(tmp_path)
    assert len(result) == 4
    states_found = {s.state for s in result}
    assert states_found == {"assigned", "pending", "legacy", "orphan"}


# ---------------------------------------------------------------------------
# summarize
# ---------------------------------------------------------------------------


def test_summarize_zero_filled(tmp_path: Path) -> None:
    """summarize always returns all four state keys, even when counts are zero."""
    states: list[IdentityState] = []
    summary = summarize(states)
    counts = summary["counts"]
    assert isinstance(counts, dict)
    for key in ("assigned", "pending", "legacy", "orphan"):
        assert key in counts
        assert counts[key] == 0


def test_summarize_legacy_and_orphan_paths(tmp_path: Path) -> None:
    """summarize populates legacy_paths and orphan_paths."""
    specs = tmp_path / "kitty-specs"
    _mission_dir(specs, "001-legacy", None, 1)
    _mission_dir(specs, "002-orphan", None, None)
    _mission_dir(specs, "003-assigned", _ULID_A, 3)
    result = audit_repo(tmp_path)
    summary = summarize(result)
    legacy: list[str] = summary["legacy_paths"]  # type: ignore[assignment]
    orphan: list[str] = summary["orphan_paths"]  # type: ignore[assignment]
    assert any("001-legacy" in p for p in legacy)
    assert any("002-orphan" in p for p in orphan)
    assert not any("003-assigned" in p for p in legacy + orphan)


def test_summarize_counts_assigned_and_pending(tmp_path: Path) -> None:
    """summarize increments assigned and pending counts without path buckets."""
    specs = tmp_path / "kitty-specs"
    _mission_dir(specs, "001-assigned", _ULID_A, 1)
    _mission_dir(specs, "002-pending", _ULID_B, None)

    summary = summarize(audit_repo(tmp_path))

    counts = summary["counts"]
    assert counts["assigned"] == 1
    assert counts["pending"] == 1
    assert summary["legacy_paths"] == []
    assert summary["orphan_paths"] == []


# ---------------------------------------------------------------------------
# T014: Duplicate-prefix report
# ---------------------------------------------------------------------------


def test_find_duplicate_prefixes_three_080(tmp_path: Path) -> None:
    """Three 080-* missions produce {'080': [<3 states>]}."""
    specs = tmp_path / "kitty-specs"
    _mission_dir(specs, "080-alpha", _ULID_A, 80)
    _mission_dir(specs, "080-beta", _ULID_B, 80)
    _mission_dir(specs, "080-gamma", _ULID_C, 80)
    dupes = find_duplicate_prefixes(tmp_path)
    assert "080" in dupes
    assert frozenset(s.slug for s in dupes["080"]) == frozenset(
        {"080-alpha", "080-beta", "080-gamma"}
    )


def test_find_duplicate_prefixes_single_not_flagged(tmp_path: Path) -> None:
    """A lone 080-* mission is NOT flagged as a duplicate."""
    specs = tmp_path / "kitty-specs"
    _mission_dir(specs, "080-only", _ULID_A, 80)
    dupes = find_duplicate_prefixes(tmp_path)
    assert "080" not in dupes


def test_find_duplicate_prefixes_no_duplicates(tmp_path: Path) -> None:
    """A repo with unique prefixes returns empty dict."""
    specs = tmp_path / "kitty-specs"
    _mission_dir(specs, "001-alpha", _ULID_A, 1)
    _mission_dir(specs, "002-beta", _ULID_B, 2)
    dupes = find_duplicate_prefixes(tmp_path)
    assert dupes == {}


def test_find_duplicate_prefixes_missing_specs_dir_returns_empty(tmp_path: Path) -> None:
    """Missing kitty-specs/ returns an empty duplicate-prefix report."""
    assert find_duplicate_prefixes(tmp_path) == {}


def test_find_duplicate_prefixes_skips_non_directory_entries(tmp_path: Path) -> None:
    """Files directly under kitty-specs/ are ignored by duplicate-prefix scanning."""
    specs = tmp_path / "kitty-specs"
    specs.mkdir()
    (specs / "README.md").write_text("ignore me", encoding="utf-8")
    _mission_dir(specs, "080-one", _ULID_A, 80)
    _mission_dir(specs, "080-two", _ULID_B, 80)

    dupes = find_duplicate_prefixes(tmp_path)

    assert "080" in dupes
    assert frozenset(s.slug for s in dupes["080"]) == frozenset({"080-one", "080-two"})


def test_find_duplicate_prefixes_unstattable_entry_is_skipped_not_crashed(
    tmp_path: Path,
) -> None:
    """`#3194` companion to ``test_audit_repo_unstattable_entry_is_skipped_not_crashed``,
    for ``find_duplicate_prefixes``'s own separate directory walk."""
    import os

    from tests._support.eacces import mode_bits_enforced

    specs = tmp_path / "kitty-specs"
    _mission_dir(specs, "080-one", _ULID_A, 80)
    _mission_dir(specs, "080-two", _ULID_B, 80)

    vault = tmp_path / "vault"
    (vault / "m-target").mkdir(parents=True)
    (specs / "m-link").symlink_to(vault / "m-target", target_is_directory=True)

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
        dupes = find_duplicate_prefixes(tmp_path)
    finally:
        os.chmod(vault, 0o700)

    assert "080" in dupes
    assert frozenset(s.slug for s in dupes["080"]) == frozenset({"080-one", "080-two"})


def test_find_duplicate_prefixes_skips_no_prefix(tmp_path: Path) -> None:
    """Directories without a leading NNN- prefix are silently skipped."""
    specs = tmp_path / "kitty-specs"
    d = specs / "no-prefix-dir"
    d.mkdir(parents=True)
    (d / "meta.json").write_text("{}", encoding="utf-8")
    dupes = find_duplicate_prefixes(tmp_path)
    assert dupes == {}


def test_find_duplicate_prefixes_distinct_07x(tmp_path: Path) -> None:
    """070, 071, 072 are reported as distinct prefix groups, not merged."""
    specs = tmp_path / "kitty-specs"
    _mission_dir(specs, "070-a", None, 70)
    _mission_dir(specs, "070-b", None, 70)
    _mission_dir(specs, "071-c", None, 71)
    _mission_dir(specs, "071-d", None, 71)
    dupes = find_duplicate_prefixes(tmp_path)
    assert "070" in dupes
    assert "071" in dupes
    assert frozenset(s.slug for s in dupes["070"]) == frozenset({"070-a", "070-b"})
    assert frozenset(s.slug for s in dupes["071"]) == frozenset({"071-c", "071-d"})


# ---------------------------------------------------------------------------
# T015: Selector-ambiguity report
# ---------------------------------------------------------------------------


def test_find_ambiguous_selectors_three_080(tmp_path: Path) -> None:
    """Three 080-* missions flag '080' as ambiguous."""
    specs = tmp_path / "kitty-specs"
    _mission_dir(specs, "080-alpha", _ULID_A, 80)
    _mission_dir(specs, "080-beta", _ULID_B, 80)
    _mission_dir(specs, "080-gamma", _ULID_C, 80)
    states = audit_repo(tmp_path)
    ambiguous = find_ambiguous_selectors(states)
    assert "080" in ambiguous
    assert frozenset(s.slug for s in ambiguous["080"]) == frozenset(
        {"080-alpha", "080-beta", "080-gamma"}
    )


def test_find_ambiguous_selectors_shared_human_slug(tmp_path: Path) -> None:
    """Missions with the same human slug flag that slug as ambiguous."""
    specs = tmp_path / "kitty-specs"
    _mission_dir(specs, "081-foo-bar", _ULID_A, 81)
    _mission_dir(specs, "082-foo-bar", _ULID_B, 82)
    states = audit_repo(tmp_path)
    ambiguous = find_ambiguous_selectors(states)
    assert "foo-bar" in ambiguous
    assert frozenset(s.slug for s in ambiguous["foo-bar"]) == frozenset(
        {"081-foo-bar", "082-foo-bar"}
    )


def test_find_ambiguous_selectors_no_ambiguity(tmp_path: Path) -> None:
    """Distinct missions with distinct handles produce no ambiguities."""
    specs = tmp_path / "kitty-specs"
    _mission_dir(specs, "001-alpha", _ULID_A, 1)
    _mission_dir(specs, "002-beta", _ULID_B, 2)
    states = audit_repo(tmp_path)
    ambiguous = find_ambiguous_selectors(states)
    assert ambiguous == {}


def test_find_ambiguous_selectors_prefix_not_substring(tmp_path: Path) -> None:
    """'foo' does not collide with 'foobar' — only exact handle matches count."""
    specs = tmp_path / "kitty-specs"
    _mission_dir(specs, "001-foo", _ULID_A, 1)
    _mission_dir(specs, "002-foobar", _ULID_B, 2)
    states = audit_repo(tmp_path)
    ambiguous = find_ambiguous_selectors(states)
    # Neither "foo" nor "foobar" should be flagged (they are distinct handles)
    assert "foo" not in ambiguous
    assert "foobar" not in ambiguous


def test_find_ambiguous_selectors_distinct_081_and_081_bar(tmp_path: Path) -> None:
    """081-foo and 081-bar both share prefix '081' — that prefix is ambiguous."""
    specs = tmp_path / "kitty-specs"
    _mission_dir(specs, "081-foo", _ULID_A, 81)
    _mission_dir(specs, "081-bar", _ULID_B, 81)
    states = audit_repo(tmp_path)
    ambiguous = find_ambiguous_selectors(states)
    assert "081" in ambiguous
    assert frozenset(s.slug for s in ambiguous["081"]) == frozenset(
        {"081-foo", "081-bar"}
    )


# ---------------------------------------------------------------------------
# T016: JSON schema contract via typer.testing.CliRunner
# ---------------------------------------------------------------------------


def test_identity_json_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--json emits a valid document matching the documented schema."""
    import specify_cli.cli.commands.doctor as doctor_mod
    from typer.testing import CliRunner

    from specify_cli.cli.commands.doctor import app

    specs = tmp_path / "kitty-specs"
    _mission_dir(specs, "001-assigned", _ULID_A, 1)
    _mission_dir(specs, "002-pending", _ULID_B, None)
    _mission_dir(specs, "003-legacy", None, 3)
    _mission_dir(specs, "004-orphan", None, None)
    _mission_dir(specs, "080-foo", _ULID_A, 80)
    _mission_dir(specs, "080-bar", _ULID_B, 80)

    # Patch at the module where the name is bound (doctor.py top-level import)
    monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: tmp_path)

    runner = CliRunner()
    result = runner.invoke(app, ["identity", "--json"])

    assert result.exit_code == 0, result.output
    doc = json.loads(result.output)

    # Top-level keys
    assert "summary" in doc
    assert "missions" in doc
    assert "duplicate_prefixes" in doc
    assert "ambiguous_selectors" in doc
    assert "fail_on_triggered" in doc

    # Summary counts all four states
    summary = doc["summary"]
    for state in ("assigned", "pending", "legacy", "orphan"):
        assert state in summary
    # 001-assigned (assigned), 080-foo (assigned), 080-bar (assigned) = 3 assigned
    assert summary["assigned"] == 3
    assert summary["pending"] == 1
    assert summary["legacy"] == 1
    assert summary["orphan"] == 1

    # Missions list
    missions = doc["missions"]
    slugs = {m["slug"] for m in missions}
    assert slugs == {
        "001-assigned",
        "002-pending",
        "003-legacy",
        "004-orphan",
        "080-foo",
        "080-bar",
    }

    # Each mission entry has the documented fields
    for m in missions:
        assert "slug" in m
        assert "mission_id" in m
        assert "mission_number" in m
        assert "state" in m
        assert "path" in m
        assert "error" in m

    # Duplicate prefixes
    assert "080" in doc["duplicate_prefixes"]
    assert frozenset(m["slug"] for m in doc["duplicate_prefixes"]["080"]) == frozenset(
        {"080-foo", "080-bar"}
    )

    # fail_on_triggered is False when --fail-on not given
    assert doc["fail_on_triggered"] is False


def test_identity_fail_on_legacy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--fail-on legacy exits 1 when a legacy mission exists."""
    import specify_cli.cli.commands.doctor as doctor_mod
    from typer.testing import CliRunner

    from specify_cli.cli.commands.doctor import app

    specs = tmp_path / "kitty-specs"
    _mission_dir(specs, "001-legacy", None, 1)

    monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: tmp_path)

    runner = CliRunner()
    result = runner.invoke(app, ["identity", "--json", "--fail-on", "legacy"])

    assert result.exit_code == 1
    doc = json.loads(result.output)
    assert doc["fail_on_triggered"] is True


def test_identity_fail_on_no_trigger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--fail-on legacy exits 0 when no legacy missions exist."""
    import specify_cli.cli.commands.doctor as doctor_mod
    from typer.testing import CliRunner

    from specify_cli.cli.commands.doctor import app

    specs = tmp_path / "kitty-specs"
    _mission_dir(specs, "001-assigned", _ULID_A, 1)

    monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: tmp_path)

    runner = CliRunner()
    result = runner.invoke(app, ["identity", "--json", "--fail-on", "legacy"])

    assert result.exit_code == 0
    doc = json.loads(result.output)
    assert doc["fail_on_triggered"] is False


def test_identity_mission_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--mission <slug> scopes the report to one mission."""
    import specify_cli.cli.commands.doctor as doctor_mod
    from typer.testing import CliRunner

    from specify_cli.cli.commands.doctor import app

    specs = tmp_path / "kitty-specs"
    _mission_dir(specs, "001-alpha", _ULID_A, 1)
    _mission_dir(specs, "002-beta", _ULID_B, 2)

    monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: tmp_path)

    runner = CliRunner()
    result = runner.invoke(app, ["identity", "--json", "--mission", "001-alpha"])

    assert result.exit_code == 0
    doc = json.loads(result.output)
    assert frozenset(m["slug"] for m in doc["missions"]) == frozenset({"001-alpha"})


# ---------------------------------------------------------------------------
# T017: NFR-002 timing — 200 missions in < 3 seconds
# ---------------------------------------------------------------------------


def _build_200_mission_repo(tmp_path: Path) -> Path:
    """Create a synthetic repo with 200 missions using raw meta.json writes.

    Uses raw file writes (not spec-kitty agent mission create) to stay fast.
    """
    specs = tmp_path / "kitty-specs"
    specs.mkdir(parents=True)
    for i in range(200):
        slug = f"{i + 1:03d}-test-mission-{i}"
        d = specs / slug
        d.mkdir()
        meta: dict[str, Any] = {
            "slug": slug,
            "mission_slug": slug,
            "friendly_name": slug,
            "mission_type": "software-dev",
            "target_branch": "main",
            "created_at": "2026-01-01T00:00:00+00:00",
            "mission_id": _ULID_A,
            "mission_number": i + 1,
        }
        (d / "meta.json").write_text(
            json.dumps(meta, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return tmp_path


def test_audit_200_missions_functional() -> None:
    """audit_repo + find_duplicate_prefixes + find_ambiguous_selectors is correct
    for a synthetic 200-mission repo (functional, #4015 split)."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = _build_200_mission_repo(Path(tmpdir))

        states = audit_repo(repo_root)
        dupes = find_duplicate_prefixes(repo_root)
        ambiguous = find_ambiguous_selectors(states)

        # Sanity checks: the data is correct
        assert len(states) == 200
        assert all(s.state == "assigned" for s in states)
        assert dupes == {}  # all distinct prefixes
        assert ambiguous == {}  # all distinct human slugs


@pytest.mark.performance
def test_nfr_002_timing_200_missions() -> None:
    """audit_repo + find_duplicate_prefixes + find_ambiguous_selectors must complete
    in < 3 seconds for a synthetic 200-mission repo (NFR-002, #4015 split)."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = _build_200_mission_repo(Path(tmpdir))

        start = time.monotonic()
        states = audit_repo(repo_root)
        find_duplicate_prefixes(repo_root)
        find_ambiguous_selectors(states)
        elapsed = time.monotonic() - start

        # NFR-002: must be under 3 seconds
        assert_timing_budget(elapsed, 3.0, name="elapsed")
