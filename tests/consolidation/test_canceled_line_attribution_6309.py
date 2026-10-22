"""Line attribution of canceled content (#6309): partial keeps, deletions, renames, reworks.

#5932 replaced the path-touch supersession rule with a line-SUBSET test: a canceled
commit's content counted as gone unless EVERY line it added survived in the lane's
final state. Two fail-opens remained (#6309): a survivor that kept SOME of the
canceled lines laundered them, and a canceled DELETION (no added lines) read as gone
whenever a survivor touched the path. A third surfaced in the design review: a
survivor that RENAMED the canceled path left the content at a path nobody judged.

The operator ruling (#6309, recorded in ADR 2026-09-29-1, Amendment 2026-10-22):

* a non-trivial line still attributed (``git blame``) to a canceled commit is
  surviving canceled content, so the gate FAILs, even when a survivor reworked the
  rest of the hunk; blank, whitespace-only and punctuation-only lines are ignored;
* the #5932 subset test stays as a second "survives" signal;
* a canceled deletion stays in effect unless its lines come back in their spot, or
  approved work rewrote that spot;
* a rename is followed and the content is judged and reported at the new path.

Every case is real git, no mocking of the attribution itself. The ``canceled_spine_content``
slice (the dependency-lane axis) is driven by a small lane builder; the mixed-lane
axis is driven end to end through ``build_approved_wp_set`` + ``MergeOutcomeVerifier``
with the helpers of ``test_canceled_content_residuals``.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from kernel.git import BlameLine, GitCommandError, blame_lines
from specify_cli.consolidation import line_attribution as la
from specify_cli.consolidation import wp_attribution as wpa
from specify_cli.consolidation.git_probes import GitProbeError, first_parent_commits_in_range
from specify_cli.consolidation.reconciliation import VerifyStatus
from specify_cli.lanes.branch_naming import lane_branch_name
from tests.consolidation.test_canceled_content_residuals import (
    _TARGET,
    _event,
    _init_repo,
    _rev,
    _squash_target,
    _verify_today_result,
    _write_events,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_PATH = "src/pkg/mod.py"
_RENAMED = "src/pkg/renamed.py"


# --------------------------------------------------------------------------- #
# A linear lane builder for the ``canceled_spine_content`` slice
# --------------------------------------------------------------------------- #


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


@dataclass
class _Lane:
    """A real repository whose lane is a linear first-parent spine from ``base``."""

    repo: Path
    base: str
    canceled: set[str] = field(default_factory=set)

    def commit(self, files: Mapping[str, str | None], *, canceled: bool = False, message: str = "change") -> str:
        for path, content in files.items():
            target = self.repo / path
            if content is None:
                _git(self.repo, "rm", "-q", path)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content.encode("utf-8"))
            _git(self.repo, "add", path)
        _git(self.repo, "commit", "-qm", message)
        sha = _git(self.repo, "rev-parse", "HEAD")
        if canceled:
            self.canceled.add(sha)
        return sha

    def move(self, src: str, dst: str) -> str:
        _git(self.repo, "mv", src, dst)
        _git(self.repo, "commit", "-qm", f"move {src}")
        return _git(self.repo, "rev-parse", "HEAD")

    def revert(self, sha: str) -> str:
        _git(self.repo, "revert", "--no-edit", sha)
        return _git(self.repo, "rev-parse", "HEAD")

    def spine(self) -> list[str]:
        return [str(sha) for sha in first_parent_commits_in_range(self.repo, self.base, "HEAD")]

    def content(self) -> tuple[frozenset[str], dict[str, tuple[str, str | None]]]:
        superseded, live = wpa.canceled_spine_content(self.repo, self.spine(), frozenset(self.canceled), lambda _p: False)
        return superseded, {path: (entry[0], entry[1]) for path, entry in live.items()}

    def blob(self, path: str) -> str:
        return _git(self.repo, "rev-parse", f"HEAD:{path}")


def _lane(tmp_path: Path, files: dict[str, str] | None = None) -> _Lane:
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (
        ("init", "-q", "-b", "main"),
        ("config", "user.email", "t@example.invalid"),
        ("config", "user.name", "Test"),
        ("config", "commit.gpgsign", "false"),
    ):
        _git(repo, *args)
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "bootstrap")
    lane = _Lane(repo=repo, base=_git(repo, "rev-parse", "HEAD"))
    if files:
        lane.commit(files, message="approved base")
    return lane


def _lines(*lines: str) -> str:
    return "".join(f"{line}\n" for line in lines)


def _chmod_commit(lane: _Lane, path: str, flag: str, *, canceled: bool = True) -> str:
    """Commit a mode-only change of *path* (``+x`` / ``-x``), recorded as canceled by default."""
    (lane.repo / path).chmod(0o755 if flag == "+x" else 0o644)  # the working tree keeps the mode a later `git add` records
    _git(lane.repo, "add", path)
    _git(lane.repo, "commit", "-qm", f"chmod {flag}")
    sha = _git(lane.repo, "rev-parse", "HEAD")
    if canceled:
        lane.canceled.add(sha)
    return sha


_BASE = _lines("import os", "", "def keep_one() -> int:", "    return 1", "check_auth(user)", "def keep_two() -> int:", "    return 2")


# --------------------------------------------------------------------------- #
# Added lines
# --------------------------------------------------------------------------- #


def test_partial_keep_of_canceled_lines_stays_live(tmp_path: Path) -> None:
    """#6309: the survivor keeps two of three canceled lines; the two still ship."""
    lane = _lane(tmp_path, {_PATH: _lines("BASE = 'shared base'")})
    canceled = lane.commit({_PATH: _lines("BASE = 'shared base'", "WP02_A = 'canceled a'", "WP02_B = 'canceled b'", "WP02_C = 'canceled c'")}, canceled=True)
    lane.commit({_PATH: _lines("BASE = 'shared base'", "WP02_A = 'canceled a'", "WP02_B = 'canceled b'", "WP01_REWORK = 'rework'")})

    superseded, live = lane.content()

    assert canceled not in superseded
    assert live == {_PATH: (canceled, lane.blob(_PATH))}


