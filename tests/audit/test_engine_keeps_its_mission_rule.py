"""The audit engine keeps its own Mission rule; its collision reports do not.

``doctor identity`` reports a ``spec.md``-only folder as ``residue`` (#5875), and
Mission selection cannot reach it. The audit engine deliberately keeps the looser
``is_mission_dir`` rule for its per-folder findings, so such a folder still gets
``IDENTITY_MISSING`` here (FR-008 / C-004 of #5875).

Its *collision* reports are different (#6757): ``DUPLICATE_PREFIX`` and
``AMBIGUOUS_SELECTOR`` are judged against the Missions selection can reach
(``audit_repo(..., residue_aware=True)``), so a folder no selector can reach can
neither fake a collision on a healthy Mission nor silence one between two real
Missions. Both directions are pinned below, on fixtures built by the same
helpers.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.audit import AuditOptions, run_audit

#: Two distinct mission ids, so a fixture never has to invent one.
ULID_A = "01KNXQS9ATWWFXS3K5ZJ9E5008"
ULID_B = "01KNXQS9ATWWFXS3K5ZJ9E5009"

#: A finding as the engine reports it: ``(code, severity, artifact_path, detail)``.
Finding = tuple[str, str, str, str]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _git_repo(root: Path) -> Path:
    """Make *root* a git repository whose default scan root is ``kitty-specs/``."""
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / "kitty-specs").mkdir(exist_ok=True)
    return root


def _mission(specs: Path, slug: str, *, mission_id: str | None = ULID_A, number: int = 1) -> Path:
    """A selectable Mission: ``meta.json`` on disk, with or without a ``mission_id``."""
    folder = specs / slug
    folder.mkdir(parents=True)
    meta: dict[str, object] = {"mission_slug": slug, "mission_number": number}
    if mission_id is not None:
        meta["mission_id"] = mission_id
    (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (folder / "spec.md").write_text(f"# {slug}\n", encoding="utf-8")
    return folder


def _spec_only(specs: Path, slug: str) -> Path:
    """Residue: only a ``spec.md``, no ``meta.json``, so selection never lists it."""
    folder = specs / slug
    folder.mkdir(parents=True)
    (folder / "spec.md").write_text(f"# {slug}\n", encoding="utf-8")
    return folder


def _commit(root: Path) -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "fixture")


def _findings(repo: Path) -> dict[str, list[Finding]]:
    """Run the audit through its public entry point and flatten each mission's findings."""
    report = run_audit(AuditOptions(repo_root=repo))
    return {mission.mission_slug: [(f.code, f.severity.value, f.artifact_path, f.detail) for f in mission.findings] for mission in report.missions}


_IDENTITY_MISSING: Finding = ("IDENTITY_MISSING", "error", "meta.json", "meta.json absent")


# ---------------------------------------------------------------------------
# The defect (#6757): a residue folder cannot fake a collision.
# ---------------------------------------------------------------------------


@pytest.mark.git_repo
def test_committed_spec_only_folder_cannot_fake_a_collision(tmp_path: Path) -> None:
    """#6757: the healthy Mission is clean; the residue folder keeps only its own identity finding."""
    repo = _git_repo(tmp_path)
    specs = repo / "kitty-specs"
    _mission(specs, "001-real")
    _spec_only(specs, "001-tracked-spec-only")
    _commit(repo)

    assert _findings(repo) == {
        "001-real": [],
        "001-tracked-spec-only": [_IDENTITY_MISSING],
    }


@pytest.mark.git_repo
def test_two_real_missions_sharing_the_prefix_still_collide(tmp_path: Path) -> None:
    """Positive control for the test above: the same fixture shape, with both folders as Missions."""
    repo = _git_repo(tmp_path)
    specs = repo / "kitty-specs"
    _mission(specs, "001-real")
    _mission(specs, "001-also-real", mission_id=ULID_B)
    _commit(repo)

    findings = _findings(repo)

    assert findings["001-real"] == [
        ("AMBIGUOUS_SELECTOR", "warning", "meta.json", "handle '001' also matches: 001-also-real"),
        ("DUPLICATE_PREFIX", "warning", "meta.json", "prefix '001' shared with: 001-also-real"),
    ]
    assert findings["001-also-real"] == [
        ("AMBIGUOUS_SELECTOR", "warning", "meta.json", "handle '001' also matches: 001-real"),
        ("DUPLICATE_PREFIX", "warning", "meta.json", "prefix '001' shared with: 001-real"),
    ]


@pytest.mark.git_repo
def test_residue_folder_in_a_real_collision_group_does_not_silence_it(tmp_path: Path) -> None:
    """The group is rebuilt over selectable Missions: a third, residue member cannot hide the collision."""
    repo = _git_repo(tmp_path)
    specs = repo / "kitty-specs"
    _mission(specs, "082-alpha")
    _mission(specs, "082-beta", mission_id=ULID_B)
    _spec_only(specs, "082-leftover")
    _commit(repo)

    findings = _findings(repo)

    assert findings["082-alpha"] == [
        ("AMBIGUOUS_SELECTOR", "warning", "meta.json", "handle '082' also matches: 082-beta"),
        ("DUPLICATE_PREFIX", "warning", "meta.json", "prefix '082' shared with: 082-beta"),
    ]
    assert findings["082-beta"] == [
        ("AMBIGUOUS_SELECTOR", "warning", "meta.json", "handle '082' also matches: 082-alpha"),
        ("DUPLICATE_PREFIX", "warning", "meta.json", "prefix '082' shared with: 082-alpha"),
    ]
    assert findings["082-leftover"] == [_IDENTITY_MISSING]


