"""Focused per-helper tests for ``_coordination_doctor`` (WP07, #2059).

Exercise the git-version detect/check branches, the tracked-.worktrees/ hygiene
check, the decomposed lane sparse-checkout drift sub-helpers, the finding
aggregation + emission, and the entrypoint exit contract. Also asserts the H2
invariant: the ``merge.path_is_under_worktrees`` import is function-local and no
``doctor <-> merge`` cycle exists.
"""

from __future__ import annotations

import json as _json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
import typer

from specify_cli.cli.commands import _coordination_doctor as cd
from specify_cli.coordination.coherence import coord_incoherent_done_wps
from specify_cli.merge.state import MergeState, load_state, save_state
from tests._support.eacces import mode_bits_enforced

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# --- _detect_git_version -----------------------------------------------------


def test_detect_git_version_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: "git version 2.45.1\n")
    assert cd._detect_git_version() == (2, 45)


def test_detect_git_version_command_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_a: Any, **_k: Any) -> str:
        raise OSError("no git")

    monkeypatch.setattr(subprocess, "check_output", _boom)
    assert cd._detect_git_version() is None


def test_detect_git_version_unparseable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: "weird output")
    assert cd._detect_git_version() is None


def test_detect_git_version_non_numeric(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: "git version x.y.z")
    assert cd._detect_git_version() is None


# --- _check_git_version ------------------------------------------------------


def test_check_git_version_too_old() -> None:
    out = cd._check_git_version((2, 20))
    assert out[0].severity == "error"
    assert out[0].error_code == "GIT_VERSION_TOO_OLD"


def test_check_git_version_ok() -> None:
    out = cd._check_git_version((2, 40))
    assert out[0].severity == "ok"


def test_check_git_version_undetectable_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cd, "_detect_git_version", lambda: None)
    out = cd._check_git_version()
    assert out[0].error_code == "GIT_VERSION_UNDETECTABLE"


# --- _check_tracked_worktrees_content ----------------------------------------


def test_tracked_worktrees_clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: "")
    out = cd._check_tracked_worktrees_content(tmp_path)
    assert out[0].severity == "ok"


def test_tracked_worktrees_flagged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        subprocess, "check_output", lambda *a, **k: ".worktrees/m-coord/file.txt\n"
    )
    out = cd._check_tracked_worktrees_content(tmp_path)
    assert out[0].severity == "error"
    assert out[0].error_code == "TRACKED_WORKTREES_CONTENT"


def test_tracked_worktrees_git_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def _boom(*_a: Any, **_k: Any) -> str:
        raise OSError("not a repo")

    monkeypatch.setattr(subprocess, "check_output", _boom)
    assert cd._check_tracked_worktrees_content(tmp_path) == []


# --- _coordination_identity --------------------------------------------------


def test_coordination_identity_legacy() -> None:
    assert cd._coordination_identity({}) is None


def test_coordination_identity_incomplete() -> None:
    assert cd._coordination_identity({"coordination_branch": "x"}) == ("", "", "")


def test_coordination_identity_complete() -> None:
    meta: dict[str, object] = {"coordination_branch": "kitty/x", "mission_slug": "m", "mission_id": "01ABC"}
    assert cd._coordination_identity(meta) == ("kitty/x", "m", "01ABC")


# --- _check_coordination_worktree_health -------------------------------------


def test_coord_health_legacy_skips() -> None:
    assert cd._check_coordination_worktree_health(Path("/x"), {}) == []


def test_coord_health_incomplete_meta() -> None:
    out = cd._check_coordination_worktree_health(Path("/x"), {"coordination_branch": "y"})
    assert out[0].error_code == "COORDINATION_META_INCOMPLETE"


def test_coord_health_missing_worktree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from specify_cli import coordination as coord_mod

    monkeypatch.setattr(
        coord_mod.CoordinationWorkspace,
        "worktree_path",
        staticmethod(lambda *_a: tmp_path / "missing-coord"),
    )
    from specify_cli.lanes import branch_naming

    monkeypatch.setattr(branch_naming, "resolve_mid8", lambda *a, **k: "01ABCDEF")
    meta: dict[str, object] = {"coordination_branch": "kitty/x", "mission_slug": "m", "mission_id": "01ABCDEF"}
    out = cd._check_coordination_worktree_health(tmp_path, meta)
    assert out[0].error_code == "COORDINATION_WORKTREE_MISSING"


# --- _scan_lane_sparse_drift -------------------------------------------------


def test_scan_lane_unresolvable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cd, "_lane_sparse_file", lambda _d: None)
    finding = cd._scan_lane_sparse_drift(tmp_path, {"a"})
    assert finding is not None
    assert finding.error_code == cd._LANE_DRIFT_CODE


def test_scan_lane_missing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cd, "_lane_sparse_file", lambda _d: tmp_path / "nope")
    finding = cd._scan_lane_sparse_drift(tmp_path, {"a"})
    assert finding is not None
    assert "missing the sparse-checkout" in finding.message


def test_scan_lane_drift_detected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sparse = tmp_path / "sparse"
    sparse.write_text("pattern-a\n", encoding="utf-8")
    monkeypatch.setattr(cd, "_lane_sparse_file", lambda _d: sparse)
    finding = cd._scan_lane_sparse_drift(tmp_path, {"pattern-a", "pattern-b"})
    assert finding is not None
    assert finding.extra["missing_patterns"] == ["pattern-b"]


def test_scan_lane_healthy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sparse = tmp_path / "sparse"
    sparse.write_text("pattern-a\npattern-b\n", encoding="utf-8")
    monkeypatch.setattr(cd, "_lane_sparse_file", lambda _d: sparse)
    assert cd._scan_lane_sparse_drift(tmp_path, {"pattern-a"}) is None


def test_check_lane_drift_legacy_skips() -> None:
    assert cd._check_lane_sparse_checkout_drift(Path("/x"), {}) == []


# --- emission + entrypoint ---------------------------------------------------


def test_emit_findings_json() -> None:
    findings = [cd.DoctorFinding(severity="ok", message="fine")]
    cd._emit_coordination_findings(findings, json_output=True)


def test_emit_findings_human() -> None:
    findings = [
        cd.DoctorFinding(severity="error", message="bad", next_step="fix it"),
        cd.DoctorFinding(severity="warning", message="meh"),
    ]
    cd._emit_coordination_findings(findings, json_output=False)


def test_run_coordination_health_not_in_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cd, "locate_project_root", lambda: None)
    with pytest.raises(typer.Exit) as exc:
        cd.run_coordination_health(json_output=False)
    assert exc.value.exit_code == 1


def test_run_coordination_health_error_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cd, "locate_project_root", lambda: tmp_path)
    # `run_coordination_health` now calls `_collect_coordination_findings` with
    # the `check_staleness` keyword unconditionally (E-1 fix: the closure that
    # used to preserve a single-positional-arg call shape was removed) — the
    # stub must accept it.
    monkeypatch.setattr(
        cd,
        "_collect_coordination_findings",
        lambda _r, **_k: [cd.DoctorFinding(severity="error", message="boom")],
    )
    with pytest.raises(typer.Exit) as exc:
        cd.run_coordination_health(json_output=True)
    assert exc.value.exit_code == 1