def test_rework_keeping_only_the_canceled_signature_stays_live(tmp_path: Path) -> None:
    """The operator ruling: a kept non-trivial canceled line ships, even a signature."""
    lane = _lane(tmp_path)
    canceled = lane.commit({_PATH: _lines("def wp01() -> int:", "    return 1")}, canceled=True)
    lane.commit({_PATH: _lines("def wp01() -> int:", "    return 'superseded by WP02'")})

    assert lane.content() == (frozenset(), {_PATH: (canceled, lane.blob(_PATH))})


def test_full_rewrite_sharing_only_trivial_lines_is_superseded(tmp_path: Path) -> None:
    """Blank and punctuation-only lines a rewrite happens to keep are not canceled content."""
    lane = _lane(tmp_path)
    canceled = lane.commit({_PATH: _lines("CONFIG = {", "    'a': 1,", "", "}", "")}, canceled=True)
    lane.commit({_PATH: _lines("SETTINGS = {", "    'b': 2,", "", "}", "")})

    assert lane.content() == (frozenset({canceled}), {})


def test_reindented_and_crlf_canceled_lines_stay_live(tmp_path: Path) -> None:
    """A survivor that only re-indents the canceled lines and converts them to CRLF keeps them."""
    lane = _lane(tmp_path, {_PATH: _lines("BASE = 1")})
    canceled = lane.commit({_PATH: _lines("BASE = 1", "if enabled:", "    run_canceled_feature()")}, canceled=True)
    lane.commit({_PATH: "BASE = 1\r\nif enabled:\r\n        run_canceled_feature()\r\nAPPROVED = 2\r\n"})

    assert lane.content() == (frozenset(), {_PATH: (canceled, lane.blob(_PATH))})


_PY_BASE = "def f(x):\n    if x:\n        a()\n    b()\n"
_PY_REINDENTED = "def f(x):\n    if x:\n        a()\n        b()\n"


