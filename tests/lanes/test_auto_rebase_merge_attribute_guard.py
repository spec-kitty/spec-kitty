"""#5604 review fold I1: the stale-lane auto-rebase runs WP01's merge-attribute guard in the lane checkout.

git computes the auto-rebase merge in the lane checkout, so it honours that checkout's merge
attributes: an uncommitted ``.gitattributes`` there, ``$GIT_COMMON_DIR/info/attributes``, a
lane-committed ``.gitattributes`` and any ``merge.<name>.driver``. A ``merge=union`` turns a real
conflict into bytes neither side wrote; before the fold the tool committed that merge and RECORDED
it, and the claim then exempted it (its own attribute check reads the repository root checkout and
the committed attributes only). The auto-rebase now runs
:func:`~specify_cli.consolidation.merge_attribute_guard.assert_registered_merge_behaviour` in the lane
checkout, over every path that differs between the two tips (every path a merge driver can see), with the target branch tip as
the committed attributes source (the claim's own rule), BEFORE the merge: a refusal halts with a
reason, makes no merge and records nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.lanes.auto_rebase import AutoRebaseReport, attempt_auto_rebase
from tests.lanes.test_auto_rebase_record import _LANE, _MISSION, _PREFIX, _commit, _git, _init_repo, _lane, _lane_worktree, _refs_under

pytestmark = pytest.mark.git_repo

_TEN = "".join(f"l{i} = {i}\n" for i in range(10))
_UNION = "code.py merge=union\n"
_FORGE_DRIVER = "cp %B %A"


def _conflict(tmp_path: Path, *, target_attrs: str | None = None, lane_attrs: str | None = None) -> tuple[Path, Path]:
    """The lane and the Mission branch edit line 5 of ``code.py`` differently: stock git conflicts there."""
    root = _init_repo(tmp_path)
    if target_attrs is not None:
        _commit(root, ".gitattributes", target_attrs, "reviewed attributes on the target")
    _commit(root, "code.py", _TEN, "seed code")
    _git(root, "branch", "-f", _MISSION, "main")
    worktree = _lane_worktree(root)
    if lane_attrs is not None:
        _commit(worktree, ".gitattributes", lane_attrs, "lane: attributes")
    _commit(worktree, "code.py", _TEN.replace("l5 = 5", "l5 = 'LANE'"), "lane: edit l5")
    _git(root, "checkout", "-q", _MISSION)
    _commit(root, "code.py", _TEN.replace("l5 = 5", "l5 = 'MISSION'"), "mission: edit l5")
    _git(root, "checkout", "-q", "main")
    return root, worktree


def _rebase(root: Path, worktree: Path, *, target_branch: str | None = "main") -> AutoRebaseReport:
    return attempt_auto_rebase(lane=_lane(), branch=_LANE, mission_branch=_MISSION, repo_root=root, worktree_path=worktree, target_branch=target_branch)


def _assert_halted_untouched(root: Path, worktree: Path, report: AutoRebaseReport, before: str, *named: str) -> None:
    assert report.succeeded is False, report
    assert report.halt_reason is not None
    for word in named:
        assert word in report.halt_reason, report.halt_reason
    assert "nothing was merged" in report.halt_reason, report.halt_reason
    assert _git(worktree, "rev-parse", "HEAD") == before, "the guard must refuse before any merge"
    assert _refs_under(root, _PREFIX) == [], "a refused auto-rebase records nothing"
    merge_head = _git(worktree, "rev-parse", "--git-path", "MERGE_HEAD")
    assert not (worktree / merge_head).exists() and not Path(merge_head).exists(), "no merge is left in progress"
    assert "'LANE'" in (worktree / "code.py").read_text(encoding="utf-8")


def test_an_uncommitted_union_in_the_lane_checkout_halts_before_the_merge(tmp_path: Path) -> None:
    """Red before the fold: git union-merged the conflict and the tool committed AND recorded the merge."""
    root, worktree = _conflict(tmp_path)
    (worktree / ".gitattributes").write_text(_UNION, encoding="utf-8")
    before = _git(worktree, "rev-parse", "HEAD")

    report = _rebase(root, worktree)

    _assert_halted_untouched(root, worktree, report, before, "union", "code.py")


def test_a_lane_committed_union_halts_before_the_merge(tmp_path: Path) -> None:
    """The target does not commit the ``union``: an unreviewed lane commit cannot turn the conflict clean."""
    root, worktree = _conflict(tmp_path, lane_attrs=_UNION)
    before = _git(worktree, "rev-parse", "HEAD")

    report = _rebase(root, worktree)

    _assert_halted_untouched(root, worktree, report, before, "union", "code.py")


def test_a_clone_local_info_attributes_union_halts_before_the_merge(tmp_path: Path) -> None:
    root, worktree = _conflict(tmp_path)
    info = Path(_git(root, "rev-parse", "--git-common-dir"))
    info = info if info.is_absolute() else root / info
    (info / "info").mkdir(parents=True, exist_ok=True)
    (info / "info" / "attributes").write_text(_UNION, encoding="utf-8")
    before = _git(worktree, "rev-parse", "HEAD")

    _assert_halted_untouched(root, worktree, _rebase(root, worktree), before, "union")


def test_a_configured_text_driver_halts_before_the_merge(tmp_path: Path) -> None:
    """``merge.text.driver`` shadows git's built-in text merge for a committed ``merge=text``."""
    root, worktree = _conflict(tmp_path, target_attrs="code.py merge=text\n")
    _git(root, "config", "merge.text.driver", _FORGE_DRIVER)
    before = _git(worktree, "rev-parse", "HEAD")

    _assert_halted_untouched(root, worktree, _rebase(root, worktree), before, "merge.text.driver")


