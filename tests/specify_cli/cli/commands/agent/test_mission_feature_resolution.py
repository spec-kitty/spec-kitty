"""Direct unit tests for the feature-dir resolution seam (#2056 WP02, Seam D).

These tests exercise the extracted resolvers in
``specify_cli.cli.commands.agent.mission_feature_resolution`` directly (no CLI
boot), pinning: handle → read-path resolution, ambiguous-handle structured
error (no silent fallback), sole-mission auto-select, candidate listing, the
silent-empty/silent-none meta readers, and the detection-error payload shape.

Behavior is preserved from the pre-decomposition ``mission.py``; the WP01 golden
harness is the CLI-surface regression net, these are the seam-level net.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mission_runtime import ActionContextError
from specify_cli.cli.commands.agent import mission_feature_resolution as seam
from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mission(specs: Path, slug: str, *, spec: bool = True, meta: bool = False) -> Path:
    d = specs / slug
    d.mkdir(parents=True, exist_ok=True)
    if spec:
        (d / "spec.md").write_text("# Spec\n", encoding="utf-8")
    if meta:
        (d / "meta.json").write_text(json.dumps({"mission_slug": slug}), encoding="utf-8")
    return d


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A repo root with a ``kitty-specs`` directory."""
    (tmp_path / "kitty-specs").mkdir(parents=True, exist_ok=True)
    return tmp_path


# ---------------------------------------------------------------------------
# _list_feature_spec_candidates
# ---------------------------------------------------------------------------


def test_list_candidates_empty_when_no_specs_dir(tmp_path: Path) -> None:
    """No ``kitty-specs`` directory → empty candidate list (no crash)."""
    assert seam._list_feature_spec_candidates(tmp_path) == []


def test_list_candidates_skips_dirs_without_spec_or_meta(repo: Path) -> None:
    """A bare directory (no spec.md / meta.json) is not a candidate."""
    (repo / "kitty-specs" / "001-empty").mkdir()
    _make_mission(repo / "kitty-specs", "002-real")
    candidates = seam._list_feature_spec_candidates(repo)
    slugs = {c["mission_slug"] for c in candidates}
    assert slugs == {"002-real"}


def test_list_candidates_includes_meta_only_mission(repo: Path) -> None:
    """A mission with only meta.json (no spec.md) is still a candidate."""
    _make_mission(repo / "kitty-specs", "003-meta-only", spec=False, meta=True)
    candidates = seam._list_feature_spec_candidates(repo)
    assert len(candidates) == 1
    assert candidates[0]["mission_slug"] == "003-meta-only"
    assert candidates[0]["spec_exists"] is False


# ---------------------------------------------------------------------------
# _sole_mission_slug_or_none
# ---------------------------------------------------------------------------


def test_sole_mission_none_when_zero(repo: Path) -> None:
    assert seam._sole_mission_slug_or_none(repo) is None


def test_sole_mission_returns_only_slug(repo: Path) -> None:
    _make_mission(repo / "kitty-specs", "001-only")
    assert seam._sole_mission_slug_or_none(repo) == "001-only"


def test_sole_mission_none_when_ambiguous(repo: Path) -> None:
    _make_mission(repo / "kitty-specs", "001-alpha")
    _make_mission(repo / "kitty-specs", "002-beta")
    assert seam._sole_mission_slug_or_none(repo) is None


# ---------------------------------------------------------------------------
# _sole_active_mission_slug_or_none (#4677)
# ---------------------------------------------------------------------------


def _make_merged_mission(specs: Path, slug: str) -> Path:
    """A completed mission: ``meta.json`` carries the ``merged_at`` marker."""
    d = _make_mission(specs, slug)
    (d / "meta.json").write_text(
        json.dumps({"mission_slug": slug, "merged_at": "2026-01-01T00:00:00+00:00"}),
        encoding="utf-8",
    )
    return d


def test_sole_active_mission_none_when_zero(repo: Path) -> None:
    assert seam._sole_active_mission_slug_or_none(repo) is None


def test_sole_active_mission_returns_only_slug(repo: Path) -> None:
    _make_mission(repo / "kitty-specs", "001-only")
    assert seam._sole_active_mission_slug_or_none(repo) == "001-only"