@pytest.mark.parametrize(
    ("base", "canceled_content", "approved_content", "ships"),
    [
        pytest.param(_PY_BASE, _PY_REINDENTED, _PY_REINDENTED + "# approved\n", True, id="python-reindent-moves-b-into-the-if"),
        pytest.param(_PY_BASE, _PY_REINDENTED, _PY_BASE + "# approved\n", False, id="python-reindent-undone-by-approved-work"),
        pytest.param(_PY_BASE, _PY_REINDENTED, _PY_BASE.replace("    b()", "          b()") + "# approved\n", False, id="python-reindent-reworked-differently"),
        pytest.param("A = 1\nB = 2\n", "A = 1\r\nB = 2\r\n", "A = 1\r\nB = 2\r\nC = 3\r\n", True, id="crlf-only-conversion"),
        pytest.param("A = 1\nB = 2\n", "A = 1\r\nB = 2\r\n", "A = 1\nB = 2\nC = 3\n", False, id="crlf-only-conversion-undone"),
        pytest.param("x = call(1,\n    2\n", "x = call(1,\n    2\n)\n", "x = call(1,\n    2\n)\ny = 3\n", True, id="punctuation-only-closing-paren-added"),
        pytest.param("x = call(1,\n    2\n)\n", "x = call(1,\n    2\n", "x = call(1,\n    2\ny = 3\n", True, id="punctuation-only-closing-paren-removed"),
    ],
)
def test_whitespace_or_punctuation_only_canceled_change_is_not_superseded_by_an_unrelated_append(
    tmp_path: Path, base: str, canceled_content: str, approved_content: str, ships: bool
) -> None:
    """Fail-closed: a canceled re-indent, line-ending or lone-punctuation change is meaning-changing.

    ``-w`` blame and diff ignore such a change, so it read as superseded and shipped; it stays live
    unless approved work really replaced the bytes.
    """
    lane = _lane(tmp_path, {_PATH: base})
    canceled = lane.commit({_PATH: canceled_content}, canceled=True)
    lane.commit({_PATH: approved_content})

    expected = (frozenset(), {_PATH: (canceled, lane.blob(_PATH))}) if ships else (frozenset({canceled}), {})
    assert lane.content() == expected


@pytest.mark.parametrize("undone", [False, True], ids=["mode-kept", "mode-undone-by-approved-work"])
def test_canceled_mode_change_stays_live_unless_the_mode_is_undone(tmp_path: Path, undone: bool) -> None:
    """A +x with no line change leaves nothing to blame: it ships while the final mode is the executable one."""
    lane = _lane(tmp_path, {_PATH: _BASE})
    canceled = _chmod_commit(lane, _PATH, "+x")
    if undone:
        _chmod_commit(lane, _PATH, "-x", canceled=False)
    lane.commit({_PATH: _BASE + _lines("APPROVED = 3")})

    expected = (frozenset({canceled}), {}) if undone else (frozenset(), {_PATH: (canceled, lane.blob(_PATH))})
    assert lane.content() == expected


def test_canceled_empty_file_creation_stays_live_once_a_survivor_writes_into_it(tmp_path: Path) -> None:
    """Creating an empty marker file adds no line; a survivor filling it in does not make the file approved."""
    lane = _lane(tmp_path)
    canceled = lane.commit({"src/pkg/__init__.py": ""}, canceled=True)
    lane.commit({"src/pkg/__init__.py": "APPROVED = 1\n"})

    assert lane.content() == (frozenset(), {"src/pkg/__init__.py": (canceled, lane.blob("src/pkg/__init__.py"))})


def test_lines_removed_then_readded_by_approved_work_are_its_own(tmp_path: Path) -> None:
    """An approved commit that re-adds a line after another removed it authored that line itself."""
    lane = _lane(tmp_path, {_PATH: _lines("BASE = 1")})
    canceled = lane.commit({_PATH: _lines("BASE = 1", "import json", "PAYLOAD = json.dumps({})")}, canceled=True)
    lane.commit({_PATH: _lines("BASE = 1")}, message="approved removes the canceled lines")
    lane.commit({_PATH: _lines("BASE = 1", "import json", "APPROVED = json.loads('{}')")}, message="approved writes its own code")

    assert lane.content() == (frozenset({canceled}), {})


