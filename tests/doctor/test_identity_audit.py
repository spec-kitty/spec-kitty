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


def test_audit_repo_unstattable_entry_is_skipped_not_crashed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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

    from tests._support.eacces import deny_path_method

    specs = tmp_path / "kitty-specs"
    specs.mkdir()
    _mission_dir(specs, "001-hello", _ULID_A, 1)

    vault = tmp_path / "vault"
    (vault / "m-target").mkdir(parents=True)
    (specs / "m-link").symlink_to(vault / "m-target", target_is_directory=True)

    # Deny the stat at the seam: root stats through a 0o000 directory (#5691).
    deny_path_method(monkeypatch, "stat", specs / "m-link")
    result = audit_repo(tmp_path)

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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`#3194` companion to ``test_audit_repo_unstattable_entry_is_skipped_not_crashed``,
    for ``find_duplicate_prefixes``'s own separate directory walk."""

    from tests._support.eacces import deny_path_method

    specs = tmp_path / "kitty-specs"
    _mission_dir(specs, "080-one", _ULID_A, 80)
    _mission_dir(specs, "080-two", _ULID_B, 80)

    vault = tmp_path / "vault"
    (vault / "m-target").mkdir(parents=True)
    (specs / "m-link").symlink_to(vault / "m-target", target_is_directory=True)

    # Deny the stat at the seam: root stats through a 0o000 directory (#5691).
    deny_path_method(monkeypatch, "stat", specs / "m-link")
    dupes = find_duplicate_prefixes(tmp_path)

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


