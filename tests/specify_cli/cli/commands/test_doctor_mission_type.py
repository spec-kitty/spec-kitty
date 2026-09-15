"""ATDD pin for ``spec-kitty doctor mission-type`` (FR-007, FR-008, FR-009, NFR-004).

Modeled directly on ``tests/specify_cli/cli/commands/test_identity_audit.py`` and
``tests/doctor/test_identity_audit.py`` — the precedent ``doctor identity``'s own
test suites.

Covers:
- FR-008: the six-state taxonomy classifies every fixture mission correctly,
  including the boundary case (blank/null/non-string ``mission_type`` classifies
  as ``typeless``, never falling through to the legacy ``mission`` key).
- FR-009 / SC-006: ``--fail-on`` exit-code contract, matching ``doctor identity``.
- NFR-004: an automated timing regression test (200-mission synthetic repo,
  < 2 seconds), mirroring ``test_nfr_002_timing_200_missions``'s shape.

This whole file is RED against the WP's base commit: no ``mission-type`` Typer
command is registered yet, so every assertion fails at the CLI-invocation
boundary (and the direct-import tests fail to collect).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from tests._perf_helpers import assert_timing_budget

pytestmark = [pytest.mark.fast]

_CUSTOM_UNRESOLVABLE_TYPE = "custom-unresolvable-type"
_UNKNOWN_TYPE = "totally-unregistered-mission-type"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_meta(feature_dir: Path, meta: dict[str, Any]) -> None:
    """Write a minimal meta.json for test fixtures."""
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_config(repo_root: Path, activated: list[str]) -> None:
    """Write a minimal .kittify/config.yaml activating the given mission types."""
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    lines = ["mission_type_activations:"]
    lines += [f"  - {mission_type}" for mission_type in activated]
    (kittify / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_taxonomy_repo(tmp_path: Path) -> Path:
    """Build a kitty-specs/ tree with one mission per FR-008 taxonomy state,
    plus the FR-008 boundary case (blank mission_type wins over a real legacy
    `mission` value).

    `software-dev` is activated AND a real built-in doctrine YAML (resolved).
    `_CUSTOM_UNRESOLVABLE_TYPE` is activated but has no doctrine YAML
    (activated-unresolvable). `_UNKNOWN_TYPE` is neither activated nor a
    built-in (unknown).
    """
    specs = tmp_path / "kitty-specs"

    _write_meta(specs / "001-resolved", {"mission_type": "software-dev"})
    _write_meta(
        specs / "002-activated-unresolvable",
        {"mission_type": _CUSTOM_UNRESOLVABLE_TYPE},
    )
    _write_meta(specs / "003-unknown", {"mission_type": _UNKNOWN_TYPE})
    _write_meta(specs / "004-typeless", {})
    _write_meta(specs / "005-legacy-key-only", {"mission": "software-dev"})
    (specs / "006-error").mkdir(parents=True)
    (specs / "006-error" / "meta.json").write_text("{not valid json", encoding="utf-8")
    # FR-008 boundary case: a present-but-blank `mission_type` key classifies
    # as typeless REGARDLESS of the legacy `mission` key holding a real value.
    _write_meta(
        specs / "007-blank-wins-over-legacy",
        {"mission_type": "", "mission": "software-dev"},
    )

    _write_config(tmp_path, ["software-dev", _CUSTOM_UNRESOLVABLE_TYPE])
    return tmp_path


_ALL_TAXONOMY_SLUGS = {
    "001-resolved",
    "002-activated-unresolvable",
    "003-unknown",
    "004-typeless",
    "005-legacy-key-only",
    "006-error",
    "007-blank-wins-over-legacy",
}


# ---------------------------------------------------------------------------
# FR-008 / SC-005: CLI classification of every taxonomy state
# ---------------------------------------------------------------------------


def test_mission_type_json_classifies_every_taxonomy_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--json classifies every fixture mission into the correct, single state
    (SC-005) — none omitted, and the FR-008 boundary case is exercised."""
    import specify_cli.cli.commands.doctor as doctor_mod
    from typer.testing import CliRunner

    from specify_cli.cli.commands.doctor import app

    repo_root = _build_taxonomy_repo(tmp_path)
    monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: repo_root)

    runner = CliRunner()
    result = runner.invoke(app, ["mission-type", "--json"])

    assert result.exit_code == 0, result.output
    doc = json.loads(result.output)

    by_slug = {m["slug"]: m["state"] for m in doc["missions"]}
    assert set(by_slug) == _ALL_TAXONOMY_SLUGS

    assert by_slug["001-resolved"] == "resolved"
    assert by_slug["002-activated-unresolvable"] == "activated-unresolvable"
    assert by_slug["003-unknown"] == "unknown"
    assert by_slug["004-typeless"] == "typeless"
    assert by_slug["005-legacy-key-only"] == "legacy-key-only"
    assert by_slug["006-error"] == "error"
    # FR-008 boundary case: blank mission_type wins over the legacy `mission`
    # key holding a real value — this is the plausible-but-wrong trap.
    assert by_slug["007-blank-wins-over-legacy"] == "typeless"

    # Summary is zero-filled across all six states.
    for state in (
        "resolved",
        "activated-unresolvable",
        "unknown",
        "typeless",
        "legacy-key-only",
        "error",
    ):
        assert state in doc["summary"]
    assert doc["summary"]["resolved"] == 1
    assert doc["summary"]["activated-unresolvable"] == 1
    assert doc["summary"]["unknown"] == 1
    assert doc["summary"]["typeless"] == 2  # 004 + 007
    assert doc["summary"]["legacy-key-only"] == 1
    assert doc["summary"]["error"] == 1

    assert doc["fail_on_triggered"] is False