def test_revert_by_approved_work_supersedes(tmp_path: Path) -> None:
    lane = _lane(tmp_path, {_PATH: _BASE})
    canceled = lane.commit({_PATH: _BASE + _lines("CANCELED = 'feature'")}, canceled=True)
    lane.revert(canceled)
    lane.commit({_PATH: _BASE + _lines("APPROVED = 'feature'")})

    assert lane.content() == (frozenset({canceled}), {})


def test_merge_on_the_spine_does_not_hide_partially_kept_lines(tmp_path: Path) -> None:
    """A lane-sync merge after the canceled commit neither attributes nor launders."""
    lane = _lane(tmp_path, {_PATH: _lines("BASE = 1")})
    canceled = lane.commit({_PATH: _lines("BASE = 1", "CANCELED_A = 'a'", "CANCELED_B = 'b'")}, canceled=True)
    _git(lane.repo, "checkout", "-q", "-b", "side", lane.base)
    (lane.repo / "other.txt").write_text("other\n", encoding="utf-8")
    _git(lane.repo, "add", "other.txt")
    _git(lane.repo, "commit", "-qm", "side work")
    _git(lane.repo, "checkout", "-q", "-")
    _git(lane.repo, "merge", "--no-ff", "-qm", "lane sync", "side")
    lane.commit({_PATH: _lines("BASE = 1", "CANCELED_A = 'a'", "APPROVED = 'c'")})

    assert lane.content() == (frozenset(), {_PATH: (canceled, lane.blob(_PATH))})


# --------------------------------------------------------------------------- #
# Deletions
# --------------------------------------------------------------------------- #


def test_canceled_deletion_kept_under_an_approved_append_stays_live(tmp_path: Path) -> None:
    """The #6310 review widening: the canceled WP removed the auth check, approved work appended."""
    lane = _lane(tmp_path, {_PATH: _BASE})
    canceled = lane.commit({_PATH: _BASE.replace("check_auth(user)\n", "")}, canceled=True)
    lane.commit({_PATH: _BASE.replace("check_auth(user)\n", "") + _lines("APPROVED = 3")})

    assert lane.content() == (frozenset(), {_PATH: (canceled, lane.blob(_PATH))})


def test_canceled_deletion_survives_an_approved_move_of_its_neighbour(tmp_path: Path) -> None:
    """Pre-PR review: a moved neighbour must not turn untouched original lines into "rework"."""
    original = [f"def original_function_{index:02d}(argument): return compute(argument, {index})" for index in range(1, 11)]
    lane = _lane(tmp_path, {_PATH: _lines(*original)})
    kept = [line for index, line in enumerate(original, start=1) if index != 6]
    canceled = lane.commit({_PATH: _lines(*kept)}, canceled=True)  # the canceled WP deletes line 6
    moved = [kept[4], *kept[:4], *kept[5:]]  # approved work only moves line 5 to the top
    lane.commit({_PATH: _lines(*moved)})

    assert lane.content() == (frozenset(), {_PATH: (canceled, lane.blob(_PATH))})


def test_another_canceled_commit_in_the_spot_is_not_approved_rework(tmp_path: Path) -> None:
    """Both canceled commits stay live: the second one's line in the first one's spot is canceled work."""
    lane = _lane(tmp_path, {_PATH: _BASE})
    first = lane.commit({_PATH: _BASE.replace("check_auth(user)\n", "")}, canceled=True)
    second = lane.commit({_PATH: _BASE.replace("check_auth(user)\n", "skip_auth(user)\n")}, canceled=True)
    lane.commit({_PATH: _BASE.replace("check_auth(user)\n", "skip_auth(user)\n") + _lines("APPROVED = 3")})

    superseded, live = lane.content()

    assert first not in superseded and second not in superseded
    assert set(live) == {_PATH}