def test_run_coordination_health_clean_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cd, "locate_project_root", lambda: tmp_path)
    # See test_run_coordination_health_error_exit above: the stub must accept
    # the `check_staleness` keyword now that the call is unconditional.
    monkeypatch.setattr(
        cd,
        "_collect_coordination_findings",
        lambda _r, **_k: [cd.DoctorFinding(severity="ok", message="fine")],
    )
    with pytest.raises(typer.Exit) as exc:
        cd.run_coordination_health(json_output=False)
    assert exc.value.exit_code == 0


def test_collect_findings_no_specs_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cd, "_check_git_version", lambda: [])
    monkeypatch.setattr(cd, "_check_tracked_worktrees_content", lambda _r: [])
    # No kitty-specs dir → only the (stubbed-empty) repo-level checks.
    assert cd._collect_coordination_findings(tmp_path) == []


# --- coord worktree head/dirty helpers ---------------------------------------


def test_coord_head_finding_mismatch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: "refs/heads/other\n")
    finding = cd._coord_worktree_head_finding(tmp_path, "kitty/x")
    assert finding is not None
    assert finding.error_code == "COORDINATION_WORKTREE_BRANCH_MISMATCH"


def test_coord_head_finding_match(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: "refs/heads/kitty/x\n")
    assert cd._coord_worktree_head_finding(tmp_path, "kitty/x") is None


def test_coord_head_finding_detached(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def _boom(*_a: Any, **_k: Any) -> str:
        raise subprocess.CalledProcessError(1, "git")

    monkeypatch.setattr(subprocess, "check_output", _boom)
    finding = cd._coord_worktree_head_finding(tmp_path, "kitty/x")
    assert finding is not None


def test_coord_dirty_finding(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: " M file.py\n")
    finding = cd._coord_worktree_dirty_finding(tmp_path)
    assert finding is not None
    assert finding.error_code == "COORDINATION_WORKTREE_DIRTY"


def test_coord_dirty_finding_clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: "")
    assert cd._coord_worktree_dirty_finding(tmp_path) is None


def test_coord_health_healthy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from specify_cli import coordination as coord_mod
    from specify_cli.lanes import branch_naming

    worktree = tmp_path / "coord"
    worktree.mkdir()
    monkeypatch.setattr(
        coord_mod.CoordinationWorkspace, "worktree_path", staticmethod(lambda *_a: worktree)
    )
    monkeypatch.setattr(branch_naming, "resolve_mid8", lambda *a, **k: "01ABCDEF")
    monkeypatch.setattr(cd, "_coord_worktree_head_finding", lambda *a: None)
    monkeypatch.setattr(cd, "_coord_worktree_dirty_finding", lambda *a: None)
    meta: dict[str, object] = {"coordination_branch": "kitty/x", "mission_slug": "m", "mission_id": "01ABCDEF"}
    out = cd._check_coordination_worktree_health(tmp_path, meta)
    assert out[0].severity == "ok"


# --- _lane_sparse_file -------------------------------------------------------


def test_lane_sparse_file_unresolvable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def _boom(*_a: Any, **_k: Any) -> str:
        raise subprocess.CalledProcessError(1, "git")

    monkeypatch.setattr(subprocess, "check_output", _boom)
    assert cd._lane_sparse_file(tmp_path) is None


def test_lane_sparse_file_relative(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: ".git/info/sparse-checkout\n")
    resolved = cd._lane_sparse_file(tmp_path)
    assert resolved == tmp_path / ".git/info/sparse-checkout"


# --- _check_lane_sparse_checkout_drift full loop -----------------------------


def test_check_lane_drift_no_worktrees_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from specify_cli import coordination as coord_mod
    from specify_cli.lanes import branch_naming

    monkeypatch.setattr(branch_naming, "resolve_mid8", lambda *a, **k: "01ABCDEF")
    monkeypatch.setattr(coord_mod, "lane_sparse_checkout_patterns", lambda *a: ["p"])
    meta: dict[str, object] = {"coordination_branch": "kitty/x", "mission_slug": "m", "mission_id": "01ABCDEF"}
    # No .worktrees dir under tmp_path → returns [].
    assert cd._check_lane_sparse_checkout_drift(tmp_path, meta) == []


def test_check_lane_drift_all_clean(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from specify_cli import coordination as coord_mod
    from specify_cli.lanes import branch_naming

    wt = tmp_path / ".worktrees" / "m-lane-a"
    wt.mkdir(parents=True)
    monkeypatch.setattr(branch_naming, "resolve_mid8", lambda *a, **k: "01ABCDEF")
    monkeypatch.setattr(coord_mod, "lane_sparse_checkout_patterns", lambda *a: ["p"])
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: str(wt.resolve()) + "\n")
    monkeypatch.setattr(cd, "_scan_lane_sparse_drift", lambda *a: None)
    meta: dict[str, object] = {"coordination_branch": "kitty/x", "mission_slug": "m", "mission_id": "01ABCDEF"}
    out = cd._check_lane_sparse_checkout_drift(tmp_path, meta)
    assert out[0].severity == "ok"


# --- _collect_coordination_findings mission loop -----------------------------


def test_collect_findings_iterates_missions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import json as _json

    specs = tmp_path / "kitty-specs"
    mission = specs / "083-a"
    mission.mkdir(parents=True)
    (mission / "meta.json").write_text(_json.dumps({"slug": "083-a"}), encoding="utf-8")
    monkeypatch.setattr(cd, "_check_git_version", lambda: [])
    monkeypatch.setattr(cd, "_check_tracked_worktrees_content", lambda _r: [])
    monkeypatch.setattr(
        cd, "_check_coordination_worktree_health",
        lambda _r, _m: [cd.DoctorFinding(severity="ok", message="coord")],
    )
    monkeypatch.setattr(cd, "_check_lane_sparse_checkout_drift", lambda _r, _m: [])
    out = cd._collect_coordination_findings(tmp_path)
    assert any(f.message == "coord" for f in out)