def test_mission_type_mission_entry_has_documented_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each mission entry in --json carries the documented fields."""
    import specify_cli.cli.commands.doctor as doctor_mod
    from typer.testing import CliRunner

    from specify_cli.cli.commands.doctor import app

    repo_root = _build_taxonomy_repo(tmp_path)
    monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: repo_root)

    runner = CliRunner()
    result = runner.invoke(app, ["mission-type", "--json"])
    doc = json.loads(result.output)

    for m in doc["missions"]:
        assert "path" in m
        assert "slug" in m
        assert "mission_type_raw" in m
        assert "resolved_key" in m
        assert "state" in m
        assert "error" in m

    by_slug = {m["slug"]: m for m in doc["missions"]}
    assert by_slug["001-resolved"]["mission_type_raw"] == "software-dev"
    assert by_slug["001-resolved"]["resolved_key"] == "software-dev"
    assert by_slug["005-legacy-key-only"]["mission_type_raw"] is None
    assert by_slug["005-legacy-key-only"]["resolved_key"] == "software-dev"
    assert by_slug["006-error"]["error"] is not None


# ---------------------------------------------------------------------------
# FR-008 boundary case: direct classifier-level coverage (null / non-string)
# ---------------------------------------------------------------------------


def test_classify_mission_type_null_value_is_typeless(tmp_path: Path) -> None:
    from specify_cli.cli.commands._mission_type_audit import classify_mission_type

    d = tmp_path / "kitty-specs" / "001-null"
    _write_meta(d, {"mission_type": None, "mission": "software-dev"})

    state = classify_mission_type(d, registered=["software-dev"], roster={})
    assert state.state == "typeless"
    assert state.mission_type_raw is None


def test_classify_mission_type_non_string_value_is_typeless(tmp_path: Path) -> None:
    from specify_cli.cli.commands._mission_type_audit import classify_mission_type

    d = tmp_path / "kitty-specs" / "001-non-string"
    _write_meta(d, {"mission_type": 42, "mission": "software-dev"})

    state = classify_mission_type(d, registered=["software-dev"], roster={})
    assert state.state == "typeless"
    assert state.mission_type_raw is None


def test_classify_mission_type_missing_meta_json_is_typeless(tmp_path: Path) -> None:
    from specify_cli.cli.commands._mission_type_audit import classify_mission_type

    d = tmp_path / "kitty-specs" / "001-no-meta"
    d.mkdir(parents=True)

    state = classify_mission_type(d, registered=[], roster={})
    assert state.state == "typeless"


def test_classify_mission_type_to_dict_shape(tmp_path: Path) -> None:
    from specify_cli.cli.commands._mission_type_audit import classify_mission_type

    d = tmp_path / "kitty-specs" / "001-resolved"
    _write_meta(d, {"mission_type": "software-dev"})

    state = classify_mission_type(
        d, registered=["software-dev"], roster={"software-dev": object()}
    )
    payload = state.to_dict()
    assert payload["slug"] == "001-resolved"
    assert payload["state"] == "resolved"
    assert payload["mission_type_raw"] == "software-dev"
    assert payload["resolved_key"] == "software-dev"
    assert payload["error"] is None


def test_classify_present_key_resolves_non_builtin_type_via_roster() -> None:
    """Finding 1 (#3402 landing): an activated org-/project-pack custom mission
    type that resolves in the LAYERED roster but is absent from the built-in
    bundle must classify as ``resolved`` — not ``activated-unresolvable``. The
    built-in-only repository would have misreported it, redding a valid
    ``--fail-on activated-unresolvable`` gate.
    """
    from specify_cli.cli.commands._mission_type_audit import _classify_present_key

    org_type = "org-custom-mission-type"
    # Roster mirrors resolve_layered_mission_types' output: the custom type is
    # present (project > org > built-in), even though it is not a built-in.
    resolved_key, state = _classify_present_key(
        org_type, registered=[org_type], roster={org_type: object()}
    )
    assert state == "resolved"
    assert resolved_key == org_type

    # Absent from every layer of the roster → the activated-unresolvable twin of
    # _resolve_action_slot's UnknownMissionTypeError.
    _, missing_state = _classify_present_key(org_type, registered=[org_type], roster={})
    assert missing_state == "activated-unresolvable"


def test_classify_mission_type_classification_helper_exception_is_error_not_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-008 Edge Case: 'one bad mission must never crash the whole audit
    run' also covers bugs in the classification helpers that run AFTER the
    meta.json read, not just the read itself. A mission whose classifier
    raises must be reported as ``error`` with the reason preserved — never
    let the exception propagate out of ``classify_mission_type``.
    """
    import specify_cli.cli.commands._mission_type_audit as mission_type_audit_mod

    d = tmp_path / "kitty-specs" / "001-boom"
    _write_meta(d, {"mission_type": "software-dev"})

    def _boom(raw_val: object) -> str | None:
        raise RuntimeError("classifier exploded")

    monkeypatch.setattr(mission_type_audit_mod, "canonical_mission_type_key", _boom)

    state = mission_type_audit_mod.classify_mission_type(
        d, registered=["software-dev"], roster={}
    )
    assert state.state == "error"
    assert state.error is not None
    assert "classifier exploded" in state.error


def test_audit_mission_types_classification_error_does_not_abort_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-008 Edge Case, run-level: one mission whose classifier blows up
    must not abort the whole ``audit_mission_types`` walk — every other
    mission in the tree must still be classified and reported.
    """
    import specify_cli.cli.commands._mission_type_audit as mission_type_audit_mod

    specs = tmp_path / "kitty-specs"
    _write_meta(specs / "001-good", {"mission_type": "software-dev"})
    _write_meta(specs / "002-boom", {"mission_type": "software-dev"})
    _write_config(tmp_path, ["software-dev"])

    real_canonical = mission_type_audit_mod.canonical_mission_type_key
    calls = {"n": 0}

    def _flaky(raw_val: object) -> str | None:
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("classifier exploded")
        return real_canonical(raw_val)

    monkeypatch.setattr(mission_type_audit_mod, "canonical_mission_type_key", _flaky)

    states = mission_type_audit_mod.audit_mission_types(tmp_path)
    # Exact-membership (not a bare count): both missions were classified, none
    # dropped, none duplicated, nothing extra materialized by the walk.
    assert sorted(s.slug for s in states) == ["001-good", "002-boom"]
    by_slug = {s.slug: s for s in states}
    assert by_slug["001-good"].state == "resolved"
    assert by_slug["002-boom"].state == "error"
    assert by_slug["002-boom"].error is not None
    assert "classifier exploded" in (by_slug["002-boom"].error or "")


def test_audit_mission_types_resolves_org_pack_type_via_layered_roster(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding 1 (#3402 landing): ``audit_mission_types`` must classify an
    activated non-built-in (org/project pack) mission type as ``resolved`` by
    consulting the LAYERED roster (``resolve_layered_mission_types`` — the same
    factory the runtime's ``_resolve_action_slot`` uses), not the built-in-only
    ``MissionTypeRepository.default()``. Patching the layered resolver proves
    the wiring: were the audit still built-in-only, this patch would be inert
    and the type would misreport as ``activated-unresolvable``.
    """
    import specify_cli.cli.commands._mission_type_audit as mission_type_audit_mod

    org_type = "org-custom-mission-type"
    specs = tmp_path / "kitty-specs"
    _write_meta(specs / "001-org-custom", {"mission_type": org_type})
    _write_config(tmp_path, [org_type])

    def _fake_layered(mission_types_dirs: object, pack_context: object) -> dict[str, object]:
        return {org_type: object()}

    monkeypatch.setattr(
        mission_type_audit_mod, "resolve_layered_mission_types", _fake_layered
    )

    states = mission_type_audit_mod.audit_mission_types(tmp_path)
    by_slug = {s.slug: s for s in states}
    assert by_slug["001-org-custom"].state == "resolved"


# ---------------------------------------------------------------------------
# audit_mission_types / summarize_mission_types (direct, unit-level)
# ---------------------------------------------------------------------------


def test_audit_mission_types_no_specs_dir_returns_empty(tmp_path: Path) -> None:
    from specify_cli.cli.commands._mission_type_audit import audit_mission_types

    assert audit_mission_types(tmp_path) == []


def test_audit_mission_types_skips_non_directories(tmp_path: Path) -> None:
    from specify_cli.cli.commands._mission_type_audit import audit_mission_types

    specs = tmp_path / "kitty-specs"
    specs.mkdir()
    (specs / "README.md").write_text("ignore me", encoding="utf-8")
    _write_meta(specs / "001-resolved", {"mission_type": "software-dev"})
    _write_config(tmp_path, ["software-dev"])

    states = audit_mission_types(tmp_path)
    # Exact-membership (not a bare count): the README non-directory entry was
    # skipped and exactly the one real mission directory was classified.
    assert [s.slug for s in states] == ["001-resolved"]


def test_summarize_mission_types_zero_filled() -> None:
    from specify_cli.cli.commands._mission_type_audit import summarize_mission_types

    summary = summarize_mission_types([])
    counts = summary["counts"]
    assert isinstance(counts, dict)
    for state in (
        "resolved",
        "activated-unresolvable",
        "unknown",
        "typeless",
        "legacy-key-only",
        "error",
    ):
        assert state in counts
        assert counts[state] == 0


# ---------------------------------------------------------------------------
# FR-009 / SC-006: --fail-on exit-code contract (matches doctor identity)
# ---------------------------------------------------------------------------


def test_mission_type_fail_on_unknown_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import specify_cli.cli.commands.doctor as doctor_mod
    from typer.testing import CliRunner

    from specify_cli.cli.commands.doctor import app

    repo_root = _build_taxonomy_repo(tmp_path)
    monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: repo_root)

    runner = CliRunner()
    result = runner.invoke(app, ["mission-type", "--json", "--fail-on", "unknown"])

    assert result.exit_code == 1
    doc = json.loads(result.output)
    assert doc["fail_on_triggered"] is True