def test_sole_active_mission_ignores_completed_missions(repo: Path) -> None:
    """A merged mission does not count -- the one still-active mission is the default."""
    _make_merged_mission(repo / "kitty-specs", "001-shipped")
    _make_mission(repo / "kitty-specs", "002-live")
    assert seam._sole_active_mission_slug_or_none(repo) == "002-live"


def test_sole_active_mission_none_when_only_completed(repo: Path) -> None:
    _make_merged_mission(repo / "kitty-specs", "001-shipped")
    assert seam._sole_active_mission_slug_or_none(repo) is None


def test_sole_active_mission_none_when_ambiguous(repo: Path) -> None:
    _make_mission(repo / "kitty-specs", "001-alpha")
    _make_mission(repo / "kitty-specs", "002-beta")
    assert seam._sole_active_mission_slug_or_none(repo) is None


def test_sole_active_mission_unreadable_state_counts_as_active(repo: Path) -> None:
    """A corrupt ``meta.json`` must not silently pick the *other* mission."""
    corrupt = _make_mission(repo / "kitty-specs", "001-corrupt")
    (corrupt / "meta.json").write_text("{not json", encoding="utf-8")
    _make_mission(repo / "kitty-specs", "002-live")
    assert seam._sole_active_mission_slug_or_none(repo) is None


# ---------------------------------------------------------------------------
# _build_setup_plan_detection_error
# ---------------------------------------------------------------------------


def test_detection_error_no_candidates_payload(repo: Path) -> None:
    payload = seam._build_setup_plan_detection_error(repo, "base", None)
    assert payload["error_code"] == "PLAN_CONTEXT_UNRESOLVED"
    assert payload["mission_flag"] is None
    assert "spec_kitty_version" in payload
    assert payload["error"] == "No missions found in kitty-specs/"
    assert "remediation" in payload
    # No-candidate branch carries no available_missions / example_command.
    assert "available_missions" not in payload
    assert "example_command" not in payload


def test_detection_error_multi_candidate_payload(repo: Path) -> None:
    _make_mission(repo / "kitty-specs", "001-alpha")
    _make_mission(repo / "kitty-specs", "002-beta")
    payload = seam._build_setup_plan_detection_error(repo, "base", None)
    assert payload["error_code"] == "PLAN_CONTEXT_UNRESOLVED"
    assert payload["available_missions"] == ["001-alpha", "002-beta"]
    assert "2 missions found" in str(payload["error"])
    assert str(payload["example_command"]).startswith(
        "spec-kitty agent mission setup-plan --mission 001-alpha"
    )
    assert payload["remediation"] == "Re-run with --mission <slug>"


def test_detection_error_custom_command_and_args(repo: Path) -> None:
    _make_mission(repo / "kitty-specs", "001-alpha")
    _make_mission(repo / "kitty-specs", "002-beta")
    payload = seam._build_setup_plan_detection_error(
        repo,
        "base",
        "bad-flag",
        error_code="CUSTOM_CODE",
        command_name="finalize-tasks",
        command_args=["--validate-only", "--json"],
    )
    assert payload["error_code"] == "CUSTOM_CODE"
    assert payload["mission_flag"] == "bad-flag"
    assert (
        payload["example_command"]
        == "spec-kitty agent mission finalize-tasks --mission 001-alpha --validate-only --json"
    )


# ---------------------------------------------------------------------------
# _read_feature_meta / _safe_load_meta (silent-empty / silent-none contracts)
# ---------------------------------------------------------------------------


def test_read_feature_meta_missing_returns_empty(tmp_path: Path) -> None:
    """Missing meta.json degrades to {} — never raises."""
    assert seam._read_feature_meta(tmp_path) == {}


def test_read_feature_meta_malformed_returns_empty(tmp_path: Path) -> None:
    """Malformed meta.json degrades to {} — never raises."""
    (tmp_path / "meta.json").write_text("{not json", encoding="utf-8")
    assert seam._read_feature_meta(tmp_path) == {}