def test_canceled_deletion_restored_in_place_is_superseded(tmp_path: Path) -> None:
    lane = _lane(tmp_path, {_PATH: _BASE})
    canceled = lane.commit({_PATH: _BASE.replace("check_auth(user)\n", "")}, canceled=True)
    lane.commit({_PATH: _BASE + _lines("APPROVED = 3")})

    assert lane.content() == (frozenset({canceled}), {})


def test_canceled_deletion_readded_elsewhere_stays_live(tmp_path: Path) -> None:
    """The count-rule hole the review found: the same line elsewhere does not restore the deleted check."""
    lane = _lane(tmp_path, {_PATH: _BASE})
    canceled = lane.commit({_PATH: _BASE.replace("check_auth(user)\n", "")}, canceled=True)
    lane.commit({_PATH: _lines("check_auth(user)") + _BASE.replace("check_auth(user)\n", "")})

    assert lane.content() == (frozenset(), {_PATH: (canceled, lane.blob(_PATH))})


def test_canceled_change_reworked_by_approved_work_is_superseded(tmp_path: Path) -> None:
    """The operator ruling: ``value = 1 -> 2`` (canceled) then ``-> 3`` (approved) is approved work."""
    before = _lines("def limits() -> dict:", "    return {", "        'value': 1,", "    }")
    lane = _lane(tmp_path, {_PATH: before})
    canceled = lane.commit({_PATH: before.replace("'value': 1", "'value': 2")}, canceled=True)
    lane.commit({_PATH: before.replace("'value': 1", "'value': 3")})

    assert lane.content() == (frozenset({canceled}), {})


def test_whitespace_only_deletion_is_not_content(tmp_path: Path) -> None:
    lane = _lane(tmp_path, {_PATH: _lines("A = 1", "", "", "B = 2")})
    canceled = lane.commit({_PATH: _lines("A = 1", "", "B = 2")}, canceled=True)
    lane.commit({_PATH: _lines("A = 1", "", "B = 2", "C = 3")})

    assert lane.content() == (frozenset({canceled}), {})


# --------------------------------------------------------------------------- #
# Renames
# --------------------------------------------------------------------------- #


def test_rename_of_the_canceled_path_is_followed_and_reported_at_the_new_path(tmp_path: Path) -> None:
    lane = _lane(tmp_path, {_PATH: _BASE})
    canceled = lane.commit({_PATH: _BASE + _lines("CANCELED = 'feature flag'")}, canceled=True)
    lane.move(_PATH, _RENAMED)

    superseded, live = wpa.canceled_spine_content(lane.repo, lane.spine(), frozenset(lane.canceled), lambda _p: False)

    assert superseded == frozenset()
    assert set(live) == {_RENAMED}
    assert (live[_RENAMED][0], live[_RENAMED][1]) == (canceled, lane.blob(_RENAMED))
    assert live[_RENAMED].renamed_from == _PATH


def test_rename_that_drops_the_canceled_content_is_superseded(tmp_path: Path) -> None:
    lane = _lane(tmp_path, {_PATH: _BASE})
    canceled = lane.commit({_PATH: _BASE + _lines("CANCELED = 'feature flag'")}, canceled=True)
    lane.move(_PATH, _RENAMED)
    lane.commit({_RENAMED: _BASE})

    assert lane.content() == (frozenset({canceled}), {})


def test_deleted_path_without_a_rename_is_superseded(tmp_path: Path) -> None:
    lane = _lane(tmp_path, {_PATH: _BASE})
    canceled = lane.commit({_PATH: _BASE + _lines("CANCELED = 'feature flag'")}, canceled=True)
    lane.commit({_PATH: None})

    assert lane.content() == (frozenset({canceled}), {})


# --------------------------------------------------------------------------- #
# Fail-closed and cost
# --------------------------------------------------------------------------- #