def test_mission_type_no_fail_on_exits_zero_regardless_of_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exits zero with no --fail-on flag regardless of findings (SC-006)."""
    import specify_cli.cli.commands.doctor as doctor_mod
    from typer.testing import CliRunner

    from specify_cli.cli.commands.doctor import app

    repo_root = _build_taxonomy_repo(tmp_path)
    monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: repo_root)

    runner = CliRunner()
    result = runner.invoke(app, ["mission-type", "--json"])

    assert result.exit_code == 0
    doc = json.loads(result.output)
    assert doc["fail_on_triggered"] is False


def test_mission_type_fail_on_state_with_no_matches_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import specify_cli.cli.commands.doctor as doctor_mod
    from typer.testing import CliRunner

    from specify_cli.cli.commands.doctor import app

    repo_root = tmp_path
    _write_meta(repo_root / "kitty-specs" / "001-resolved", {"mission_type": "software-dev"})
    _write_config(repo_root, ["software-dev"])
    monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: repo_root)

    runner = CliRunner()
    result = runner.invoke(app, ["mission-type", "--json", "--fail-on", "unknown"])

    assert result.exit_code == 0
    doc = json.loads(result.output)
    assert doc["fail_on_triggered"] is False


def test_mission_type_fail_on_rejects_unknown_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding 2 (#3402 landing): a misspelled --fail-on state (e.g. ``unkown``)
    must fail loudly — exit 2 (typer.BadParameter / click UsageError) — NOT
    silently match nothing and exit 0, which would be a vacuous-green CI gate.
    """
    import specify_cli.cli.commands.doctor as doctor_mod
    from typer.testing import CliRunner

    from specify_cli.cli.commands.doctor import app

    repo_root = _build_taxonomy_repo(tmp_path)
    monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: repo_root)

    runner = CliRunner()
    result = runner.invoke(app, ["mission-type", "--json", "--fail-on", "unkown"])

    # Exit 2 is click's UsageError convention — distinct from the old vacuous
    # 0 (nothing matched) and from a legitimate --fail-on trigger (1).
    assert result.exit_code == 2, result.output