def test_a_union_committed_at_the_target_tip_is_honoured(tmp_path: Path) -> None:
    """Control (operator ruling (a)): a ``union`` the target commits is reviewed, so the auto-rebase merges and records."""
    root, worktree = _conflict(tmp_path, target_attrs=_UNION)

    report = _rebase(root, worktree)

    assert report.succeeded, report.halt_reason
    head = _git(worktree, "rev-parse", "HEAD")
    assert report.merge_sha == head
    assert _refs_under(root, _PREFIX) == [f"{_PREFIX}{_LANE}/{head}"]


def test_without_a_target_branch_no_committed_union_is_honoured(tmp_path: Path) -> None:
    """No committed attributes source: a ``union`` is refused from any source (fail closed)."""
    root, worktree = _conflict(tmp_path, target_attrs=_UNION)
    before = _git(worktree, "rev-parse", "HEAD")

    _assert_halted_untouched(root, worktree, _rebase(root, worktree, target_branch=None), before, "union")


def test_an_unreadable_target_branch_honours_no_committed_union(tmp_path: Path) -> None:
    root, worktree = _conflict(tmp_path, target_attrs=_UNION)
    before = _git(worktree, "rev-parse", "HEAD")

    _assert_halted_untouched(root, worktree, _rebase(root, worktree, target_branch="no-such-branch"), before, "union")


def test_a_plain_conflict_still_reaches_the_classifier(tmp_path: Path) -> None:
    """Control: with git's built-in merge the guard passes and the classifier halts on the Manual conflict, as before."""
    root, worktree = _conflict(tmp_path)

    report = _rebase(root, worktree)

    assert report.succeeded is False
    assert report.halt_reason is not None and "no classifier rule matched" in report.halt_reason, report.halt_reason
    assert "nothing was merged" not in report.halt_reason


# --- #5604 review fold R1: the record step's tree read is immune to signature and format config ------------------


@pytest.mark.parametrize(
    "config",
    [
        pytest.param(("log.showSignature", "true"), id="log_show_signature"),
        pytest.param(("format.pretty", "fuller"), id="format_pretty"),
        pytest.param(("color.ui", "always"), id="color_ui_always"),
        pytest.param(("log.decorate", "full"), id="log_decorate"),
    ],
)
def test_a_clean_auto_rebase_is_recorded_whatever_the_log_config(tmp_path: Path, config: tuple[str, str]) -> None:
    """Red before the fold with ``log.showSignature=true``: ``git show -s --format=%T`` printed the signature check first,
    the tree never matched, and every auto-rebase was undone as "a pre-commit hook altered it"."""
    from tests.lanes.test_auto_rebase_record import _clean_shape

    root, worktree = _clean_shape(tmp_path)
    _git(root, "config", *config)

    report = _rebase(root, worktree)

    assert report.succeeded, report.halt_reason
    head = _git(worktree, "rev-parse", "HEAD")
    assert report.merge_sha == head
    assert _refs_under(root, _PREFIX) == [f"{_PREFIX}{_LANE}/{head}"]


def test_a_signed_auto_rebase_merge_is_recorded_with_log_show_signature(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R1 red-first: with ``log.showSignature=true`` and a signed merge commit, ``git show -s --format=%T`` printed gpg's
    verification before the tree id; the record step's tree comparison failed and the merge was undone.

    The tool's own commit disables signing today, so the merge is signed here through the merge-conclusion
    seam (a signing setup the read must survive, whoever signs).
    """
    import subprocess

    from specify_cli.git.merge_conclusion import conclude_in_progress_op
    from tests._support.gpg_signing import sign_commits_and_show_signatures, use_throwaway_signing_key
    from tests.lanes.test_auto_rebase_record import _clean_shape

    use_throwaway_signing_key(tmp_path, monkeypatch)
    root, worktree = _clean_shape(tmp_path)
    sign_commits_and_show_signatures(root)

    def _signed(checkout: Path, *, env: dict[str, str] | None, message: str | None = None) -> subprocess.CompletedProcess[str]:
        result: subprocess.CompletedProcess[str] = conclude_in_progress_op(checkout, env=env, message=message, disable_gpgsign=False)
        return result

    monkeypatch.setattr("specify_cli.lanes.auto_rebase.conclude_in_progress_op", _signed)

    report = _rebase(root, worktree)

    assert report.succeeded, report.halt_reason
    head = _git(worktree, "rev-parse", "HEAD")
    shown = subprocess.run(["git", "-C", str(root), "log", "-1", head], capture_output=True, text=True, check=True)
    assert "Good signature" in shown.stdout + shown.stderr, "fixture: the merge must be signed"
    assert report.merge_sha == head
    assert _refs_under(root, _PREFIX) == [f"{_PREFIX}{_LANE}/{head}"]