def test_read_feature_meta_valid(tmp_path: Path) -> None:
    (tmp_path / "meta.json").write_text(json.dumps({"k": "v"}), encoding="utf-8")
    assert seam._read_feature_meta(tmp_path) == {"k": "v"}


def test_safe_load_meta_returns_none_for_unknown_mission(repo: Path) -> None:
    """An unresolvable mission slug yields None (mid8 derivation falls back)."""
    assert seam._safe_load_meta(repo, "999-nonexistent") is None


# ---------------------------------------------------------------------------
# _find_feature_directory (no silent fallback)
# ---------------------------------------------------------------------------


def test_find_feature_directory_requires_handle(repo: Path) -> None:
    """No handle → structured MISSION_CONTEXT_UNRESOLVED error."""
    with pytest.raises(ActionContextError) as excinfo:
        seam._find_feature_directory(repo, repo, explicit_feature=None)
    assert excinfo.value.code == "MISSION_CONTEXT_UNRESOLVED"


def test_find_feature_directory_blank_handle_rejected(repo: Path) -> None:
    with pytest.raises(ActionContextError) as excinfo:
        seam._find_feature_directory(repo, repo, explicit_feature="   ")
    assert excinfo.value.code == "MISSION_CONTEXT_UNRESOLVED"


def test_find_feature_directory_not_found_is_structured(repo: Path) -> None:
    """An unresolvable handle raises a structured (not bare) error."""
    with pytest.raises(ActionContextError) as excinfo:
        seam._find_feature_directory(repo, repo, explicit_feature="999-nope")
    assert excinfo.value.code == "MISSION_CONTEXT_UNRESOLVED"


def test_find_feature_directory_ambiguous_propagates_error_code(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An ambiguous selector surfaces MissionSelectorAmbiguous's error_code."""

    def _raise_ambiguous(*_args: object, **_kwargs: object) -> Path:
        raise MissionSelectorAmbiguous(handle="amb", candidates=["001-a", "002-b"])

    monkeypatch.setattr(
        "specify_cli.missions._read_path_resolver.resolve_handle_to_read_path",
        _raise_ambiguous,
    )
    with pytest.raises(ActionContextError) as excinfo:
        seam._find_feature_directory(repo, repo, explicit_feature="ambiguous")
    assert excinfo.value.code == "MISSION_AMBIGUOUS_SELECTOR"


# ---------------------------------------------------------------------------
# _primary_anchored_feature_dir / _resolve_mission_dir_name_primary_anchored
# ---------------------------------------------------------------------------


def test_primary_anchored_none_without_handle(repo: Path) -> None:
    assert seam._primary_anchored_feature_dir(repo, None) is None
    assert seam._primary_anchored_feature_dir(repo, "  ") is None


def test_resolve_mission_dir_name_none_without_handle(repo: Path) -> None:
    assert seam._resolve_mission_dir_name_primary_anchored(repo, None) is None
    assert seam._resolve_mission_dir_name_primary_anchored(repo, "") is None


def test_primary_anchored_resolves_existing_primary_dir(repo: Path) -> None:
    """A literal slug whose primary dir exists resolves to that dir."""
    _make_mission(repo / "kitty-specs", "001-real-mission")
    resolved = seam._primary_anchored_feature_dir(repo, "001-real-mission")
    assert resolved is not None
    assert resolved.name == "001-real-mission"


def test_primary_anchored_none_for_unknown(repo: Path) -> None:
    assert seam._primary_anchored_feature_dir(repo, "404-missing") is None


def test_primary_anchored_ambiguous_raises_structured_error(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An ambiguous handle surfaces a structured ActionContextError (no silent fallback)."""

    def _raise_ambiguous(*_args: object, **_kwargs: object) -> str | None:
        raise MissionSelectorAmbiguous(handle="amb", candidates=["001-a", "002-b"])

    monkeypatch.setattr(
        seam, "_resolve_mission_dir_name_primary_anchored", _raise_ambiguous
    )
    with pytest.raises(ActionContextError) as excinfo:
        seam._primary_anchored_feature_dir(repo, "ambiguous")
    assert excinfo.value.code == "MISSION_AMBIGUOUS_SELECTOR"