def test_mission_type_mission_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--mission <slug> scopes the report to one mission."""
    import specify_cli.cli.commands.doctor as doctor_mod
    from typer.testing import CliRunner

    from specify_cli.cli.commands.doctor import app

    repo_root = _build_taxonomy_repo(tmp_path)
    monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: repo_root)

    runner = CliRunner()
    result = runner.invoke(app, ["mission-type", "--json", "--mission", "001-resolved"])

    assert result.exit_code == 0
    doc = json.loads(result.output)
    assert {m["slug"] for m in doc["missions"]} == {"001-resolved"}


def test_mission_type_mission_scope_not_found_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import specify_cli.cli.commands.doctor as doctor_mod
    from typer.testing import CliRunner

    from specify_cli.cli.commands.doctor import app

    repo_root = _build_taxonomy_repo(tmp_path)
    monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: repo_root)

    runner = CliRunner()
    result = runner.invoke(app, ["mission-type", "--json", "--mission", "999-nope"])

    assert result.exit_code == 1


def test_mission_type_human_output_smoke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The human-readable (non-JSON) path renders without crashing."""
    import specify_cli.cli.commands.doctor as doctor_mod
    from typer.testing import CliRunner

    from specify_cli.cli.commands.doctor import app

    repo_root = _build_taxonomy_repo(tmp_path)
    monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: repo_root)

    runner = CliRunner()
    result = runner.invoke(app, ["mission-type", "--fail-on", "unknown"])

    assert result.exit_code == 1
    assert "Mission Type Audit" in result.output
    assert "FAIL" in result.output