def test_collect_findings_unstattable_mission_candidate_is_not_silently_skipped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`#3194`: the `mission_dir.is_dir()` filter must not use the EACCES-divergent
    predicate.

    `Path.is_dir()` returns `False` for an unreadable candidate on Python 3.14
    only (RAISES on 3.11-3.13) — so on 3.14 an unstattable mission candidate
    would be silently treated as "not a directory" and dropped from the scan
    with no signal at all, the same silent-misclassification shape `#3177`
    fixed in `specify_cli.decisions.ownership`. `safe_is_dir` makes the
    behaviour the SAME on every interpreter: it raises, which is what this
    module already did (uncaught) on 3.11-3.13 before this fix — so this pins
    parity across interpreters rather than a new graceful-degradation contract.
    """
    monkeypatch.setattr(cd, "_check_git_version", lambda: [])
    monkeypatch.setattr(cd, "_check_tracked_worktrees_content", lambda _r: [])
    vault = tmp_path / "vault"
    (vault / "m-target").mkdir(parents=True)
    specs = tmp_path / "kitty-specs"
    specs.mkdir()
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
        with pytest.raises(OSError):
            cd._collect_coordination_findings(tmp_path)
    finally:
        os.chmod(vault, 0o700)


def test_apply_coord_staleness_fixes_unstattable_mission_candidate_is_not_silently_skipped(
    tmp_path: Path,
) -> None:
    """The `_apply_coord_staleness_fixes` twin of the test above (same `#3194` shape)."""
    vault = tmp_path / "vault"
    (vault / "m-target").mkdir(parents=True)
    specs = tmp_path / "kitty-specs"
    specs.mkdir()
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
        with pytest.raises(OSError):
            cd._apply_coord_staleness_fixes(tmp_path)
    finally:
        os.chmod(vault, 0o700)


# --- H2 / cycle invariants ---------------------------------------------------






# --- _fix_never_created_branches ---------------------------------------------


def test_fix_removes_coordination_branch_key(tmp_path: Path) -> None:
    """_fix_never_created_branches deletes coordination_branch from meta.json."""
    import json

    mission_dir = tmp_path / "kitty-specs" / "my-mission-01AB"
    mission_dir.mkdir(parents=True)
    meta: dict[str, object] = {"mission_slug": "my-mission-01AB", "coordination_branch": "kitty/mission-my-mission-01AB"}
    (mission_dir / "meta.json").write_text(json.dumps(meta))

    finding = cd.DoctorFinding(
        severity="warning",
        message="branch absent",
        error_code="COORDINATION_WORKTREE_NEVER_CREATED",
        extra={"meta_path": str(mission_dir / "meta.json")},
    )
    fixed = cd._fix_never_created_branches([finding])
    assert fixed == ["my-mission-01AB"]
    written = json.loads((mission_dir / "meta.json").read_text())
    assert "coordination_branch" not in written


def test_fix_skips_unrelated_error_codes(tmp_path: Path) -> None:
    """_fix_never_created_branches ignores findings with other error codes."""
    finding = cd.DoctorFinding(
        severity="warning",
        message="worktree missing",
        error_code="COORDINATION_WORKTREE_MISSING",
        extra={"meta_path": str(tmp_path / "meta.json")},
    )
    assert cd._fix_never_created_branches([finding]) == []


def test_fix_skips_finding_without_meta_path(tmp_path: Path) -> None:
    """_fix_never_created_branches is safe when meta_path is absent from extra."""
    finding = cd.DoctorFinding(
        severity="warning",
        message="branch absent",
        error_code="COORDINATION_WORKTREE_NEVER_CREATED",
    )
    assert cd._fix_never_created_branches([finding]) == []


def test_fix_is_idempotent_when_key_already_absent(tmp_path: Path) -> None:
    """_fix_never_created_branches does not list missions that had no key to remove."""
    import json

    mission_dir = tmp_path / "kitty-specs" / "already-flat-01AB"
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(json.dumps({"mission_slug": "already-flat-01AB"}))

    finding = cd.DoctorFinding(
        severity="warning",
        message="branch absent",
        error_code="COORDINATION_WORKTREE_NEVER_CREATED",
        extra={"meta_path": str(mission_dir / "meta.json")},
    )
    assert cd._fix_never_created_branches([finding]) == []


# --- _collect_coordination_findings injects meta_path -----------------------


def test_collect_injects_meta_path_for_never_created_findings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """_collect_coordination_findings stamps meta_path on COORDINATION_WORKTREE_NEVER_CREATED."""
    import json

    specs = tmp_path / "kitty-specs" / "demo-01AB"
    specs.mkdir(parents=True)
    (specs / "meta.json").write_text(
        json.dumps({"mission_slug": "demo-01AB", "coordination_branch": "kitty/mission-demo-01AB"})
    )

    monkeypatch.setattr(cd, "_check_git_version", lambda: [])
    monkeypatch.setattr(cd, "_check_tracked_worktrees_content", lambda _r: [])
    monkeypatch.setattr(
        cd,
        "_check_coordination_worktree_health",
        lambda _r, _m: [cd.DoctorFinding(
            severity="warning",
            message="never created",
            error_code="COORDINATION_WORKTREE_NEVER_CREATED",
        )],
    )
    monkeypatch.setattr(cd, "_check_lane_sparse_checkout_drift", lambda _r, _m: [])

    findings = cd._collect_coordination_findings(tmp_path)
    never_created = [f for f in findings if f.error_code == "COORDINATION_WORKTREE_NEVER_CREATED"]
    assert never_created, "expected NEVER_CREATED finding from monkeypatched check"
    assert "meta_path" in never_created[0].extra
    meta_path = never_created[0].extra["meta_path"]
    assert isinstance(meta_path, str)
    assert meta_path.endswith("meta.json")


# ---------------------------------------------------------------------------
# WP04 (#2786 / #2367-B, FR-007): stranded-coord-revert check + --fix.
#
# The load-bearing separator is the NEGATIVE AC (US2-S5): a marker present but a
# committed coord ref that re-derives COHERENT must yield NO finding. A
# marker-presence-only implementation passes the positive test and FAILS this.
# These tests build a real committed coord ref so re-verification is genuine.
# ---------------------------------------------------------------------------

_DOCTOR_MISSION_SLUG = "coord-doctor-fixture-01KXTM59"
_DOCTOR_MISSION_ID = "01MIDDOCTOR00000000000000A0"
_DOCTOR_EVENTS_REL = f"kitty-specs/{_DOCTOR_MISSION_SLUG}/status.events.jsonl"


def _git_doctor(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )


def _init_doctor_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-qb", "main", str(repo)], check=True, capture_output=True
    )
    _git_doctor(repo, "config", "user.email", "test@test.com")
    _git_doctor(repo, "config", "user.name", "Test")
    _git_doctor(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git_doctor(repo, "add", ".")
    _git_doctor(repo, "commit", "-m", "init")


def _doctor_event(
    wp_id: str, to_lane: str, *, event_id: str, from_lane: str
) -> dict[str, object]:
    return {
        "actor": "reviewer-renata",
        "at": "2026-07-18T10:00:00+00:00",
        "event_id": event_id,
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": _DOCTOR_MISSION_SLUG,
        "force": False,
        "from_lane": from_lane,
        "reason": None,
        "review_ref": None,
        "to_lane": to_lane,
        "wp_id": wp_id,
    }


def _seed_doctor_coord_ref(
    repo: Path, events: list[dict[str, object]], *, branch: str = "coord"
) -> None:
    """Init ``repo`` and commit ``events`` as the mission's coord event log on ``branch``.

    The mission meta deliberately omits ``coordination_branch`` (legacy shape) so
    the unrelated worktree-health check skips it — the exit code then reflects the
    stranded-revert check alone.
    """
    _init_doctor_repo(repo)
    feature_dir = repo / "kitty-specs" / _DOCTOR_MISSION_SLUG
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        _json.dumps(
            {
                "mission_slug": _DOCTOR_MISSION_SLUG,
                "mission_id": _DOCTOR_MISSION_ID,
                "mission_number": None,
                "mission_type": "software-dev",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (feature_dir / "status.events.jsonl").write_text(
        "".join(_json.dumps(e, sort_keys=True) + "\n" for e in events),
        encoding="utf-8",
    )
    _git_doctor(repo, "add", ".")
    _git_doctor(repo, "commit", "-m", "seed coord events")
    _git_doctor(repo, "branch", branch)


def _save_marker_state(
    repo: Path,
    *,
    stranded_wp_ids: list[str],
    coord_ref: str = "coord",
    captured_sha: str = "deadbeef",
    coord_worktree: str = "/sentinel/coord-wt",
) -> None:
    marker = {
        "coord_ref": coord_ref,
        "captured_sha": captured_sha,
        "coord_worktree": coord_worktree,
        "stranded_wp_ids": stranded_wp_ids,
        "revert_error": None,
        "detected_at": "2026-07-18T10:05:00+00:00",
    }
    save_state(
        MergeState(
            mission_id=_DOCTOR_MISSION_ID,
            mission_slug=_DOCTOR_MISSION_SLUG,
            target_branch="main",
            wp_order=stranded_wp_ids or ["WP-A"],
            current_wp=(stranded_wp_ids or ["WP-A"])[0],
            pending_coord_reconcile=marker,
        ),
        repo,
    )


# --- T014 (a) POSITIVE: live strand -> error finding + exit 1 ----------------


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_stranded_check_emits_error_for_live_strand(tmp_path: Path) -> None:
    """A marker whose committed ref STILL reduces WP-A to done -> one error finding."""
    repo = tmp_path / "repo"
    _seed_doctor_coord_ref(
        repo,
        [
            _doctor_event("WP-A", "approved", event_id="01A00", from_lane="in_review"),
            _doctor_event("WP-A", "done", event_id="01A01", from_lane="approved"),
            _doctor_event("WP-B", "approved", event_id="01B00", from_lane="in_review"),
        ],
    )
    # An EXISTING coord worktree so the live strand surfaces as a healable `error`
    # (a pruned worktree is the distinct STUCK-warning case, covered separately).
    _save_marker_state(repo, stranded_wp_ids=["WP-A"], coord_worktree=str(repo))

    findings = cd._check_stranded_coord_revert(repo)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "error"
    assert finding.error_code == cd._STRANDED_COORD_REVERT_CODE
    # Re-derived from the committed ref, not echoed from the marker.
    assert finding.extra["stranded_wp_ids"] == ["WP-A"]
    assert finding.extra["mission_slug"] == _DOCTOR_MISSION_SLUG


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_run_coordination_health_json_exits_1_on_live_strand(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`doctor coordination --json` exits 1 and surfaces the stable error_code."""
    repo = tmp_path / "repo"
    _seed_doctor_coord_ref(
        repo,
        [
            _doctor_event("WP-A", "approved", event_id="01A00", from_lane="in_review"),
            _doctor_event("WP-A", "done", event_id="01A01", from_lane="approved"),
        ],
    )
    # Existing coord worktree → the live strand is a healable `error` (exit 1).
    _save_marker_state(repo, stranded_wp_ids=["WP-A"], coord_worktree=str(repo))

    # Isolate the exit code to the stranded-revert check (git-version/tracked
    # checks are environment-dependent and never emit errors here).
    monkeypatch.setattr(cd, "locate_project_root", lambda: repo)
    monkeypatch.setattr(cd, "_check_git_version", lambda: [])
    monkeypatch.setattr(cd, "_check_tracked_worktrees_content", lambda _r: [])

    with pytest.raises(typer.Exit) as exc:
        cd.run_coordination_health(json_output=True)
    assert exc.value.exit_code == 1
    assert cd._STRANDED_COORD_REVERT_CODE in capsys.readouterr().out


