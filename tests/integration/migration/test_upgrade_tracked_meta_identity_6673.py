"""#6673 regression guard: ``spec-kitty upgrade`` never re-identifies a Mission git already holds.

The red-first reproduction for #6673, found by the post-specify adversarial review of the
#6669/#6668 Mission. A Mission's ``kitty-specs/<slug>/meta.json`` is tracked by git but absent
from the working tree -- an accidental ``rm``, a sparse/partial checkout. On ``main`` the
``2.0.6`` sweep wrote a baseline ``meta.json`` rebuilt from the directory name, the
``3.2.0a4`` normalization minted a fresh ULID into it, and the ``3.2.6rc1`` runtime-state
cutover wrote a one-key ``{"status_phase": "1"}`` stub when the file was still missing. Any
later ``git add -A`` committed a second identity for a Mission whose history used the first.

One ``upgrade --yes`` run over a scratch git repository holds every shape at once:

* ``sparse-...``: a committed, valid ``meta.json`` deleted from the working tree -- the file
  must come back with the **tracked** ``mission_id`` (FR-001/FR-002);
* ``legacy-...``: a pre-identity Mission (tracked ``spec.md``, no ``meta.json`` in git) -- the
  control that must still be repaired and given an identity (FR-004);
* ``corrupt-...``: a committed ``meta.json`` that is not JSON, deleted from the working tree --
  nothing may be written for it by any migration, and the output must name the restore
  command (FR-003/FR-008).

``upgrade --yes`` auto-commits what it writes, so the surviving ``mission_id`` is compared
against the **pre-run** commit, never against post-run ``HEAD`` (that would compare a minted
id with itself and pass vacuously).
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as root_app

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SPARSE = "sparse-mission-01REALMIS"
_SPARSE_ID = "01REALMISZZZZZZZZZZZZZZZZZ"
_LEGACY = "legacy-mission-01LEGACYM"
_CORRUPT = "corrupt-mission-01CORRUP"
_CORRUPT_META = b"{not json\n"
_WP_WITH_LANE = "---\nwork_package_id: WP01\ntitle: leftover\nlane: doing\n---\n# WP01\n"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def _meta(slug: str, mission_id: str) -> dict[str, object]:
    return {
        "mission_id": mission_id,
        "mission_slug": slug,
        "slug": slug,
        "friendly_name": slug.rsplit("-", 1)[0].replace("-", " "),
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00+00:00",
    }


def _commit_mission(root: Path, slug: str, meta: dict[str, object] | bytes) -> Path:
    mission_dir = root / "kitty-specs" / slug
    mission_dir.mkdir(parents=True)
    payload = meta if isinstance(meta, bytes) else (json.dumps(meta, sort_keys=True, indent=2) + "\n").encode("utf-8")
    (mission_dir / "meta.json").write_bytes(payload)
    (mission_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    return mission_dir


def _build_project(root: Path) -> dict[str, Path]:
    """Three committed Missions, one per shape; returns them by slug (meta.json deleted after the commit)."""
    root.mkdir(parents=True)
    (root / ".kittify").mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    folders = {
        _SPARSE: _commit_mission(root, _SPARSE, _meta(_SPARSE, _SPARSE_ID)),
        _LEGACY: root / "kitty-specs" / _LEGACY,
        _CORRUPT: _commit_mission(root, _CORRUPT, _CORRUPT_META),
    }
    # The pre-identity control: a tracked spec.md and a legacy lane file, no meta.json anywhere in git.
    (folders[_LEGACY] / "tasks" / "doing").mkdir(parents=True)
    (folders[_LEGACY] / "spec.md").write_text("# legacy\n", encoding="utf-8")
    (folders[_LEGACY] / "tasks" / "doing" / "WP01-x.md").write_text(_WP_WITH_LANE, encoding="utf-8")
    # State a later step would rewrite, so the refusal has something to leave alone in the corrupt folder.
    (folders[_CORRUPT] / "status.json").write_text('{"work_packages": {}}\n', encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    (folders[_SPARSE] / "meta.json").unlink()
    (folders[_CORRUPT] / "meta.json").unlink()
    return folders


def _snapshot(path: Path) -> dict[str, bytes]:
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in sorted(path.rglob("*")) if p.is_file()}


def _upgrade(project: Path) -> tuple[int, str]:
    with contextlib.chdir(project):
        result = CliRunner().invoke(root_app, ["upgrade", "--yes"], catch_exceptions=False)
    return result.exit_code, result.output


def _tracked_meta(root: Path, ref: str, slug: str) -> dict[str, object]:
    return json.loads(_git(root, "show", f"{ref}:kitty-specs/{slug}/meta.json"))


def test_upgrade_keeps_the_tracked_identity_and_refuses_an_unreadable_one(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    folders = _build_project(project)
    pre_run_sha = _git(project, "rev-parse", "HEAD").strip()
    before = {slug: _snapshot(folder) for slug, folder in folders.items()}

    exit_code, output = _upgrade(project)

    assert exit_code == 0, output
    flat_output = " ".join(output.split())  # the console wraps long lines

    # FR-001/FR-002: the deleted copy comes back carrying the identity its history uses.
    restored = json.loads((folders[_SPARSE] / "meta.json").read_text(encoding="utf-8"))
    assert restored["mission_id"] == _SPARSE_ID
    assert restored["mission_id"] == _tracked_meta(project, pre_run_sha, _SPARSE)["mission_id"]
    assert f"kitty-specs/{_SPARSE}/meta.json" in flat_output

    # FR-003/FR-008: no metadata is written for the unreadable tracked copy by any migration in the
    # run, and nothing in the folder carries an identity afterwards. (Derived views such as
    # status.json belong to other migrations and are not this mission's contract.)
    assert not (folders[_CORRUPT] / "meta.json").exists(), "a meta.json was fabricated for an unreadable tracked copy"
    for name in _snapshot(folders[_CORRUPT]):
        assert "mission_id" not in (folders[_CORRUPT] / name).read_text(encoding="utf-8", errors="replace")
    assert before[_CORRUPT]["spec.md"] == (folders[_CORRUPT] / "spec.md").read_bytes()
    assert f"git checkout -- kitty-specs/{_CORRUPT}/meta.json" in flat_output

    # FR-004 positive control on the same fixture: the pre-identity Mission is still repaired.
    legacy_meta = json.loads((folders[_LEGACY] / "meta.json").read_text(encoding="utf-8"))
    assert isinstance(legacy_meta.get("mission_id"), str) and legacy_meta["mission_id"]
    assert legacy_meta["mission_id"] != _SPARSE_ID
    assert (folders[_LEGACY] / "tasks" / "WP01-x.md").is_file()
    assert not (folders[_LEGACY] / "tasks" / "doing").exists()


def test_a_second_upgrade_rewrites_nothing_and_keeps_the_identity(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    folders = _build_project(project)
    exit_code, output = _upgrade(project)
    assert exit_code == 0, output
    restored = json.loads((folders[_SPARSE] / "meta.json").read_text(encoding="utf-8"))
    snapshot = _snapshot(folders[_SPARSE])

    second_exit, second_output = _upgrade(project)

    assert second_exit == 0, second_output
    assert _snapshot(folders[_SPARSE]) == snapshot, "a second upgrade rewrote the restored Mission"
    assert json.loads((folders[_SPARSE] / "meta.json").read_text(encoding="utf-8"))["mission_id"] == restored["mission_id"]


def test_upgrade_leaves_a_healthy_project_alone(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir(parents=True)
    (project / ".kittify").mkdir()
    _git(project, "init", "-q", "-b", "main")
    _git(project, "config", "user.email", "test@example.com")
    _git(project, "config", "user.name", "Test")
    healthy = _commit_mission(project, "healthy-mission-01HEALTH", _meta("healthy-mission-01HEALTH", "01HEALTHZZZZZZZZZZZZZZZZZZ"))
    _git(project, "add", "-A")
    _git(project, "commit", "-q", "-m", "init")
    before_meta = json.loads((healthy / "meta.json").read_text(encoding="utf-8"))

    exit_code, output = _upgrade(project)

    assert exit_code == 0, output
    flat_output = " ".join(output.split())
    assert "tracked meta.json is missing" not in flat_output
    assert "git checkout --" not in flat_output
    # The Mission keeps its identity and gains only baseline bookkeeping (the pre-existing 2.0.6
    # baseline adds mission_number); derived views the upgrade materializes are not this mission's
    # concern. Nothing about an identity changed on a healthy project (NFR-003/SC-004).
    after_meta = json.loads((healthy / "meta.json").read_text(encoding="utf-8"))
    assert after_meta.pop("mission_number", "") == ""
    assert after_meta == before_meta


def test_the_consistency_sweep_skips_a_refused_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-003: the sweep must not hand a refused Mission to its per-folder repair (which writes state).

    Without the skip, ``_repair_feature`` runs for a Mission whose tracked ``meta.json`` cannot be
    read, so its later steps rewrite state for a Mission we could not identify. The positive control
    on the same fixture is the repaired pre-identity Mission, which must still reach the repair.
    """
    from specify_cli.upgrade.migrations import m_2_0_6_residue_safe_consistency_sweep as sweep

    project = tmp_path / "proj"
    _build_project(project)
    repaired: list[str] = []
    original = sweep._repair_feature

    def _record(mission_dir: Path, repo_root: Path, dry_run: bool):
        repaired.append(mission_dir.name)
        return original(mission_dir, repo_root, dry_run)

    monkeypatch.setattr(sweep, "_repair_feature", _record)

    result = sweep.ResidueSafeConsistencySweepMigration().apply(project)

    assert result.success
    assert _CORRUPT not in repaired, "a Mission whose tracked meta.json is unreadable was repaired anyway"
    assert _LEGACY in repaired, "the pre-identity Mission must still be repaired (positive control)"


def test_the_lifecycle_normalization_reports_the_restore_command(tmp_path: Path) -> None:
    """FR-003/FR-005: the 3.2.0a4 walk names the file and the command instead of a bare "skipped"."""
    from specify_cli.migration.normalize_mission_lifecycle import normalize_repo

    project = tmp_path / "proj"
    _build_project(project)

    results = {result.slug: result for result in normalize_repo(project)}

    refused = results[_CORRUPT]
    notice = " ".join(refused.warnings)
    assert f"git checkout -- kitty-specs/{_CORRUPT}/meta.json" in notice
    assert "meta.json missing; mission skipped" not in notice