# ---------------------------------------------------------------------------
# NFR-004: automated timing regression — 200 missions in < 2 seconds
# (TASKS-VERIFY-004 fix; mirrors test_nfr_002_timing_200_missions's shape)
# ---------------------------------------------------------------------------


def _build_200_mission_type_repo(tmp_path: Path) -> Path:
    """Create a synthetic repo with 200 missions using raw meta.json writes."""
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
        }
        (d / "meta.json").write_text(
            json.dumps(meta, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    _write_config(tmp_path, ["software-dev"])
    return tmp_path


def test_audit_mission_types_resolves_200_missions() -> None:
    """audit_mission_types resolves every mission in a synthetic 200-mission repo."""
    import tempfile

    from specify_cli.cli.commands._mission_type_audit import audit_mission_types

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = _build_200_mission_type_repo(Path(tmpdir))

        states = audit_mission_types(repo_root)

        # Sanity checks: the data is correct.
        assert len(states) == 200
        assert all(s.state == "resolved" for s in states)


@pytest.mark.performance
def test_nfr_004_timing_200_missions() -> None:
    """audit_mission_types must complete in < 2 seconds for a synthetic
    200-mission repo (NFR-004)."""
    import tempfile

    from specify_cli.cli.commands._mission_type_audit import audit_mission_types

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = _build_200_mission_type_repo(Path(tmpdir))

        start = time.monotonic()
        audit_mission_types(repo_root)
        elapsed = time.monotonic() - start

        # NFR-004: must be under 2 seconds.
        assert_timing_budget(elapsed, 2.0, name="audit_mission_types (200 missions)")