# --- T014 (b) NEGATIVE (the separator): stale marker, coherent ref -> exit 0 --


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_stranded_check_no_finding_for_stale_marker_over_coherent_ref(
    tmp_path: Path,
) -> None:
    """Marker present, but the committed ref re-derives COHERENT -> NO finding.

    This is the AC that separates re-verification from marker-presence: WP-A is
    only ever ``approved`` on the ref, so a marker-presence-only implementation
    would (wrongly) emit a finding here.
    """
    repo = tmp_path / "repo"
    _seed_doctor_coord_ref(
        repo,
        [_doctor_event("WP-A", "approved", event_id="01A00", from_lane="in_review")],
    )
    _save_marker_state(repo, stranded_wp_ids=["WP-A"])

    # Sanity: the marker IS present and non-empty.
    st = load_state(repo, _DOCTOR_MISSION_ID)
    assert st is not None and st.pending_coord_reconcile is not None

    assert cd._check_stranded_coord_revert(repo) == []


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_run_coordination_health_exits_0_for_stale_marker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The entrypoint exits 0 when every marker's ref re-derives coherent."""
    repo = tmp_path / "repo"
    _seed_doctor_coord_ref(
        repo,
        [_doctor_event("WP-A", "approved", event_id="01A00", from_lane="in_review")],
    )
    _save_marker_state(repo, stranded_wp_ids=["WP-A"])

    monkeypatch.setattr(cd, "locate_project_root", lambda: repo)
    monkeypatch.setattr(cd, "_check_git_version", lambda: [])
    monkeypatch.setattr(cd, "_check_tracked_worktrees_content", lambda _r: [])

    with pytest.raises(typer.Exit) as exc:
        cd.run_coordination_health(json_output=True)
    assert exc.value.exit_code == 0


def test_parse_reconcile_marker_rejects_empty_strand() -> None:
    """An empty strand is not a strand (data-model): the marker is unusable."""
    base: dict[str, object] = {
        "coord_ref": "coord",
        "captured_sha": "deadbeef",
        "coord_worktree": "/sentinel/wt",
        "stranded_wp_ids": [],
    }
    assert cd._parse_reconcile_marker(base) is None
    assert cd._parse_reconcile_marker(None) is None
    assert cd._parse_reconcile_marker({**base, "coord_ref": ""}) is None
    assert cd._parse_reconcile_marker({**base, "stranded_wp_ids": ["WP-A"]}) == (
        "coord",
        "deadbeef",
        "/sentinel/wt",
        ["WP-A"],
    )


# --- T014 (c) --fix heals coherence + idempotency (byte-stable, marker once) --


def _bake_stranding_done(repo: Path, tmp_path: Path) -> tuple[str, Path]:
    """Materialize a coord worktree and bake a stranding WP-A ``done`` commit.

    Returns ``(captured_sha, coord_worktree)`` where ``captured_sha`` is the coord
    tip BEFORE the bake (the ``git revert`` base).
    """
    captured_sha = _git_doctor(repo, "rev-parse", "coord").stdout.strip()
    worktree = tmp_path / "coord-wt"
    _git_doctor(repo, "worktree", "add", str(worktree), "coord")
    wt_events = worktree / "kitty-specs" / _DOCTOR_MISSION_SLUG / "status.events.jsonl"
    with wt_events.open("a", encoding="utf-8") as fh:
        fh.write(
            _json.dumps(
                _doctor_event("WP-A", "done", event_id="01A01", from_lane="approved"),
                sort_keys=True,
            )
            + "\n"
        )
    _git_doctor(worktree, "add", ".")
    _git_doctor(worktree, "commit", "-m", "bake WP-A done (strands on rollback)")
    return captured_sha, worktree