def test_a_failed_blame_raises_a_probe_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lane = _lane(tmp_path, {_PATH: _BASE})
    lane.commit({_PATH: _BASE + _lines("CANCELED = 1")}, canceled=True)
    lane.commit({_PATH: _BASE + _lines("CANCELED = 1", "APPROVED = 2")})

    def _broken(*_args: object, **_kwargs: object) -> None:
        raise GitCommandError(argv=("blame",), cwd=lane.repo, returncode=128, stderr="fatal: bad object")

    monkeypatch.setattr(la, "blame_lines", _broken)
    with pytest.raises(GitProbeError, match="bad object"):
        lane.content()


def test_one_forward_blame_per_path_however_many_canceled_commits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cost bound: a canceled WP with many commits on one hot path blames that path once."""
    lane = _lane(tmp_path, {_PATH: _lines("BASE = 0")})
    lines = ["BASE = 0"]
    newest = ""
    for index in range(25):
        lines.append(f"CANCELED_{index} = {index}")
        newest = lane.commit({_PATH: _lines(*lines)}, canceled=True, message=f"canceled {index}")
    lane.commit({_PATH: _lines(*lines[:-1], "APPROVED = 1")})  # replaces only the newest canceled line
    calls: list[bool] = []

    def _counting(cwd: Path, path: str, **kwargs: Any) -> tuple[BlameLine, ...]:
        calls.append(bool(kwargs.get("reverse")))
        return blame_lines(cwd, path, **kwargs)

    monkeypatch.setattr(la, "blame_lines", _counting)
    superseded, live = lane.content()

    assert set(live) == {_PATH}
    assert superseded == frozenset({newest}), "only the newest canceled commit's one line was replaced"
    assert calls.count(False) == 1, f"forward blames: {calls.count(False)}"


# --------------------------------------------------------------------------- #
# Residuals of the ruling (strict xfail, so a change in behaviour turns RED)
# --------------------------------------------------------------------------- #


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="#6309 ruling residual: approved lines inserted exactly at a canceled deletion's spot supersede it")
def test_approved_insert_at_a_canceled_deletion_spot_ideally_stays_live(tmp_path: Path) -> None:
    lane = _lane(tmp_path, {_PATH: _BASE})
    canceled = lane.commit({_PATH: _BASE.replace("check_auth(user)\n", "")}, canceled=True)
    lane.commit({_PATH: _BASE.replace("check_auth(user)\n", "log_access(user)\n")})

    assert lane.content() == (frozenset(), {_PATH: (canceled, lane.blob(_PATH))})


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="#6309 residual: canceled content copied into another file by approved work is not followed")
def test_canceled_content_moved_to_another_file_ideally_stays_live(tmp_path: Path) -> None:
    lane = _lane(tmp_path, {_PATH: _BASE})
    canceled = lane.commit({_PATH: _BASE + _lines("def canceled_feature(user, payload, options):", "    return transmit(user, payload, options)")}, canceled=True)
    lane.commit(
        {
            _PATH: _BASE,
            "src/pkg/other.py": _lines("def canceled_feature(user, payload, options):", "    return transmit(user, payload, options)"),
        }
    )

    _superseded, live = lane.content()
    assert live, "the canceled function ships from other.py"
    del canceled


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="#6309 residual: a rename whose old path is re-created is judged at the re-created path only")
def test_rename_whose_old_path_is_recreated_ideally_stays_live(tmp_path: Path) -> None:
    lane = _lane(tmp_path, {_PATH: _BASE})
    canceled = lane.commit({_PATH: _BASE + _lines("CANCELED = 'feature flag'")}, canceled=True)
    lane.move(_PATH, _RENAMED)
    lane.commit({_PATH: _lines("APPROVED = 'a new module at the old path'")})

    _superseded, live = lane.content()
    assert _RENAMED in live, "the canceled line ships from the renamed file"
    del canceled


# --------------------------------------------------------------------------- #
# The mixed-lane axis, end to end
# --------------------------------------------------------------------------- #


def _mixed_lane_verdict(tmp_path: Path, slug: str, seed: str, canceled: str, rework: Sequence[tuple[str, str | None]]) -> tuple[VerifyStatus, str]:
    """WP01 seeds *seed*, canceled WP02 writes *canceled*, WP01's rework applies *rework*; squash and verify.

    *rework* is a list of ``(path, content)`` commits made in WP01's rework window;
    ``content`` ``None`` with a path ``"mv:<dst>"`` renames ``_PATH`` to ``<dst>``.
    """
    repo, feature_dir, manifest, coord_base = _init_repo(tmp_path, slug=slug, wp_ids=("WP01", "WP02"))
    lane_branch = lane_branch_name(slug, "lane-a", target_branch=_TARGET)
    _git(repo, "branch", lane_branch, coord_base)
    _git(repo, "checkout", "-q", lane_branch)
    (repo / _PATH).parent.mkdir(parents=True, exist_ok=True)

    def write(path: str, content: str, message: str) -> None:
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(content, encoding="utf-8")
        _git(repo, "add", path)
        _git(repo, "commit", "-qm", message)

    events: list[dict[str, object]] = []
    events.append(_event(1, "WP01", "planned", "claimed", slug=slug, at="2026-01-01T00:00:00+00:00", stamp=coord_base))
    events.append(_event(2, "WP01", "claimed", "in_progress", slug=slug, at="2026-01-01T00:01:00+00:00", stamp=coord_base))
    write(_PATH, seed, "wp01 seeds the module")
    events.append(_event(3, "WP01", "in_progress", "for_review", slug=slug, at="2026-01-01T00:02:00+00:00", stamp=_rev(repo)))
    events.append(_event(4, "WP01", "for_review", "in_review", slug=slug, at="2026-01-01T00:03:00+00:00", stamp=None))
    events.append(_event(5, "WP01", "in_review", "approved", slug=slug, at="2026-01-01T00:04:00+00:00", stamp=_rev(repo)))
    events.append(_event(6, "WP02", "planned", "claimed", slug=slug, at="2026-01-02T00:00:00+00:00", stamp=_rev(repo)))
    events.append(_event(7, "WP02", "claimed", "in_progress", slug=slug, at="2026-01-02T00:01:00+00:00", stamp=_rev(repo)))
    write(_PATH, canceled, "wp02 changes the module")
    events.append(_event(8, "WP02", "in_progress", "canceled", slug=slug, at="2026-01-02T00:02:00+00:00", stamp=_rev(repo)))
    events.append(_event(9, "WP01", "approved", "in_progress", slug=slug, at="2026-01-03T00:00:00+00:00", stamp=_rev(repo)))
    for path, content in rework:
        if path.startswith("mv:"):
            _git(repo, "mv", _PATH, path[3:])
            _git(repo, "commit", "-qm", "wp01 renames the module")
        else:
            assert content is not None
            write(path, content, "wp01 rework")
    events.append(_event(10, "WP01", "in_progress", "for_review", slug=slug, at="2026-01-03T00:01:00+00:00", stamp=_rev(repo)))
    events.append(_event(11, "WP01", "for_review", "in_review", slug=slug, at="2026-01-03T00:02:00+00:00", stamp=None))
    events.append(_event(12, "WP01", "in_review", "approved", slug=slug, at="2026-01-03T00:03:00+00:00", stamp=_rev(repo)))
    _git(repo, "checkout", "-q", _TARGET)
    _write_events(repo, feature_dir, events)
    target_ref = _squash_target(repo, _TARGET, lane_branch)
    result = _verify_today_result(repo, feature_dir, manifest, coord_base, target_ref, frozenset({"WP02"}))
    return result.status, result.recovery_guidance()


def test_mixed_lane_canceled_deletion_under_an_append_fails(tmp_path: Path) -> None:
    kept_deletion = _BASE.replace("check_auth(user)\n", "")
    status, _ = _mixed_lane_verdict(tmp_path, "line-attr-deletion", _BASE, kept_deletion, [(_PATH, kept_deletion + _lines("APPROVED = 3"))])
    assert status == VerifyStatus.FAIL, "the canceled WP's removal of the auth check ships"


def test_mixed_lane_rename_keeping_canceled_lines_fails_naming_the_new_path(tmp_path: Path) -> None:
    canceled = _BASE + _lines("CANCELED = 'feature flag'")
    status, text = _mixed_lane_verdict(tmp_path, "line-attr-rename", _BASE, canceled, [("mv:" + _RENAMED, None)])
    assert status == VerifyStatus.FAIL
    assert _RENAMED in text


def test_mixed_lane_rework_of_the_canceled_change_passes(tmp_path: Path) -> None:
    before = _lines("def limits() -> dict:", "    return {", "        'value': 1,", "    }")
    status, _ = _mixed_lane_verdict(
        tmp_path, "line-attr-rework", before, before.replace("'value': 1", "'value': 2"), [(_PATH, before.replace("'value': 1", "'value': 3"))]
    )
    assert status == VerifyStatus.PASS


# --------------------------------------------------------------------------- #
# LineAttribution edges
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("text", "trivial"), [(b"", True), (b"   \r", True), (b"    }),", True), (b"x", False), (b"  return 1", False), ("é".encode(), False)])
def test_is_trivial_line(text: bytes, trivial: bool) -> None:
    assert la.is_trivial_line(text) is trivial


def test_no_canceled_commit_is_nothing_to_survive(tmp_path: Path) -> None:
    lane = _lane(tmp_path, {_PATH: _BASE})
    survival = la.LineAttribution(lane.repo).survival((), _PATH, "HEAD", floor="HEAD")
    assert survival == la.CanceledSurvival(None, "HEAD", added=False, deletion=False)
    assert not survival.survives


def test_a_root_canceled_commit_is_attributed_without_a_parent(tmp_path: Path) -> None:
    repo = tmp_path / "root"
    repo.mkdir()
    for args in (
        ("init", "-q", "-b", "main"),
        ("config", "user.email", "t@example.invalid"),
        ("config", "user.name", "Test"),
        ("config", "commit.gpgsign", "false"),
    ):
        _git(repo, *args)
    lane = _Lane(repo=repo, base="")
    root = lane.commit({_PATH: _lines("CANCELED_A = 1", "CANCELED_B = 2", "CANCELED_C = 3")}, canceled=True, message="canceled root")
    lane.commit({_PATH: _lines("CANCELED_A = 1", "APPROVED = 9")})
    attribution = la.LineAttribution(repo)

    survival = attribution.survival((root,), _PATH, "HEAD", floor=root)

    assert survival.survives and survival.added and survival.final_path == _PATH
    lane.commit({_PATH: _lines("APPROVED = 9")})
    assert not la.LineAttribution(repo).survival((root,), _PATH, "HEAD", floor=root).survives


def test_a_rename_to_two_paths_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from kernel.git import GitPath, NameStatusEntry

    lane = _lane(tmp_path, {_PATH: _BASE})
    canceled = lane.commit({_PATH: _BASE + _lines("CANCELED = 1")}, canceled=True)
    lane.commit({_PATH: None})
    split = (
        NameStatusEntry("R090", GitPath.parse("src/pkg/a.py"), GitPath.parse(_PATH)),
        NameStatusEntry("R080", GitPath.parse("src/pkg/b.py"), GitPath.parse(_PATH)),
    )
    monkeypatch.setattr(la, "changed_entries", lambda *_a, **_k: split)

    with pytest.raises(GitProbeError, match="more than one path"):
        la.LineAttribution(lane.repo).survival((canceled,), _PATH, "HEAD", floor=canceled)


def test_rename_detection_config_is_appended_to_the_callers_git_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.quotePath")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "false")
    env = la._git_env_with((("diff.renameLimit", "0"),))
    assert (env["GIT_CONFIG_COUNT"], env["GIT_CONFIG_KEY_1"], env["GIT_CONFIG_VALUE_1"]) == ("2", "diff.renameLimit", "0")
    assert env["GIT_CONFIG_KEY_0"] == "core.quotePath"
    monkeypatch.setenv("GIT_CONFIG_COUNT", "not-a-number")
    assert la._git_env_with((("diff.renameLimit", "0"),))["GIT_CONFIG_KEY_0"] == "diff.renameLimit"