@pytest.mark.git_repo
def test_pre_identity_mission_still_collides(tmp_path: Path) -> None:
    """A tracked, id-less ``meta.json`` is selectable (the legacy/backfill state), so it still collides."""
    repo = _git_repo(tmp_path)
    specs = repo / "kitty-specs"
    _mission(specs, "081-legacy", mission_id=None)
    _mission(specs, "081-real", mission_id=ULID_B)
    _commit(repo)

    findings = _findings(repo)

    assert findings["081-legacy"] == [
        ("AMBIGUOUS_SELECTOR", "warning", "meta.json", "handle '081' also matches: 081-real"),
        ("DUPLICATE_PREFIX", "warning", "meta.json", "prefix '081' shared with: 081-real"),
        ("IDENTITY_MISSING", "error", "meta.json", "missing mission_id field"),
    ]
    assert findings["081-real"] == [
        ("AMBIGUOUS_SELECTOR", "warning", "meta.json", "handle '081' also matches: 081-legacy"),
        ("DUPLICATE_PREFIX", "warning", "meta.json", "prefix '081' shared with: 081-legacy"),
    ]


# ---------------------------------------------------------------------------
# Non-git roots: the residue rule falls back to meta.json presence on disk.
# ---------------------------------------------------------------------------


def test_spec_only_folder_on_a_non_git_root_keeps_identity_missing(tmp_path: Path) -> None:
    """Outside git a ``spec.md``-only folder is residue for collisions, a Mission for IDENTITY_MISSING."""
    specs = tmp_path / "kitty-specs"
    _mission(specs, "002-real")
    _spec_only(specs, "002-spec-only")

    assert _findings(tmp_path) == {
        "002-real": [],
        "002-spec-only": [_IDENTITY_MISSING],
    }


def test_spec_only_folder_alone_on_a_non_git_root_keeps_identity_missing(tmp_path: Path) -> None:
    """The #5875 half: the engine's own Mission rule still reports the folder's identity gap."""
    _spec_only(tmp_path / "kitty-specs", "002-spec-only")

    assert _findings(tmp_path) == {"002-spec-only": [_IDENTITY_MISSING]}


# ---------------------------------------------------------------------------
# The rest of the engine's contract is unchanged by the split.
# ---------------------------------------------------------------------------


@pytest.mark.git_repo
def test_mission_filter_still_reports_the_collision(tmp_path: Path) -> None:
    """``--mission`` scoping keeps the scoped Mission's collision findings."""
    repo = _git_repo(tmp_path)
    specs = repo / "kitty-specs"
    _mission(specs, "083-alpha")
    _mission(specs, "083-beta", mission_id=ULID_B)
    _commit(repo)

    report = run_audit(AuditOptions(repo_root=repo, mission_filter="083-alpha"))

    assert [mission.mission_slug for mission in report.missions] == ["083-alpha"]
    findings = report.missions[0].findings
    assert [(f.code, f.detail) for f in findings] == [
        ("AMBIGUOUS_SELECTOR", "handle '083' also matches: 083-beta"),
        ("DUPLICATE_PREFIX", "prefix '083' shared with: 083-beta"),
    ]


@pytest.mark.git_repo
def test_duplicate_mission_id_still_reported_through_the_engine(tmp_path: Path) -> None:
    """``DUPLICATE_MISSION_ID`` keeps its population: both real Missions share one id."""
    repo = _git_repo(tmp_path)
    specs = repo / "kitty-specs"
    _mission(specs, "084-alpha", mission_id=ULID_A)
    _mission(specs, "085-beta", mission_id=ULID_A)
    _commit(repo)

    findings = _findings(repo)

    for slug, other in (("084-alpha", "085-beta"), ("085-beta", "084-alpha")):
        assert ("DUPLICATE_MISSION_ID", "error", "meta.json", f"mission_id {ULID_A!r} also used by: {other}") in findings[slug]


@pytest.mark.git_repo
def test_custom_scan_root_keeps_its_population_and_makes_no_git_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A custom scan root (audit fixtures) keeps the engine's population and its no-probe posture.

    The residue-aware collision walk is a default-scan behaviour: a
    ``--fixture-dir`` audit used to make no git call at all, so a broken index
    must not start failing it (#6757 review).
    """
    import specify_cli.context.mission_resolver as mission_resolver

    repo = _git_repo(tmp_path)
    specs = repo / "kitty-specs"
    _mission(specs, "003-real")
    _mission(specs, "003-legacy", mission_id=None)
    _commit(repo)
    fixtures = tmp_path / "fixtures"
    _mission(fixtures, "004-fixture")

    def _no_git(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("a custom scan root must not probe git")

    monkeypatch.setattr(mission_resolver, "tracked_paths", _no_git)
    monkeypatch.setattr(mission_resolver, "run_git", _no_git)

    report = run_audit(AuditOptions(repo_root=repo, scan_root=fixtures))

    assert [mission.mission_slug for mission in report.missions] == ["004-fixture"]
    # 004-fixture neither shares a prefix nor a mission_id with the repo's folders.
    assert [(f.code, f.detail) for f in report.missions[0].findings] == []