def _bake_stranding_done_dirty(repo: Path, tmp_path: Path) -> tuple[str, Path]:
    """Bake a stranding ``done`` commit, then leave the coord worktree DIRTY.

    Reuses :func:`_bake_stranding_done` (HEAD advances to the committed ``done``)
    and then rolls the WORKING ``status.events.jsonl`` back to ``approved`` WITHOUT
    committing — reproducing the realistic post-rollback state where the byte
    restore leaves the coord worktree DIRTY (working ``approved`` vs HEAD ``done``).
    ``git revert`` refuses over that divergence (exit 128), so a heal that does not
    clean-to-HEAD first cannot repair it.
    """
    captured_sha, worktree = _bake_stranding_done(repo, tmp_path)
    wt_events = worktree / "kitty-specs" / _DOCTOR_MISSION_SLUG / "status.events.jsonl"
    # Roll the working tree back to the pre-``done`` (``approved``) content, mirroring
    # the rollback byte-restore, without committing → the worktree is now dirty.
    wt_events.write_text(
        _json.dumps(
            _doctor_event("WP-A", "approved", event_id="01A00", from_lane="in_review"),
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return captured_sha, worktree


def _porcelain(worktree: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(worktree), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _committed_coord_events(repo: Path) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), "show", f"coord:{_DOCTOR_EVENTS_REL}"],
        check=True,
        capture_output=True,
    ).stdout


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_run_coordination_health_fix_heals_dirty_coord_worktree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`--fix` heals a strand whose coord worktree is DIRTY (the HIGH, #2786/#2367-B).

    The realistic post-rollback state: the coord worktree's WORKING
    ``status.events.jsonl`` is byte-restored to ``approved`` while HEAD is still the
    committed ``done``. ``git revert`` refuses over that dirty tree, so the pre-fix
    ``repair_coord_strand`` (no clean-to-HEAD) leaves the marker + strand and
    ``doctor coordination --fix`` returns exit 1. The self-sufficient primitive
    scoped-cleans the mission status paths to HEAD first, so ``--fix`` HEALS it:
    committed ref coherent, worktree clean, marker cleared.
    """
    repo = tmp_path / "repo"
    _seed_doctor_coord_ref(
        repo,
        [_doctor_event("WP-A", "approved", event_id="01A00", from_lane="in_review")],
    )
    captured_sha, worktree = _bake_stranding_done_dirty(repo, tmp_path)
    _save_marker_state(
        repo,
        stranded_wp_ids=["WP-A"],
        captured_sha=captured_sha,
        coord_worktree=str(worktree),
    )
    feature_dir = repo / "kitty-specs" / _DOCTOR_MISSION_SLUG

    # Preconditions: the coord worktree is genuinely DIRTY and WP-A is stranded done.
    assert _porcelain(worktree), "fixture precondition: coord worktree must be dirty"
    assert coord_incoherent_done_wps(
        "coord", ["WP-A"], repo_root=repo, feature_dir=feature_dir
    ) == ["WP-A"]

    monkeypatch.setattr(cd, "locate_project_root", lambda: repo)
    monkeypatch.setattr(cd, "_check_git_version", lambda: [])
    monkeypatch.setattr(cd, "_check_tracked_worktrees_content", lambda _r: [])

    with pytest.raises(typer.Exit) as exc:
        cd.run_coordination_health(json_output=True, fix=True)

    # Healed: exit 0, committed ref coherent, worktree clean, marker cleared.
    assert exc.value.exit_code == 0
    assert coord_incoherent_done_wps(
        "coord", ["WP-A"], repo_root=repo, feature_dir=feature_dir
    ) == []
    assert _porcelain(worktree) == "", "the heal must leave the coord worktree clean"
    healed_state = load_state(repo, _DOCTOR_MISSION_ID)
    assert healed_state is not None
    assert healed_state.pending_coord_reconcile is None


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_run_coordination_health_fix_heals_then_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`--fix` reverts the strand, clears the marker, and re-running is byte-stable."""
    repo = tmp_path / "repo"
    _seed_doctor_coord_ref(
        repo,
        [_doctor_event("WP-A", "approved", event_id="01A00", from_lane="in_review")],
    )
    captured_sha, worktree = _bake_stranding_done(repo, tmp_path)
    _save_marker_state(
        repo,
        stranded_wp_ids=["WP-A"],
        captured_sha=captured_sha,
        coord_worktree=str(worktree),
    )
    feature_dir = repo / "kitty-specs" / _DOCTOR_MISSION_SLUG

    # Pre-condition: WP-A is genuinely stranded done on the committed ref.
    assert coord_incoherent_done_wps(
        "coord", ["WP-A"], repo_root=repo, feature_dir=feature_dir
    ) == ["WP-A"]

    monkeypatch.setattr(cd, "locate_project_root", lambda: repo)
    monkeypatch.setattr(cd, "_check_git_version", lambda: [])
    monkeypatch.setattr(cd, "_check_tracked_worktrees_content", lambda _r: [])

    # First --fix: reverts the strand -> coherent -> exit 0.
    with pytest.raises(typer.Exit) as exc:
        cd.run_coordination_health(json_output=True, fix=True)
    assert exc.value.exit_code == 0
    assert coord_incoherent_done_wps(
        "coord", ["WP-A"], repo_root=repo, feature_dir=feature_dir
    ) == []
    # Marker cleared exactly once.
    healed_state = load_state(repo, _DOCTOR_MISSION_ID)
    assert healed_state is not None
    assert healed_state.pending_coord_reconcile is None
    bytes_after_first = _committed_coord_events(repo)

    # Second --fix: marker gone -> no finding, no revert, byte-stable coord log.
    with pytest.raises(typer.Exit) as exc2:
        cd.run_coordination_health(json_output=True, fix=True)
    assert exc2.value.exit_code == 0
    assert _committed_coord_events(repo) == bytes_after_first
    second_state = load_state(repo, _DOCTOR_MISSION_ID)
    assert second_state is not None
    assert second_state.pending_coord_reconcile is None


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_fix_stranded_reverts_direct_returns_healed_slug(tmp_path: Path) -> None:
    """`_fix_stranded_reverts` heals and returns the mission slug; a 2nd call is a no-op."""
    repo = tmp_path / "repo"
    _seed_doctor_coord_ref(
        repo,
        [_doctor_event("WP-A", "approved", event_id="01A00", from_lane="in_review")],
    )
    captured_sha, worktree = _bake_stranding_done(repo, tmp_path)
    _save_marker_state(
        repo,
        stranded_wp_ids=["WP-A"],
        captured_sha=captured_sha,
        coord_worktree=str(worktree),
    )

    findings = cd._check_stranded_coord_revert(repo)
    assert [f.error_code for f in findings] == [cd._STRANDED_COORD_REVERT_CODE]

    healed, warnings = cd._fix_stranded_reverts(findings, repo)
    assert healed == [_DOCTOR_MISSION_SLUG]
    assert warnings == []
    # Marker cleared -> re-checking finds nothing -> a second fix heals nothing.
    assert cd._check_stranded_coord_revert(repo) == []
    healed_again, warnings_again = cd._fix_stranded_reverts(findings, repo)
    assert healed_again == []
    assert warnings_again == []


# ---------------------------------------------------------------------------
# Bare-handle feature_dir canonicalization in the coord strand check (paula LOW).
#
# paula-patterns pre-merge finding: `_check_stranded_coord_revert` /
# `_fix_stranded_reverts` resolve the mission ``feature_dir`` via the
# canonicalizing ``resolve_planning_read_dir(..., kind=WORK_PACKAGE_TASK)`` — the
# SAME read seam the executor's mark/heal use — instead of the raw
# ``primary_feature_dir_for_mission``. When a saved marker's ``state.mission_slug``
# is a BARE handle (``foo``) while the on-disk mission dir is the canonical
# ``foo-<mid8>``, the raw resolver composes ``kitty-specs/foo/...`` (non-existent)
# → no events → ``coord_incoherent_done_wps`` returns ``[]`` → the doctor silently
# declares the marker stale: a split-brain safety-net FALSE-NEGATIVE. The
# canonicalizing resolver folds ``foo`` → ``foo-<mid8>`` (via
# ``_canonicalize_bare_modern_handle`` / ``resolve_bare_modern_mission_dir_name``)
# and reads the right dir. This is the resolver-unification: check, fix, and the
# executor's mark/heal all resolve the IDENTICAL feature_dir.
# ---------------------------------------------------------------------------

_BARE_HANDLE = "bare-handle-fixture"
_BARE_MID8 = "01KXTM60"
_BARE_COMPOSED = f"{_BARE_HANDLE}-{_BARE_MID8}"
_BARE_MISSION_ID = "01MIDBAREHANDLE0000000000A0"


def _seed_bare_handle_fixture(repo: Path) -> None:
    """Seed a mission whose on-disk dir is canonical ``<slug>-<mid8>`` but whose
    saved reconcile marker carries the BARE handle.

    The committed ``coord`` ref holds a live WP-A ``done`` strand under the CANONICAL
    dir name (``kitty-specs/<slug>-<mid8>/status.events.jsonl``), so only a resolver
    that folds the bare handle → the canonical dir name reads the events and derives
    the strand. The marker's ``mission_slug`` is deliberately the bare handle (no
    ``-<mid8>`` suffix). The seeded events reuse :func:`_doctor_event`; their
    ``feature_slug`` field is cosmetic — the coherence reduction keys on
    ``wp_id`` + lane only.
    """
    _init_doctor_repo(repo)
    feature_dir = repo / "kitty-specs" / _BARE_COMPOSED
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        _json.dumps(
            {
                "mission_slug": _BARE_COMPOSED,
                "mission_id": _BARE_MISSION_ID,
                "mission_number": None,
                "mission_type": "software-dev",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    events = [
        _doctor_event("WP-A", "approved", event_id="01A00", from_lane="in_review"),
        _doctor_event("WP-A", "done", event_id="01A01", from_lane="approved"),
    ]
    (feature_dir / "status.events.jsonl").write_text(
        "".join(_json.dumps(e, sort_keys=True) + "\n" for e in events),
        encoding="utf-8",
    )
    _git_doctor(repo, "add", ".")
    _git_doctor(repo, "commit", "-m", "seed coord events (canonical dir)")
    _git_doctor(repo, "branch", "coord")

    marker = {
        "coord_ref": "coord",
        "captured_sha": "deadbeef",
        # An existing worktree path so the live strand stays a healable `error`
        # (the pruned-worktree STUCK-warning case is covered by its own test).
        "coord_worktree": str(repo),
        "stranded_wp_ids": ["WP-A"],
        "revert_error": None,
        "detected_at": "2026-07-18T10:05:00+00:00",
    }
    save_state(
        MergeState(
            mission_id=_BARE_MISSION_ID,
            mission_slug=_BARE_HANDLE,  # BARE handle — no -<mid8> suffix.
            target_branch="main",
            wp_order=["WP-A"],
            current_wp="WP-A",
            pending_coord_reconcile=marker,
        ),
        repo,
    )


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_stranded_check_folds_bare_handle_to_canonical_feature_dir(
    tmp_path: Path,
) -> None:
    """A marker with a BARE ``mission_slug`` STILL yields the strand finding.

    The on-disk mission dir is the canonical ``<slug>-<mid8>``; the canonicalizing
    ``resolve_planning_read_dir(..., kind=WORK_PACKAGE_TASK)`` folds ``bare`` →
    ``<slug>-<mid8>`` so the committed coord ref is read from the right dir and the
    live WP-A ``done`` strand is derived (paula-patterns pre-merge finding —
    resolver-unification with the executor mark/heal). The non-vacuity companion
    (:func:`test_stranded_check_bare_handle_false_negative_under_raw_resolver`)
    proves this REDs under the pre-fix raw resolver.
    """
    repo = tmp_path / "repo"
    _seed_bare_handle_fixture(repo)

    findings = cd._check_stranded_coord_revert(repo)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "error"
    assert finding.error_code == cd._STRANDED_COORD_REVERT_CODE
    # Re-derived from the committed ref read at the CANONICAL dir, not echoed.
    assert finding.extra["stranded_wp_ids"] == ["WP-A"]
    assert finding.extra["mission_slug"] == _BARE_HANDLE


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_stranded_check_bare_handle_false_negative_under_raw_resolver(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Non-vacuity guard: the SAME fixture yields ZERO findings under the raw resolver.

    Simulates the pre-fix code path by swapping the canonicalizing
    ``resolve_planning_read_dir`` for the raw, module-private
    ``_compose_primary_feature_dir`` leaf, which composes ``kitty-specs/<bare>``
    — a directory that does not exist. The committed ref is then unreadable →
    no events → ``coord_incoherent_done_wps`` returns ``[]`` → the split-brain
    safety net silently declares the marker stale. This proves the positive
    test above genuinely distinguishes the canonicalizing resolver from the
    broken raw one (it would RED before the resolver-unification fix).
    ``_check_stranded_coord_revert`` imports the resolver function-locally, so
    patching the module attribute swaps in the pre-fix behaviour.

    read-side-seam-primary-primitive-closure-01KYKMMT WP08 (T039,
    reconciliation item #4): this ``_raw`` helper used to route through the
    public wrapper ``primary_feature_dir_for_mission``, which WP03's Half-B
    delegation (T019) made re-enter ``read_dir`` — so patching
    ``resolve_planning_read_dir`` to route through ``_raw`` closed a
    ``_raw → wrapper → read_dir → resolve_planning_read_dir`` cycle
    (``RecursionError``, GREEN at the true mission base `765cdcc59`, RED from
    WP03 onward — a genuine mission regression in this TEST fixture, never in
    production: WP03's reviewer proved ``read_dir`` production-acyclic across
    all 16 kinds). The wrapper is now deleted (T035) and this helper's actual
    intent -- a genuinely raw, non-canonicalizing composition -- is exactly
    what the module-private leaf ``_compose_primary_feature_dir`` is: it
    imports no seam and cannot re-enter ``read_dir``, restoring the test's
    real, non-recursive intent (STALE test per DIRECTIVE_041; production was
    always acyclic).
    """
    from specify_cli.missions import _read_path_resolver as rpr

    repo = tmp_path / "repo"
    _seed_bare_handle_fixture(repo)

    def _raw(repo_root: Path, mission_slug: str, **_kwargs: object) -> Path:
        # Bind explicitly: the resolver crosses the ``follow_imports=skip``
        # boundary, so mypy widens the ``-> Path`` primitive to ``Any``.
        resolved: Path = rpr._compose_primary_feature_dir(repo_root, mission_slug)
        return resolved

    monkeypatch.setattr(rpr, "resolve_planning_read_dir", _raw)

    assert cd._check_stranded_coord_revert(repo) == []


# ---------------------------------------------------------------------------
# FR-007 pruned/unresolvable coord worktree → distinct STUCK diagnostic
# (not a silent skip, not a looping `error` whose hint points back at `--fix`).
# ---------------------------------------------------------------------------


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_stranded_check_pruned_worktree_emits_stuck_error(tmp_path: Path) -> None:
    """A live strand whose coord worktree is PRUNED → a distinct STUCK ``error``.

    It is STILL a committed-ref split-brain, so it stays an ``error`` (the doctor
    must not report the mission healthy — debugger-debbie HIGH). Only the
    ``next_step`` differs: a manual-recovery hint instead of the healable hint that
    would loop the user back to a ``--fix`` that can never succeed.
    """
    repo = tmp_path / "repo"
    _seed_doctor_coord_ref(
        repo,
        [
            _doctor_event("WP-A", "approved", event_id="01A00", from_lane="in_review"),
            _doctor_event("WP-A", "done", event_id="01A01", from_lane="approved"),
        ],
    )
    pruned = tmp_path / "does-not-exist-coord-wt"
    assert not pruned.exists()
    _save_marker_state(repo, stranded_wp_ids=["WP-A"], coord_worktree=str(pruned))

    findings = cd._check_stranded_coord_revert(repo)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "error"  # still a committed split-brain → exit 1
    assert finding.error_code == cd._STRANDED_COORD_REVERT_STUCK_CODE
    # The recovery hint must NOT loop the user back at plain `--fix`.
    assert finding.next_step == cd._STRANDED_COORD_REVERT_STUCK_HINT
    assert "no longer exists" in finding.message


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_run_coordination_health_pruned_worktree_exits_1_with_stuck_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A pruned-worktree STUCK strand is a committed split-brain → ``error``, exit 1."""
    repo = tmp_path / "repo"
    _seed_doctor_coord_ref(
        repo,
        [
            _doctor_event("WP-A", "approved", event_id="01A00", from_lane="in_review"),
            _doctor_event("WP-A", "done", event_id="01A01", from_lane="approved"),
        ],
    )
    _save_marker_state(
        repo,
        stranded_wp_ids=["WP-A"],
        coord_worktree=str(tmp_path / "pruned-coord-wt"),
    )
    monkeypatch.setattr(cd, "locate_project_root", lambda: repo)
    monkeypatch.setattr(cd, "_check_git_version", lambda: [])
    monkeypatch.setattr(cd, "_check_tracked_worktrees_content", lambda _r: [])

    with pytest.raises(typer.Exit) as exc:
        cd.run_coordination_health(json_output=True)
    # A stuck strand is an unresolved committed split-brain — the gate MUST fail
    # (exit 1); a warning/exit-0 would report the mission healthy and hide it.
    assert exc.value.exit_code == 1
    assert cd._STRANDED_COORD_REVERT_STUCK_CODE in capsys.readouterr().out


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_fix_stranded_reverts_pruned_worktree_yields_stuck_error_not_silent(
    tmp_path: Path,
) -> None:
    """`_fix_stranded_reverts` on a strand finding whose worktree is pruned → STUCK error.

    Directly exercises the fix-path defensive branch (a worktree pruned between the
    check and the fix): the shared primitive returns ``worktree_missing`` and the
    fixer surfaces a STUCK ``error`` (exit 1 — still a committed split-brain) rather
    than silently dropping the marker or reporting healthy.
    """
    repo = tmp_path / "repo"
    (repo / ".kittify").mkdir(parents=True)
    finding = cd.DoctorFinding(
        severity="error",
        message="live strand",
        next_step=cd._STRANDED_COORD_REVERT_HINT,
        error_code=cd._STRANDED_COORD_REVERT_CODE,
        extra={
            "mission_id": _DOCTOR_MISSION_ID,
            "mission_slug": _DOCTOR_MISSION_SLUG,
            "coord_ref": "coord",
            "captured_sha": "deadbeef",
            "coord_worktree": str(tmp_path / "pruned"),
            "candidate_wps": ["WP-A"],
            "stranded_wp_ids": ["WP-A"],
        },
    )

    healed, extra = cd._fix_stranded_reverts([finding], repo)

    assert healed == []
    assert [w.error_code for w in extra] == [cd._STRANDED_COORD_REVERT_STUCK_CODE]
    assert [w.severity for w in extra] == ["error"]  # exit-1, not a hidden warning


# ---------------------------------------------------------------------------
# #4950 fold: `CoordRepairOutcome.branch_mismatch` must not fall through to a
# silent `(None, None)` -- the operator needs a reason, and the stranded-
# revert hint (`_STRANDED_COORD_REVERT_HINT`, "run `--fix`") can never
# succeed while the coord worktree stays on a foreign branch.
# ---------------------------------------------------------------------------


@pytest.mark.git_repo
@pytest.mark.non_sandbox
def test_fix_stranded_reverts_branch_mismatch_yields_error_not_silent(
    tmp_path: Path,
) -> None:
    """`_fix_stranded_reverts` on a strand whose coord worktree is on a FOREIGN
    branch -> a distinct branch-mismatch ``error``, and the marker stays pending.

    Sibling of #4920/#4950's mismatched-worktree-branch bug for the
    fast-forward path (`_coord_worktree_mismatch_fix_blocked_finding`): here the
    equivalent refusal is on the ``git revert`` repair path
    (`CoordRepairOutcome.branch_mismatch`, ``coordination/coherence.py``).
    Before this fold, ``_heal_one_strand`` let that outcome fall through to
    ``(None, None)`` -- no warning, and the ``--fix`` re-run the persistent
    ``error`` finding still points at can never succeed while the worktree
    stays off the coord branch.
    """
    repo = tmp_path / "repo"
    _seed_doctor_coord_ref(
        repo,
        [_doctor_event("WP-A", "approved", event_id="01A00", from_lane="in_review")],
    )
    captured_sha, worktree = _bake_stranding_done(repo, tmp_path)
    # Operator (or another process) switches the coord worktree onto a sibling
    # branch created from its current tip -- byte-identical, but not "the"
    # coord branch. Git permits this freely.
    _git_doctor(worktree, "switch", "-c", "scratch")
    scratch_tip_before = _git_doctor(worktree, "rev-parse", "scratch").stdout.strip()
    coord_tip_before = _git_doctor(repo, "rev-parse", "coord").stdout.strip()

    _save_marker_state(
        repo,
        stranded_wp_ids=["WP-A"],
        captured_sha=captured_sha,
        coord_worktree=str(worktree),
    )

    findings = cd._check_stranded_coord_revert(repo)
    assert [f.error_code for f in findings] == [cd._STRANDED_COORD_REVERT_CODE]

    healed, extra = cd._fix_stranded_reverts(findings, repo)

    assert healed == []
    assert [w.error_code for w in extra] == [cd._STRANDED_COORD_REVERT_BRANCH_MISMATCH_CODE]
    assert [w.severity for w in extra] == ["error"]  # still a committed split-brain
    assert "scratch" in extra[0].message
    assert "'coord'" in extra[0].message
    # Nothing mutated -- neither the foreign branch nor the declared coord ref.
    assert _git_doctor(worktree, "rev-parse", "scratch").stdout.strip() == scratch_tip_before
    assert _git_doctor(repo, "rev-parse", "coord").stdout.strip() == coord_tip_before
    # The marker must NOT be cleared -- the strand persists for the next pass.
    state = load_state(repo, _DOCTOR_MISSION_ID)
    assert state is not None and state.pending_coord_reconcile is not None


# ---------------------------------------------------------------------------
# Safety-net warning: an un-parseable marker must not be silently dropped.
# ---------------------------------------------------------------------------


def _save_raw_marker(repo: Path, marker: dict[str, object]) -> None:
    """Persist a merge state carrying an arbitrary (possibly malformed) marker."""
    (repo / ".kittify").mkdir(parents=True, exist_ok=True)
    save_state(
        MergeState(
            mission_id=_DOCTOR_MISSION_ID,
            mission_slug=_DOCTOR_MISSION_SLUG,
            target_branch="main",
            wp_order=["WP-A"],
            current_wp="WP-A",
            pending_coord_reconcile=marker,
        ),
        repo,
    )


def test_stranded_check_unparseable_marker_emits_warning(tmp_path: Path) -> None:
    """An enumerated-but-unparseable marker yields a ``warning``, not a silent skip.

    The marker is present (so the enumeration yields it) but malformed (empty
    ``captured_sha``), so ``_parse_reconcile_marker`` returns ``None``. A safety-net
    checker must surface a ``warning`` (reviewer-renata LOW) rather than ``continue``.
    """
    repo = tmp_path / "repo"
    _save_raw_marker(
        repo,
        {
            "coord_ref": "coord",
            "captured_sha": "",  # malformed → unparseable.
            "coord_worktree": "/sentinel/wt",
            "stranded_wp_ids": ["WP-A"],
            "revert_error": None,
            "detected_at": "2026-07-18T10:05:00+00:00",
        },
    )

    findings = cd._check_stranded_coord_revert(repo)

    assert len(findings) == 1
    assert findings[0].severity == "warning"
    assert findings[0].error_code == cd._MARKER_UNPARSEABLE_CODE


# --- FR-012: `doctor coordination --mission <handle>` per-mission scoping ------


def _seed_mission_meta(specs: Path, slug: str, mission_id: str) -> None:
    mission = specs / slug
    mission.mkdir(parents=True)
    (mission / "meta.json").write_text(
        _json.dumps({"slug": slug, "mission_slug": slug, "mission_id": mission_id}),
        encoding="utf-8",
    )


def test_collect_findings_mission_filter_scopes_to_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`_collect_coordination_findings(mission_filter=...)` scopes the kitty-specs
    iteration to the single mission the shared resolver maps the handle to (#2696,
    FR-012). Assert on the specific per-mission finding, not exit codes."""
    specs = tmp_path / "kitty-specs"
    _seed_mission_meta(specs, "083-alpha", "01AAAAAAAAAAAAAAAAAAAAAAAA")
    _seed_mission_meta(specs, "084-beta", "01BBBBBBBBBBBBBBBBBBBBBBBB")

    monkeypatch.setattr(cd, "_check_git_version", lambda: [])
    monkeypatch.setattr(cd, "_check_tracked_worktrees_content", lambda _r: [])
    monkeypatch.setattr(cd, "_check_stranded_coord_revert", lambda _r: [])
    monkeypatch.setattr(cd, "_check_lane_sparse_checkout_drift", lambda _r, _m: [])
    monkeypatch.setattr(
        cd,
        "_check_coordination_worktree_health",
        lambda _r, m: [
            cd.DoctorFinding(severity="warning", message=f"coord:{m['mission_slug']}")
        ],
    )

    scoped = cd._collect_coordination_findings(tmp_path, mission_filter="084-beta")
    messages = [f.message for f in scoped]
    assert "coord:084-beta" in messages
    assert "coord:083-alpha" not in messages

    unscoped = cd._collect_coordination_findings(tmp_path)
    unscoped_messages = [f.message for f in unscoped]
    assert "coord:084-beta" in unscoped_messages
    assert "coord:083-alpha" in unscoped_messages


def test_run_coordination_health_mission_not_found_exits_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An unresolvable `--mission` handle fails closed with exit 1 (mission-state parity)."""
    (tmp_path / "kitty-specs").mkdir()
    monkeypatch.setattr(cd, "locate_project_root", lambda: tmp_path)
    with pytest.raises(typer.Exit) as exc:
        cd.run_coordination_health(json_output=False, mission="does-not-exist")
    assert exc.value.exit_code == 1


def test_run_coordination_health_mission_not_found_json_envelope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--json` unresolvable-handle emits a JSON error envelope (mission-state parity)."""
    (tmp_path / "kitty-specs").mkdir()
    monkeypatch.setattr(cd, "locate_project_root", lambda: tmp_path)
    with pytest.raises(typer.Exit) as exc:
        cd.run_coordination_health(json_output=True, mission="nope")
    assert exc.value.exit_code == 1
    payload = _json.loads(capsys.readouterr().out.strip())
    assert payload["ok"] is False
    assert payload["error"]["code"] == "MISSION_NOT_FOUND"
    assert payload["error"]["message"] == "Mission not found: 'nope'"
    assert payload["handle"] == "nope"


def test_run_coordination_health_ambiguous_handle_exits_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An ambiguous `--mission` handle fails closed with exit 1 (mission-state parity)."""
    specs = tmp_path / "kitty-specs"
    # Two missions sharing the same human slug (differ only by numeric prefix)
    # → the human-slug ladder rung matches both → AmbiguousHandleError.
    _seed_mission_meta(specs, "083-dup", "01AAAAAAAAAAAAAAAAAAAAAAAA")
    _seed_mission_meta(specs, "084-dup", "01BBBBBBBBBBBBBBBBBBBBBBBB")
    monkeypatch.setattr(cd, "locate_project_root", lambda: tmp_path)
    with pytest.raises(typer.Exit) as exc:
        cd.run_coordination_health(json_output=False, mission="dup")
    assert exc.value.exit_code == 1
