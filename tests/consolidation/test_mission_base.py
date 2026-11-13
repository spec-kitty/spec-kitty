"""The Mission base authority (#7560): recorded, else derived, else unavailable; fail-closed."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.consolidation.mission_base import (
    MissionBase,
    MissionBaseProvenance,
    MissionBaseReason,
    pre_mission_history,
    resolve_mission_base,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.fast]

SLUG = "demo-mission-01ABCDEF"
MISSION_BRANCH = "kitty/mission-demo-mission-01ABCDEF"


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)
    return done.stdout.strip()


def _commit(repo: Path, rel: str, content: str, message: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "commit.gpgsign", "false")
    return root


def _write_meta(feature_dir: Path, **fields: object) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_slug": SLUG, **fields}), encoding="utf-8")


def _mission_on_branch(repo: Path) -> tuple[str, str]:
    """main: base; Mission branch cut at base, then a scaffold commit and a work commit."""
    base = _commit(repo, "README.md", "base\n", "base")
    _git(repo, "checkout", "-q", "-b", MISSION_BRANCH)
    scaffold = _commit(repo, f"kitty-specs/{SLUG}/spec.md", "spec\n", "scaffold")
    _commit(repo, "src/app.py", "x = 1\n", "work")
    return base, scaffold


def test_recorded_and_valid_is_recorded(repo: Path, tmp_path: Path) -> None:
    base, _ = _mission_on_branch(repo)
    feature_dir = tmp_path / "meta"
    _write_meta(feature_dir, mission_base_sha=base)

    result = resolve_mission_base(repo, feature_dir, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert result == MissionBase(base, MissionBaseProvenance.RECORDED)


def test_recorded_not_on_branch_falls_through_to_derived(repo: Path, tmp_path: Path) -> None:
    base, _ = _mission_on_branch(repo)
    _git(repo, "checkout", "-q", "main")
    elsewhere = _commit(repo, "other.txt", "o\n", "elsewhere")
    feature_dir = tmp_path / "meta"
    _write_meta(feature_dir, mission_base_sha=elsewhere)

    result = resolve_mission_base(repo, feature_dir, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert result.provenance is MissionBaseProvenance.DERIVED
    assert result.sha == base
    assert result.reason is not None and elsewhere[:12] in result.reason


@pytest.mark.parametrize(
    "spell",
    [
        pytest.param(lambda _base: MISSION_BRANCH, id="branch-name"),
        pytest.param(lambda _base: "HEAD", id="HEAD"),
        pytest.param(lambda base: base[:12], id="short-sha"),
        pytest.param(lambda base: base.upper(), id="uppercase-sha"),
        pytest.param(lambda base: f"{base}^0", id="revision-expression"),
    ],
)
def test_recorded_value_that_is_not_a_full_sha_is_not_recorded(repo: Path, tmp_path: Path, spell: Any) -> None:
    """HIGH-2: only a full lowercase object id is a recorded base; a name floats with its ref."""
    base, _ = _mission_on_branch(repo)
    feature_dir = tmp_path / "meta"
    _write_meta(feature_dir, mission_base_sha=spell(base))

    result = resolve_mission_base(repo, feature_dir, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert (result.sha, result.provenance) == (base, MissionBaseProvenance.DERIVED)
    assert result.kind is MissionBaseReason.RECORDED_NOT_A_SHA
    assert result.reason is not None and "is not a full commit id" in result.reason


def test_recorded_full_sha_of_a_tag_object_is_not_recorded(repo: Path, tmp_path: Path) -> None:
    """A full hex id that names an annotated tag resolves to a different commit id: not the base."""
    base, _ = _mission_on_branch(repo)
    _git(repo, "tag", "-a", "-m", "t", "pinned", base)
    tag_object = _git(repo, "rev-parse", "pinned")
    assert tag_object != base
    feature_dir = tmp_path / "meta"
    _write_meta(feature_dir, mission_base_sha=tag_object)

    result = resolve_mission_base(repo, feature_dir, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert (result.sha, result.provenance, result.kind) == (base, MissionBaseProvenance.DERIVED, MissionBaseReason.RECORDED_NOT_A_SHA)


@pytest.mark.parametrize("which", ["scaffold", "work", "tip"])
def test_recorded_base_at_or_above_the_mission_start_is_not_used(repo: Path, tmp_path: Path, which: str) -> None:
    """HIGH-1: a recorded base from which the Mission directory is reachable sits above the Mission's start."""
    base, scaffold = _mission_on_branch(repo)
    forged = {"scaffold": scaffold, "work": _git(repo, "rev-parse", f"{MISSION_BRANCH}~0"), "tip": ""}[which]
    if which == "tip":
        forged = _commit(repo, "src/evil.py", "evil\n", "smuggled")
    feature_dir = tmp_path / "meta"
    _write_meta(feature_dir, mission_base_sha=forged)

    result = resolve_mission_base(repo, feature_dir, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert (result.sha, result.provenance) == (base, MissionBaseProvenance.DERIVED)
    assert result.kind is MissionBaseReason.RECORDED_NOT_BELOW_ORIGIN
    assert result.reason is not None and forged[:12] in result.reason


def test_recorded_base_on_a_side_branch_merged_after_the_start_is_not_used(repo: Path, tmp_path: Path) -> None:
    """A side branch cut below the Mission and merged in after its scaffold never saw the Mission directory.

    Its commits are reachable from the Mission branch and the Mission directory is not
    reachable from them, so only the anchor to the Mission's origin (the scaffold commit's
    first parent) tells them apart from genuine pre-Mission history.
    """
    base, _ = _mission_on_branch(repo)
    _git(repo, "checkout", "-q", "-b", "side", base)
    smuggled = _commit(repo, "src/evil.py", "evil\n", "smuggled on a side branch")
    _git(repo, "checkout", "-q", MISSION_BRANCH)
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", "side")
    feature_dir = tmp_path / "meta"
    _write_meta(feature_dir, mission_base_sha=smuggled)

    result = resolve_mission_base(repo, feature_dir, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert (result.sha, result.provenance) == (base, MissionBaseProvenance.DERIVED)
    assert result.kind is MissionBaseReason.RECORDED_NOT_BELOW_ORIGIN
    assert result.reason is not None and smuggled[:12] in result.reason


def test_recorded_base_without_a_scaffold_commit_is_not_anchored(repo: Path, tmp_path: Path) -> None:
    """No scaffold on the first-parent history: the recorded value cannot be anchored, so nothing is (fail-closed)."""
    base = _commit(repo, "README.md", "base\n", "base")
    _git(repo, "checkout", "-q", "-b", MISSION_BRANCH)
    _commit(repo, "src/app.py", "x = 1\n", "work without a scaffold")
    feature_dir = tmp_path / "meta"
    _write_meta(feature_dir, mission_base_sha=base)

    result = resolve_mission_base(repo, feature_dir, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert (result.sha, result.provenance) == (None, MissionBaseProvenance.UNAVAILABLE)
    assert result.reason is not None and "not on the history the Mission started from" in result.reason


def test_derived_base_that_reaches_the_mission_dir_is_unavailable(repo: Path) -> None:
    """HIGH-1, derived step: the Mission directory came and went on a side branch below the scaffold."""
    base = _commit(repo, "README.md", "base\n", "base")
    _git(repo, "checkout", "-q", "-b", "side", base)
    _commit(repo, f"kitty-specs/{SLUG}/spec.md", "early\n", "early add")
    _git(repo, "rm", "-q", "-r", f"kitty-specs/{SLUG}")
    _git(repo, "commit", "-q", "-m", "drop it")
    _git(repo, "checkout", "-q", "-b", MISSION_BRANCH, base)
    _commit(repo, "src/app.py", "x\n", "work")
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge side", "side")
    _commit(repo, f"kitty-specs/{SLUG}/spec.md", "spec\n", "scaffold")

    result = resolve_mission_base(repo, None, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert (result.sha, result.provenance) == (None, MissionBaseProvenance.UNAVAILABLE)
    assert result.kind is MissionBaseReason.ABOVE_MISSION_START


def test_mission_start_probe_failure_is_unavailable(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base, _ = _mission_on_branch(repo)
    feature_dir = tmp_path / "meta"
    _write_meta(feature_dir, mission_base_sha=base)
    from specify_cli.core.git_ops import run_command as real

    def failing_log(argv: list[str], **kwargs: Any) -> Any:
        if argv[:2] == ["git", "log"] and "-1" in argv:
            return 128, "", "fatal: bad object"
        return real(argv, **kwargs)

    monkeypatch.setattr("specify_cli.consolidation.git_probes.run_command", failing_log)

    result = resolve_mission_base(repo, feature_dir, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert (result.sha, result.provenance, result.kind) == (None, MissionBaseProvenance.UNAVAILABLE, MissionBaseReason.PROBE_FAILED)


def test_recorded_sha_resolve_failure_is_a_probe_failure(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base, _ = _mission_on_branch(repo)
    feature_dir = tmp_path / "meta"
    _write_meta(feature_dir, mission_base_sha=base)
    from specify_cli.core.git_ops import run_command as real

    def failing_rev_parse(argv: list[str], **kwargs: Any) -> Any:
        if argv[:2] == ["git", "rev-parse"] and "--quiet" in argv:  # the recorded-sha probe, not the branch resolve
            return 128, "", "fatal: corrupt"
        return real(argv, **kwargs)

    monkeypatch.setattr("specify_cli.consolidation.git_probes.run_command", failing_rev_parse)

    result = resolve_mission_base(repo, feature_dir, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert (result.sha, result.kind) == (None, MissionBaseReason.PROBE_FAILED)
    assert result.reason is not None and "fatal: corrupt" in result.reason


def test_recorded_sha_absent_from_clone_falls_through(repo: Path, tmp_path: Path) -> None:
    base, _ = _mission_on_branch(repo)
    feature_dir = tmp_path / "meta"
    _write_meta(feature_dir, mission_base_sha="0" * 40)

    result = resolve_mission_base(repo, feature_dir, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert (result.sha, result.provenance) == (base, MissionBaseProvenance.DERIVED)


def test_not_recorded_derives_first_parent_of_scaffold(repo: Path, tmp_path: Path) -> None:
    base, scaffold = _mission_on_branch(repo)
    feature_dir = tmp_path / "meta"
    _write_meta(feature_dir)

    result = resolve_mission_base(repo, feature_dir, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert result.provenance is MissionBaseProvenance.DERIVED
    assert result.sha == base == _git(repo, "rev-parse", f"{scaffold}^1")
    assert result.reason == "no mission_base_sha recorded"
    assert result.kind is MissionBaseReason.NOT_RECORDED


def test_no_feature_dir_and_unreadable_meta_derive(repo: Path, tmp_path: Path) -> None:
    base, _ = _mission_on_branch(repo)
    feature_dir = tmp_path / "meta"
    feature_dir.mkdir()
    (feature_dir / "meta.json").write_text("{not json", encoding="utf-8")

    for candidate in (None, feature_dir):
        result = resolve_mission_base(repo, candidate, mission_branch=MISSION_BRANCH, mission_slug=SLUG)
        assert (result.sha, result.provenance) == (base, MissionBaseProvenance.DERIVED)


def test_scaffold_root_commit_is_unavailable(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", MISSION_BRANCH)
    _commit(repo, f"kitty-specs/{SLUG}/spec.md", "spec\n", "root scaffold")

    result = resolve_mission_base(repo, None, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert result.sha is None
    assert result.provenance is MissionBaseProvenance.UNAVAILABLE
    assert result.reason is not None and "root commit" in result.reason
    assert result.kind is MissionBaseReason.ROOT_SCAFFOLD


def test_no_scaffold_commit_is_unavailable(repo: Path) -> None:
    _commit(repo, "README.md", "base\n", "base")
    _git(repo, "checkout", "-q", "-b", MISSION_BRANCH)
    _commit(repo, "src/app.py", "x\n", "work only")

    result = resolve_mission_base(repo, None, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert result == MissionBase(None, MissionBaseProvenance.UNAVAILABLE, result.reason, MissionBaseReason.NO_SCAFFOLD)
    assert result.reason is not None and f"kitty-specs/{SLUG}/" in result.reason


def _renamed_mission(repo: Path) -> dict[str, str]:
    """base -> scaffold (kitty-specs/old/) -> work -> rename (git mv old -> <slug>) -> plan."""
    shas = {"base": _commit(repo, "README.md", "base\n", "base")}
    _git(repo, "checkout", "-q", "-b", MISSION_BRANCH)
    shas["scaffold"] = _commit(repo, "kitty-specs/old/spec.md", "spec body for the mission\n", "scaffold")
    shas["work"] = _commit(repo, "src/app.py", "x = 1\n", "work")
    _git(repo, "mv", "kitty-specs/old", f"kitty-specs/{SLUG}")
    _git(repo, "commit", "-q", "-m", "rename")
    shas["rename"] = _git(repo, "rev-parse", "HEAD")
    shas["plan"] = _commit(repo, f"kitty-specs/{SLUG}/plan.md", "plan\n", "plan")
    return shas


def test_mission_dir_arrived_by_rename_is_unavailable(repo: Path, tmp_path: Path) -> None:
    """Review cycle 1, issue 1: ``rename^1`` sits above the scaffold and the work commit.

    A pathspec-limited log sees the rename as an add, so without the rename check the
    derived base would be ``work`` and both Mission commits would read as pre-Mission.
    """
    shas = _renamed_mission(repo)
    feature_dir = tmp_path / "meta"
    _write_meta(feature_dir)

    result = resolve_mission_base(repo, feature_dir, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert result.sha is None
    assert result.provenance is MissionBaseProvenance.UNAVAILABLE
    assert result.reason is not None
    assert "by a rename from kitty-specs/old/spec.md" in result.reason
    assert shas["rename"][:12] in result.reason
    assert result.kind is MissionBaseReason.RENAMED_INTO


def test_rename_does_not_override_a_valid_recorded_base(repo: Path, tmp_path: Path) -> None:
    shas = _renamed_mission(repo)
    feature_dir = tmp_path / "meta"
    _write_meta(feature_dir, mission_base_sha=shas["base"])

    result = resolve_mission_base(repo, feature_dir, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert (result.sha, result.provenance) == (shas["base"], MissionBaseProvenance.RECORDED)


_SCAFFOLD_FILES = {
    "spec.md": "# Mission specification\n\n## Scope\n\nTo be written.\n",
    "tasks/.gitkeep": "",
    "tasks/README.md": "# Tasks\n\nWork package prompt files live here, one per WP.\nDo not edit by hand.\n",
    "checklists/requirements.md": "# Requirements checklist\n\n- [ ] No implementation details\n- [ ] Testable\n",
    "issue-matrix.json": '{"schema_version": 1, "issues": []}\n',
}


def _scaffold(repo: Path, slug: str, message: str) -> str:
    """Commit a Mission scaffold shaped like ``agent mission create``'s, in one commit."""
    for rel, content in _SCAFFOLD_FILES.items():
        path = repo / "kitty-specs" / slug / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def test_scaffold_beside_an_older_mission_still_derives(repo: Path) -> None:
    """Review cycle 2: a new scaffold that resembles an older Mission is not a rename.

    The older Mission holds identical files (an empty ``tasks/.gitkeep``, the same
    ``tasks/README.md``, checklist and issue matrix). Copy detection would pair every one of
    them with the new scaffold; the rename-only probe must not, so the base is DERIVED.
    """
    _commit(repo, "README.md", "base\n", "base")
    _scaffold(repo, "older-mission-01AAAAAA", "older mission")
    base = _commit(repo, "src/app.py", "x = 1\n", "older mission work")
    _git(repo, "checkout", "-q", "-b", MISSION_BRANCH)
    scaffold = _scaffold(repo, SLUG, "scaffold")
    _commit(repo, "src/app.py", "x = 2\n", "work")

    result = resolve_mission_base(repo, None, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert (result.sha, result.provenance) == (base, MissionBaseProvenance.DERIVED)
    assert _git(repo, "rev-parse", f"{scaffold}^1") == base


def test_rename_probe_uses_no_copy_detection(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The probe is rename-only through ``kernel.git``: renames on, ``R`` only, never copy detection."""
    _mission_on_branch(repo)
    from specify_cli.consolidation import mission_base

    calls: list[dict[str, Any]] = []
    real = mission_base.changed_entries

    def recording(*args: Any, **kwargs: Any) -> Any:
        calls.append(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(mission_base, "changed_entries", recording)

    resolve_mission_base(repo, None, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert calls == [{"renames": True, "diff_filter": "R"}]


def test_copy_that_keeps_its_source_derives_residual(repo: Path) -> None:
    """Named residual: a copy that leaves its source in place (``cp -r old <slug>``) is not detected.

    It cannot be told apart from an ordinary scaffold that resembles an older Mission, so the
    derived base is the copying commit's first parent (here above the ``work`` commit).
    """
    _commit(repo, "README.md", "base\n", "base")
    _git(repo, "checkout", "-q", "-b", MISSION_BRANCH)
    _commit(repo, "kitty-specs/old/spec.md", "spec body for the mission\n", "scaffold")
    work = _commit(repo, "src/app.py", "x = 1\n", "work")
    _commit(repo, f"kitty-specs/{SLUG}/spec.md", "spec body for the mission\n", "copy")

    result = resolve_mission_base(repo, None, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert (result.sha, result.provenance) == (work, MissionBaseProvenance.DERIVED)


def test_mission_dir_renamed_from_outside_kitty_specs_is_unavailable(repo: Path) -> None:
    _commit(repo, "README.md", "base\n", "base")
    _git(repo, "checkout", "-q", "-b", MISSION_BRANCH)
    _commit(repo, "drafts/spec.md", "spec body for the mission\n", "draft")
    (repo / "kitty-specs").mkdir()
    _git(repo, "mv", "drafts", f"kitty-specs/{SLUG}")
    _git(repo, "commit", "-q", "-m", "move draft in")

    result = resolve_mission_base(repo, None, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert result.provenance is MissionBaseProvenance.UNAVAILABLE
    assert result.reason is not None and "drafts/spec.md" in result.reason


def test_rename_inside_the_mission_dir_after_scaffold_still_derives(repo: Path) -> None:
    """A rename that is not the earliest add does not disturb the derivation."""
    base, _ = _mission_on_branch(repo)
    _git(repo, "mv", f"kitty-specs/{SLUG}/spec.md", f"kitty-specs/{SLUG}/spec-v2.md")
    _git(repo, "commit", "-q", "-m", "rename spec")

    result = resolve_mission_base(repo, None, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert (result.sha, result.provenance) == (base, MissionBaseProvenance.DERIVED)


def test_rename_probe_failure_is_unavailable(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _mission_on_branch(repo)
    from kernel.git import GitCommandError
    from specify_cli.consolidation import mission_base

    def failing_diff(*_args: Any, **_kwargs: Any) -> Any:
        raise GitCommandError(argv=("diff",), cwd=repo, returncode=128, stderr="fatal: bad object")

    monkeypatch.setattr(mission_base, "changed_entries", failing_diff)

    result = resolve_mission_base(repo, None, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert result.provenance is MissionBaseProvenance.UNAVAILABLE
    assert result.reason is not None and "git probe failed" in result.reason
    assert result.kind is MissionBaseReason.PROBE_FAILED


def test_scaffold_through_second_parent_merge_never_picks_above_mission_work(repo: Path) -> None:
    """The scaffold arrives through a merge's second parent, so it is off the first-parent spine.

    Observed behaviour: the merge itself, diffed against its first parent, is the earliest
    first-parent commit adding the Mission directory, so the derived base is the merge's
    first parent. That base excludes the side branch's scaffold commit, which therefore
    stays Mission history (it is never exempted as pre-Mission).
    """
    base = _commit(repo, "README.md", "base\n", "base")
    _git(repo, "checkout", "-q", "-b", MISSION_BRANCH)
    spine = _commit(repo, "src/app.py", "x\n", "spine work")
    _git(repo, "checkout", "-q", "-b", "side", base)
    side_scaffold = _commit(repo, f"kitty-specs/{SLUG}/spec.md", "spec\n", "side scaffold")
    _git(repo, "checkout", "-q", MISSION_BRANCH)
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge side", "side")
    merge = _git(repo, "rev-parse", "HEAD")

    result = resolve_mission_base(repo, None, mission_branch=MISSION_BRANCH, mission_slug=SLUG)

    assert result.provenance is MissionBaseProvenance.DERIVED
    assert result.sha == spine == _git(repo, "rev-parse", f"{merge}^1")
    assert side_scaffold in pre_mission_history(repo, "main", MissionBase(merge, MissionBaseProvenance.DERIVED))
    assert side_scaffold not in pre_mission_history(repo, "main", result)


def test_unresolvable_mission_branch_is_unavailable_never_raises(repo: Path, tmp_path: Path) -> None:
    base, _ = _mission_on_branch(repo)
    feature_dir = tmp_path / "meta"
    _write_meta(feature_dir, mission_base_sha=base)

    result = resolve_mission_base(repo, feature_dir, mission_branch="kitty/no-such-branch", mission_slug=SLUG)

    assert result.sha is None
    assert result.provenance is MissionBaseProvenance.UNAVAILABLE
    assert result.kind is MissionBaseReason.MISSION_BRANCH_UNRESOLVED
    assert result.reason == "the Mission branch does not resolve"


def test_unresolvable_branch_without_record_is_unavailable(repo: Path) -> None:
    _mission_on_branch(repo)

    result = resolve_mission_base(repo, None, mission_branch="kitty/no-such-branch", mission_slug=SLUG)

    assert (result.sha, result.provenance, result.kind) == (None, MissionBaseProvenance.UNAVAILABLE, MissionBaseReason.MISSION_BRANCH_UNRESOLVED)


def test_pre_mission_history_empty_when_target_reaches_base(repo: Path) -> None:
    base, _ = _mission_on_branch(repo)

    assert pre_mission_history(repo, "main", MissionBase(base, MissionBaseProvenance.RECORDED)) == ()


def test_pre_mission_history_lists_commits_the_window_base_lacks(repo: Path) -> None:
    first = _commit(repo, "README.md", "base\n", "base")
    _git(repo, "checkout", "-q", "-b", "dependency")
    dep_a = _commit(repo, "dep.txt", "a\n", "dep a")
    dep_b = _commit(repo, "dep.txt", "b\n", "dep b")
    base = MissionBase(dep_b, MissionBaseProvenance.RECORDED)

    assert set(pre_mission_history(repo, first, base)) == {dep_a, dep_b}


def test_pre_mission_history_empty_for_unavailable_or_no_window(repo: Path) -> None:
    base, _ = _mission_on_branch(repo)

    assert pre_mission_history(repo, "main", MissionBase(None, MissionBaseProvenance.UNAVAILABLE, "x")) == ()
    assert pre_mission_history(repo, None, MissionBase(base, MissionBaseProvenance.RECORDED)) == ()


def test_pre_mission_history_probe_error_propagates(repo: Path) -> None:
    base, _ = _mission_on_branch(repo)

    with pytest.raises(GitProbeError):
        pre_mission_history(repo, "no-such-ref", MissionBase(base, MissionBaseProvenance.RECORDED))