# ---------------------------------------------------------------------------
# #5875: non-Mission kitty-specs/ folders are ``residue`` (FR-003..FR-006)
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    import subprocess

    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _residue_repo(tmp_path: Path) -> Path:
    """A git repo whose ``kitty-specs/`` mixes Missions and residue folders.

    Missions: ``001-mission`` (committed, with id), ``004-legacy`` (tracked
    id-less meta with a number), ``005-orphan`` (tracked id-less empty meta).
    Residue: ``001-spec-only`` (untracked spec.md, shares prefix 001 with a
    Mission), ``002-mission`` (tracked spec.md only, shares the human slug
    ``mission`` with ``001-mission``), ``003-noid`` (untracked id-less meta),
    ``006-lock-only`` (a gitignored lock and nothing else).
    """
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "T")
    (tmp_path / ".gitignore").write_text("*.lock\n", encoding="utf-8")
    specs = tmp_path / "kitty-specs"
    _mission_dir(specs, "001-mission", _ULID_A, None)
    _write_meta(specs / "004-legacy", {"mission_number": 4})
    _write_meta(specs / "005-orphan", {})
    (specs / "002-mission").mkdir(parents=True)
    (specs / "002-mission" / "spec.md").write_text("# s\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "fixture")
    (specs / "001-spec-only").mkdir()
    (specs / "001-spec-only" / "spec.md").write_text("# s\n", encoding="utf-8")
    _write_meta(specs / "003-noid", {"mission_number": 3})
    (specs / "006-lock-only").mkdir()
    (specs / "006-lock-only" / "index.json.lock").write_text("", encoding="utf-8")
    return tmp_path


_RESIDUE_SLUGS = frozenset({"001-spec-only", "002-mission", "003-noid", "006-lock-only"})


@pytest.mark.git_repo
def test_audit_repo_classifies_non_missions_as_residue(tmp_path: Path) -> None:
    repo = _residue_repo(tmp_path)

    by_slug = {s.slug: s for s in audit_repo(repo, residue_aware=True)}

    assert by_slug["001-mission"].state == "pending"
    assert by_slug["004-legacy"].state == "legacy"
    assert by_slug["005-orphan"].state == "orphan"
    for slug in _RESIDUE_SLUGS:
        residue = by_slug[slug]
        assert residue.state == "residue", slug
        assert residue.error is None
        assert residue.mission_id is None
        assert residue.mission_number is None


@pytest.mark.git_repo
def test_summarize_counts_and_lists_residue(tmp_path: Path) -> None:
    repo = _residue_repo(tmp_path)

    summary = summarize(audit_repo(repo, residue_aware=True))

    assert summary["counts"] == {"assigned": 0, "pending": 1, "legacy": 1, "orphan": 1, "residue": 4}
    residue_paths = summary["residue_paths"]
    assert isinstance(residue_paths, list)
    assert {Path(p).name for p in residue_paths} == _RESIDUE_SLUGS
    orphan_paths = summary["orphan_paths"]
    assert isinstance(orphan_paths, list)
    assert [Path(p).name for p in orphan_paths] == ["005-orphan"]


@pytest.mark.git_repo
def test_default_walk_keeps_the_pre_residue_contract(tmp_path: Path) -> None:
    """FR-008 / C-004: without ``residue_aware`` (the audit engine's call) nothing is ``residue``."""
    repo = _residue_repo(tmp_path)

    by_slug = {s.slug: s.state for s in audit_repo(repo)}

    assert "residue" not in by_slug.values()
    assert by_slug["001-spec-only"] == "orphan"
    assert by_slug["003-noid"] == "legacy"
    dupes = find_duplicate_prefixes(repo)
    assert {s.slug for s in dupes["001"]} == {"001-mission", "001-spec-only"}


def test_summarize_zero_fills_residue() -> None:
    summary = summarize([])
    assert summary["counts"] == {"assigned": 0, "pending": 0, "legacy": 0, "orphan": 0, "residue": 0}
    assert summary["residue_paths"] == []


@pytest.mark.git_repo
def test_residue_is_excluded_from_duplicate_prefixes(tmp_path: Path) -> None:
    repo = _residue_repo(tmp_path)
    assert "001" not in find_duplicate_prefixes(repo, residue_aware=True)


@pytest.mark.git_repo
def test_residue_is_excluded_from_ambiguous_selectors(tmp_path: Path) -> None:
    repo = _residue_repo(tmp_path)
    ambiguous = find_ambiguous_selectors(audit_repo(repo, residue_aware=True))
    assert "mission" not in ambiguous
    assert all(s.state != "residue" for items in ambiguous.values() for s in items)


def test_find_ambiguous_selectors_drops_residue_states() -> None:
    mission = IdentityState(Path("/r/kitty-specs/001-x"), "001-x", _ULID_A, 1, "assigned")
    residue = IdentityState(Path("/r/kitty-specs/002-x"), "002-x", None, None, "residue")
    assert find_ambiguous_selectors([mission, residue]) == {}


def test_id_less_meta_in_non_git_root_is_not_residue(tmp_path: Path) -> None:
    """Outside git the existence fallback holds: an id-less meta.json stays a Mission state."""
    specs = tmp_path / "kitty-specs"
    _write_meta(specs / "001-legacy", {"mission_number": 1})
    (specs / "002-spec-only").mkdir()
    (specs / "002-spec-only" / "spec.md").write_text("# s\n", encoding="utf-8")

    by_slug = {s.slug: s.state for s in audit_repo(tmp_path, residue_aware=True)}

    assert by_slug == {"001-legacy": "legacy", "002-spec-only": "residue"}


@pytest.mark.git_repo
def test_audit_makes_no_git_call_when_every_child_has_an_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-001: a walk whose every child carries a mission_id never probes git."""
    import specify_cli.context.mission_resolver as mr

    specs = tmp_path / "kitty-specs"
    _mission_dir(specs, "001-a", _ULID_A, 1)
    _mission_dir(specs, "002-b", _ULID_B, None)

    def _no_git(*_a: object, **_kw: object) -> object:
        raise AssertionError("git must not be probed when every child carries a mission_id")

    monkeypatch.setattr(mr, "run_git", _no_git)
    monkeypatch.setattr(mr, "tracked_paths", _no_git)
    monkeypatch.setattr(mr, "is_tracked", _no_git)

    assert {s.state for s in audit_repo(tmp_path, residue_aware=True)} == {"assigned", "pending"}
    assert find_duplicate_prefixes(tmp_path, residue_aware=True) == {}


@pytest.mark.git_repo
def test_audit_probes_git_at_most_once_per_walk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-002: at most one batch ``git ls-files`` per walk, however many id-less children."""
    import specify_cli.context.mission_resolver as mr

    repo = _residue_repo(tmp_path)
    calls: list[object] = []
    real = mr.tracked_paths

    def _counting(*args: Any, **kwargs: Any) -> Any:
        calls.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(mr, "tracked_paths", _counting)

    audit_repo(repo, residue_aware=True)

    assert len(calls) == 1


@pytest.mark.git_repo
def test_audit_repo_surfaces_a_broken_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``doctor identity`` is a read-only reporter: a broken index raises, never a weaker answer."""
    import specify_cli.context.mission_resolver as mr
    from kernel.git import GitCommandError

    repo = _residue_repo(tmp_path)

    def _broken(*_a: object, **_kw: object) -> object:
        raise GitCommandError(argv=("ls-files",), cwd=repo, returncode=128, stderr="index file corrupt")

    monkeypatch.setattr(mr, "tracked_paths", _broken)

    with pytest.raises(GitCommandError):
        audit_repo(repo, residue_aware=True)


def _invoke_identity(repo: Path, monkeypatch: pytest.MonkeyPatch, *args: str) -> Any:
    import specify_cli.cli.commands.doctor as doctor_mod
    from typer.testing import CliRunner

    monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: repo)
    return CliRunner().invoke(doctor_mod.app, ["identity", *args])


@pytest.mark.git_repo
def test_identity_json_reports_residue_with_remedy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands._identity_audit import RESIDUE_REMEDIES

    repo = _residue_repo(tmp_path)

    result = _invoke_identity(repo, monkeypatch, "--json")

    assert result.exit_code == 0, result.output
    doc = json.loads(result.output)
    assert doc["summary"]["residue"] == 4
    rows = {m["slug"]: m for m in doc["missions"]}
    assert rows["003-noid"] == {
        "path": str(repo / "kitty-specs" / "003-noid"),
        "slug": "003-noid",
        "mission_id": None,
        "mission_number": None,
        "state": "residue",
        "error": None,
        "residue_reason": "untracked_idless_meta",
    }
    assert rows["001-mission"]["residue_reason"] is None
    assert doc["residue_remedies"] == {reason: RESIDUE_REMEDIES[reason] for reason in ("no_meta", "untracked_idless_meta")}
    assert "residue_remedy" not in doc
    assert "001" not in doc["duplicate_prefixes"]
    assert "mission" not in doc["ambiguous_selectors"]


def test_identity_json_omits_remedy_without_residue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _mission_dir(tmp_path / "kitty-specs", "001-a", _ULID_A, 1)

    result = _invoke_identity(tmp_path, monkeypatch, "--json")

    assert result.exit_code == 0, result.output
    doc = json.loads(result.output)
    assert doc["summary"]["residue"] == 0
    assert "residue_remedies" not in doc and "residue_remedy" not in doc


@pytest.mark.git_repo
def test_identity_fail_on_residue_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _residue_repo(tmp_path)

    result = _invoke_identity(repo, monkeypatch, "--json", "--fail-on", "residue")

    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["fail_on_triggered"] is True


@pytest.mark.git_repo
def test_identity_human_output_shows_residue_section_and_remedy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _residue_repo(tmp_path)

    result = _invoke_identity(repo, monkeypatch)

    assert result.exit_code == 0, result.output
    flat = " ".join(result.output.split())
    assert "residue" in flat
    assert "Residue folders (not Missions; Mission selection does not list them):" in flat
    assert "006-lock-only" in flat
    assert flat.count("git restore <path>/meta.json") == 1  # the no_meta remedy, printed once for three rows
    assert flat.count("spec-kitty migrate backfill-identity") == 1  # the untracked_idless_meta remedy
    assert "spec-kitty agent mission create" in flat
    assert "could not be read" not in flat  # no corrupt_meta row, so no corrupt_meta remedy


@pytest.mark.git_repo
def test_identity_mission_scope_reports_residue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _residue_repo(tmp_path)

    result = _invoke_identity(repo, monkeypatch, "--json", "--mission", "001-spec-only")

    assert result.exit_code == 0, result.output
    doc = json.loads(result.output)
    assert [(m["slug"], m["state"]) for m in doc["missions"]] == [("001-spec-only", "residue")]
    assert doc["duplicate_prefixes"] == {}


# ---------------------------------------------------------------------------
# #5875 fold: residue reasons (D5), the broken-index message, the header count, NFR-002
# ---------------------------------------------------------------------------


@pytest.mark.git_repo
def test_residue_rows_carry_their_reason(tmp_path: Path) -> None:
    repo = _residue_repo(tmp_path)

    reasons = {s.slug: s.residue_reason for s in audit_repo(repo, residue_aware=True)}

    assert reasons == {
        "001-mission": None,
        "001-spec-only": "no_meta",
        "002-mission": "no_meta",
        "003-noid": "untracked_idless_meta",
        "004-legacy": None,
        "005-orphan": None,
        "006-lock-only": "no_meta",
    }


@pytest.mark.git_repo
@pytest.mark.parametrize("raw", ["{not json", "[1, 2]"], ids=["malformed", "non-object"])
def test_an_untracked_corrupt_meta_is_residue_with_its_read_error(tmp_path: Path, raw: str) -> None:
    """D5: a present but unparseable or non-object meta.json stays residue, reported as corrupt."""
    repo = _residue_repo(tmp_path)
    corrupt = repo / "kitty-specs" / "007-corrupt"
    corrupt.mkdir()
    (corrupt / "meta.json").write_text(raw, encoding="utf-8")

    row = {s.slug: s for s in audit_repo(repo, residue_aware=True)}["007-corrupt"]

    assert (row.state, row.residue_reason) == ("residue", "corrupt_meta")
    assert row.error and "meta.json" in row.error


@pytest.mark.git_repo
def test_an_unreadable_meta_is_residue_with_its_read_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """D5: an unreadable meta.json (EACCES) is residue with reason corrupt_meta, never "delete it"."""
    repo = _residue_repo(tmp_path)
    unreadable = repo / "kitty-specs" / "008-unreadable"
    _write_meta(unreadable, {"mission_id": _ULID_B})
    real_read_text = Path.read_text
    real_read_bytes = Path.read_bytes

    def _denied_text(self: Path, *args: Any, **kwargs: Any) -> str:
        if self.parent == unreadable:
            raise PermissionError(13, "Permission denied", str(self))
        return real_read_text(self, *args, **kwargs)

    def _denied_bytes(self: Path) -> bytes:
        if self.parent == unreadable:
            raise PermissionError(13, "Permission denied", str(self))
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_text", _denied_text)
    monkeypatch.setattr(Path, "read_bytes", _denied_bytes)

    row = {s.slug: s for s in audit_repo(repo, residue_aware=True)}["008-unreadable"]

    assert (row.state, row.residue_reason) == ("residue", "corrupt_meta")
    assert row.error


@pytest.mark.git_repo
def test_identity_human_output_groups_corrupt_residue_with_its_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _residue_repo(tmp_path)
    corrupt = repo / "kitty-specs" / "007-corrupt"
    corrupt.mkdir()
    (corrupt / "meta.json").write_text("{not json", encoding="utf-8")

    result = _invoke_identity(repo, monkeypatch)

    assert result.exit_code == 0, result.output
    flat = " ".join(result.output.split())
    assert "The Mission content is corrupt" in flat
    assert "Do not delete the folder before checking." in flat
    corrupt_line = next(line for line in result.output.splitlines() if "007-corrupt" in line)
    assert "meta.json" in corrupt_line.split("007-corrupt", 1)[1]  # the read error sits on the row


@pytest.mark.git_repo
def test_identity_json_names_the_corrupt_remedy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands._identity_audit import RESIDUE_REMEDIES

    repo = _residue_repo(tmp_path)
    corrupt = repo / "kitty-specs" / "007-corrupt"
    corrupt.mkdir()
    (corrupt / "meta.json").write_text("[1, 2]", encoding="utf-8")

    doc = json.loads(_invoke_identity(repo, monkeypatch, "--json").output)

    row = next(m for m in doc["missions"] if m["slug"] == "007-corrupt")
    assert row["residue_reason"] == "corrupt_meta" and row["error"]
    assert set(doc["residue_remedies"]) == {"no_meta", "untracked_idless_meta", "corrupt_meta"}
    assert doc["residue_remedies"]["corrupt_meta"] == RESIDUE_REMEDIES["corrupt_meta"]


def _corrupt_index_repo(tmp_path: Path) -> Path:
    """A git repo whose index is garbage, with an id-less meta.json so the walk must ask git."""
    repo = _residue_repo(tmp_path)
    (repo / ".git" / "index").write_bytes(b"not a git index" * 4)
    return repo


@pytest.mark.git_repo
def test_identity_with_a_broken_index_prints_one_line_and_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _corrupt_index_repo(tmp_path)

    result = _invoke_identity(repo, monkeypatch)

    assert result.exit_code == 1, result.output
    assert not isinstance(result.exception, Exception) or isinstance(result.exception, SystemExit), result.exception
    assert "Traceback" not in result.output
    flat = " ".join(result.output.split())
    assert "git index" in flat and "git reset" in flat


@pytest.mark.git_repo
def test_identity_json_with_a_broken_index_emits_an_error_envelope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _corrupt_index_repo(tmp_path)

    result = _invoke_identity(repo, monkeypatch, "--json")

    assert result.exit_code == 1, result.output
    doc = json.loads(result.output)
    assert doc["error_code"] == "GIT_INDEX_UNREADABLE"
    assert doc["error"] and "git reset" in doc["remediation"]


@pytest.mark.git_repo
def test_identity_header_counts_missions_and_residue_apart(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _residue_repo(tmp_path)

    result = _invoke_identity(repo, monkeypatch)

    flat = " ".join(result.output.split())
    assert "Mission Identity Audit — 3 Mission(s), 4 residue folder(s)" in flat


@pytest.mark.git_repo
@pytest.mark.performance
def test_nfr_002_timing_residue_aware_200_children_half_id_less(tmp_path: Path) -> None:
    """NFR-002 on the residue-aware path: a real git repo, 200 children, half without a mission_id."""
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    specs = tmp_path / "kitty-specs"
    for i in range(200):
        _mission_dir(specs, f"{i + 1:03d}-m{i}", _ULID_A if i % 2 == 0 else None, i + 1)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)

    start = time.monotonic()
    states = audit_repo(tmp_path, residue_aware=True)
    find_duplicate_prefixes(tmp_path, residue_aware=True)
    find_ambiguous_selectors(states)
    elapsed = time.monotonic() - start

    assert len(states) == 200 and "residue" not in {s.state for s in states}
    assert_timing_budget(elapsed, 3.0, name="elapsed")
